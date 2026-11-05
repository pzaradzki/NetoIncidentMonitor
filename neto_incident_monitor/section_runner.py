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
    read_retry_used = login_recovery_used = False
    for attempt in range(1, 4):
        checkpoint(stop)
        diagnostics.record('section_read_attempt', attempt=attempt)
        state('W trakcie aktualizacji' if attempt == 1 else 'Ponawianie odczytu')
        # Reserve time for recovery; never restart a full independent budget.
        attempt_seconds = min((total.end - monotonic()), ACTIVE_SECONDS * .65 if attempt == 1 else ACTIVE_SECONDS)
        try:
            attempt_budget = Budget(attempt_seconds)
            with budget_scope(attempt_budget, recovery=attempt > 1), diagnostic_steps(diagnostics, page=page):
                attempt_budget.check()
                result = read()
                checkpoint(stop)
                attempt_budget.check()
                if not validate(result):
                    raise DashboardReadError('incomplete_widgets')
            diagnostics.record('section_read_complete',
                active_ms=max(0, round((ACTIVE_SECONDS - total.end + monotonic()) * 1000)),
                login_wait_ms=login_wait_ms)
            return result
        except AuthenticationRequired as error:
            diagnostics.record('session_expired')
            final_failure = login_recovery_used or monotonic() >= total.end
            diagnostics.record('section_read_error', read_reason='authentication_required',
                final_failure=final_failure, **error_facts(error))
            if final_failure:
                raise
            login_recovery_used = True
            state('Oczekuje')
            paused = monotonic()
            outcome, recovery_facts = 'error', {}
            diagnostics.record('section_login_recovery_start', attempt=attempt)
            try:
                checkpoint(stop)
                if not restore():
                    raise Cancelled()
                checkpoint(stop)
                outcome = 'returned'
            except Cancelled:
                outcome = 'cancelled'
                diagnostics.record('login_cancelled')
                raise
            except Exception as recovery_error:
                recovery_facts = error_facts(recovery_error)
                diagnostics.record('section_read_error', read_reason='authentication_required',
                    final_failure=True, **recovery_facts)
                raise
            finally:
                waited = monotonic() - paused
                total.end += waited
                login_wait_ms += round(waited * 1000)
                diagnostics.record('section_login_recovery_end', attempt=attempt, outcome=outcome,
                    duration_ms=max(0, round(waited * 1000)), login_wait_ms=login_wait_ms, **recovery_facts)
            measured_record(diagnostics, 'section_read_retry', attempt=attempt,
                            read_reason='authentication_required')
        except Cancelled:
            diagnostics.record('login_cancelled')
            raise
        except Exception as error:
            facts = error_facts(error)
            reason = error.reason if isinstance(error, DashboardReadError) else facts['error_category']
            retryable = error.retryable if isinstance(error, DashboardReadError) else facts['error_category'] in {
                'timeout', 'document_changed', 'navigation_interrupted', 'network_connection', 'network_dns', 'element_unavailable'}
            final_failure = not retryable or read_retry_used or monotonic() >= total.end
            diagnostics.record('section_read_error', read_reason=reason, final_failure=final_failure,
                operation=getattr(diagnostics, 'operation', None),
                category=getattr(diagnostics, 'category', None), **facts)
            if final_failure:
                raise
            read_retry_used = True
            measured_record(diagnostics, 'section_read_retry', attempt=attempt, read_reason=reason)
    raise DashboardReadError('incomplete_widgets')
