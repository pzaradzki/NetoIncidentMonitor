"""Read-only ServiceNow REST calls on the card owned by SharedSession."""
import re
from contextlib import contextmanager
from contextvars import ContextVar
from time import monotonic
from urllib.parse import urlsplit

from playwright.sync_api import TimeoutError

from neto_incident_monitor.authentication import authentication_required
from neto_incident_monitor.browser_actions import checkpoint, navigate_page
from neto_incident_monitor.dashboard import MONTHLY_TITLES, measured_record, operation
from neto_incident_monitor.dashboard_context import DashboardReadError
from neto_incident_monitor.favorites import HOME
from neto_incident_monitor.read_errors import AuthenticationRequired, Cancelled
from neto_incident_monitor.read_budget import remaining_ms
from neto_incident_monitor.service_now_urls import RECORD_TABLES, TENANT_HOST, is_short_url

ORIGIN = 'https://' + TENANT_HOST
STATS_TABLES = ('task_sla', 'incident_metric', 'sc_task', 'incident')
TABLE_ROUTES = tuple('/api/now/table/' + table for table in ('task_sla', *RECORD_TABLES.values()))
FAVORITES_ROUTE = '/api/now/ui/navigator/favorites'
TIMEOUT_MS = 5000
READ_MESSAGES = {
    'api_configuration': 'Brak poprawnej lokalnej konfiguracji API.',
    'api_document': 'Strona ServiceNow nie udostępniła kontekstu API.',
    'api_access': 'ServiceNow odmówił dostępu.',
    'api_rate_limit': 'ServiceNow ograniczył liczbę żądań.',
    'api_timeout': 'Upłynął limit czasu odpowiedzi API.',
    'api_network': 'Brak połączenia z API ServiceNow.',
    'api_service': 'API ServiceNow jest chwilowo niedostępne.',
    'api_http': 'ServiceNow odrzucił zapytanie API.',
    'api_incomplete': 'API zwróciło niepełną listę.',
    'api_schema': 'API zwróciło dane w nieoczekiwanym formacie.',
    'api_filter_mismatch': 'API zwróciło dane poza zakresem filtra.',
    'filter_definition_save': 'Nie udało się zapisać definicji filtra.',
    'filter_definition_columns': 'Nie udało się rozpoznać wszystkich kolumn listy ServiceNow.',
    'filter_short_link': 'Nie udało się rozwinąć skrótu. Użyj pełnego adresu listy w ServiceNow.',
    'filter_query_scope': 'Nie udało się ustalić pełnych warunków. Użyj adresu listy z jawnym zapytaniem.',
    'filter_condition_operator': 'Warunek filtra używa operatora nieobsługiwanego dla tego pola.',
    'filter_condition_value': 'Warunek filtra zawiera niepoprawną wartość lub ścieżkę pola.',
    'filter_context_unsupported': 'Adres wskazuje dodatkowy kontekst listy, którego aplikacja nie może potwierdzić.',
    'filter_variable_missing': 'ServiceNow nie udostępniło wskazanej zmiennej katalogowej.',
    'filter_variable_access': 'Brak dostępu do metadanych zmiennej katalogowej.',
    'filter_variable_metadata': 'ServiceNow zwróciło niepełną definicję zmiennej katalogowej.',
    'filter_variable_context': 'Zmienna katalogowa nie pasuje do tabeli lub formularza wskazanego przez filtr.',
    'filter_layout_view': 'Nie udało się potwierdzić widoku listy ServiceNow.',
    'filter_layout_account': 'Nie udało się ustalić konta dla układu kolumn ServiceNow.',
    'filter_layout_save': 'Nie udało się zapisać układu kolumn ServiceNow.',
}

_data_times = ContextVar('data_request_times', default=None)


@contextmanager
def measure_data_requests():
    times = {}
    token = _data_times.set(times)
    try:
        yield times
    finally:
        _data_times.reset(token)


def data_duration(times):
    return round(sum(times.values())) if times and all(value is not None for value in times.values()) else None


