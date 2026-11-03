"""The single retry owner for analytics sections; login time is separate."""
from time import monotonic

from neto_incident_monitor.browser_actions import checkpoint
from neto_incident_monitor.read_budget import Budget, budget_scope
from neto_incident_monitor.pagination import AuthenticationRequired, Cancelled
from neto_incident_monitor.dashboard_context import DashboardReadError
from neto_incident_monitor.login_diagnostics import error_facts

ACTIVE_SECONDS = 60


def run_section(page, stop, read, diagnostics, restore, state, validate):
    from neto_incident_monitor.dashboard import diagnostic_steps, measured_record
    total = Budget(ACTIVE_SECONDS)
    login_wait_ms = 0
    for attempt in range(1, 3):
        checkpoint(stop)
        diagnostics.record('section_read_attempt', attempt=attempt)
        state('W trakcie aktualizacji' if attempt == 1 else 'Ponawianie odczytu')
        # Reserve time for recovery; never restart a full independent budget.
        attempt_seconds = min((total.end - monotonic()), ACTIVE_SECONDS * .65 if attempt == 1 else ACTIVE_SECONDS)
        try:
            with budget_scope(Budget(attempt_seconds), recovery=attempt > 1), diagnostic_steps(diagnostics, page=page):
                result = read()
                checkpoint(stop)
                if not validate(result):
                    raise DashboardReadError('incomplete_widgets')
            diagnostics.record('section_read_complete',
                active_ms=max(0, round((ACTIVE_SECONDS - total.end + monotonic()) * 1000)),
                login_wait_ms=login_wait_ms)
            return result
        except AuthenticationRequired:
            diagnostics.record('session_expired')
            if attempt == 2:
                raise
            state('Oczekuje')
            paused = monotonic()
            try:
                if not restore():
                    raise Cancelled()
            except Cancelled:
                diagnostics.record('login_cancelled')
                raise
            finally:
                waited = monotonic() - paused
                total.end += waited
                login_wait_ms += round(waited * 1000)
        except Cancelled:
            diagnostics.record('login_cancelled')
            raise
        except Exception as error:
            facts = error_facts(error)
            reason = error.reason if isinstance(error, DashboardReadError) else facts['error_category']
            retryable = error.retryable if isinstance(error, DashboardReadError) else facts['error_category'] in {
                'timeout', 'document_changed', 'navigation_interrupted', 'network_connection', 'network_dns', 'element_unavailable'}
            final_failure = not retryable or attempt == 2 or monotonic() >= total.end
            diagnostics.record('section_read_error', read_reason=reason, final_failure=final_failure,
                operation=getattr(diagnostics, 'operation', None),
                category=getattr(diagnostics, 'category', None), **facts)
            if final_failure:
                raise
            measured_record(diagnostics, 'section_read_retry', attempt=attempt, read_reason=reason)
    raise DashboardReadError('incomplete_widgets')
