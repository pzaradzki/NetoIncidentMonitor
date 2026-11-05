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
                  'Wnioski L1 >14 dni', 'Nieprzypisane wnioski L1',
                  'Wnioski Smartfon – start >3 dni')
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
    """Compatibility entry point; navigation and recovery have one owner."""
    aliases = {'Wstrzymane L1': 'held', 'Wnioski L1': 'requests',
               'Dashboard SLA': 'sla', 'Dasboard SLA': 'sla',
               'L1 – Incydenty zagrożone SLA': 'threatened'}
    return open_section(page, aliases[name], stop)


_measurement = ContextVar('dashboard_measurement', default=None)


def measured_record(diagnostics, event, **facts):
    # Test doubles and unavailable diagnostic sinks cannot affect the reader.
    try:
        diagnostics.record(event, **facts)
    except Exception:
        pass


@contextmanager
def diagnostic_steps(diagnostics, page=None):
    token = _diagnostics.set(diagnostics)
    state = {'started': time.monotonic(), 'operation': None, 'category': None}
    timing_token = _measurement.set(state)
    outcome = 'returned'
    detach = None
    try:
        if page is not None:
            try:
                detach = diagnostics.attach(page)
            except Exception:
                pass
        yield
    except Cancelled:
        outcome = 'cancelled'
        raise
    except AuthenticationRequired:
        outcome = 'authentication'
        raise
    except Exception:
        outcome = 'error'
        raise
    finally:
        try:
            if state['operation']:
                measured_record(diagnostics, 'dashboard_stage_end', operation=state['operation'],
                    category=state['category'], outcome=outcome,
                    duration_ms=round((time.monotonic() - state['started']) * 1000))
            if detach:
                try:
                    detach()
                except Exception:
                    pass
        finally:
            _measurement.reset(timing_token)
            _diagnostics.reset(token)


def operation(code, category=None):
    diagnostics = _diagnostics.get()
    if diagnostics:
        state = _measurement.get()
        if state is not None and (code, category) != (state['operation'], state['category']):
            now = time.monotonic()
            if state['operation']:
                measured_record(diagnostics, 'dashboard_stage_end', operation=state['operation'],
                    category=state['category'], outcome='returned',
                    duration_ms=round((now - state['started']) * 1000))
            state.update(started=now, operation=code, category=category)
        diagnostics.operation = code
        diagnostics.category = category
        measured_record(diagnostics, 'dashboard_operation', operation=code, category=category)


def observation(reason, ready, expected):
    diagnostics = _diagnostics.get()
    if diagnostics:
        measured_record(diagnostics, 'dashboard_observation', wait_reason=reason,
                        ready_count=ready, expected_count=expected)


def click_control(control, page, stop, timeout=30000):
    from neto_incident_monitor.read_budget import remaining_ms
    ready_control(control, stop, timeout=timeout, check=lambda: check_session(page))
    control.click(timeout=remaining_ms(5000), no_wait_after=True)


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
    return read_section_cards(page, 'requests', REQUEST_TITLES, stop)


def activate_dashboard_widgets(page, stop, required=None, ready=None):
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
        try:
            box = card.bounding_box(timeout=500)
        except TimeoutError:
            # The workspace can replace its card collection while mounting.
            # A later bounded observation will collect the replacement cards.
            continue
        if box:
            positions.append((box['y'], box['x'], index))
    activated = 0
    for _, _, index in sorted(positions):
        checkpoint(stop)
        check_session(page)
        if ready and ready():
            break
        if required and all(read_tile(page, title)['state'] == 'ready' for title in required):
            break
        from neto_incident_monitor.read_budget import remaining_ms
        try:
            cards.nth(index).scroll_into_view_if_needed(timeout=remaining_ms(1500))
        except TimeoutError:
            continue
        # Yield for IntersectionObserver/paint before moving to another card.
        page.wait_for_timeout(100)
        activated += 1
    diagnostics = _diagnostics.get()
    if diagnostics:
        diagnostics.record('dashboard_widgets_activated', widget_count=len(positions), activated_count=activated)


