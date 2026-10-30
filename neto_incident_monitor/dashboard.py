"""Read analytics scores through the authenticated browser UI."""
from functools import wraps
from neto_incident_monitor.browser_actions import navigate_page, wait_control, checkpoint, ready_control, read_control
from contextvars import ContextVar
from contextlib import contextmanager
from urllib.parse import urlparse
from neto_incident_monitor.authentication import authentication_required
from neto_incident_monitor.pagination import AuthenticationRequired, Cancelled
import calendar
import re
import time
from decimal import Decimal
from playwright.sync_api import TimeoutError, expect
from neto_incident_monitor.dashboard_progress import completed_step

DASHBOARD_URL = ('https://adeo.service-now.com/now/platform-analytics-workspace/dashboards/params/edit/false/'
                 'tab-sys-id/ba36dad72b6a8b504b98f4c2c891bf73/sys-id/22361ad72b6a8b504b98f4c2c891bfab/'
                 'unified-filters-param/tinyurl/__state__/b64-tiny~WKEf3X0ASg6M0LcR1kiqt049NKRrAV35')
TITLES = ('Liczba zgłoszeń',) + tuple(f'Zgłoszenia P{i}' for i in range(1, 6)) + tuple(f'Przekroczone P{i}' for i in range(1, 6))
HELD_TITLES = ('Wstrzymane L1 >14 dni', 'Wstrzymane L1 >7 dni')
REQUEST_TITLES = ('Otwarte wnioski L1', 'Wnioski L1 >7 dni',
                  'Wnioski L1 >14 dni', 'Nieprzypisane wnioski L1')
REQUEST_READ_TIMEOUT = 60
_diagnostics = ContextVar('dashboard_diagnostics', default=None)
TAB_IDS = {
    'Wstrzymane L1': 'c228c7d455c81f90211a1d000e482311',
    'Wnioski L1': '17fcfee03dcc5310e5e0b24c4676861c',
}


def same_dashboard(page):
    if not isinstance(page.url, str):
        return False
    actual, expected = urlparse(page.url), urlparse(DASHBOARD_URL)
    if actual.scheme != expected.scheme or actual.netloc != expected.netloc:
        return False
    expected_path = expected.path.split('/sys-id/', 1)
    dashboard_id = expected_path[1].split('/', 1)[0]
    parts = actual.path.split('/sys-id/', 1)
    return (len(parts) == 2 and parts[0].startswith('/now/platform-analytics-workspace/dashboards/')
            and parts[1].split('/', 1)[0] == dashboard_id)


def open_dashboard_tab(page, name, stop):
    """Reuse the loaded workspace; reload only when reuse is unavailable."""
    checkpoint(stop)
    if isinstance(page.url, str) and urlparse(page.url).scheme == 'https':
        check_session(page)
    target = DASHBOARD_URL.replace('ba36dad72b6a8b504b98f4c2c891bf73', TAB_IDS[name])
    reused = same_dashboard(page)
    diagnostics = _diagnostics.get()
    if diagnostics:
        diagnostics.record('dashboard_navigation', reused=reused)
    if not reused:
        operation('navigate')
        navigate_page(page, target, stop)
    check_session(page)
    for attempt in range(2 if reused else 1):
        operation('open_tab')
        tab = page.get_by_role('tab', name=name, exact=True)
        try:
            selected = read_control(tab, stop, lambda: tab.get_attribute('aria-selected', timeout=500),
                                    check=lambda: check_session(page))
            if selected != 'true':
                click_control(tab, page, stop)
                if selected == 'false':
                    read_control(tab, stop, lambda: expect(tab).to_have_attribute('aria-selected', 'true', timeout=500),
                                 assertion=True, check=lambda: check_session(page))
            completed_step('open_tab')
            return
        except TimeoutError:
            check_session(page)
            if attempt or not reused:
                raise
            if diagnostics:
                diagnostics.record('dashboard_navigation', reused=False)
            operation('navigate')
            navigate_page(page, target, stop)


@contextmanager
def diagnostic_steps(diagnostics):
    token = _diagnostics.set(diagnostics)
    try:
        yield
    finally:
        _diagnostics.reset(token)


def operation(code, category=None):
    diagnostics = _diagnostics.get()
    if diagnostics:
        diagnostics.operation = code
        diagnostics.category = category
        diagnostics.record('dashboard_operation', operation=code, category=category)


def click_control(control, page, stop, timeout=30000):
    ready_control(control, stop, timeout=timeout, check=lambda: check_session(page))
    control.click(timeout=5000, no_wait_after=True)


