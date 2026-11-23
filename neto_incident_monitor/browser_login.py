"""Navigation and authentication for the monitored ServiceNow card."""
import time
from urllib.parse import urlparse

from playwright._impl._errors import TargetClosedError

from neto_incident_monitor import browser_actions
from neto_incident_monitor.login_diagnostics import error_facts
from neto_incident_monitor.read_errors import BrowserClosedError, Cancelled, LoginTargetUnavailable
from neto_incident_monitor.service_now_urls import is_short_url, normalize_list_url


def navigate(page, url, stop=None):
    # SSO can start a second navigation before goto has finished. Keep that
    # navigation alive so that the user can complete authentication.
    url = normalize_list_url(url)
    try:
        if stop is None:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
        else:
            from neto_incident_monitor.browser_actions import navigate_page
            navigate_page(page, url, stop)
        actual = page.url
        if (not is_short_url(url) and isinstance(actual, str) and urlparse(actual).hostname == urlparse(url).hostname
                and actual.startswith(f"https://{urlparse(url).netloc}/now/nav/ui/classic/params/target/")):
            # Authentication/session restoration can wrap an otherwise direct
            # URL. Reopen the requested list rather than the navigation shell.
            if stop is None:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
            else:
                navigate_page(page, url, stop)
    except Exception as exc:
        if "interrupted by another navigation" not in str(exc):
            raise


def navigate_login_target(page, url, stop):
    from neto_incident_monitor.favorites import HOME
    if url == HOME:
        from neto_incident_monitor.browser_actions import navigate_page
        return navigate_page(page, url, stop)
    return navigate(page, url, stop)


def open_login_target(page, url, stop, on_error=None):
    from neto_incident_monitor.login_diagnostics import LoginDiagnostics
    diagnostics = LoginDiagnostics(source='monitor')
    detach = diagnostics.attach(page)
    try:
        for attempt in range(1, 4):
            if stop.is_set():
                return False
            diagnostics.record('initial_navigation_attempt', attempt=attempt)
            try:
                navigate_login_target(page, url, stop)
                return True
            except Cancelled:
                diagnostics.record('login_cancelled')
                return False
            except TargetClosedError:
                raise
            except Exception as exc:
                diagnostics.record('initial_navigation_error', attempt=attempt, **error_facts(exc))
                if on_error:
                    try:
                        on_error(error_facts(exc))
                    except Exception:
                        pass
                actual = urlparse(page.url)
                if actual.scheme == 'https' and actual.hostname:
                    # Continue inspecting the current page after a slow redirect.
                    return True
                if attempt < 3:
                    page.wait_for_timeout(1000)
        raise LoginTargetUnavailable('Nie udało się połączyć z ServiceNow po trzech próbach.')
    finally:
        detach()


def authentication_page(page, url):
    from neto_incident_monitor.authentication import authentication_required
    return authentication_required(page, url)


