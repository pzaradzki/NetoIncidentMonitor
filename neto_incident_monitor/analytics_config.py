"""Validated local inputs for the two ServiceNow analytics views."""
import json
import re

from neto_incident_monitor.dashboard import HELD_TITLES, REQUEST_TITLES, month_range
from neto_incident_monitor.dashboard_context import DashboardReadError
from neto_incident_monitor.runtime_paths import DATA

CONFIG_PATH = DATA / 'dashboard-api.json'
SYS_ID = re.compile(r'[0-9a-f]{32}', re.ASCII | re.IGNORECASE)


def load_config(path=None):
    try:
        with (CONFIG_PATH if path is None else path).open(encoding='utf-8-sig') as stream:
            raw = stream.read(24_001)
        if len(raw) > 24_000:
            raise ValueError
        config = json.loads(raw)
        if (not isinstance(config, dict) or type(config.get('version')) is not int
                or config['version'] != 1):
            raise ValueError
        return config
    except (OSError, ValueError) as exc:
        raise DashboardReadError('api_configuration', retryable=False) from exc


def reference(config, key):
    value = config.get(key)
    if not isinstance(value, str) or not SYS_ID.fullmatch(value):
        raise DashboardReadError('api_configuration', retryable=False)
    return value.lower()


def reference_set(config, key):
    values = config.get(key)
    if (not isinstance(values, list) or not 1 <= len(values) <= 250
            or any(not isinstance(value, str) or not SYS_ID.fullmatch(value) for value in values)
            or len({value.lower() for value in values}) != len(values)):
        raise DashboardReadError('api_configuration', retryable=False)
    return ','.join(value.lower() for value in values)


def dashboard_scope(config):
    return {key: reference_set(config, key).split(',') for key in ('assignees', 'locations')}


def scope_from_p1_query(query):
    if not isinstance(query, str) or len(query) > 24_000 or any(ord(char) < 32 or ord(char) == 127 for char in query):
        raise DashboardReadError('dashboard_scope_query', retryable=False)
    clauses = query.split('^')
    if clauses.count('task.priority=1') != 1 or any(clause.startswith(('OR', 'NQ')) and
                                                    not clause.startswith('ORDERBY') for clause in clauses):
        raise DashboardReadError('dashboard_scope_query', retryable=False)
    scope = {}
    for key, prefix in (('assignees', 'task.assigned_toIN'), ('locations', 'task.locationIN')):
        matches = [clause[len(prefix):] for clause in clauses if clause.startswith(prefix)]
        if len(matches) != 1:
            raise DashboardReadError('dashboard_scope_query', retryable=False)
        scope[key] = matches[0].split(',')
    try:
        return dashboard_scope(scope)
    except DashboardReadError:
        raise DashboardReadError('dashboard_scope_query', retryable=False) from None


def save_dashboard_scope(scope, path=None):
    from neto_incident_monitor.app import save_json
    from neto_incident_monitor.data_reset import reject_redirect

    path = CONFIG_PATH if path is None else path
    scope = dashboard_scope(scope)
    try:
        reject_redirect(path)
        reject_redirect(path.with_suffix('.tmp'))
        config = load_config(path)
        save_json(path, {**config, **scope})
    except (OSError, ValueError, DashboardReadError):
        raise DashboardReadError('dashboard_scope_save', retryable=False) from None


def monthly_query(config, year, month):
    start, end = month_range(year, month)
    return '^'.join((
        'task.locationIN' + reference_set(config, 'locations'),
        'task.stateIN1,2,3,6,7,8',
        'task.assigned_toIN' + reference_set(config, 'assignees'),
        f"task.opened_atBETWEENjavascript:gs.dateGenerate('{start}','start')"
        f"@javascript:gs.dateGenerate('{end}','end')",
        'task.assignment_group=' + reference(config, 'monthly_group'),
        'stage!=cancelled', 'sla.nameLIKE6/22', 'task.ref_incident.parent_incidentISEMPTY',
    ))


def held_queries(config):
    prefix = (
        'inc_assigned_toIN' + reference_set(config, 'assignees'),
        'mi_definition=' + reference(config, 'held_metric'),
        'mi_value=On Hold', 'inc_assignment_group.name=' + group_name(config), 'mi_endISEMPTY',
    )
    return {
        title: '^'.join((*prefix, f'mi_startRELATIVELT@dayofweek@ago@{days}',
                         'inc_active=true', 'inc_parent_incidentISEMPTY'))
        for title, days in zip(HELD_TITLES, (14, 7))
    }


def group_name(config):
    value = config.get('l1_group_name')
    if not isinstance(value, str) or not re.fullmatch(r'[\w .-]{1,120}', value):
        raise DashboardReadError('api_configuration', retryable=False)
    return value


def smartphone_start_condition(config):
    variable = reference(config, 'smartphone_variable')
    return f'variables.{variable}RELATIVELT@dayofweek@ago@3'


def request_queries(config):
    prefix = '^'.join(('assigned_toIN' + reference_set(config, 'assignees'),
                       'active=true', 'assignment_group.name=' + group_name(config)))
    description = config.get('smartphone_description')
    if not isinstance(description, str) or not re.fullmatch(r'[\w .()/-]{1,120}', description):
        raise DashboardReadError('api_configuration', retryable=False)
    age = '^sys_created_onRELATIVELT@dayofweek@ago@'
    return dict(zip(REQUEST_TITLES, (
        prefix, prefix + age + '7', prefix + age + '14', prefix + '^assigned_toISEMPTY',
        f'{prefix}^{smartphone_start_condition(config)}'
        f'^short_descriptionLIKE{description}{age}14',
    )))