def check_session(page):
    if authentication_required(page, DASHBOARD_URL):
        raise AuthenticationRequired()


def authenticated_read(operation):
    @wraps(operation)
    def read(page, *args, **kwargs):
        try:
            return operation(page, *args, **kwargs)
        except Cancelled:
            raise
        except Exception:
            if not page.is_closed():
                check_session(page)
            raise
    return read


@authenticated_read
def read_requests_dashboard(page, stop):
    diagnostics = _diagnostics.get()
    for attempt in range(2):
        checkpoint(stop)
        if diagnostics:
            diagnostics.record('dashboard_scores_attempt', attempt=attempt + 1)
        try:
            open_dashboard_tab(page, 'Wnioski L1', stop)
            ensure_all_categories(page, stop, ('Agent L1',))
            activate_dashboard_widgets(page, stop)
            values = _read_request_scores(page, stop)
        except (TimeoutError, ValueError) as error:
            if diagnostics:
                from neto_incident_monitor.login_diagnostics import error_facts
                diagnostics.record('dashboard_scores_error', attempt=attempt + 1, **error_facts(error))
            if attempt:
                raise
            values = {}
        if len(values) == len(REQUEST_TITLES):
            completed_step('scores')
            return values
        if attempt:
            if values:
                return values  # Caller explicitly reports a partial section.
            raise ValueError('Nie udało się odczytać kafelków Wnioski L1.')
        if diagnostics:
            diagnostics.record('dashboard_scores_retry', attempt=attempt + 1)
        operation('navigate')
        target = DASHBOARD_URL.replace('ba36dad72b6a8b504b98f4c2c891bf73', TAB_IDS['Wnioski L1'])
        navigate_page(page, target, stop)


def activate_dashboard_widgets(page, stop):
    """Activate lazy cards even when their title/score has not been created yet.

    First entry through dashboard tabs can leave offscreen component-renderers
    empty indefinitely. A reload of an already initialized tab masks this case.
    Walk physical layout order so each card gets an intersection notification.
    """
    operation('prepare_widgets')
    cards = page.locator('.grid-stack-item-content').filter(visible=True)
    positions = []
    for index in range(cards.count()):
        checkpoint(stop)
        check_session(page)
        card = cards.nth(index)
        box = card.bounding_box(timeout=500)
        if box:
            positions.append((box['y'], box['x'], index))
    activated = 0
    for _, _, index in sorted(positions):
        checkpoint(stop)
        check_session(page)
        cards.nth(index).scroll_into_view_if_needed(timeout=1500)
        # Yield for IntersectionObserver/paint before moving to another card.
        page.wait_for_timeout(100)
        activated += 1
    diagnostics = _diagnostics.get()
    if diagnostics:
        diagnostics.record('dashboard_widgets_activated', widget_count=len(positions), activated_count=activated)


def _request_tile(page, title):
    """Read the rendered score inside its titled widget, not its drilldown link.

    ServiceNow renders scores independently of interactive button metadata.
    Headers and the grid card also isolate loading from unrelated charts.
    """
    heading = page.get_by_role('heading', name=re.compile(
        r'^\s*' + r'\s+'.join(re.escape(part).replace('/', r'\/') for part in title.split()).replace('>', r'>\s*') + r'\s*$'))
    widgets = page.locator('.grid-stack-item-content').filter(has=heading).filter(visible=True)
    widget_count = widgets.count()
    source = widgets if widget_count == 1 else page
    button = source.get_by_role('button', name=score_pattern(title)).filter(visible=True)
    facts = {'state': 'missing', 'loading': False, 'score_source': 'none',
             'button_available': button.count() == 1, 'value': None}
    if widget_count > 1:
        facts['state'] = 'ambiguous'
        return facts
    loading = source.get_by_text('Trwa ładowanie danych wizualizacji', exact=True).filter(visible=True).count()
    if widget_count == 1:
        loading = loading or source.locator('[aria-busy="true"], [role="progressbar"]').filter(visible=True).count()
        loading = loading or source.get_attribute('aria-busy', timeout=300) == 'true'
    facts['loading'] = bool(loading)
    if loading:
        facts['state'] = 'loading'
        return facts
    rendered = source.locator('now-score-basic .now-score-value').filter(visible=True) if widget_count == 1 else None
    rendered_count = rendered.count() if rendered is not None else 0
    if rendered_count > 1:
        facts['state'] = 'ambiguous'
        return facts
    if rendered_count == 1:
        score, facts['score_source'] = rendered, 'widget_value'
    elif facts['button_available']:
        score, facts['score_source'] = button, 'button'
    else:
        facts['state'] = 'ambiguous' if button.count() > 1 else 'missing'
        return facts
    try:
        facts['value'] = parse_score(score.inner_text(timeout=300))
        facts['state'] = 'ready'
    except TimeoutError:
        facts['state'] = 'unavailable'
    except ValueError:
        facts['state'] = 'invalid'
    return facts


