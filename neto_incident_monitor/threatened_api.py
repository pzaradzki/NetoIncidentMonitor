"""One bounded snapshot for the risk scores and incident details."""
from datetime import datetime, timedelta, timezone
import re

from neto_incident_monitor.analytics_api import ORIGIN, count, get
from neto_incident_monitor.analytics_config import SYS_ID, reference
from neto_incident_monitor.dashboard import measured_record
from neto_incident_monitor.dashboard_context import DashboardReadError
from neto_incident_monitor.service_now_urls import safe_record_url
from neto_incident_monitor.threatened import KEYS

WINDOWS = dict(zip(KEYS, (timedelta(hours=1), timedelta(hours=2), timedelta(hours=4),
                          timedelta(days=1), timedelta(days=2), timedelta(minutes=5))))
PAGE_SIZE = 100
MAX_PAGES = 10
FIELDS = ('sys_id', 'task', 'task.number', 'task.priority', 'sla.target',
          'planned_end_time', 'business_time_left', 'business_percentage')
DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'


def build_query(config, as_of):
    common = '^'.join((
        'task.sys_class_name=incident',
        'task.assignment_group=' + reference(config, 'threatened_group'),
        'task.active=true', 'task.stateNOT IN3,6,7,8', 'active=true', 'stage=in_progress',
        'task.ref_incident.parent_incidentISEMPTY',
    ))
    branches = []
    for key, interval in WINDOWS.items():
        kind = 'sla.target=response' if key == 'Podjęcie' else f'sla.target=resolution^task.priority={key[1]}'
        limit = (as_of + interval).strftime(DATETIME_FORMAT)
        branches.append(f'{common}^{kind}^planned_end_time<{limit}')
    return '^NQ'.join(branches) + '^ORDERBYsys_id'


def field(row, key, variant='value'):
    value = row.get(key)
    return value.get(variant) if isinstance(value, dict) else value


def summarize(rows, as_of):
    scores = dict.fromkeys(KEYS, 0)
    incidents, task_by_number, number_by_task = {}, {}, {}
    for row in rows:
        task, sla, number = (field(row, key) for key in ('task', 'sys_id', 'task.number'))
        if (not isinstance(task, str) or not SYS_ID.fullmatch(task)
                or not isinstance(number, str) or not re.fullmatch(r'INC[0-9]{1,20}', number)):
            raise DashboardReadError('api_schema', retryable=False)
        task = task.lower()
        target, priority = (field(row, key) for key in ('sla.target', 'task.priority'))
        if target == 'response':
            category = 'Podjęcie'
        elif target == 'resolution' and priority in ('1', '2', '3', '4', '5'):
            category = 'P' + priority
        else:
            raise DashboardReadError('api_filter_mismatch', retryable=False)
        try:
            deadline = datetime.strptime(field(row, 'planned_end_time'), DATETIME_FORMAT).replace(tzinfo=timezone.utc)
            raw_percent = field(row, 'business_percentage')
            if (type(raw_percent) not in (str, int, float)
                    or not re.fullmatch(r'[0-9]{1,12}(?:\.[0-9]{1,10})?', str(raw_percent))):
                raise ValueError
            percent = float(raw_percent)
        except (TypeError, ValueError) as exc:
            raise DashboardReadError('api_schema', retryable=False) from exc
        if deadline >= as_of + WINDOWS[category]:
            raise DashboardReadError('api_filter_mismatch', retryable=False)
        remaining = field(row, 'business_time_left', 'display_value')
        if not isinstance(remaining, str) or not remaining.strip() or len(remaining) > 120:
            raise DashboardReadError('api_schema', retryable=False)
        if (task_by_number.setdefault(number, task) != task or
                number_by_task.setdefault(task, number) != number):
            raise DashboardReadError('api_incomplete')
        url = safe_record_url(f'{ORIGIN}/incident.do?sys_id={task}', number)
        scores[category] += 1
        current = incidents.get(number)
        categories = set(current[2]['categories']) if current else set()
        categories.add(category)
        # Store timestamps in the same local format as existing history rows.
        local_deadline = deadline.astimezone().replace(tzinfo=None).isoformat()
        if current is None or (deadline, sla) < current[0:2]:
            data = dict(number=number, url=url, deadline=local_deadline, sla=sla,
                        remaining=remaining.strip(), percent=percent)
            # The selection key uses UTC, including on a fall-back DST day.
            current = deadline, sla, data
            incidents[number] = current
        current[2]['categories'] = [key for key in KEYS if key in categories]
    return scores, {key: item[2] for key, item in incidents.items()}


def read_threats(page, stop, diagnostics, config, *, as_of=None):
    as_of = (as_of or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(microsecond=0)
    params = {'sysparm_query': build_query(config, as_of), 'sysparm_fields': ','.join(FIELDS),
              'sysparm_display_value': 'all', 'sysparm_exclude_reference_link': 'true',
              'sysparm_limit': str(PAGE_SIZE), 'sysparm_no_count': 'false'}
    rows, total, last_id = [], None, ''
    for page_number in range(1, MAX_PAGES + 1):
        offset = (page_number - 1) * PAGE_SIZE
        reply = get(page, stop, diagnostics, 'threatened', '/api/now/table/task_sla',
                    dict(params, sysparm_offset=str(offset)), ordinal=page_number)
        page_rows = reply['result']
        observed_total = count(reply.get('total'))
        if total is None:
            total = observed_total
        if (observed_total != total or total > PAGE_SIZE * MAX_PAGES
                or not isinstance(page_rows, list) or len(page_rows) != min(PAGE_SIZE, total - offset)
                or reply['next'] != (total > offset + PAGE_SIZE)):
            raise DashboardReadError('api_incomplete')
        for row in page_rows:
            key = field(row, 'sys_id') if isinstance(row, dict) else None
            if not isinstance(key, str) or not SYS_ID.fullmatch(key) or key.lower() <= last_id:
                raise DashboardReadError('api_incomplete')
            last_id = key.lower()
        rows.extend(page_rows)
        if not reply['next']:
            result = summarize(rows, as_of)
            measured_record(diagnostics, 'analytics_api_snapshot', api_target='threatened',
                            page_count=page_number, records_read=len(rows), outcome='returned')
            return result
    raise DashboardReadError('api_incomplete')
