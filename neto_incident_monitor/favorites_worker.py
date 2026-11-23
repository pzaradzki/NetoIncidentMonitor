"""Deliver the REST import result from the shared session to Tk."""
from time import monotonic

from playwright._impl._errors import TargetClosedError

from neto_incident_monitor.analytics_api import READ_MESSAGES
from neto_incident_monitor.dashboard import measured_record
from neto_incident_monitor.dashboard_context import DashboardReadError
from neto_incident_monitor.favorites_api import read_favorites
from neto_incident_monitor.login_diagnostics import LoginDiagnostics, error_facts
from neto_incident_monitor.read_errors import AuthenticationRequired, Cancelled
from neto_incident_monitor.section_runner import run_section


ACTIVE_SECONDS = 30
STATUS_TEXT = {
    'W trakcie aktualizacji': 'Pobieranie Ulubionych z ServiceNow…',
    'Ponawianie odczytu': 'Ponawianie odczytu Ulubionych…',
    'Oczekuje': 'Oczekiwanie na logowanie do ServiceNow…',
}
READ_ERROR = 'Nie udało się pobrać Ulubionych z ServiceNow.'


def read_on_session(page, request, session, stop):
    from neto_incident_monitor.read_errors import BrowserClosedError

    token = request['id']
    log = LoginDiagnostics(source='favorites', import_id=token, request_id=session.active_job.id)
    started = monotonic()
    outcome = 'error'
    payload = READ_ERROR

    def status(message):
        request['events'].put((token, 'status', STATUS_TEXT.get(message, message)))

    try:
        payload = run_section(page, stop, lambda: read_favorites(page, stop, log), log,
                              lambda: session.authenticate(page, stop), status,
                              active_seconds=ACTIVE_SECONDS)
        outcome = 'returned'
    except Cancelled:
        outcome = 'cancelled'
        raise
    except (TargetClosedError, BrowserClosedError):
        raise
    except AuthenticationRequired:
        payload = 'Sesja ServiceNow wygasła ponownie. Uruchom import jeszcze raz.'
    except DashboardReadError as error:
        payload = READ_MESSAGES.get(error.reason, READ_ERROR)
    except Exception as error:
        measured_record(log, 'favorites_error', **error_facts(error))
    finally:
        measured_record(log, 'favorites_end', outcome=outcome, duration_ms=round((monotonic() - started) * 1000))
    success = outcome == 'returned'
    request['events'].put((token, 'result', ('success' if success else 'error', payload)))
    return success