def wait_for_login(page, url, stop, auto_login=False, minimize_after_login=False, browser_window=None,
                   on_visibility_failure=None, runtime=None, on_activity=None, fail_unavailable=False,
                   on_password_save=None):
    """Observe authentication, retain delivery ownership and recover only safe GETs."""
    from neto_incident_monitor.automatic_login import AutomaticLogin
    from neto_incident_monitor.authentication import (login_surface, login_observation,
        document_generation, manual_handoff, finish_authentication, set_login_activity, clear_login_activity,
        take_manual_password_entry)
    from neto_incident_monitor.login_diagnostics import LoginDiagnostics
    from neto_incident_monitor.login_observation import origin_kind
    diagnostics = LoginDiagnostics(auto_login=bool(auto_login), minimize=bool(minimize_after_login))
    if runtime:
        diagnostics.network_error = {'network_dns': 'dns', 'network_connection': 'connection',
            'network_tls': 'certificate', 'timeout': 'timeout'}.get(getattr(runtime, 'navigation_error', None))
        runtime.navigation_error = None
    enabled = lambda: not stop.is_set() and (runtime.options.snapshot()['auto_login'] if runtime else auto_login)
    automatic = AutomaticLogin(diagnostics=diagnostics, enabled=enabled)
    detach = [diagnostics.attach(page)]
    popup = None
    stale_main_generation = None
    previous_signature = None
    progress_at = time.monotonic()
    recover_at = 0
    recoveries = 0
    manual_visible = False
    manual_attempts = 0
    manual_due = 0
    visibility_warned = False
    last_activity = None

    def activity(text, tone='working'):
        nonlocal last_activity
        if on_activity and last_activity != (text, tone):
            last_activity = (text, tone)
            on_activity(text, tone)

    def visibility(surface, required):
        nonlocal manual_visible, browser_window, auto_login, minimize_after_login
        nonlocal manual_attempts, manual_due, visibility_warned
        if runtime:
            runtime.page = surface
            runtime.manual_required = required
            options = runtime.tick()
            auto_login = options['auto_login']
            minimize_after_login = options['minimize_browser']
            browser_window = runtime.window
            if runtime.visibility_failure and not visibility_warned:
                visibility_warned = True
                diagnostics.record('manual_login_show_failed', attempt=runtime.manual_attempts)
                if on_visibility_failure:
                    on_visibility_failure()
        elif required and not manual_visible:
            now = time.monotonic()
            if manual_attempts and browser_window and browser_window.is_visible() is True:
                manual_visible = True
                return
            if now < manual_due:
                return
            if manual_attempts >= 3:
                if not visibility_warned:
                    visibility_warned = True
                    diagnostics.record('manual_login_show_failed', attempt=manual_attempts)
                    if on_visibility_failure:
                        on_visibility_failure()
                return
            manual_attempts += 1
            manual_due = now + 2
            if browser_window:
                shown = browser_window.show(activate=True)
            else:
                shown = browser_actions.set_chromium_window_state(surface, 'normal')
            surface.bring_to_front()
            manual_visible = shown is not False
            diagnostics.record('manual_login_shown' if manual_visible else 'manual_login_show_retry', attempt=manual_attempts)

    try:
        set_login_activity(page)
        if runtime:
            runtime.login_rendering.close('not_needed')
            runtime.login_rendering.diagnostics = diagnostics
            runtime.page = page
            runtime.set_activity('login')
        while not stop.is_set():
            if page.is_closed():
                diagnostics.record('browser_closed')
                raise BrowserClosedError('Przeglądarka logowania została zamknięta.')
            try:
                auto_login = runtime.options.snapshot()['auto_login'] if runtime else auto_login
                if popup is not None and popup.is_closed():
                    diagnostics.record('authentication_popup_closed')
                    stale_main_generation = document_generation(page)
                    popup = None
                    if runtime:
                        runtime.page = page
                        runtime.manual_required = not auto_login
                    # The original identity may predate the popup. A fresh safe
                    # target GET is permitted; the delivery ledger is retained.
                    if origin_kind(url) == 'servicenow':
                        diagnostics.record('login_recovery', recovery_reason='popup_closed', attempt=recoveries+1)
                        navigate_login_target(page, url, stop)
                elif popup is not None and login_observation(popup, url).session_ready:
                    diagnostics.record('session_confirmed')
                    if runtime:
                        runtime.page = page
                        runtime.manual_required = not auto_login
                    navigate_login_target(page, url, stop)
                    popup = None
                surface = login_surface(page, url)
                set_login_activity(surface)
                owned_popup = surface != page
                if owned_popup and surface is not popup:
                    popup = surface
                    detach.append(diagnostics.attach(surface))
                    diagnostics.record('authentication_popup')
                observation = login_observation(surface, url, surface='owned_popup' if owned_popup else 'main')
                facts = observation.facts
                diagnostics.inspect(surface, automatic, target=url,
                                    surface_alias='owned_popup' if owned_popup else 'main')
                signature = (surface, observation.state, observation.origin, observation.generation,
                             facts.get('account_count'), facts.get('password_count'),
                             facts.get('password_filled'), facts.get('document_ready'))
                now = time.monotonic()
                if signature != previous_signature:
                    previous_signature, progress_at = signature, now
                owner = manual_handoff(surface) or facts.get('password_manual_edit') is True
                if owner:
                    automatic.block('wykryto ręczną obsługę formularza')
                required = (not auto_login or owner or owned_popup or automatic.blocked or
                            facts.get('intervention') is True)
                if runtime and runtime.rendering_failed:
                    automatic.pause('strona wymaga interwencji użytkownika lub zgłasza błąd')
                    required = True
                if observation.state == 'session' and not owned_popup:
                    fresh = stale_main_generation is None or document_generation(page) != stale_main_generation
                    if fresh:
                        if on_password_save and enabled() and take_manual_password_entry(page):
                            if not on_password_save(page, diagnostics):
                                diagnostics.record('login_cancelled')
                                return False
                            if not login_observation(page, url).session_ready:
                                continue
                        if runtime:
                            runtime.page = page
                            runtime.complete_login()
                        elif browser_window:
                            browser_window.hide()
                        elif minimize_after_login:
                            browser_actions.minimize_chromium(page)
                        finish_authentication(page)
                        diagnostics.record('session_confirmed')
                        diagnostics.record('login_complete')
                        activity('Zalogowano do ServiceNow', 'success')
                        return True
                visibility(surface, required or automatic.needs_user)
                if observation.state == 'authentication':
                    if auto_login and not owned_popup and not (runtime and runtime.rendering_failed):
                        try:
                            automatic.step(surface)
                        except Cancelled:
                            raise
                        except Exception as error:
                            diagnostics.record('automatic_login_step_error', **error_facts(error))
                    required = required or automatic.needs_user or automatic.blocked
                    visibility(surface, required)
                    if required:
                        activity('Wymagane ręczne logowanie', 'waiting')
                    elif automatic.submitted:
                        activity('Oczekiwanie na wynik logowania')
                    elif automatic.prefill_since is not None:
                        activity('Oczekiwanie na autouzupełnienie')
                    else:
                        activity('Logowanie automatyczne')
                else:
                    pending = automatic.submitted or automatic.pending_delivery_token is not None
                    network = diagnostics.network_error
                    certificate = network == 'certificate'
                    if fail_unavailable and (network in ('dns', 'connection', 'timeout', 'certificate') or
                            (isinstance(diagnostics.document_status, int) and diagnostics.document_status >= 500)):
                        raise LoginTargetUnavailable('ServiceNow jest niedostępny.')
                    waiting = now - progress_at
                    reason = ('logout' if observation.state == 'logout' else
                              'network' if network in ('dns', 'connection', 'timeout') or
                              (isinstance(diagnostics.document_status, int) and diagnostics.document_status >= 500)
                              else 'stalled')
                    due = observation.state == 'logout' or (reason == 'network' and waiting >= 5) or waiting >= 180
                    # Never navigate over an authentication form or repeat a
                    # delivered/uncertain password request. The monitor keeps
                    # waiting rather than silently stopping when a budget ends.
                    if (due and now >= recover_at and not pending and not automatic.blocked and
                            not owner and not owned_popup and not certificate and origin_kind(url) == 'servicenow'):
                        recoveries += 1
                        recover_at = now + (5, 15, 60, 300)[min(recoveries-1, 3)]
                        diagnostics.record('login_recovery', recovery_reason=reason, attempt=recoveries,
                                           delay_s=round(recover_at-now))
                        try:
                            navigate_login_target(page, url, stop)
                        except Cancelled:
                            raise
                        except Exception as error:
                            diagnostics.record('login_loop_error', **error_facts(error))
                        progress_at = time.monotonic()
                    need_help = required or certificate or (waiting >= 180 and not network) or (pending and waiting >= 30)
                    visibility(surface, need_help)
                    activity('Wymagane ręczne logowanie' if need_help else
                             'Oczekiwanie na połączenie z ServiceNow' if reason == 'network' else
                             'Odzyskiwanie sesji ServiceNow' if observation.state == 'logout' else
                             'Sprawdzanie sesji ServiceNow', 'waiting' if need_help or reason == 'network' else 'working')
            except Cancelled:
                diagnostics.record('login_cancelled')
                return False
            except (BrowserClosedError, LoginTargetUnavailable):
                raise
            except Exception as error:
                diagnostics.record('login_loop_error', **error_facts(error))
                if page.is_closed():
                    raise BrowserClosedError('Przeglądarka logowania została zamknięta.') from None
            page.wait_for_timeout(100)
        diagnostics.record('login_cancelled')
        return False
    finally:
        clear_login_activity(page)
        if runtime:
            runtime.login_rendering.close('not_needed')
            runtime.login_rendering.diagnostics = runtime.diagnostics
        for release in reversed(detach):
            try:
                release()
            except Exception:
                pass
