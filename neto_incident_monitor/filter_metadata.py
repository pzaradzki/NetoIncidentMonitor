"""Recognize ServiceNow list addresses without rendering the classic list."""
from html.parser import HTMLParser
import json
import re
from time import monotonic, time
from urllib.parse import parse_qs, urlsplit

from neto_incident_monitor.analytics_api import short_link
from neto_incident_monitor.dashboard import measured_record
from neto_incident_monitor.dashboard_context import DashboardReadError
from neto_incident_monitor.filter_conditions import (
    METADATA_LIFETIME, VALIDATION_VERSION, ConditionValidator, FilterConditionError, parse_query,
    requires_current_validation,
)
from neto_incident_monitor.filter_definition import unsupported_context
from neto_incident_monitor.read_errors import AuthenticationRequired, Cancelled
from neto_incident_monitor.service_now_urls import TENANT_HOST, is_short_url, normalize_list_url


MAX_ROUTE_BYTES = 2 * 1024 * 1024
ROUTE_PAYLOAD = re.compile(
    r'''(?m)^\s*window\.__initialRoutePayload\s*=\s*JSON\.parse\(\s*(?P<quote>['"])'''
    r'''(?P<data>(?:(?!(?P=quote))[^\\\r\n]|\\[^\r\n])*)(?P=quote)\s*\)\s*;''')
ESCAPE = re.compile(r'\\(?:u([0-9a-fA-F]{4})|x([0-9a-fA-F]{2})|(.))')
ESCAPES = {'\\': '\\', '"': '"', "'": "'", '/': '/', 'b': '\b', 'f': '\f', 'n': '\n', 'r': '\r', 't': '\t'}
LIST_PARAMETERS = {'sysparm_query', 'sysparm_view', 'sysparm_first_row', 'sysparm_clear_stack',
                   'sysparm_stack', 'sysparm_view_forced'}
VIEW_NAME = re.compile(r'[a-zA-Z0-9_.-]{1,128}')


def _error(reason):
    return DashboardReadError(reason, retryable=False)