def read_tile(page, title):
    """Read the rendered score inside its titled widget, not its drilldown link.

    ServiceNow renders scores independently of interactive button metadata.
    Headers and the grid card also isolate loading from unrelated charts.
    """
    heading = page.get_by_role('heading', name=re.compile(
        r'^\s*' + r'\s+'.join(re.escape(part).replace('/', r'\/') for part in title.split()).replace('>', r'>\s*') + r'\s*$'))
    widgets = page.locator('.grid-stack-item-content').filter(has=heading).filter(visible=True)
    widget_count = widgets.count()
    source = widgets
    button = source.get_by_role('button', name=score_pattern(title)).filter(visible=True)
    facts = {'state': 'missing', 'loading': False, 'score_source': 'none',
             'button_available': button.count() == 1, 'value': None}
    if widget_count == 0:
        return facts
    if widget_count > 1:
        facts['state'] = 'ambiguous'
        return facts
    loading = source.get_by_text('Trwa ładowanie danych wizualizacji', exact=True).filter(visible=True).count()
    if widget_count == 1:
        loading = loading or source.locator('[aria-busy="true"], [role="progressbar"]').filter(visible=True).count()
        busy = source.evaluate_all('(elements)=>elements.map(e=>e.getAttribute("aria-busy")==="true")')
        if len(busy) != 1:
            facts['state'] = 'ambiguous' if len(busy) > 1 else 'unavailable'
            return facts
        loading = loading or busy[0]
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


# One observer implementation; retain the old internal name for existing callers.
_request_tile = read_tile


def calculate_wjruw(values):
    """Weighted SLA score from the same complete snapshot as the tiles."""
    weights = {1: 50, 2: 10, 3: 5, 4: 2, 5: 1}
    required = [f'{kind} P{p}' for kind in ('Zgłoszenia', 'Przekroczone') for p in weights]
    if any(type(values.get(key)) is not int or values[key] < 0 for key in required):
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


def check_category(checkbox, page, stop):
    """Confirm a delivered check; never click twice to recover a delayed state."""
    from playwright.sync_api import Error
    from neto_incident_monitor.read_budget import remaining_ms, BudgetExpired
    try:
        checkbox.check(timeout=remaining_ms(1000), no_wait_after=True)
    except Error as error:
        if type(error) is not Error or str(error).splitlines()[0].strip() != 'Locator.check: Clicking the checkbox did not change its state':
            raise
        def confirmed():
            if not checkbox.evaluate('(e) => e.checked && !e.indeterminate', timeout=remaining_ms(100)):
                raise AssertionError('Category selection not confirmed')
        try:
            read_control(checkbox, stop, confirmed, timeout=500,
                         check=lambda: check_session(page), assertion=True)
        except BudgetExpired:
            raise
        except TimeoutError:
            diagnostics = _diagnostics.get()
            if diagnostics:
                diagnostics.record('category_check_failed')
            raise error from None
        diagnostics = _diagnostics.get()
        if diagnostics:
            diagnostics.record('category_check_recovered')


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
        def category_tick():
            check_session(page)
            if checkbox.count() == 0:
                # Category widgets can be offscreen/lazy just like score cards.
                activate_dashboard_widgets(page, stop, ready=lambda: checkbox.count() == 1)
                operation('category_select', category_code)
        wait_control(checkbox, stop, state='attached', check=category_tick)
        selected = read_control(checkbox, stop,
            lambda: checkbox.evaluate('(element) => element.checked && !element.indeterminate', timeout=500),
            check=lambda: check_session(page))
        if not selected:
            ready_control(checkbox, stop, check=lambda: check_session(page))
            check_category(checkbox, page, stop)
        operation('category_apply', category_code)
        click_control(container.get_by_role('button', name='Zastosuj', exact=True), page, stop)
        operation('category_confirm', category_code)
        def confirmed():
            if not checkbox.evaluate('(element) => element.checked && !element.indeterminate', timeout=300):
                raise AssertionError('Category selection not confirmed')
        read_control(checkbox, stop, confirmed, assertion=True,
                     check=lambda: check_session(page))
        completed_step(category_code)