def _read_request_scores(page, stop):
    operation('read_scores')
    deadline = time.monotonic() + REQUEST_READ_TIMEOUT
    previous, stable_since = None, None
    values = {}
    diagnostics = _diagnostics.get()
    last_states = {}
    while time.monotonic() < deadline:
        checkpoint(stop)
        check_session(page)
        if stop.is_set():
            raise Cancelled()
        current = {}
        states = {}
        for title in REQUEST_TITLES:
            checkpoint(stop)
            state = _request_tile(page, title)
            states[title] = state
            if state['state'] == 'ready':
                current[title] = state['value']
        loading = any(state['loading'] for state in states.values())
        if diagnostics:
            for title, state in states.items():
                facts = (state['state'], state['loading'], state['score_source'], state['button_available'])
                if last_states.get(title) != facts:
                    diagnostics.record('dashboard_tile_state', tile=title, tile_state=state['state'],
                                       loading=state['loading'], score_source=state['score_source'],
                                       button_available=state['button_available'])
                    last_states[title] = facts
        if not loading and current:
            if current != previous:
                previous, stable_since = current, time.monotonic()
                values = {}
            elif time.monotonic() - stable_since >= 1:
                values = current
                if len(values) == len(REQUEST_TITLES):
                    return values
        else:
            previous = stable_since = None
            values = {}
        page.wait_for_timeout(200)
    return values


def calculate_wjruw(values):
    """Weighted SLA score from the same complete snapshot as the tiles."""
    weights = {1: 50, 2: 10, 3: 5, 4: 2, 5: 1}
    required = [f'{kind} P{p}' for kind in ('Zgłoszenia', 'Przekroczone') for p in weights]
    if any(not isinstance(values.get(key), int) or values[key] < 0 for key in required):
        return None
    total = sum(values[f'Zgłoszenia P{p}'] * weight for p, weight in weights.items())
    exceeded = sum(values[f'Przekroczone P{p}'] * weight for p, weight in weights.items())
    return Decimal(100) - Decimal(exceeded) * 100 / Decimal(total) if total else None


def month_range(year, month):
    last = calendar.monthrange(year, month)[1]
    return f'{year:04}-{month:02}-01', f'{year:04}-{month:02}-{last:02}'


def parse_score(text):
    value = re.sub(r'[\s\u00a0\u202f]', '', text)
    if not re.fullmatch(r'\d+', value):
        raise ValueError('Widżet nie zwrócił pełnej wartości liczbowej.')
    return int(value)


def score_pattern(title):
    # ServiceNow can leave whitespace at the end of the configured widget title.
    pattern = r'\s+'.join(re.escape(part).replace('/', r'\/') for part in title.split()).replace('>', r'>\s*')
    return re.compile(r'^\s*' + pattern + r'\s*,')


def ensure_all_categories(page, stop, categories=('Status zgłoszenia', 'Lokalizacja', 'Przypisany do')):
    """Apply each category separately, scoped by its heading rather than order."""
    for category in categories:
        checkpoint(stop)
        check_session(page)
        if stop.is_set():
            raise Cancelled()
        heading = re.compile(r'^(?:Agent|Agenci) L1$') if category == 'Agent L1' else category
        container = page.locator('sn-component-filter').filter(
            has=page.get_by_text(heading, exact=True)).filter(visible=True)
        checkbox = container.get_by_role('checkbox', name=re.compile(r'^(?:Wybierz|Zaznacz) wszystko$'))
        category_code = {'Status zgłoszenia': 'status', 'Lokalizacja': 'location',
                         'Przypisany do': 'assigned', 'Agent L1': 'agent'}.get(category, 'other')
        operation('category_select', category_code)
        wait_control(checkbox, stop, state='attached', check=lambda: check_session(page))
        selected = read_control(checkbox, stop,
            lambda: checkbox.evaluate('(element) => element.checked && !element.indeterminate', timeout=500),
            check=lambda: check_session(page))
        if not selected:
            ready_control(checkbox, stop, check=lambda: check_session(page))
            checkbox.check(timeout=5000, no_wait_after=True)
            read_control(checkbox, stop, lambda: expect(checkbox).to_be_checked(timeout=500),
                         assertion=True, check=lambda: check_session(page))
            operation('category_apply', category_code)
            click_control(container.get_by_role('button', name='Zastosuj', exact=True), page, stop)
            read_control(checkbox, stop, lambda: expect(checkbox).to_be_checked(timeout=500),
                         assertion=True, check=lambda: check_session(page))
            if read_control(checkbox, stop, lambda: checkbox.evaluate('(element) => element.indeterminate', timeout=500),
                            check=lambda: check_session(page)):
                raise ValueError(f'Nie udało się zaznaczyć wszystkich pozycji: {category}.')
        completed_step(category_code)


