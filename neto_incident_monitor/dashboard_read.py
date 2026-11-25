"""Run a selected dashboard period and report section results to Tk."""
import logging
from datetime import datetime
from time import monotonic

from playwright._impl._errors import TargetClosedError

from neto_incident_monitor import analytics_config, dashboard_api
from neto_incident_monitor.analytics_api import READ_MESSAGES, data_duration, measure_data_requests
from neto_incident_monitor.browser_actions import checkpoint
from neto_incident_monitor.dashboard import TITLES, HELD_TITLES, REQUEST_TITLES, measured_record
from neto_incident_monitor.dashboard_context import DashboardReadError
from neto_incident_monitor.login_diagnostics import LoginDiagnostics, diagnostic_read
from neto_incident_monitor.read_errors import (
    AuthenticationRequired, BrowserClosedError, Cancelled, LoginTargetUnavailable,
)
from neto_incident_monitor.section_runner import run_section


LOG = logging.getLogger("servicenow")


@diagnostic_read
def read_dashboard_request(page, *, request, stop, events, restore, schedule=None):
    request_id, year, month = request
    events.put(('dashboard_updating', (request_id, year, month, 'running')))
    success, values, failures = False, {}, []
    restarting = cancelled = False
    section = 'Dashboard SLA'
    schedule_started = monotonic()
    schedule_log = None
    try:
        if schedule is not None:
            try:
                schedule_log = LoginDiagnostics(source='dashboard', request_id=request_id, year=year, month=month)
            except Exception:
                pass
            measured_record(schedule_log, 'dashboard_schedule', outcome='started', **schedule)
        try:
            config = analytics_config.load_config()
        except DashboardReadError:
            config = None
        if config is not None and not analytics_config.has_dashboard_scope(config):
            checkpoint(stop)
            diagnostics = LoginDiagnostics(source='dashboard', request_id=request_id, year=year, month=month)
            diagnostics.record('dashboard_scope_check', scope_state='missing', read_reason='dashboard_scope_missing')
            detail = ('Brakuje list agentów i lokalizacji. Pobierz je w Ustawieniach → Dane aplikacji → '
                      'Agenci i lokalizacje Dashboardu SLA → Aktualizuj, a następnie ponów odczyt.')
            events.put(('dashboard_result', (request_id, year, month, {}, None, detail)))
            return False
        for section, alias, expected, reader in (
            ('Dashboard SLA', 'sla', TITLES, dashboard_api.read_month),
            ('Wstrzymane L1', 'held', HELD_TITLES, dashboard_api.read_held),
            ('Wnioski L1', 'requests', REQUEST_TITLES, dashboard_api.read_requests)):
            checkpoint(stop)
            context = {'year': year, 'month': month} if alias == 'sla' else {}
            diagnostics = LoginDiagnostics(source='dashboard', section=alias, request_id=request_id, **context)
            completed = {}
            def state(value):
                events.put(('dashboard_section_status', (request_id, section, value)))
            def read():
                if config is None:
                    raise DashboardReadError('api_configuration', retryable=False)
                if alias == 'sla':
                    return reader(page, stop, diagnostics, config, year, month, completed)
                return reader(page, stop, diagnostics, config, completed)
            try:
                # Count queries reuse validated counters across a retry. Their timings follow the same scope.
                with measure_data_requests() as times:
                    result = run_section(page, stop, read, diagnostics, restore, state,
                        lambda v: set(v) == set(expected) and all(type(n) is int and n >= 0 for n in v.values()))
                values.update(result)
                state('Zaktualizowany')
                metadata = {'section': alias, 'read_at': datetime.now().astimezone().isoformat(timespec='seconds'),
                            'diagnostics': diagnostics, 'values': dict(result), 'duration_ms': data_duration(times)}
            except (TargetClosedError, BrowserClosedError, Cancelled, AuthenticationRequired, LoginTargetUnavailable):
                raise
            except Exception as exc:
                state('Błąd odczytu')
                reason = READ_MESSAGES.get(getattr(exc, 'reason', None))
                failures.append(f'{section} ({reason.rstrip(".")})' if reason else section)
                LOG.warning('Dashboard: sekcja %s nie powiodła się (%s).', alias, type(exc).__name__)
                metadata = {'section': alias, 'error': True, 'diagnostics': diagnostics}
            events.put(('dashboard_result', (request_id, year, month, dict(values), None, '', metadata)))
        message = ''
        if failures:
            message = 'Sekcje bez nowego wyniku: ' + ', '.join(failures) + '.'
        events.put(('dashboard_result', (request_id, year, month, dict(values), None, message)))
        success = not failures and not stop.is_set()
    except (TargetClosedError, BrowserClosedError):
        restarting = True
        raise
    except Cancelled:
        cancelled = True
        events.put(('dashboard_updating', (request_id, year, month, 'cancelled')))
    except Exception as exc:
        events.put(('dashboard_section_status', (request_id, section, 'Błąd odczytu')))
        events.put(('dashboard_result', (request_id, year, month, None, True)))
    finally:
        if schedule is not None:
            outcome = ('cancelled' if cancelled or stop.is_set() else 'returned' if success else
                       'partial' if values and failures and not restarting else 'error')
            terminal = {'request_state': 'retrying'} if restarting else {}
            measured_record(schedule_log, 'dashboard_schedule', outcome=outcome, **terminal,
                            duration_ms=round((monotonic() - schedule_started) * 1000), **schedule)
        events.put(('dashboard_updating', (request_id, year, month,
                         'retrying' if restarting else 'finished')))

    return success
