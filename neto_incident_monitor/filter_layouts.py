"""Ordered ServiceNow column layouts shared across filters on one account."""
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from time import monotonic
from xml.etree import ElementTree
from playwright._impl._errors import TargetClosedError
from playwright.sync_api import Error

from neto_incident_monitor.analytics_api import list_layout, ORIGIN
from neto_incident_monitor.browser_actions import checkpoint
from neto_incident_monitor.dashboard import measured_record
from neto_incident_monitor.dashboard_context import DashboardReadError
from neto_incident_monitor.filter_metadata import VIEW_NAME
from neto_incident_monitor.read_errors import AuthenticationRequired, Cancelled
from neto_incident_monitor.service_now_urls import RECORD_TABLES


MAX_LAYOUT_BYTES = 512 * 1024
DEFAULT_LAYOUT_PREFIXES = ('INC', 'REQ', 'RITM', 'SCTASK')
FIELD = re.compile(r'[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*')
ACCOUNT_ID = re.compile(r'[0-9a-fA-F]{32}')
LANGUAGE_TAG = re.compile(r'[a-zA-Z]{2,8}(?:-[a-zA-Z0-9]{1,8}){0,4}')
STABLE_FIELDS = {
    'number': ('number',), 'short_description': ('short_description',), 'priority': ('priority',),
    'location': ('location',), 'created': ('sys_created_on',), 'updated': ('sys_updated_on',),
    'state': ('state', 'incident_state', 'request_state'), 'caller': ('caller_id',),
    'requested_for': ('requested_for', 'request.requested_for', 'request_item.request.requested_for'),
    'opened_by': ('opened_by',), 'assigned_to': ('assigned_to',), 'description': ('description',),
    'parent_incident': ('parent_incident', 'parent'), 'configuration_item': ('cmdb_ci',),
    'assignment_group': ('assignment_group',),
}
RELATED_FIELDS = {'opened_by': 'request.opened_by', 'state': 'request_item.state'}


@dataclass(frozen=True)
class LayoutAccount:
    key: str
    language: str


def read_account(page, stop):
    checkpoint(stop)
    try:
        facts = page.evaluate("""origin => {
            if (location.origin !== origin || !window.g_ck) return null;
            return [window.NOW?.user?.userID ?? null, document.documentElement.lang];
        }""", ORIGIN)
    except TargetClosedError:
        raise
    except Error:
        return None
    checkpoint(stop)
    if isinstance(facts, list) and len(facts) == 2:
        account, language = facts
        if (isinstance(account, str) and ACCOUNT_ID.fullmatch(account) and int(account, 16)
                and isinstance(language, str) and LANGUAGE_TAG.fullmatch(language)):
            return LayoutAccount(sha256(f'{ORIGIN}:{account.lower()}'.encode()).hexdigest(), language.lower())
    return None


def parse_layout(body):
    if (not isinstance(body, str) or len(body.encode('utf-8', errors='replace')) > MAX_LAYOUT_BYTES
            or re.search(r'<!\s*(?:DOCTYPE|ENTITY)', body, re.IGNORECASE)):
        raise DashboardReadError('filter_definition_columns', retryable=False)
    try:
        root = ElementTree.fromstring(body)
        [operation] = root.findall('xml')
        if (root.tag != 'xml' or root.get('sysparm_processor') != 'AJAXXMLHttpAggregator'
                or operation.get('sysparm_processor') != 'UIPage' or operation.get('sysparm_name') != 'getList'
                or operation.get('sysparm_processor_index') != '0' or operation.get('status') != '200'):
            raise ValueError('Unexpected operation')
        [choices] = operation.findall('choice_list_set')
        [selected] = choices.findall('selected')
        personal = choices.get('user_list')
        if not 1 <= len(selected) <= 256 or personal not in ('true', 'false'):
            raise ValueError('Incomplete layout')
        fields = {}
        for choice in selected:
            field, label = choice.get('value'), choice.get('label')
            if (choice.tag != 'choice' or field is None or not FIELD.fullmatch(field)
                    or field in fields or len(field) > 256 or not label or not label.strip() or len(label) > 512):
                raise ValueError('Invalid column')
            fields[field] = ' '.join(label.split())
    except (ElementTree.ParseError, ValueError):
        raise DashboardReadError('filter_definition_columns', retryable=False) from None
    aliases = {}
    for key, names in STABLE_FIELDS.items():
        field = next((field for field in fields if field in names), None)
        if field is None and RELATED_FIELDS.get(key) in fields:
            field = RELATED_FIELDS[key]
        if field and field != 'request_state':
            aliases[field] = key
    columns = [dict(field=field, label=label, key=aliases.get(field, 'sn:' + field))
               for field, label in fields.items()]
    return columns, personal == 'true'


