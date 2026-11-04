"""Read-only startup checks; invalid business data is never replaced with defaults."""
import math
import sqlite3
import time


class StartupDataError(Exception):
    def __init__(self, area, category):
        self.area, self.category = area, category
        super().__init__('Nie można bezpiecznie odczytać lokalnych danych aplikacji.')


def _require(condition):
    if not condition:
        raise ValueError('Nieprawidłowa struktura lokalnych danych.')


def _string_map(value):
    return isinstance(value, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in value.items())


def _template(value, named=False):
    _require(isinstance(value, dict))
    for key in ('name', 'message', 'item', 'template_id'):
        if key in value:
            _require(isinstance(value[key], str))
    if named:
        _require(all(isinstance(value.get(k), str) for k in ('name', 'message', 'item')))
    if 'bindings' in value:
        _require(_string_map(value['bindings']))


def validate_filters(entries):
    _require(isinstance(entries, list))
    for entry in entries:
        _require(isinstance(entry, dict) and all(isinstance(entry.get(k), str) for k in ('name', 'url')))
        if 'notification_templates' in entry:
            _require(isinstance(entry['notification_templates'], dict))
            for template in entry['notification_templates'].values():
                _template(template)


def validate_config(settings):
    _require(isinstance(settings, dict))
    if 'filters' in settings:
        validate_filters(settings['filters'])
    if 'urls' in settings:
        _require(isinstance(settings['urls'], list) and all(isinstance(v, str) for v in settings['urls']))
    for key in ('window_layout', 'column_widths', 'filter_visible_columns'):
        if key in settings:
            _require(isinstance(settings[key], dict))
    if 'window_layout' in settings:
        layout = settings['window_layout']
        if 'geometry' in layout:
            _require(isinstance(layout['geometry'], str))
    if 'sidebar_width' in settings:
        _require(isinstance(settings['sidebar_width'], (str, int)))
        int(settings['sidebar_width'])
    if 'notification_library' in settings:
        _require(isinstance(settings['notification_library'], dict))
        for template in settings['notification_library'].values():
            _template(template, named=True)
    # Reject values that Tcl BooleanVar cannot represent; retain legacy 0/1.
    boolean_keys = ('notify', 'teams_enabled', 'google_chat_enabled', 'notify_threatened',
                    'auto_login', 'dashboard_auto_refresh', 'minimize_to_tray',
                    'start_monitoring', 'start_minimized', 'minimize_browser', 'hide_browser')
    for key in boolean_keys:
        if key in settings:
            _require(type(settings[key]) in (bool, int) and settings[key] in (0, 1))


def _timestamp(value):
    _require(type(value) in (float, int) and math.isfinite(value))
    try:
        time.localtime(value)
    except (OverflowError, OSError):
        raise ValueError('Nieprawidłowa data lokalnych danych.') from None


def validate_history(records):
    _require(isinstance(records, dict))
    for record in records.values():
        _require(isinstance(record, dict))
        incident = record.get('incident')
        _require(isinstance(incident, dict) and isinstance(incident.get('number'), str) and bool(incident['number']))
        _require(_string_map(record.get('filters')))
        _timestamp(record.get('detected'))
        from neto_incident_monitor.columns import FIELDS
        for key in [field[0] for field in FIELDS] + ['url', 'summary']:
            if key in incident:
                _require(isinstance(incident[key], str))
        if '_values' in incident:
            _require(_string_map(incident['_values']))


def _validate_threatened(records):
    for number, record in records.items():
        _require(isinstance(record, dict) and record.get('number') == number)
        _require(all(isinstance(record.get(k), str) for k in ('number', 'url', 'deadline', 'remaining')))
        _require(isinstance(record.get('categories'), list) and all(isinstance(k, str) for k in record['categories']))
        _require(type(record.get('percent')) in (float, int) and math.isfinite(record['percent']))
        _require(type(record.get('present')) is bool)
        for field in ('first_seen', 'last_seen'):
            _timestamp(record.get(field))


def preflight(config_path, history_path):
    from neto_incident_monitor.secret_config import load_config
    from neto_incident_monitor.history import History
    from neto_incident_monitor.filter_state import FilterState
    from neto_incident_monitor.service_now_urls import normalize_list_url
    for area, check in (
        ('configuration', lambda: validate_config(load_config(config_path, {}, migrate_plaintext=False))),
        ('history', lambda: _check_history(History(history_path), FilterState, normalize_list_url)),
    ):
        try:
            check()
        except (OSError, sqlite3.OperationalError):
            raise StartupDataError(area, 'unavailable') from None
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError, sqlite3.DatabaseError):
            raise StartupDataError(area, 'invalid') from None


def _check_history(history, legacy_type, normalize):
    _validate_threatened(history.threatened_snapshot())
    if history.membership is None:
        legacy_type(history.path.with_name('seen.json'), normalize)
