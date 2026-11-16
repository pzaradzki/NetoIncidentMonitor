"""Build complete filter snapshots through ServiceNow Table API."""
import re

from neto_incident_monitor.analytics_api import count, get
from neto_incident_monitor.browser_actions import checkpoint
from neto_incident_monitor.dashboard import measured_record
from neto_incident_monitor.dashboard_context import DashboardReadError
from neto_incident_monitor.filter_definition import OPTIONAL_LAYOUT_FIELDS, api_query
from neto_incident_monitor.service_now_urls import RECORD_TABLES, TENANT_HOST, safe_record_url

MAX_FILTER_RECORDS = 1000
MAX_READ_SECONDS = 1800
SYS_ID = re.compile(r'[0-9a-fA-F]{32}')
NUMBER_PATTERNS = {table: re.compile(prefix + r'[0-9]{1,20}') for prefix, table in RECORD_TABLES.items()}


class FilterListLimitExceeded(DashboardReadError):
    def __init__(self, total):
        super().__init__('api_filter_limit', retryable=False)
        self.total = total


def extract_value(row, field, *, display=False):
    value = row.get(field)
    if isinstance(value, dict):
        key = 'display_value' if display else 'value'
        if key not in value:
            raise DashboardReadError('api_schema', retryable=False)
        value = value[key]
    if value is None or type(value) in (str, int, float, bool):
        return value
    raise DashboardReadError('api_schema', retryable=False)


def read_filter_records(page, stop, diagnostics, definition):
    table = definition['table']
    columns = {column['key']: column['field'] for column in definition['columns']}
    fields = set(columns.values()) | {'sys_id', 'number'}
    if table == 'incident':
        fields.add('sys_created_on')
    required = fields - OPTIONAL_LAYOUT_FIELDS.get(table, frozenset())
    query, ordered_by_id = api_query(definition['query'])
    # Keep the whole source view so hidden columns remain usable in history and templates.
    params = {'sysparm_query': query,
              'sysparm_fields': ','.join(sorted(fields)), 'sysparm_display_value': 'all',
              'sysparm_exclude_reference_link': 'true', 'sysparm_no_count': 'false',
              'sysparm_limit': str(MAX_FILTER_RECORDS), 'sysparm_suppress_pagination_header': 'false'}
    reply = get(page, stop, diagnostics, table, '/api/now/table/' + table, params)
    rows = reply['result']
    facts = dict(api_target=table, page_index=1, page_size=MAX_FILTER_RECORDS, api_has_next=reply['next'])
    issue = 'total'
    try:
        total = facts['total_rows'] = count(reply.get('total'))
        issue = 'shape'
        if not isinstance(rows, list):
            raise DashboardReadError('api_schema', retryable=False)
        facts['row_count'] = len(rows)
        issue = 'limit'
        if total > MAX_FILTER_RECORDS:
            raise FilterListLimitExceeded(total)
        issue = 'record_count' if len(rows) != total else 'next_page'
        if len(rows) != total or reply['next']:
            raise DashboardReadError('api_incomplete', retryable=False)
        incidents, seen_ids, last_id = {}, set(), ''
        facts['optional_field_omissions'] = 0
        for row in rows:
            issue = 'fields'
            if not isinstance(row, dict) or not required.issubset(row):
                raise DashboardReadError('api_schema', retryable=False)
            record_id, number = extract_value(row, 'sys_id'), extract_value(row, 'number')
            issue = 'record_identity'
            if (not isinstance(record_id, str) or not SYS_ID.fullmatch(record_id)
                    or record_id.lower() in seen_ids
                    or (ordered_by_id and record_id.lower() <= last_id)
                    or not isinstance(number, str)
                    or not NUMBER_PATTERNS[table].fullmatch(number) or number in incidents):
                raise DashboardReadError('api_incomplete', retryable=False)
            last_id = record_id.lower()
            seen_ids.add(last_id)
            issue = 'fields'
            values = {}
            for key, field in columns.items():
                if field not in row:
                    facts['optional_field_omissions'] += 1
                    continue
                value = extract_value(row, field, display=True)
                values[key] = ' '.join(str(value).split()) if value is not None else ''
            url = safe_record_url(f'https://{TENANT_HOST}/{table}.do?sys_id={record_id}', number)
            if not url:
                raise DashboardReadError('api_schema', retryable=False)
            record = dict(values, number=number, url=url, _values=values,
                          summary=values.get('short_description') or number)
            if table == 'sc_request' and 'state' not in record and 'sn:request_state' in values:
                record['state'] = values['sn:request_state']
            if table == 'incident':
                raw_created = extract_value(row, 'sys_created_on')
                if isinstance(raw_created, str) and re.fullmatch(
                        r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', raw_created):
                    record['_created_utc'] = raw_created.replace(' ', 'T') + 'Z'
                # Preserve the displayed date when an existing view contains it.
                if not values.get('created'):
                    display_created = extract_value(row, 'sys_created_on', display=True)
                    record['created'] = display_created or record.get('_created_utc', '')
            incidents[number] = record
        checkpoint(stop)
    except DashboardReadError as error:
        measured_record(diagnostics, 'filter_api_page', outcome='error', api_list_check=issue,
                        read_reason=error.reason, **facts)
        raise
    measured_record(diagnostics, 'filter_api_page', outcome='returned', records_read=len(incidents), **facts)
    return incidents