class LayoutStore:
    """Single writer on the session thread, retaining the last complete snapshot."""
    def __init__(self, path):
        self.path = path
        self.entries = None

    def load(self):
        from neto_incident_monitor.config_io import read_json
        from neto_incident_monitor.data_reset import reject_redirect

        if self.entries is None:
            try:
                reject_redirect(self.path)
                settings = read_json(self.path, {})
                data = settings.get('layouts') if settings.get('version') == 1 else None
                self.entries = data if isinstance(data, dict) else {}
            except (OSError, ValueError, AttributeError):
                self.entries = {}
        return self.entries

    def snapshot(self):
        # The worker replaces entries on save. A reader can keep that complete
        # version and initialize its own view if the worker has yet to load it.
        snapshot = LayoutStore(self.path)
        snapshot.entries = self.entries
        return snapshot

    @staticmethod
    def key(account, table, view):
        return ':'.join((account.key, table, view))

    def get(self, account, table, view):
        value = self.load().get(self.key(account, table, view))
        if not isinstance(value, dict) or value.get('language') != account.language:
            return None
        columns = value.get('columns')
        if not isinstance(columns, list) or not 1 <= len(columns) <= 256:
            return None
        fields, keys = set(), set()
        for column in columns:
            if not isinstance(column, dict):
                return None
            field, label, key = (column.get(name) for name in ('field', 'label', 'key'))
            if (not isinstance(field, str) or len(field) > 256 or not FIELD.fullmatch(field) or field in fields
                    or not isinstance(label, str) or not label.strip() or len(label) > 512
                    or not isinstance(key, str) or key not in (*STABLE_FIELDS, 'sn:' + field) or key in keys):
                return None
            fields.add(field)
            keys.add(key)
        return columns

    def save(self, account, table, view, columns):
        from neto_incident_monitor.config_io import save_json
        from neto_incident_monitor.data_reset import reject_redirect

        value = {'language': account.language, 'columns': columns,
                 'read_at': datetime.now(timezone.utc).isoformat()}
        entries = {**self.load(), self.key(account, table, view): value}
        try:
            reject_redirect(self.path)
            reject_redirect(self.path.with_suffix('.tmp'))
            save_json(self.path, {'version': 1, 'layouts': entries})
        except (OSError, ValueError):
            raise DashboardReadError('filter_layout_save', retryable=False) from None
        self.entries = entries


def fetch_layout(page, stop, diagnostics, table, view):
    if table not in RECORD_TABLES.values() or not VIEW_NAME.fullmatch(view):
        raise DashboardReadError('filter_layout_view', retryable=False)
    started = monotonic()
    facts = {'api_target': table, 'outcome': 'error'}
    try:
        columns, personal = parse_layout(list_layout(page, stop, diagnostics, table, view, MAX_LAYOUT_BYTES))
        if view != 'default' and not personal:
            fallback, _ = parse_layout(list_layout(page, stop, diagnostics, table, '', MAX_LAYOUT_BYTES))
            if [c['field'] for c in columns] == [c['field'] for c in fallback]:
                raise DashboardReadError('filter_layout_view', retryable=False)
        facts.update(outcome='returned', item_count=len(columns))
        return columns
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
        measured_record(diagnostics, 'filter_layout_read',
                        duration_ms=round((monotonic() - started) * 1000), **facts)