@authenticated_read
def read_held_dashboard(page, stop):
    return read_section_cards(page, 'held', HELD_TITLES, stop)


@authenticated_read
def read_dashboard(page, year, month, stop):
    return read_section_cards(page, 'sla', TITLES, stop, year=year, month=month)


def verify_context(page, section, year=None, month=None):
    from neto_incident_monitor.dashboard_context import verify_target, DashboardReadError
    check_session(page)
    verify_target(page, section)
    if section == 'sla':
        start, end = month_range(year, month)
        period = page.get_by_role('button', name=f'Filtr Okres otwarcia z typem daterange. Wybrane wartości to: {start} - {end}', exact=True)
        if period.count() != 1:
            raise DashboardReadError('wrong_period')
    categories = ('Status zgłoszenia', 'Lokalizacja', 'Przypisany do') if section == 'sla' else ('Agent L1',) if section in ('held', 'requests') else ()
    for category in categories:
        container = category_container(page, category)
        checkbox = container.get_by_role('checkbox', name=re.compile(r'^(?:Wybierz|Zaznacz) wszystko$'))
        checks = checkbox.evaluate_all('(elements)=>elements.map(e=>!!e.checked && !e.indeterminate)')
        if container.count() != 1 or checks != [True]:
            raise DashboardReadError('wrong_filter')
    if _diagnostics.get():
        measured_record(_diagnostics.get(), 'dashboard_context', context_confirmed=True,
                        year=year, month=month, category_count=len(categories))


def category_container(page, category):
    heading = re.compile(r'^(?:Agent|Agenci) L1$') if category == 'Agent L1' else category
    return page.locator('sn-component-filter').filter(has=page.get_by_text(heading, exact=True)).filter(visible=True)


def open_section(page, section, stop, fresh=False):
    from neto_incident_monitor.dashboard_context import TAB_IDS as ids, selected_tab, verify_target
    from neto_incident_monitor.read_budget import RECOVERY
    fresh = fresh or RECOVERY.get()
    checkpoint(stop)
    if isinstance(page.url, str) and page.url.startswith('https:'):
        check_session(page)
    wait_document(page, stop)
    if fresh or not same_dashboard(page):
        operation('navigate')
        target = DASHBOARD_URL.replace('ba36dad72b6a8b504b98f4c2c891bf73', ids[section])
        navigate_page(page, target, stop)
    operation('open_tab')
    tab = selected_tab(page, section)
    if tab.count() > 1:
        from neto_incident_monitor.dashboard_context import DashboardReadError
        raise DashboardReadError('wrong_tab', retryable=False)
    wait_control(tab, stop, check=lambda: check_session(page))
    selected = read_control(tab, stop, lambda: tab.get_attribute('aria-selected', timeout=300),
                            check=lambda: check_session(page))
    if selected != 'true':
        click_control(tab, page, stop)
    read_control(tab, stop, lambda: expect(tab).to_have_attribute('aria-selected', 'true', timeout=300),
                 assertion=True, check=lambda: check_session(page))
    verify_target(page, section)
    completed_step('open_tab')


def wait_document(page, stop):
    """Observe document readiness separately from authenticated-session state."""
    operation('document_ready')
    until = time.monotonic() + 5
    previous = None
    while time.monotonic() < until:
        checkpoint(stop)
        if page.url != 'about:blank':
            check_session(page)
        current = (page.url, page.evaluate('() => document.readyState'))
        if current == previous and current[1] in ('interactive', 'complete'):
            return
        previous = current
        page.wait_for_timeout(100)
    raise TimeoutError('Document readiness deadline exceeded')


