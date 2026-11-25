"""Read SLA risk and publish the result of the existing snapshot transaction."""
import logging
import sqlite3
import time

from playwright._impl._errors import TargetClosedError

from neto_incident_monitor import analytics_config, threatened_api
from neto_incident_monitor.analytics_api import READ_MESSAGES, data_duration, measure_data_requests
from neto_incident_monitor.browser_actions import checkpoint
from neto_incident_monitor.dashboard import measured_record
from neto_incident_monitor.login_diagnostics import LoginDiagnostics, diagnostic_read, error_facts
from neto_incident_monitor.read_errors import BrowserClosedError, Cancelled
from neto_incident_monitor.section_runner import run_section
from neto_incident_monitor.threatened import KEYS


LOG = logging.getLogger("servicenow")


@diagnostic_read
def read_threatened_request(page, *, request, stop, events, restore, schedule, commit, deliver):
    diagnostics = LoginDiagnostics(source='dashboard', section='threatened', request_id=request)
    started = time.monotonic()
    if schedule is not None:
        measured_record(diagnostics, 'threatened_schedule',
                        lateness_ms=max(0, round((started - schedule['deadline']) * 1000)),
                        delay_reason=schedule['delay_reason'], interval_s=schedule['interval_s'])
    restarting = False
    outcome = 'error'
    try:
        def state(value):
            events.put(('threatened_state', (request, value)))
        checkpoint(stop)
        config = analytics_config.load_config()
        def read():
            with measure_data_requests() as times:
                values, details = threatened_api.read_threats(page, stop, diagnostics, config)
            return values, details, data_duration(times)
        values, details, duration = run_section(page, stop, read, diagnostics, restore, state,
            lambda result: set(result[0]) == set(KEYS)
            and all(type(v) is int and v >= 0 for v in result[0].values())
            and isinstance(result[1], dict))
        checkpoint(stop)
        timestamp = time.time()
        saved = None
        try:
            saved, arrivals = commit(details, timestamp, values, duration)
            diagnostics.record('threatened_details_complete', records_read=len(details), row_count=arrivals,
                               api_data_ms=duration)
            if arrivals:
                deliver()
        except (OSError, ValueError, sqlite3.Error) as exc:
            diagnostics.record('section_read_error', **error_facts(exc))
        if saved is None:
            diagnostics.record('threatened_details_incomplete')
        events.put(('threatened_result', (request, values, timestamp)))
        events.put(('threatened_details', (request, saved, duration)))
        outcome = 'partial' if saved is None else 'returned'
        return saved is not None
    except (TargetClosedError, BrowserClosedError):
        restarting = True
        events.put(('threatened_state', (request, 'Oczekuje')))
        raise
    except Cancelled:
        outcome = 'cancelled'
        events.put(('threatened_state', (request, 'Dane nieaktualne')))
    except Exception as exc:
        reason = getattr(exc, 'reason', None)
        diagnostics.record('section_read_error', read_reason=reason, **error_facts(exc))
        LOG.warning('Nie odczytano zagrożeń SLA (%s).', type(exc).__name__)
        message = READ_MESSAGES.get(reason)
        result = (request, None, None)
        events.put(('threatened_result', (*result, message) if message else result))
    finally:
        fields = {'request_state': 'retrying'} if restarting else {}
        measured_record(diagnostics, 'threatened_read_finished', outcome=outcome,
                        duration_ms=round((time.monotonic() - started) * 1000), **fields)
        if not restarting:
            events.put(('threatened_finished', request))
