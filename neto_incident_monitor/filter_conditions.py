"""Validate encoded filter conditions without changing the submitted query."""
from dataclasses import dataclass
from itertools import groupby
import re
from time import monotonic, time

from neto_incident_monitor.analytics_api import catalog_set_membership, catalog_variable_metadata, field_metadata
from neto_incident_monitor.browser_actions import checkpoint
from neto_incident_monitor.dashboard import measured_record
from neto_incident_monitor.dashboard_context import DashboardReadError
from neto_incident_monitor.filter_definition import OPTIONAL_LAYOUT_FIELDS, ORDER, api_query
from neto_incident_monitor.read_errors import AuthenticationRequired, Cancelled


FIELD_PATH = r'[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)*'
IDENTIFIER = re.compile(r'[0-9a-f]{32}')
FIELD_COMPARISONS = {'SAMEAS', 'NSAMEAS'}
EMPTY_OPERATORS = {'ISEMPTYSTRING', 'ISEMPTY', 'ISNOTEMPTY', 'EMPTYSTRING'}
RELATIVE_OPERATORS = {'RELATIVEGT', 'RELATIVELT', 'RELATIVEGE', 'RELATIVELE'}
OPERATORS = EMPTY_OPERATORS | FIELD_COMPARISONS | RELATIVE_OPERATORS | {
    '!=', '>=', '<=', '=', '>', '<', 'NOT LIKE', 'NOT IN', 'LIKE', 'STARTSWITH', 'ENDSWITH',
    'IN', 'BETWEEN', 'DYNAMIC', 'ON', 'NOTON', 'INSTANCEOF',
}
TERM = re.compile(
    r'(?P<join>OR|NQ)?(?P<goto>GOTO)?(?P<field>variables\.[0-9a-f]{32}|' + FIELD_PATH + r')'
    r'(?P<operator>' + '|'.join(map(re.escape, sorted(OPERATORS, key=lambda value: (-len(value), value)))) + r')'
    r'(?P<argument>.*)', re.ASCII)
RELATIVE_ARGUMENT = re.compile(r'@(minute|hour|dayofweek|week|month|quarter|year)@(ago|ahead)@[1-9][0-9]{0,5}')
CATALOG_DATE_ARGUMENT = re.compile(r'@dayofweek@ago@[1-9][0-9]{0,5}')
CATALOG_OPERATORS = {'9': {'RELATIVELT'}, '6': {'ISEMPTY', 'ISNOTEMPTY'}}
CATALOG_ITEM_FIELDS = {'sc_task': 'request_item.cat_item', 'sc_req_item': 'cat_item'}
COMPARABLE_TYPES = {'boolean', 'choice', 'integer', 'string', 'reference'}
DATE_TYPES = {'glide_date', 'glide_date_time', 'calendar_date'}
METADATA_LIFETIME = 24 * 60 * 60
METADATA_BACKOFF = 60
VALIDATION_VERSION = 1
UNSUPPORTED_DIRECTIVES = ('123TEXTQUERY321', 'RLQUERY', 'ENDRLQUERY', 'GROUPBY')


@dataclass(frozen=True)
class Condition:
    field: str
    operator: str
    argument: str
    join: str | None
    goto: bool
    group: int

    @property
    def catalog(self):
        return self.field.startswith('variables.')


def condition_error(reason='filter_query_scope'):
    return DashboardReadError(reason, retryable=False)