def set_period(page, year, month, stop):
    from neto_incident_monitor.dashboard_context import date_panel, DashboardReadError
    start, end = month_range(year, month)
    operation('open_period')
    click_control(page.get_by_role('button', name=re.compile(r'^Filtr Okres otwarcia z typem daterange')), page, stop)
    completed_step('open_period')
    wait_control(page.get_by_role('textbox', name='Data rozpoczęcia', exact=True), stop,
                 timeout=15000, check=lambda: check_session(page))
    panel = date_panel(page)
    for name, value, step in (('Data rozpoczęcia', start, 'fill_start'), ('Data zakończenia', end, 'fill_end')):
        operation(step)
        field = panel.get_by_role('textbox', name=name, exact=True)
        ready_control(field, stop, editable=True, check=lambda: check_session(page))
        field.fill(value, timeout=1000)
        field.press('Tab', timeout=1000, no_wait_after=True)
        def confirmed_field():
            expect(field).to_have_value(value, timeout=300)
            if field.get_attribute('aria-invalid', timeout=300) == 'true':
                raise DashboardReadError('wrong_period', retryable=False)
        read_control(field, stop, confirmed_field, assertion=True,
                     check=lambda: check_session(page))
        completed_step(step)
    selected = page.get_by_role('button', name=f'Filtr Okres otwarcia z typem daterange. Wybrane wartości to: {start} - {end}', exact=True)
    operation('period_ready')
    apply = panel.get_by_role('button', name='Zastosuj', exact=True).filter(visible=True)
    if apply.count() != 1 or selected.count() > 1:
        raise DashboardReadError('ambiguous_period', retryable=False)
    if selected.count() == 1:
        operation('commit_period')
        click_control(panel.get_by_role('button', name='Anuluj', exact=True), page, stop)
    else:
        ready_control(apply, stop, timeout=15000, check=lambda: check_session(page))
        operation('commit_period')
        # One delivered action only; all subsequent retries observe its result.
        from neto_incident_monitor.read_budget import remaining_ms
        apply.click(timeout=remaining_ms(5000), no_wait_after=True)
    operation('period_confirm')
    wait_control(selected, stop, timeout=15000, check=lambda: check_session(page))
    wait_control(panel, stop, state='hidden', timeout=15000, check=lambda: check_session(page))
    completed_step('commit_period')


def refresh_cards(page, section, titles, stop):
    from neto_incident_monitor.dashboard_context import begin_refresh_watch, end_refresh_watch
    refresh = page.get_by_role('button', name='Odśwież bieżącą kartę', exact=True).filter(visible=True)
    if refresh.count() != 1:
        # A verified fresh document is safer than assuming a cached tab refetched.
        if _diagnostics.get():
            measured_record(_diagnostics.get(), 'dashboard_refresh', refresh_mode='document_fallback')
        open_section(page, section, stop, fresh=True)
        return False
    try:
        begin_refresh_watch(page, titles)
        operation('refresh_cards')
        click_control(refresh, page, stop)
        until = time.monotonic() + 3
        while time.monotonic() < until:
            checkpoint(stop)
            check_session(page)
            if page.evaluate('() => !!window.__netoDashboardRefresh?.seen'):
                if _diagnostics.get():
                    measured_record(_diagnostics.get(), 'dashboard_refresh', refresh_mode='observed')
                return True
            page.wait_for_timeout(100)
    finally:
        end_refresh_watch(page)
    # Never click twice after uncertain delivery. Establish a new document.
    if _diagnostics.get():
        measured_record(_diagnostics.get(), 'dashboard_refresh', refresh_mode='document_fallback')
    open_section(page, section, stop, fresh=True)
    return False


