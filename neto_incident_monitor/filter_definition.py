"""Encoded query rules and compatibility for older saved filter definitions."""
import re
from urllib.parse import parse_qs, urlsplit

from neto_incident_monitor.service_now_urls import RECORD_TABLES, normalize_list_url
from neto_incident_monitor.dashboard_context import DashboardReadError

UNSUPPORTED_LIST_PARAMETERS = {
    'sysparm_fixed_query', 'sysparm_query_category', 'sysparm_query_no_domain',
    'sysparm_relationship', 'sysparm_relationship_id', 'sysparm_collection',
    'sysparm_collectionID', 'sysparm_collection_key', 'sysparm_collection_related_field',
    'sysparm_collection_related_file',
}
ORDER = re.compile(r'ORDERBY(DESC)?([a-zA-Z_][\w.]*)')
# ADEO advertises this catalog field in getList but may omit it from Table API.
OPTIONAL_LAYOUT_FIELDS = {'sc_req_item': frozenset({'cat_item.workflow'})}


def api_query(query):
    """Keep the verified list conditions and order, adding a unique tie-breaker."""
    terms = query.split('^') if query else []
    order = []
    while terms and (terms[-1] == 'EQ' or ORDER.fullmatch(terms[-1])):
        directive = terms.pop()
        if directive != 'EQ':
            order.append(directive)
    order.reverse()
    if not any(ORDER.fullmatch(directive)[2] == 'sys_id' for directive in order):
        order.append('ORDERBYsys_id')
    if any(not term or term in ('OR', 'NQ', 'EQ')
           or term.startswith(('ORDERBY', 'GROUPBY', 'RLQUERY', 'ENDRLQUERY'))
           or any(ord(char) < 32 or ord(char) == 127 for char in term) for term in terms):
        raise DashboardReadError('api_configuration', retryable=False)
    return '^'.join([*terms, *order]), order == ['ORDERBYsys_id']


def unsupported_context(parameters):
    return any(any(value for value in parameters.get(key, ())) for key in UNSUPPORTED_LIST_PARAMETERS)


def list_identity(url):
    try:
        address = urlsplit(normalize_list_url(url, allow_short=False))
    except ValueError:
        return None
    parameters = parse_qs(address.query, keep_blank_values=True)
    if unsupported_context(parameters):
        return None
    return address.path, parameters.get('sysparm_query'), parameters.get('sysparm_view')


def context_matches(queries, views, query, view):
    from neto_incident_monitor.list_context import compare_list_conditions
    return ((not queries or (len(set(queries)) == 1
             and compare_list_conditions(queries[0], query) != 'mismatch'))
            and (not views or set(views) in ({''}, {view})))


def valid_definition(value):
    if not isinstance(value, dict) or value.get('table') not in RECORD_TABLES.values():
        return False
    query, view, columns = (value.get(key) for key in ('query', 'view', 'columns'))
    if (not isinstance(query, str) or len(query) > 64_000
            or not isinstance(view, str) or len(view) > 256
            or not isinstance(columns, list) or not 1 <= len(columns) <= 256):
        return False
    return all(
        isinstance(column, dict)
        and isinstance(column.get('label'), str) and 0 < len(column['label']) <= 512
        and (column.get('field') is None or
             (isinstance(column['field'], str) and re.fullmatch(
                 r'[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*', column['field'])))
        for column in columns
    ) and any(column.get('field') == 'number' for column in columns)


def ready_definition(entry):
    definition = entry.get('list_definition')
    if not valid_definition(definition) or definition.get('version') != 1:
        return False
    columns = definition['columns']
    keys = [column.get('key') for column in columns]
    from neto_incident_monitor.service_now_urls import is_short_url

    url = entry['url']
    direct = list_identity(entry.get('resolved_list_url') if is_short_url(url) else url)
    if (direct is None or definition.get('source_url') != url
            or definition.get('instance') != entry.get('filter_instance')
            or not all(isinstance(key, str) and key and len(key) <= 512 for key in keys)
            or len(set(keys)) != len(keys) or not all(column.get('field') for column in columns)):
        return False
    path, queries, views = direct
    try:
        api_query(definition['query'])
    except DashboardReadError:
        return False
    return (path == f"/{definition['table']}_list.do"
            and context_matches(queries, views, definition['query'], definition['view']))