def parse_query(query):
    if isinstance(query, str) and any(term.removeprefix('OR').removeprefix('NQ').startswith(UNSUPPORTED_DIRECTIVES)
                                      for term in query.split('^')):
        raise condition_error('filter_condition_operator')
    normalized, _ = api_query(query)
    conditions, sort_fields = [], []
    group = 0
    for term in normalized.split('^'):
        order = ORDER.fullmatch(term)
        if order:
            sort_fields.append(order[2])
            continue
        match = TERM.fullmatch(term)
        if not match or (not conditions and match['join']):
            raise condition_error()
        operator, argument = match['operator'], match['argument']
        expects_argument = operator not in EMPTY_OPERATORS
        if bool(argument) != expects_argument:
            raise condition_error('filter_condition_value')
        if operator in RELATIVE_OPERATORS and not RELATIVE_ARGUMENT.fullmatch(argument):
            raise condition_error('filter_condition_value')
        if operator in FIELD_COMPARISONS and not re.fullmatch(FIELD_PATH, argument):
            raise condition_error('filter_condition_value')
        if operator == 'DYNAMIC' and not IDENTIFIER.fullmatch(argument):
            raise condition_error('filter_condition_value')
        if match['join'] == 'NQ':
            group += 1
        conditions.append(Condition(match['field'], operator, argument, match['join'], bool(match['goto']), group))
    if not conditions:
        raise condition_error()
    return conditions, sort_fields


def requires_current_validation(conditions):
    return any(condition.catalog or condition.operator in FIELD_COMPARISONS | RELATIVE_OPERATORS
               for condition in conditions)


@dataclass(frozen=True)
class Field:
    type: str | None
    reference: str | None


@dataclass(frozen=True)
class Variable:
    type: str
    item: str | None
    variable_set: str | None


@dataclass(frozen=True)
class CachedMetadata:
    value: object
    valid_until: float
    error: str | None = None


def _field_schema(result):
    columns = result.get('columns') if isinstance(result, dict) else None
    if not isinstance(columns, dict) or not columns:
        raise condition_error()
    fields = {}
    for name, column in columns.items():
        if not isinstance(column, dict):
            continue
        reference = column.get('reference')
        if isinstance(reference, dict):
            reference = reference.get('table')
        kind = column.get('type')
        fields[name] = Field(kind if isinstance(kind, str) else None,
                             reference if isinstance(reference, str) else None)
    return fields


def _variable_definition(result, identifier):
    if not isinstance(result, dict) or result.get('sys_id') != identifier:
        raise condition_error('filter_variable_metadata')
    active, kind = result.get('active'), result.get('type')
    item, variable_set = result.get('cat_item'), result.get('variable_set')
    if active in ('false', False):
        raise condition_error('filter_variable_missing')
    if (active not in ('true', True) or not isinstance(kind, str)
            or not {'cat_item', 'variable_set'}.issubset(result)
            or any(value not in ('', None) and (not isinstance(value, str) or not IDENTIFIER.fullmatch(value))
                   for value in (item, variable_set))
            or not (item or variable_set)):
        raise condition_error('filter_variable_metadata')
    return Variable(kind, item or None, variable_set or None)


def _explicit_catalog_item(conditions, table):
    path = CATALOG_ITEM_FIELDS.get(table)
    if path is None or any(condition.join == 'OR' for condition in conditions):
        return None
    items = {condition.argument for condition in conditions if condition.field == path
             and condition.operator == '=' and IDENTIFIER.fullmatch(condition.argument)}
    return next(iter(items)) if len(items) == 1 else None