def read_section_cards(page, section, titles, stop, year=None, month=None):
    from neto_incident_monitor.read_budget import CURRENT, RECOVERY, Budget, budget_scope
    if CURRENT.get() is None:
        with budget_scope(Budget(60)):
            return read_section_cards(page, section, titles, stop, year, month)
    checkpoint(stop)
    open_section(page, section, stop, fresh=section in ('sla', 'threatened') or RECOVERY.get())
    def prepare():
        if section == 'sla':
            completed_step('navigate')
            set_period(page, year, month, stop)
            ensure_all_categories(page, stop)
        elif section in ('held', 'requests'):
            ensure_all_categories(page, stop, ('Agent L1',))
    prepare()
    if section != 'threatened':
        # Refresh after committing settings; an unchanged number is valid only
        # after a new UI update cycle or a fresh document with settings restored.
        if not refresh_cards(page, section, titles, stop):
            prepare()
    guard = lambda: verify_context(page, section, year, month)
    guard()
    return read_scores(page, titles, stop, guard=guard)


def read_scores(page, titles, stop, guard=None, timeout=None):
    from neto_incident_monitor.dashboard_context import DashboardReadError
    operation('read_scores')
    deadline = time.monotonic() + (timeout if timeout is not None else REQUEST_READ_TIMEOUT)
    previous, stable_since = None, None
    next_activation = 0
    while time.monotonic() < deadline:
        checkpoint(stop)
        check_session(page)
        if guard:
            guard()
        current, states = {}, {}
        for index, title in enumerate(titles):
            checkpoint(stop)
            state = read_tile(page, title)
            if state['state'] == 'missing' and re.match(r'^(?:P[1-5]|Podjęcie)\s+[–—-]', title):
                category = title.split()[0]
                candidate = page.get_by_role('heading', name=re.compile(
                    r'^\s*' + re.escape(category) + r'\s*[-–—:]\s*<')).filter(visible=True)
                from neto_incident_monitor.dashboard_context import normalize_title
                if candidate.count() == 1 and normalize_title(candidate.inner_text(timeout=300)) != normalize_title(title):
                    raise DashboardReadError('definition_changed', retryable=False)
            states[title] = state
            diagnostics = _diagnostics.get()
            if diagnostics:
                measured_record(diagnostics, 'dashboard_tile_state', tile_index=index,
                    risk_tile=title.split()[0] if re.match(r'^(?:P[1-5]|Podjęcie) ', title) else None,
                    tile_state=state['state'], loading=state['loading'], score_source=state['score_source'])
            if state['state'] == 'ambiguous':
                raise DashboardReadError('ambiguous_widget', retryable=False)
            if state['state'] == 'ready':
                current[title] = state['value']
        reason = 'loading' if any(s['loading'] for s in states.values()) else 'missing' if len(current) != len(titles) else 'ready' if current == previous else 'unstable'
        observation(reason, len(current), len(titles))
        if len(current) == len(titles):
            if current == previous and time.monotonic() - stable_since >= 1:
                if guard:
                    guard()
                # A second complete observation prevents a mixed read across DOM replacement.
                if all(read_tile(page, title)['value'] == current[title] and
                       read_tile(page, title)['state'] == 'ready' for title in titles):
                    if guard:
                        guard()
                    completed_step('scores')
                    return current
            if current != previous:
                previous, stable_since = current, time.monotonic()
        else:
            previous = stable_since = None
            if time.monotonic() >= next_activation and page.locator('.grid-stack-item-content').filter(visible=True).count():
                try:
                    activate_dashboard_widgets(page, stop, required=titles)
                except TimeoutError as error:
                    checkpoint(stop)
                    check_session(page)
                    if _diagnostics.get():
                        from neto_incident_monitor.login_diagnostics import error_facts
                        measured_record(_diagnostics.get(), 'dashboard_widgets_retry', **error_facts(error))
                operation('read_scores')
                next_activation = time.monotonic() + 1
        page.wait_for_timeout(200)
    raise DashboardReadError('incomplete_widgets')
