"""Read identifier lists from the P1 drill-down on the shared card."""
import re
from time import monotonic
from urllib.parse import unquote, urlsplit

from playwright._impl._errors import TargetClosedError
from playwright.sync_api import Error, TimeoutError

from neto_incident_monitor.analytics_config import load_config, save_dashboard_scope, scope_from_p1_query
from neto_incident_monitor.authentication import authentication_required
from neto_incident_monitor.browser_actions import checkpoint, navigate_page, read_control, ready_control, wait_control
from neto_incident_monitor.browser_rendering import HiddenRendering
from neto_incident_monitor.dashboard import DASHBOARD_URL, measured_record, operation
from neto_incident_monitor.dashboard_context import DashboardReadError
from neto_incident_monitor.login_diagnostics import LoginDiagnostics, error_facts
from neto_incident_monitor.read_budget import Budget, budget_scope, remaining_ms
from neto_incident_monitor.read_errors import AuthenticationRequired, Cancelled
from neto_incident_monitor.section_runner import run_section
from neto_incident_monitor.service_now_urls import trusted_url


DASHBOARD_PATH = urlsplit(DASHBOARD_URL).path.split('/unified-filters-param/', 1)[0]
CLASSIC_PREFIX = '/now/nav/ui/classic/params/target/'
P1 = re.compile(r'^Zgłoszenia P1\s*,\s*[0-9]+(?:[\u00a0 ][0-9]{3})*\s*,')
CATEGORY_SELECTION = """element => {
    if (element.indeterminate || element.getAttribute('aria-checked') === 'mixed') return 'mixed';
    return element.checked ? 'all' : 'none';
}"""


def is_scope_dashboard(url):
    if not trusted_url(url):
        return False
    path = urlsplit(url).path
    return path == DASHBOARD_PATH or path.startswith(DASHBOARD_PATH + '/')


def set_category(page, name, stop, check):
    # Preserve the old mixed -> none -> all sequence. Each click has its own confirmation.
    container = page.locator('sn-component-filter').filter(has=page.get_by_text(name, exact=True)).filter(visible=True)
    checkbox = container.get_by_role('checkbox', name='Wybierz wszystko', exact=True)

    def read_state():
        return checkbox.evaluate(CATEGORY_SELECTION, timeout=remaining_ms(500))

    def ensure(expected):
        def observe():
            if read_state() != expected:
                raise AssertionError()
        read_control(checkbox, stop, observe, timeout=2500, check=check, assertion=True)

    wait_control(checkbox, stop, check=check)
    state = read_control(checkbox, stop, read_state, check=check)
    if state == 'mixed':
        ready_control(checkbox, stop, check=check)
        checkbox.click(timeout=remaining_ms(1500))
        ensure('none')
        state = 'none'
    if state == 'none':
        ready_control(checkbox, stop, check=check)
        checkbox.click(timeout=remaining_ms(1500))
    ensure('all')
    apply = container.get_by_role('button', name='Zastosuj', exact=True)
    ready_control(apply, stop, check=check)
    apply.click(timeout=remaining_ms(1500))
    ensure('all')
    return checkbox


def p1_query(page, stop, check):
    tile = page.get_by_role('button', name=P1).filter(visible=True)
    ready_control(tile, stop, check=check)
    tile.click(timeout=remaining_ms(2500))
    rows = page.frame_locator('iframe#gsft_main').locator('table[glide_table="task_sla"][query]')

    def read():
        url = page.url
        path = urlsplit(url).path if trusted_url(url) else ''
        if not path.startswith(CLASSIC_PREFIX):
            raise AssertionError()
        destination = urlsplit(unquote(path[len(CLASSIC_PREFIX):]))
        if destination.scheme or destination.netloc or destination.path.lstrip('/') != 'task_sla_list.do':
            raise DashboardReadError('dashboard_scope_query', retryable=False)
        frames = [frame for frame in page.frames if frame.name == 'gsft_main']
        if len(frames) != 1 or not trusted_url(frames[0].url):
            raise AssertionError()
        if urlsplit(frames[0].url).path != '/task_sla_list.do':
            raise DashboardReadError('dashboard_scope_query', retryable=False)
        if rows.count() != 1:
            raise AssertionError()
        return rows.get_attribute('query', timeout=remaining_ms(500))

    return read_control(rows, stop, read, timeout=10000, check=check, assertion=True)


def read_scope(page, stop, diagnostics, runtime):
    renderer = HiddenRendering(diagnostics, scope='dashboard_scope')

    def check():
        if authentication_required(page, DASHBOARD_URL):
            raise AuthenticationRequired()
        window = runtime.window if runtime else None
        renderer.sync(page, bool(window and window.is_hidden() and not runtime.debug_show_browser))

    try:
        operation('scope_open')
        if not is_scope_dashboard(page.url):
            navigate_page(page, DASHBOARD_URL, stop)
        check()
        if not is_scope_dashboard(page.url):
            raise DashboardReadError('dashboard_scope_filter', retryable=False)
        try:
            operation('scope_location')
            location = set_category(page, 'Lokalizacja', stop, check)
            operation('scope_assigned')
            assigned = set_category(page, 'Przypisany do', stop, check)
            for checkbox in (location, assigned):
                checkpoint(stop)
                check()
                if checkbox.evaluate(CATEGORY_SELECTION, timeout=remaining_ms(500)) != 'all':
                    raise DashboardReadError('dashboard_scope_filter')
        except TimeoutError:
            raise DashboardReadError('dashboard_scope_filter') from None
        operation('scope_p1')
        try:
            query = p1_query(page, stop, check)
        except TimeoutError:
            raise DashboardReadError('dashboard_scope_query') from None
        operation('scope_query')
        return scope_from_p1_query(query)
    finally:
        renderer.close()


def refresh_scope(session, page, part, stop):
    diagnostics = LoginDiagnostics(source='dashboard', request_id=session.active_job.id)
    started = monotonic()
    previous = page.url
    outcome = 'error'

    def collect():
        if session.layout_account != part.target:
            raise Cancelled()
        return read_scope(page, stop, diagnostics, session.runtime)

    try:
        load_config()  # Preserve the rest of the analytics configuration when saving.
        scope = run_section(page, stop, collect, diagnostics, lambda: session.authenticate(page, stop), lambda _: None)
        checkpoint(stop)
        if session.layout_account != part.target:
            raise Cancelled()
        save_dashboard_scope(scope)
        measured_record(diagnostics, 'dashboard_operation', operation='scope_save', outcome='returned')
        outcome = 'returned'
        part.data['count'] = len(scope['assignees']) + len(scope['locations'])
        return True
    except Cancelled:
        outcome = 'cancelled'
        raise
    except TargetClosedError:
        raise
    except (DashboardReadError, Error, AuthenticationRequired) as error:
        part.data['reason'] = getattr(error, 'reason', 'error')
        measured_record(diagnostics, 'section_read_error', read_reason=part.data['reason'], **error_facts(error))
        return False
    finally:
        if trusted_url(previous) and not stop.is_set() and not page.is_closed() and page.url != previous:
            try:
                if trusted_url(page.url) and not authentication_required(page, DASHBOARD_URL):
                    with budget_scope(Budget(5)):
                        navigate_page(page, previous, stop)
            except (Cancelled, Error, AuthenticationRequired) as error:
                measured_record(diagnostics, 'browser_cleanup_error', **error_facts(error))
        measured_record(diagnostics, 'dashboard_scope_result', outcome=outcome,
                        item_count=part.data.get('count', 0), duration_ms=round((monotonic() - started) * 1000))
