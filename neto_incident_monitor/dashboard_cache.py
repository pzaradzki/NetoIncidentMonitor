"""Versioned per-section snapshots; legacy timestamps are not invented."""
import json
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path
from neto_incident_monitor.dashboard import TITLES, HELD_TITLES, REQUEST_TITLES

SECTIONS = {'sla': TITLES, 'held': HELD_TITLES, 'requests': REQUEST_TITLES}
NAMES = {'sla': 'Dashboard SLA', 'held': 'Wstrzymane L1', 'requests': 'Wnioski L1'}


def valid_values(section, values):
    return (isinstance(values, dict) and set(values) == set(SECTIONS[section]) and
            all(type(v) is int and v >= 0 for v in values.values()))


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
                if valid_values(section, part):
                    sections[section] = {'values': part, 'read_at': None, 'last_attempt_at': None,
                        'last_outcome': 'unknown', 'complete': True,
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
        for section, snapshot in sections.items():
            if (not isinstance(snapshot, dict) or not valid_values(section, snapshot.get('values')) or
                    snapshot.get('complete') is not True or not valid_time(snapshot.get('read_at')) or
                    not valid_time(snapshot.get('last_attempt_at')) or
                    snapshot.get('last_outcome') not in ('success', 'error', 'unknown') or
                    (snapshot.get('last_outcome') == 'success' and snapshot.get('read_at') is None)):
                return None
            if section == 'sla' and not valid_period(snapshot.get('year'), snapshot.get('month')):
                return None
        completed = None if legacy_requests else data.get('last_complete_read_at')
        try:
            if not valid_time(completed):
                completed = None
        except ValueError:
            completed = None
        return {'schema': 2, 'sections': sections, 'last_complete_read_at': completed}
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return None


def save_sections(path, sections, last_complete_read_at=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                prefix=path.name + '.', suffix='.tmp', delete=False) as stream:
            temporary = stream.name
            json.dump({'schema': 2, 'sections': sections,
                       'last_complete_read_at': last_complete_read_at}, stream, ensure_ascii=False)
        for attempt in range(4):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if attempt == 3:
                    raise
                time.sleep(.05 * (attempt + 1))
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
