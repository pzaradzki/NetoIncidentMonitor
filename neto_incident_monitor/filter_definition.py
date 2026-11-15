"""Persisted metadata from a verified ServiceNow list read."""
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


# Keep stable column keys across the API migration.
METADATA = r"""table => {
  const visible = el => !!(el.getClientRects().length &&
    getComputedStyle(el).visibility !== 'hidden');
  const fieldName = th => (th.getAttribute('glide_field') || th.getAttribute('name') || th.getAttribute('data-name') || (/^(Numer|Number)$/i.test(th.textContent.trim()) ? 'number' : th.textContent.trim())).replace(/^(?:incident|sc_task|sc_request|sc_req_item)\./, '');
  const fieldLabel = th => (th.getAttribute('glide_label') || th.querySelector('a.column_head')?.textContent || th.textContent).trim();
  const headerRows = new Set(Array.from(table.querySelectorAll('th'), th => th.parentElement)
    .filter(tr => tr.closest('table') === table && visible(tr)
      && !tr.classList.contains('list_header_search_row')));
  const candidates = Array.from(headerRows, tr => Array.from(tr.cells).filter(th => th.tagName === 'TH' && visible(th)
    && !th.classList.contains('col-control') && !th.classList.contains('list-decoration-table')
    && !th.querySelector('input, select, textarea, button, .list_header_search_toggle')
    && !!fieldName(th)));
  const marked = candidates.filter(cells => cells.some(th => th.hasAttribute('glide_field')));
  const eligible = (marked.length ? marked : candidates).filter(cells => cells.some(th => fieldName(th) === 'number'));
  if (!eligible.length) return null;
  if (eligible.length !== 1) throw new Error('Ambiguous ServiceNow column headers');
  const headers = eligible[0].filter(th => !marked.length || th.hasAttribute('glide_field'));
  const header = headers.find(th => {
    const name = fieldName(th);
    return /^(?:(?:incident|sc_task|sc_request|sc_req_item)\.)?number$/.test(name) || /^(Numer|Number)$/i.test(th.innerText.trim());
  });
  if (!header) return null;
  const column = (names, labels) => headers.find(th => {
    const name = fieldName(th);
    return names.includes(name);
  }) || headers.find(th => labels.includes(th.innerText.trim().toLowerCase()));
  const fields = {
    short_description: column(['short_description'], ['krótki opis', 'short description']),
    priority: column(['priority'], ['priorytet', 'priority']),
    location: column(['location'], ['lokalizacja', 'location']),
    created: column(['sys_created_on'], ['utworzono', 'created']),
    updated: column(['sys_updated_on'], ['zaktualizowano', 'updated']),
    state: column(['state', 'incident_state', 'request_state'], ['stan', 'state']),
    caller: column(['caller_id'], ['zgłaszający', 'caller']),
    requested_for: column(['requested_for', 'request.requested_for', 'request_item.request.requested_for'], ['wnioskowane dla', 'requested for']),
    opened_by: column(['opened_by'], ['otwarte przez', 'opened by']),
    assigned_to: column(['assigned_to'], ['przypisane do', 'assigned to']),
    description: column(['description'], ['opis', 'description']),
    parent_incident: column(['parent_incident', 'parent'], ['incydent nadrzędny', 'parent incident']),
    configuration_item: column(['cmdb_ci'], ['objęty element konfiguracji', 'element konfiguracji', 'configuration item']),
    assignment_group: column(['assignment_group'], ['grupa przypisania', 'assignment group'])
  };
  const used = new Map();
  const schema = headers.map(th => {
    const label = fieldLabel(th).replace(/\s+/g, ' ').trim();
    const raw = fieldName(th);
    const known = th === header ? 'number' : Object.keys(fields).find(key => fields[key] === th);
    const base = raw === 'request_state' ? 'sn:request_state' : known || 'sn:' + raw;
    const occurrence = used.get(base) || 0;
    used.set(base, occurrence + 1);
    const field = (th.getAttribute('glide_field') || th.getAttribute('name') || th.getAttribute('data-name') || '')
      .replace(/^(?:incident|sc_task|sc_request|sc_req_item)[.]/, '');
    return {
      key: base + (occurrence ? ':' + occurrence : ''),
      label: label || raw,
      field: /^[A-Za-z0-9_]+(?:[.][A-Za-z0-9_]+)*$/.test(field) ? field : null,
    };
  });
  return {
    schema,
    query: table.getAttribute('query'),
    busy: table.getAttribute('aria-busy') === 'true'
  };
}"""


def read_list_headers(target):
    from neto_incident_monitor.read_budget import remaining_ms
    return target.table.evaluate(METADATA, timeout=remaining_ms(1000))


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


def discover_definition(page, entry, stop, navigate, authenticate, diagnostics=None):
    from time import monotonic
    from neto_incident_monitor.browser_actions import checkpoint
    from neto_incident_monitor.dashboard import measured_record
    from neto_incident_monitor.list_context import ListTarget, ListStateError, compare_list_conditions
    from neto_incident_monitor.read_errors import AuthenticationRequired
    from neto_incident_monitor.read_budget import remaining_ms
    from neto_incident_monitor.service_now_urls import is_short_url, resolved_list_url

    address = entry['url']
    if not is_short_url(address) and list_identity(address) is None:
        raise DashboardReadError('api_configuration', retryable=False)
    navigate(page, address, stop)
    deadline = monotonic() + remaining_ms(12000) / 1000
    while monotonic() < deadline:
        checkpoint(stop)
        if authenticate(page, address):
            raise AuthenticationRequired()
        try:
            direct = resolved_list_url(page, address) if is_short_url(address) else address
        except ValueError:
            raise DashboardReadError('api_filter_mismatch', retryable=False) from None
        if direct:
            identity = list_identity(direct)
            if identity is None:
                raise DashboardReadError('api_configuration', retryable=False)
            try:
                target = ListTarget.find(page, direct)
            except ListStateError as error:
                raise DashboardReadError('api_configuration', retryable=False) from error
            if target is not None:
                schema = read_list_headers(target)
                if schema is not None and schema['query'] is not None and not schema['busy']:
                    path, requested, views = identity
                    observed = parse_qs(urlsplit(target.frame.url).query, keep_blank_values=True)
                    if unsupported_context(observed):
                        raise DashboardReadError('api_configuration', retryable=False)
                    view = observed.get('sysparm_view', [''])
                    if diagnostics is not None and requested:
                        comparison = compare_list_conditions(requested[0], schema['query'])
                        measured_record(diagnostics, 'filter_query_comparison', query_comparison=comparison,
                                        query_alias='last_7_days' if comparison == 'known_alias' else 'none')
                    if (len(set(view)) != 1 or not context_matches(requested, views, schema['query'], view[0])):
                        raise DashboardReadError('api_filter_mismatch', retryable=False)
                    definition = dict(version=1, source_url=address, instance=entry.get('filter_instance'),
                                      table=path[1:-len('_list.do')], query=schema['query'],
                                      view=view[0], columns=schema['schema'])
                    if not valid_definition(definition) or any(
                            not column.get('field') for column in definition['columns']):
                        raise DashboardReadError('filter_definition_columns', retryable=False)
                    if ready_definition(dict(entry, list_definition=definition, resolved_list_url=direct)):
                        return definition, direct
                    raise DashboardReadError('api_configuration', retryable=False)
        page.wait_for_timeout(150)
    raise DashboardReadError('api_document')
