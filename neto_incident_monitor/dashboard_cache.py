"""Versioned per-section snapshots; legacy timestamps are not invented."""
import json
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock

from neto_incident_monitor.dashboard import (
    HELD_METRIC_TITLES, HELD_TITLES, MONTHLY_TITLES, REQUEST_TITLES, TITLES, measured_record,
)
from neto_incident_monitor.login_diagnostics import LoginDiagnostics, error_facts

SECTIONS = {'sla': TITLES, 'held': HELD_TITLES, 'requests': REQUEST_TITLES}
NAMES = {'sla': 'Dashboard SLA', 'held': 'Wstrzymane L1', 'requests': 'Wnioski L1'}
LEGACY_TITLES = {'sla': MONTHLY_TITLES, 'held': HELD_METRIC_TITLES}


def valid_values(section, values):
    return (isinstance(values, dict) and set(values) == set(SECTIONS[section]) and
            all(type(v) is int and v >= 0 for v in values.values()))


def legacy_values(section, values):
    return (section in LEGACY_TITLES and isinstance(values, dict)
            and set(values) == set(LEGACY_TITLES[section])
            and all(type(value) is int and value >= 0 for value in values.values()))


def valid_period(year, month):
    return type(year) is int and type(month) is int and 2000 <= year <= 9999 and 1 <= month <= 12


def valid_time(value):
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    datetime.fromisoformat(value)
    return True


def load_snapshot(path):
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        if data.get('schema') == 1:
            year, month, values = data['year'], data['month'], data['values']
            if not valid_period(year, month) or not isinstance(values, dict):
                return None
            sections = {}
            for section, titles in SECTIONS.items():
                part = {t: values[t] for t in titles if t in values}
                complete = valid_values(section, part)
                if complete or legacy_values(section, part):
                    sections[section] = {'values': part, 'read_at': None, 'last_attempt_at': None,
                        'last_outcome': 'unknown', 'complete': complete,
                        'year': year if section == 'sla' else None, 'month': month if section == 'sla' else None}
            return {'schema': 2, 'sections': sections, 'last_complete_read_at': None} if sections else None
        if data.get('schema') != 2 or not isinstance(data.get('sections'), dict):
            return None
        sections = data['sections']
        if not sections or any(section not in SECTIONS for section in sections):
            return None
        requests = sections.get('requests')
        old_values = requests.get('values') if isinstance(requests, dict) else None
        legacy_requests = (isinstance(old_values, dict)
                           and set(old_values) == set(REQUEST_TITLES[:-1])
                           and all(type(value) is int and value >= 0 for value in old_values.values()))
        if legacy_requests:
            sections = {name: snapshot for name, snapshot in sections.items() if name != 'requests'}
            if not sections:
                return None
        historical = False
        for section, snapshot in sections.items():
            if not isinstance(snapshot, dict):
                return None
            values = snapshot.get('values')
            old = legacy_values(section, values)
            complete = snapshot.get('complete')
            if (not (valid_values(section, values) and complete is True or old and type(complete) is bool) or
                    not valid_time(snapshot.get('read_at')) or
                    not valid_time(snapshot.get('last_attempt_at')) or
                    snapshot.get('last_outcome') not in ('success', 'error', 'unknown') or
                    (snapshot.get('last_outcome') == 'success' and snapshot.get('read_at') is None)):
                return None
            if section == 'sla' and not valid_period(snapshot.get('year'), snapshot.get('month')):
                return None
            if old:
                snapshot['complete'] = False
                historical = True
        completed = None if legacy_requests or historical else data.get('last_complete_read_at')
        try:
            if not valid_time(completed):
                completed = None
        except ValueError:
            completed = None
        period = data.get('last_complete_period')
        if not (completed and isinstance(period, list) and len(period) == 2 and valid_period(*period)):
            period = None
        duration = data.get('last_complete_duration_ms')
        if period is None or type(duration) is not int or duration < 0:
            duration = None
        return {'schema': 2, 'sections': sections, 'last_complete_read_at': completed,
                'last_complete_period': period, 'last_complete_duration_ms': duration}
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return None


