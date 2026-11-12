"""Exclusive on-demand import session. No monitor start, history or senders."""
from time import monotonic
from contextlib import nullcontext
from types import SimpleNamespace
from playwright._impl._errors import TargetClosedError

from neto_incident_monitor.browser_actions import ACTION_TICK, checkpoint, navigate_page
from neto_incident_monitor.read_budget import Budget, budget_scope
from neto_incident_monitor.pagination import AuthenticationRequired, Cancelled
from neto_incident_monitor.login_diagnostics import LoginDiagnostics, error_facts
from neto_incident_monitor.favorites import HOME
from neto_incident_monitor.favorites_reader import read_favorites, FavoritesReadError


def select_import_page(context):
    pages = context.pages
    if len(pages) == 1 and pages[0].url == 'about:blank':
        return pages[0]
    # A sole restored page, or blanks mixed with restored pages, may belong to
    # the user. Leave them intact and own only a new import tab in that case.
    return context.new_page()


def collect_with_recovery(page, stop, log, restore, status, *, render=nullcontext):
    budget = Budget(30)
    technical_used = login_used = False
    for attempt in range(1, 4):
        log.record('favorites_attempt', attempt=attempt, timeout_ms=30000)
        try:
            with budget_scope(budget):
                checkpoint(stop)
                status('Odczytywanie menu Ulubione…')
                navigate_page(page, HOME, stop, timeout=15000)
                with render():
                    result = read_favorites(page, stop, log)
                checkpoint(stop)
                return result
        except AuthenticationRequired:
            if login_used:
                raise
            budget.check()
            login_used = True
            paused = monotonic()
            log.record('favorites_login_start', attempt=attempt)
            status('Oczekiwanie na logowanie do ServiceNow…')
            recovery_outcome = 'error'
            try:
                checkpoint(stop)
                if not restore():
                    raise Cancelled()
                checkpoint(stop)
                recovery_outcome = 'returned'
            except Cancelled:
                recovery_outcome = 'cancelled'
                raise
            finally:
                elapsed = monotonic()-paused
                budget.end += elapsed
                log.record('favorites_login_end', duration_ms=round(elapsed*1000), outcome=recovery_outcome)
        except Cancelled:
            raise
        except Exception as error:
            facts = error_facts(error)
            log.record('favorites_read_error', attempt=attempt,
                       import_reason=getattr(error, 'reason', facts['error_category']), **facts)
            retryable = not isinstance(error, FavoritesReadError) and facts['error_category'] in {
                'timeout','document_changed','navigation_interrupted','network_connection','network_dns','element_unavailable'}
            if technical_used or not retryable:
                raise
            budget.check()
            technical_used = True
    raise FavoritesReadError('incomplete')


def run_import(events, stop, settings, profile, import_id):
    from playwright.sync_api import sync_playwright
    from neto_incident_monitor.app import wait_for_login, set_chromium_window_state
    from neto_incident_monitor.browser_policy import BrowserOptions
    from neto_incident_monitor.browser_session import open_context, create_runtime, close_session
    log = LoginDiagnostics(source='favorites', import_id=import_id)
    def emit(kind, value):
        events.put((import_id, kind, value))
    context = runtime = page = None
    tick_token = ACTION_TICK.set(None)
    detach = None
    outcome, payload = 'error', 'Nie udało się odczytać kompletnego menu Ulubione. Spróbuj ponownie po sprawdzeniu sesji i połączenia.'
    started = monotonic()
    try:
        with sync_playwright() as pw:
            try:
                checkpoint(stop)
                context = open_context(pw, profile, log)
                initial_pages = context.pages
                page = select_import_page(context)
                log.record('favorites_stage', import_stage='page', reused=page in initial_pages)
                options = BrowserOptions(dict(settings, hide_browser=False, minimize_browser=False))
                runtime = create_runtime(page, options, log,
                    SimpleNamespace(put=lambda value: emit('runtime', value)),
                    set_chromium_window_state, lambda window: None)
                ACTION_TICK.set(runtime.tick)
                detach = log.attach(page)
                def restore():
                    runtime.set_activity('login')
                    try:
                        return wait_for_login(page, HOME, stop, settings.get('auto_login',False),
                            False, runtime.window, runtime=runtime,
                            on_activity=lambda text, tone: emit('status', text))
                    finally:
                        runtime.set_activity('filters')
                payload = collect_with_recovery(page, stop, log, restore, lambda text: emit('status', text))
                outcome = 'success'
            finally:
                if detach:
                    try:
                        detach()
                    except Exception:
                        pass
                if page is not None:
                    try:
                        page.close()
                    except Exception:
                        log.record('browser_cleanup_error', cleanup_errors=1)
                close_session(context, runtime, log)
    except Cancelled:
        outcome, payload = 'cancelled', 'Import anulowany. Nie zapisano filtrów.'
    except Exception as error:
        log.record('favorites_error', **error_facts(error), import_reason=getattr(error,'reason','unexpected'))
        if isinstance(error, FavoritesReadError):
            payload = 'Menu Ulubione jest niekompletne lub ma nieobsługiwany układ. Nie zapisano filtrów.'
        elif error_facts(error)['error_category'] == 'browser_closed':
            payload = 'Przeglądarka została zamknięta. Nie zapisano filtrów. Uruchom import ponownie.'
    finally:
        ACTION_TICK.reset(tick_token)
        log.record('favorites_end', outcome='returned' if outcome=='success' else outcome,
                   duration_ms=round((monotonic()-started)*1000))
        emit('result', (outcome, payload))  # Resources have been released before publication.


def read_on_session(page, request, session, stop):
    """Read in the session owner; the menu reader restores its viewport on exit."""
    from neto_incident_monitor.app import BrowserClosedError

    token = request['id']
    log = LoginDiagnostics(source='favorites', import_id=token)
    started = monotonic()
    outcome = 'error'
    payload = 'Nie udało się odczytać kompletnego menu Ulubione. Spróbuj ponownie po sprawdzeniu sesji i połączenia.'
    def status(message):
        request['events'].put((token, 'status', message))
    try:
        payload = collect_with_recovery(page, stop, log, lambda: session.authenticate(page, stop), status,
                                        render=lambda: session.runtime.favorites_read(page, log))
        outcome = 'success'
    except (TargetClosedError, BrowserClosedError):
        raise
    except Cancelled:
        outcome, payload = 'cancelled', 'Import anulowany. Nie zapisano filtrów.'
    except Exception as error:
        log.record('favorites_error', **error_facts(error), import_reason=getattr(error, 'reason', 'unexpected'))
    finally:
        log.record('favorites_end', outcome='returned' if outcome == 'success' else outcome,
                   duration_ms=round((monotonic() - started) * 1000))
    request['events'].put((token, 'result', (outcome, payload)))
    return outcome == 'success'
