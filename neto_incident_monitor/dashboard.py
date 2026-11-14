"""Dashboard definitions, derived SLA indicator and read diagnostics."""
import calendar
from contextlib import contextmanager
from contextvars import ContextVar
from decimal import Decimal
import time

from neto_incident_monitor.pagination import AuthenticationRequired, Cancelled


DASHBOARD_URL = ('https://adeo.service-now.com/now/platform-analytics-workspace/dashboards/params/edit/false/'
                 'tab-sys-id/ba36dad72b6a8b504b98f4c2c891bf73/sys-id/22361ad72b6a8b504b98f4c2c891bfab/'
                 'unified-filters-param/tinyurl/__state__/b64-tiny~WKEf3X0ASg6M0LcR1kiqt049NKRrAV35')


TITLES = ('Liczba zgłoszeń',) + tuple(f'Zgłoszenia P{i}' for i in range(1, 6)) + tuple(f'Przekroczone P{i}' for i in range(1, 6))


HELD_TITLES = ('Wstrzymane L1 >14 dni', 'Wstrzymane L1 >7 dni')


REQUEST_TITLES = ('Otwarte wnioski L1', 'Wnioski L1 >7 dni',
                  'Wnioski L1 >14 dni', 'Nieprzypisane wnioski L1',
                  'Wnioski Smartfon – start >3 dni')


_diagnostics = ContextVar('dashboard_diagnostics', default=None)


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
    state = {'started': time.monotonic(), 'operation': None}
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
                    outcome=outcome,
                    duration_ms=round((time.monotonic() - state['started']) * 1000))
            if detach:
                try:
                    detach()
                except Exception:
                    pass
        finally:
            _measurement.reset(timing_token)
            _diagnostics.reset(token)


def operation(code):
    diagnostics = _diagnostics.get()
    if diagnostics:
        state = _measurement.get()
        if state is not None and code != state['operation']:
            now = time.monotonic()
            if state['operation']:
                measured_record(diagnostics, 'dashboard_stage_end', operation=state['operation'],
                    outcome='returned',
                    duration_ms=round((now - state['started']) * 1000))
            state.update(started=now, operation=code)
        diagnostics.operation = code
        measured_record(diagnostics, 'dashboard_operation', operation=code)


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