READ = r"""async ({origin, route, params, timeout}) => {
    if (location.origin !== origin || typeof window.g_ck !== 'string' || !window.g_ck) {
        return {issue: 'document'};
    }
    const url = new URL(route, origin);
    url.search = new URLSearchParams(params);
    const signal = AbortSignal.timeout(timeout);
    let response;
    try {
        const started = performance.now();
        response = await fetch(url, {
            credentials: 'same-origin', redirect: 'manual', cache: 'no-store', signal,
            headers: {Accept: 'application/json', 'X-UserToken': window.g_ck},
        });
        if (response.type === 'opaqueredirect') return {issue: 'redirect'};
        const status = response.status;
        if (status !== 200) return {status};
        const body = await response.text();
        const elapsedMs = performance.now() - started;
        let payload;
        try { payload = JSON.parse(body); } catch { payload = null; }
        if (signal.aborted) return {status, issue: 'timeout'};
        if (!payload || payload.error || payload.status === 'failure' ||
            !Object.hasOwn(payload, 'result')) return {status, issue: 'schema'};
        return {status, result: payload.result, total: response.headers.get('X-Total-Count'), elapsedMs,
            next: /rel\s*=\s*["']?next\b/i.test(response.headers.get('Link') ?? '')};
    } catch {
        return {issue: signal.aborted ? 'timeout' : 'network'};
    }
}"""


READ_METADATA = r"""async ({origin, route, params, timeout, method, maxBytes, mime}) => {
    if (location.origin !== origin || typeof window.g_ck !== 'string' || !window.g_ck) {
        return {issue: 'document'};
    }
    const signal = AbortSignal.timeout(timeout);
    try {
        const response = await fetch(new URL(route, origin), {
            method, credentials: 'same-origin', redirect: 'manual', cache: 'no-store', signal,
            headers: {Accept: mime.join(', '), 'X-UserToken': window.g_ck},
            body: method === 'POST' ? new URLSearchParams(params) : undefined,
        });
        if (response.type === 'opaqueredirect') return {issue: 'redirect'};
        const status = response.status;
        if (status !== 200) return {status};
        const contentType = response.headers.get('Content-Type')?.split(';', 1)[0].trim().toLowerCase();
        if (!mime.includes(contentType) || !response.body) return {status, issue: 'schema'};
        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8', {fatal: true});
        let size = 0;
        const chunks = [];
        for (;;) {
            const {value, done} = await reader.read();
            if (done) break;
            size += value.byteLength;
            if (size > maxBytes) {
                await reader.cancel();
                return {status, issue: 'schema'};
            }
            try { chunks.push(decoder.decode(value, {stream: true})); }
            catch { return {status, issue: 'schema'}; }
        }
        try { chunks.push(decoder.decode()); }
        catch { return {status, issue: 'schema'}; }
        return {status, result: chunks.join('')};
    } catch {
        return {issue: signal.aborted ? 'timeout' : 'network'};
    }
}"""


def get(page, stop, diagnostics, alias, route, params, *, ordinal=1):
    routes = tuple('/api/now/stats/' + table for table in STATS_TABLES)
    if route == FAVORITES_ROUTE:
        if params:
            raise ValueError('Favorites endpoint does not accept parameters')
    elif route not in (*routes, *TABLE_ROUTES):
        raise ValueError('Unsupported analytics endpoint')
    return _request(page, stop, diagnostics, alias, route, params, ordinal=ordinal)


def short_link(page, stop, diagnostics, address, max_bytes):
    if not is_short_url(address):
        raise DashboardReadError('filter_short_link', retryable=False)
    return _request(page, stop, diagnostics, 'filter_short_link', urlsplit(address).path, {},
                    document={'method': 'GET', 'mime': ['text/html'], 'maxBytes': max_bytes})['result']


def list_layout(page, stop, diagnostics, table, view, max_bytes):
    if table not in RECORD_TABLES.values() or not re.fullmatch(r'[a-zA-Z0-9_.-]{0,128}', view):
        raise DashboardReadError('filter_layout_view', retryable=False)
    params = {'sysparm_processor': 'AJAXXMLHttpAggregator', 'sysparm_scope': 'global',
              'sysparm_aggregation_size': '1', '0.sysparm_processor': 'UIPage',
              '0.sysparm_scope': 'global', '0.sysparm_name': 'getList',
              '0.sysparm_table': table, '0.sysparm_list_view': view, '0.sysparm_list_parent': '',
              '0.sysparm_list_parent_id': '', '0.sysparm_list_relationship': ''}
    return _request(page, stop, diagnostics, 'filter_layout', '/xmlhttp.do', params,
                    document={'method': 'POST', 'mime': ['text/xml', 'application/xml'],
                              'maxBytes': max_bytes})['result']