def save_sections(path, sections, last_complete_read_at=None, *, period=None, duration_ms=None, on_retry=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                prefix=path.name + '.', suffix='.tmp', delete=False) as stream:
            temporary = stream.name
            json.dump({'schema': 2, 'sections': sections,
                       'last_complete_read_at': last_complete_read_at, 'last_complete_period': period,
                       'last_complete_duration_ms': duration_ms}, stream, ensure_ascii=False)
        for attempt in range(4):
            try:
                os.replace(temporary, path)
                break
            except PermissionError as error:
                if attempt == 3:
                    raise
                delay = .05 * (attempt + 1)
                if on_retry is not None:
                    on_retry(attempt + 1, delay, error)
                time.sleep(delay)
    finally:
        if temporary and os.path.exists(temporary):
            try:
                os.unlink(temporary)
            except OSError:
                pass


def save_snapshot(path, year, month, values, read_at):
    """Compatibility entry point; accepts complete sections only."""
    sections = {}
    for section, titles in SECTIONS.items():
        part = {t: values[t] for t in titles if t in values}
        if valid_values(section, part):
            sections[section] = {'values': part, 'read_at': read_at, 'last_attempt_at': read_at,
                'last_outcome': 'success', 'complete': True,
                'year': year if section == 'sla' else None, 'month': month if section == 'sla' else None}
    save_sections(path, sections)


@dataclass(frozen=True)
class CacheWrite:
    revision: int
    request_id: int
    sections: dict
    last_complete_read_at: str | None
    period: tuple | None
    duration_ms: int | None


class DashboardCacheWriter:
    """Serialize writes to one cache, keeping at most the newest pending snapshot."""

    def __init__(self, path, events):
        self.path = path
        self.events = events
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='dashboard-cache')
        self._lock = Lock()
        self._revision = 0
        self._pending = None
        self._running = False
        self._closed = False

    @property
    def idle(self):
        with self._lock:
            return not self._running

    def submit(self, request_id, sections, last_complete_read_at, *, period, duration_ms):
        snapshot = deepcopy(sections)
        with self._lock:
            if self._closed:
                return None
            self._revision += 1
            self._pending = CacheWrite(self._revision, request_id, snapshot, last_complete_read_at, period, duration_ms)
            if not self._running:
                self._running = True
                self._executor.submit(self._drain)
            return self._revision

    def close(self, *, discard=False):
        with self._lock:
            self._closed = True
            if discard:
                self._pending = None
        self._executor.shutdown(wait=False)

    def _drain(self):
        while True:
            with self._lock:
                job, self._pending = self._pending, None
                if job is None:
                    self._running = False
                    return
            self._write(job)

    def _write(self, job):
        started = time.perf_counter()
        try:
            diagnostics = LoginDiagnostics(source='dashboard', request_id=job.request_id, cache_revision=job.revision)
        except Exception:
            diagnostics = None
        measured_record(diagnostics, 'dashboard_cache', cache_result='started')

        def retry(attempt, delay, error):
            measured_record(diagnostics, 'dashboard_cache', cache_result='retry', attempt=attempt,
                            cache_retry_ms=round(delay * 1000), **error_facts(error))

        result, facts = 'saved', {}
        try:
            save_sections(self.path, job.sections, job.last_complete_read_at, period=job.period,
                          duration_ms=job.duration_ms, on_retry=retry)
        except Exception as error:
            result, facts = 'failed', error_facts(error)
        measured_record(diagnostics, 'dashboard_cache', cache_result=result,
                        duration_ms=round((time.perf_counter() - started) * 1000), **facts)
        self.events.put(('dashboard_cache_result', (job.revision, result)))