class _InlineScripts(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.payloads = []
        self.inline_script = False

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            self.inline_script = not any(name == 'src' for name, _ in attrs)

    def handle_endtag(self, tag):
        if tag == 'script':
            self.inline_script = False

    def handle_data(self, data):
        if self.inline_script:
            self.payloads.extend(match['data'] for match in ROUTE_PAYLOAD.finditer(data))


def _decode_escape(match):
    unicode_hex, byte_hex, symbol = match.groups()
    if unicode_hex or byte_hex:
        return chr(int(unicode_hex or byte_hex, 16))
    return ESCAPES[symbol]


def _unique_json_object(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError('Duplicate route key')
    return result


def resolve_route_payload(address, html):
    if (not is_short_url(address) or not isinstance(html, str) or
            len(html.encode('utf-8', errors='replace')) > MAX_ROUTE_BYTES):
        raise _error('filter_short_link')
    scripts = _InlineScripts()
    try:
        scripts.feed(html)
        if len(scripts.payloads) != 1:
            raise ValueError('Ambiguous route data')
        payload = json.loads(ESCAPE.sub(_decode_escape, scripts.payloads[0]),
                             object_pairs_hook=_unique_json_object)
        if (payload['__tinyId__'] != urlsplit(address).path.rsplit('/', 1)[1]
                or payload['wasTinyURLResolved'] is not True):
            raise ValueError('Unresolved route')
        target = payload['params']['target']
        if not isinstance(target, str) or not target or target.startswith('//'):
            raise ValueError('Invalid route target')
        if not urlsplit(target).scheme:
            target = 'https://' + TENANT_HOST + '/' + target.lstrip('/')
        return normalize_list_url(target, allow_short=False)
    except (ValueError, AttributeError, TypeError, KeyError, RecursionError):
        raise _error('filter_short_link') from None


def metadata_from_address(address, *, validate_syntax=True):
    try:
        direct = normalize_list_url(address, allow_short=False)
    except ValueError:
        raise _error('filter_query_scope') from None
    parsed = urlsplit(direct)
    params = parse_qs(parsed.query, keep_blank_values=True)
    [queries, views] = [params.get(name, []) for name in ('sysparm_query', 'sysparm_view')]
    if set(params) - LIST_PARAMETERS or unsupported_context(params):
        raise _error('filter_context_unsupported')
    if len(queries) != 1 or len(views) > 1:
        raise _error('filter_query_scope')
    query = queries[0]
    view = (views[0] if views else '') or 'default'
    if not VIEW_NAME.fullmatch(view):
        raise _error('filter_layout_view')
    table = parsed.path[1:-len('_list.do')]
    if validate_syntax:
        parse_query(query, table=table)
    return {'table': table, 'view': view, 'query': query}


def saved_query(entry, account=None, *, for_display=False):
    saved = entry.get('list_definition')
    if not isinstance(saved, dict) or saved.get('version') != 2:
        return None
    address = entry['url']
    if (saved.get('source_url') != address or saved.get('instance') != entry.get('filter_instance')
            or saved.get('account') != account or account is None):
        return None
    direct = entry.get('resolved_list_url') if is_short_url(address) else address
    try:
        metadata = metadata_from_address(direct, validate_syntax=False)
        conditions = None if for_display else parse_query(metadata['query'], table=metadata['table'])[0]
    except DashboardReadError:
        return None
    if not all(saved.get(key) == value for key, value in metadata.items()):
        return None
    if conditions is not None and requires_current_validation(conditions):
        validation = saved.get('validation')
        if (not isinstance(validation, dict) or type(validation.get('version')) is not int
                or validation['version'] != VALIDATION_VERSION):
            return None
        expiry = validation.get('valid_until')
        now = time()
        if type(expiry) not in (int, float) or not now < expiry <= now + METADATA_LIFETIME:
            return None
    return saved


def discover_query(page, stop, diagnostics, entry, account, schemas, *, fresh=False):
    address = entry['url']
    direct = address
    started = monotonic()
    facts = {'outcome': 'error', 'filter_url_kind': 'short' if is_short_url(address) else 'direct'}
    try:
        if facts['filter_url_kind'] == 'short':
            direct = resolve_route_payload(address, short_link(page, stop, diagnostics, address, MAX_ROUTE_BYTES))
        metadata = metadata_from_address(direct, validate_syntax=False)
        facts['api_target'] = metadata['table']
        validation = validate_fields(page, stop, diagnostics, metadata, schemas, fresh=fresh)
        if validation is not None:
            metadata['validation'] = validation
        facts['outcome'] = 'returned'
        return dict(metadata, version=2, source_url=address,
                    instance=entry.get('filter_instance'), account=account), direct
    except DashboardReadError as error:
        facts['read_reason'] = error.reason
        raise
    except Cancelled:
        facts['outcome'] = 'cancelled'
        raise
    except AuthenticationRequired:
        facts.update(outcome='authentication', read_reason='authentication_required')
        raise
    finally:
        measured_record(diagnostics, 'filter_definition_discovery',
                        duration_ms=round((monotonic() - started) * 1000), **facts)


def validate_fields(page, stop, diagnostics, metadata, schemas, *, fresh=False):
    """Check field paths against the table schema instead of trusting ignored conditions."""
    try:
        conditions, sort_fields = parse_query(metadata['query'], table=metadata['table'])
        validator = ConditionValidator(page, stop, diagnostics, schemas, fresh=fresh)
        validator.validate(metadata['table'], conditions, sort_fields)
    except FilterConditionError as error:
        error.table, error.view = metadata['table'], metadata.get('view')
        raise
    if requires_current_validation(conditions):
        return {'version': VALIDATION_VERSION, 'valid_until': validator.valid_until}