@authenticated_read
def read_held_dashboard(page, stop):
    if stop.is_set():
        raise Cancelled()
    open_dashboard_tab(page, 'Wstrzymane L1', stop)
    ensure_all_categories(page, stop, ('Agent L1',))
    activate_dashboard_widgets(page, stop)
    operation('read_scores')
    deadline = time.monotonic() + 60
    previous = None
    stable_since = None
    while time.monotonic() < deadline:
        checkpoint(stop)
        check_session(page)
        if stop.is_set():
            raise Cancelled()
        try:
            if page.get_by_text('Trwa ładowanie danych wizualizacji', exact=True).filter(visible=True).count():
                raise ValueError('Trwa ładowanie.')
            values = {title: parse_score(page.get_by_role('button', name=score_pattern(title)).inner_text(timeout=500)) for title in HELD_TITLES}
            if values == previous and time.monotonic() - stable_since >= 1:
                completed_step('scores')
                return values
            if values != previous:
                previous, stable_since = values, time.monotonic()
        except (ValueError, TimeoutError):
            previous = stable_since = None
        page.wait_for_timeout(200)
    raise ValueError('Nie udało się odczytać kafelków Wstrzymane L1.')


@authenticated_read
def read_dashboard(page, year, month, stop):
    if stop.is_set():
        raise Cancelled()
    start, end = month_range(year, month)
    operation('navigate')
    navigate_page(page, DASHBOARD_URL, stop)
    check_session(page)
    completed_step('navigate')
    period = page.get_by_role('button', name=re.compile(r'^Filtr Okres otwarcia z typem daterange'))
    operation('open_period')
    click_control(period, page, stop, timeout=60000)
    completed_step('open_period')
    first = page.get_by_role('textbox', name='Data rozpoczęcia', exact=True)
    last = page.get_by_role('textbox', name='Data zakończenia', exact=True)
    operation('fill_start')
    ready_control(first, stop, editable=True, check=lambda: check_session(page))
    first.fill(start, timeout=5000)
    completed_step('fill_start')
    operation('fill_end')
    ready_control(last, stop, editable=True, check=lambda: check_session(page))
    last.fill(end, timeout=5000)
    last.press('Tab', timeout=5000, no_wait_after=True)
    completed_step('fill_end')
    page.wait_for_timeout(150)
    # The popover lives in a separate shadow root, outside the dialog host.
    apply = page.get_by_role('button', name='Zastosuj', exact=True).filter(visible=True).last
    operation('commit_period')
    selected_period = page.get_by_role('button', name=f'Filtr Okres otwarcia z typem daterange. Wybrane wartości to: {start} - {end}', exact=True)
    enabled = read_control(apply, stop, lambda: apply.is_enabled(timeout=500), check=lambda: check_session(page))
    if not enabled and selected_period.count() == 1:
        click_control(page.get_by_role('button', name='Anuluj', exact=True).filter(visible=True).last, page, stop)
    else:
        click_control(apply, page, stop)
    wait_control(selected_period, stop, timeout=15000, check=lambda: check_session(page))
    completed_step('commit_period')
    ensure_all_categories(page, stop)
    activate_dashboard_widgets(page, stop)
    operation('read_scores')
    deadline = time.monotonic() + 60
    previous = None
    stable_since = None
    while time.monotonic() < deadline:
        checkpoint(stop)
        check_session(page)
        if stop.is_set():
            raise Cancelled()
        try:
            if page.get_by_text('Trwa ładowanie danych wizualizacji', exact=True).filter(visible=True).count():
                raise ValueError('Trwa ładowanie.')
            values = {title: parse_score(page.get_by_role('button', name=score_pattern(title)).inner_text(timeout=500)) for title in TITLES}
            if values == previous:
                if time.monotonic() - stable_since >= 1:
                    completed_step('scores')
                    return values
            else:
                previous, stable_since = values, time.monotonic()
        except (ValueError, TimeoutError):
            previous = stable_since = None
        page.wait_for_timeout(200)
    raise ValueError('Nie udało się odczytać wszystkich kafelków dashboardu. Sprawdź sesję ServiceNow i spróbuj ponownie.')