def field_metadata(page, stop, diagnostics, table):
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,95}', table):
        raise DashboardReadError('filter_query_scope', retryable=False)
    return _request(page, stop, diagnostics, 'filter_fields', '/api/now/ui/meta/' + table, {})['result']


def catalog_variable_metadata(page, stop, diagnostics, identifier):
    if not re.fullmatch(r'[0-9a-f]{32}', identifier):
        raise DashboardReadError('filter_condition_value', retryable=False)
    params = {'sysparm_fields': 'sys_id,type,cat_item,variable_set,active',
              'sysparm_exclude_reference_link': 'true', 'sysparm_display_value': 'false'}
    return _request(page, stop, diagnostics, 'filter_variable', '/api/now/table/item_option_new/' + identifier,
                    params, missing='filter_variable_missing')['result']


def catalog_set_membership(page, stop, diagnostics, item, variable_set):
    if not all(re.fullmatch(r'[0-9a-f]{32}', value) for value in (item, variable_set)):
        raise DashboardReadError('filter_condition_value', retryable=False)
    params = {'sysparm_query': f'sc_cat_item={item}^variable_set={variable_set}',
              'sysparm_fields': 'sc_cat_item,variable_set', 'sysparm_limit': '2',
              'sysparm_exclude_reference_link': 'true', 'sysparm_display_value': 'false',
              'sysparm_no_count': 'false'}
    reply = _request(page, stop, diagnostics, 'filter_variable_membership', '/api/now/table/io_set_item', params)
    rows = reply['result']
    if (reply['next'] or not isinstance(rows, list) or len(rows) != count(reply.get('total')) or
            len(rows) > 1 or any(not isinstance(row, dict) or row.get('sc_cat_item') != item
                                 or row.get('variable_set') != variable_set for row in rows)):
        raise DashboardReadError('filter_variable_metadata', retryable=False)
    return bool(rows)


def _request(page, stop, diagnostics, alias, route, params, *, ordinal=1, document=None, missing=None):
    checkpoint(stop)
    started = monotonic()
    timeout = remaining_ms(TIMEOUT_MS)
    operation('api_request')
    facts = {'api_target': alias, 'api_call': ordinal, 'timeout_ms': timeout, 'outcome': 'started'}
    measured_record(diagnostics, 'analytics_api_request', **facts)
    facts['outcome'] = 'error'
    try:
        arguments = {'origin': ORIGIN, 'route': route, 'params': params, 'timeout': timeout}
        script = READ
        if document is not None:
            script = READ_METADATA
            arguments.update(document)
        reply = page.evaluate(script, arguments)
        checkpoint(stop)
        if isinstance(reply, dict) and reply.get('issue') == 'document':
            operation('api_document')
            if authentication_required(page, HOME):
                raise AuthenticationRequired()
            navigate_page(page, HOME, stop)
            try:
                page.wait_for_function(
                    'origin => location.origin === origin && typeof window.g_ck === "string" && !!window.g_ck',
                    arg=ORIGIN, timeout=remaining_ms(1800))
            except TimeoutError:
                if authentication_required(page, HOME):
                    raise AuthenticationRequired() from None
                raise DashboardReadError('api_document') from None
            checkpoint(stop)
            operation('api_request')
            arguments['timeout'] = remaining_ms(TIMEOUT_MS)
            reply = page.evaluate(script, arguments)
            checkpoint(stop)
            if isinstance(reply, dict) and reply.get('issue') == 'document':
                if authentication_required(page, HOME):
                    raise AuthenticationRequired()
                raise DashboardReadError('api_document')
        if not isinstance(reply, dict):
            raise DashboardReadError('api_schema', retryable=False)
        status, issue = reply.get('status'), reply.get('issue')
        facts['http_status'] = status
        if status == 401 or issue == 'redirect':
            raise AuthenticationRequired()
        if status == 403:
            raise DashboardReadError('api_access', retryable=False)
        if status == 404 and missing is not None:
            raise DashboardReadError(missing, retryable=False)
        if status == 429:
            # Another immediate attempt would ignore the server's rate limit.
            raise DashboardReadError('api_rate_limit', retryable=False)
        if issue in ('timeout', 'network') or status in (500, 502, 503, 504):
            raise DashboardReadError('api_' + issue if issue else 'api_service')
        valid = (isinstance(reply.get('result'), str) if document is not None
                 else 'result' in reply and type(reply.get('next')) is bool)
        if status != 200 or issue or not valid:
            raise DashboardReadError('api_schema' if status == 200 else 'api_http', retryable=False)
        facts['outcome'] = 'returned'
        times = _data_times.get()
        if document is None:
            elapsed = reply.get('elapsedMs')
            elapsed = elapsed if type(elapsed) in (int, float) and 0 <= elapsed <= timeout + 1000 else None
            if elapsed is not None:
                facts['api_data_ms'] = round(elapsed)
            if times is not None:
                times[alias, ordinal] = elapsed
        return reply
    except AuthenticationRequired:
        facts.update(outcome='authentication', read_reason='authentication_required')
        raise
    except Cancelled:
        facts['outcome'] = 'cancelled'
        raise
    except DashboardReadError as exc:
        facts['read_reason'] = exc.reason
        raise
    finally:
        measured_record(diagnostics, 'analytics_api_request',
                        duration_ms=round((monotonic() - started) * 1000), **facts)


