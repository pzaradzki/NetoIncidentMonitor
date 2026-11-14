"""Read-only ServiceNow REST calls on the card owned by SharedSession."""
import re
from time import monotonic

from playwright.sync_api import TimeoutError

from neto_incident_monitor.authentication import authentication_required
from neto_incident_monitor.browser_actions import checkpoint, navigate_page
from neto_incident_monitor.dashboard import TITLES, measured_record, operation
from neto_incident_monitor.dashboard_context import DashboardReadError
from neto_incident_monitor.favorites import HOME
from neto_incident_monitor.pagination import AuthenticationRequired, Cancelled
from neto_incident_monitor.read_budget import remaining_ms
from neto_incident_monitor.service_now_urls import TENANT_HOST

ORIGIN = 'https://' + TENANT_HOST
STATS_TABLES = ('task_sla', 'incident_metric', 'sc_task')
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
}

READ = r"""async ({origin, route, params, timeout}) => {
    if (location.origin !== origin || typeof window.g_ck !== 'string' || !window.g_ck) {
        return {issue: 'document'};
    }
    const url = new URL(route, origin);
    url.search = new URLSearchParams(params);
    const signal = AbortSignal.timeout(timeout);
    let response;
    try {
        response = await fetch(url, {
            credentials: 'same-origin', redirect: 'manual', cache: 'no-store', signal,
            headers: {Accept: 'application/json', 'X-UserToken': window.g_ck},
        });
        if (response.type === 'opaqueredirect') return {issue: 'redirect'};
        const status = response.status;
        if (status !== 200) return {status};
        const payload = await response.json().catch(() => null);
        if (signal.aborted) return {status, issue: 'timeout'};
        if (!payload || payload.error || payload.status === 'failure' ||
            !Object.hasOwn(payload, 'result')) return {status, issue: 'schema'};
        return {status, result: payload.result, total: response.headers.get('X-Total-Count'),
            next: /rel\s*=\s*["']?next\b/i.test(response.headers.get('Link') ?? '')};
    } catch {
        return {issue: signal.aborted ? 'timeout' : 'network'};
    }
}"""


def get(page, stop, diagnostics, alias, route, params, *, ordinal=1):
    routes = tuple('/api/now/stats/' + table for table in STATS_TABLES)
    if route not in (*routes, '/api/now/table/task_sla'):
        raise ValueError('Unsupported analytics endpoint')
    checkpoint(stop)
    started = monotonic()
    timeout = remaining_ms(TIMEOUT_MS)
    operation('api_request')
    facts = {'api_target': alias, 'api_call': ordinal, 'timeout_ms': timeout, 'outcome': 'started'}
    measured_record(diagnostics, 'analytics_api_request', **facts)
    facts['outcome'] = 'error'
    try:
        arguments = {'origin': ORIGIN, 'route': route, 'params': params, 'timeout': timeout}
        reply = page.evaluate(READ, arguments)
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
            reply = page.evaluate(READ, arguments)
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
        if status == 429:
            # Another immediate attempt would ignore the server's rate limit.
            raise DashboardReadError('api_rate_limit', retryable=False)
        if issue in ('timeout', 'network') or status in (500, 502, 503, 504):
            raise DashboardReadError('api_' + issue if issue else 'api_service')
        if status != 200 or issue or 'result' not in reply or type(reply.get('next')) is not bool:
            raise DashboardReadError('api_schema' if status == 200 else 'api_http', retryable=False)
        facts['outcome'] = 'returned'
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
    totals = dict.fromkeys(TITLES, 0)
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


def read_counts(page, stop, diagnostics, alias, table, queries, completed):
    for ordinal, (title, query) in enumerate(queries.items(), 1):
        if title not in completed:
            result = stats(page, stop, diagnostics, alias, table, query, ordinal=ordinal)
            if not isinstance(result, dict) or not isinstance(result.get('stats'), dict):
                raise DashboardReadError('api_schema', retryable=False)
            completed[title] = count(result['stats'].get('count'))
    return dict(completed)
