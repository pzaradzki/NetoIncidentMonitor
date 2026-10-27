"""Validated local snapshot of dashboard counts, without browser/session data."""
import json
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path

from neto_incident_monitor.dashboard import TITLES, HELD_TITLES, REQUEST_TITLES


def load_snapshot(path):
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        if data.get('schema') != 1:
            return None
        year, month = data['year'], data['month']
        if type(year) is not int or type(month) is not int or not 2000 <= year <= 9999 or not 1 <= month <= 12:
            return None
        datetime.fromisoformat(data['read_at'])
        allowed = set(TITLES + HELD_TITLES + REQUEST_TITLES)
        values = data['values']
        if not isinstance(values, dict) or not values or any(
                key not in allowed or type(value) is not int or value < 0 for key, value in values.items()):
            return None
        return {'year': year, 'month': month, 'read_at': data['read_at'], 'values': values}
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return None


def save_snapshot(path, year, month, values, read_at):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix=path.name + '.', suffix='.tmp', delete=False) as stream:
            temporary = stream.name
            json.dump({'schema': 1, 'year': year, 'month': month, 'read_at': read_at,
                       'values': values}, stream, ensure_ascii=False)
        for attempt in range(4):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if attempt == 3:
                    raise
                time.sleep(0.05 * (attempt + 1))
    finally:
        if temporary and os.path.exists(temporary):
            try:
                os.unlink(temporary)
            except OSError:
                pass