class ConditionValidator:
    def __init__(self, page, stop, diagnostics, cache, *, fresh=False):
        self.page = page
        self.stop = stop
        self.diagnostics = diagnostics
        self.cache = cache
        self.fresh = fresh
        self.used = set()
        self.valid_until = time() + METADATA_LIFETIME

    def lookup(self, key, fetch):
        checkpoint(self.stop)
        entry = self.cache.get(key)
        if key in self.used:
            return entry.value
        started = monotonic()
        reused = entry is not None and entry.valid_until > time() and (not self.fresh or entry.error is not None)
        facts = {'condition_kind': key[0], 'reused': reused, 'outcome': 'error'}
        try:
            if not reused:
                try:
                    value = fetch()
                except DashboardReadError as error:
                    reason = error.reason
                    if key[0] != 'field_schema':
                        reason = {'api_access': 'filter_variable_access',
                                  'api_schema': 'filter_variable_metadata'}.get(reason, reason)
                    self.cache[key] = CachedMetadata(None, time() + METADATA_BACKOFF, reason)
                    raise condition_error(reason) from None
                checkpoint(self.stop)
                entry = self.cache[key] = CachedMetadata(value, time() + METADATA_LIFETIME)
            if entry.error is not None:
                raise condition_error(entry.error)
            self.used.add(key)
            self.valid_until = min(self.valid_until, entry.valid_until)
            facts['outcome'] = 'returned'
            return entry.value
        except DashboardReadError as error:
            facts['read_reason'] = error.reason
            raise
        except AuthenticationRequired:
            facts.update(outcome='authentication', read_reason='authentication_required')
            raise
        except Cancelled:
            facts['outcome'] = 'cancelled'
            raise
        finally:
            measured_record(self.diagnostics, 'filter_condition_metadata',
                            duration_ms=round((monotonic() - started) * 1000), **facts)

    def field(self, table, path):
        chain = path.split('.')
        if (not re.fullmatch(FIELD_PATH, path) or len(chain) > 6 or path in OPTIONAL_LAYOUT_FIELDS.get(table, ())):
            raise condition_error()
        for index, segment in enumerate(chain):
            schema = self.lookup(('field_schema', table), lambda: _field_schema(
                field_metadata(self.page, self.stop, self.diagnostics, table)))
            field = schema.get(segment)
            if field is None:
                raise condition_error()
            if index == len(chain) - 1:
                return field
            if field.reference is None:
                raise condition_error()
            table = field.reference

    def catalog_condition(self, table, condition, item):
        if table not in CATALOG_ITEM_FIELDS:
            raise condition_error('filter_variable_context')
        identifier = condition.field.removeprefix('variables.')
        if not IDENTIFIER.fullmatch(identifier):
            raise condition_error('filter_condition_value')
        if condition.goto or condition.operator not in {'RELATIVELT', 'ISEMPTY', 'ISNOTEMPTY'}:
            raise condition_error('filter_condition_operator')
        variable = self.lookup(('catalog_variable', identifier), lambda: _variable_definition(
            catalog_variable_metadata(self.page, self.stop, self.diagnostics, identifier), identifier))
        if condition.operator not in CATALOG_OPERATORS.get(variable.type, ()):
            raise condition_error('filter_condition_operator')
        if condition.operator == 'RELATIVELT' and not CATALOG_DATE_ARGUMENT.fullmatch(condition.argument):
            raise condition_error('filter_condition_value')
        if item is not None and item != variable.item:
            if variable.variable_set is None or not self.lookup(('catalog_membership', item, variable.variable_set),
                    lambda: catalog_set_membership(self.page, self.stop, self.diagnostics, item, variable.variable_set)):
                raise condition_error('filter_variable_context')

    def validate(self, table, conditions, sort_fields):
        for field in dict.fromkeys(sort_fields):
            if field.startswith('variables.'):
                raise condition_error('filter_condition_operator')
            self.field(table, field)
        for _, branch in groupby(conditions, key=lambda condition: condition.group):
            conditions_in_group = list(branch)
            item = _explicit_catalog_item(conditions_in_group, table)
            for condition in conditions_in_group:
                if condition.catalog:
                    self.catalog_condition(table, condition, item)
                    continue
                left = self.field(table, condition.field)
                if condition.operator in FIELD_COMPARISONS:
                    right = self.field(table, condition.argument)
                    if (left.type not in COMPARABLE_TYPES or left.type != right.type
                            or left.type == 'reference' and (not left.reference or left.reference != right.reference)):
                        raise condition_error('filter_condition_operator')
                elif condition.operator == 'DYNAMIC' and left.type not in {'reference', 'glide_list'}:
                    raise condition_error('filter_condition_operator')
                elif condition.operator in RELATIVE_OPERATORS and left.type not in DATE_TYPES:
                    raise condition_error('filter_condition_operator')