def count(value):
    if isinstance(value, str) and re.fullmatch(r'[0-9]{1,16}', value):
        value = int(value)
    if type(value) is not int or not 0 <= value <= 2**53 - 1:
        raise DashboardReadError('api_schema', retryable=False)
    return value


def stats(page, stop, diagnostics, alias, table, query, *, group=None, ordinal=1):
    params = {'sysparm_count': 'true', 'sysparm_query': query}
    if group:
        params['sysparm_group_by'] = group
    reply = get(page, stop, diagnostics, alias, '/api/now/stats/' + table, params, ordinal=ordinal)
    if reply['next']:
        raise DashboardReadError('api_incomplete', retryable=False)
    return reply['result']


def summarize_month(result):
    if not isinstance(result, list):
        raise DashboardReadError('api_schema', retryable=False)
    totals = dict.fromkeys(MONTHLY_TITLES, 0)
    seen = set()
    for row in result:
        try:
            fields = row['groupby_fields']
            if not isinstance(fields, list) or len(fields) != 2:
                raise TypeError
            grouped = {field['field']: field['value'] for field in fields}
            priority, breached = grouped['task.priority'], grouped['has_breached']
            records = count(row['stats']['count'])
        except (KeyError, TypeError) as exc:
            raise DashboardReadError('api_schema', retryable=False) from exc
        if (len(grouped) != 2
                or not isinstance(priority, str) or not re.fullmatch(r'[0-9]*', priority)
                or breached not in ('true', 'false') or not records or (priority, breached) in seen):
            raise DashboardReadError('api_schema', retryable=False)
        seen.add((priority, breached))
        totals['Liczba zgłoszeń'] += records
        if priority in ('1', '2', '3', '4', '5'):
            totals[f'Zgłoszenia P{priority}'] += records
            if breached == 'true':
                totals[f'Przekroczone P{priority}'] += records
    return totals


def read_count(page, stop, diagnostics, alias, table, query, *, ordinal):
    result = stats(page, stop, diagnostics, alias, table, query, ordinal=ordinal)
    if not isinstance(result, dict) or not isinstance(result.get('stats'), dict):
        raise DashboardReadError('api_schema', retryable=False)
    return count(result['stats'].get('count'))


def read_counts(page, stop, diagnostics, alias, table, queries, completed, *, start=1):
    for ordinal, (title, query) in enumerate(queries.items(), start):
        if title not in completed:
            completed[title] = read_count(page, stop, diagnostics, alias, table, query, ordinal=ordinal)
    return dict(completed)
