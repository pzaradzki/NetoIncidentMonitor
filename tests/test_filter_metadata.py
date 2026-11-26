import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
import unittest
from unittest.mock import Mock, patch
from urllib.parse import quote, urlencode, urlsplit

from neto_incident_monitor.dashboard_context import DashboardReadError
from neto_incident_monitor.dynamic_columns import update_profile, load_profiles
from neto_incident_monitor.filter_api import read_filter_records
from neto_incident_monitor.filter_conditions import FilterConditionError, parse_query
from neto_incident_monitor.filter_definition import api_query
from neto_incident_monitor.filter_layouts import LayoutAccount, LayoutStore, fetch_layout, parse_layout
from neto_incident_monitor.filter_metadata import (
    discover_query, metadata_from_address, resolve_route_payload, saved_query, validate_fields,
)
from neto_incident_monitor.read_budget import BudgetExpired
from neto_incident_monitor.read_errors import AuthenticationRequired, Cancelled
from neto_incident_monitor.shared_session import SharedSession


ORIGIN = 'https://adeo.service-now.com'
DIRECT = ORIGIN + '/incident_list.do?sysparm_query=active%3Dtrue%5EORDERBYDESCopened_at'
SHORT = ORIGIN + '/now/nav/ui/classic/__tinyId__/synthetic_id_1234'
COLUMNS = [{'key': 'caller', 'label': 'Zgłaszający', 'field': 'caller_id'},
           {'key': 'created', 'label': 'Utworzono', 'field': 'sys_created_on'}]
LAYOUT = ('<xml sysparm_processor="AJAXXMLHttpAggregator"><xml status="200" '
          'sysparm_processor="UIPage" sysparm_name="getList" sysparm_processor_index="0">'
          '<choice_list_set user_list="false"><selected>'
          '<choice label="Zgłaszający" value="caller_id"/><choice label="Utworzono" value="sys_created_on"/>'
          '</selected></choice_list_set></xml></xml>')


class FilterMetadataTests(unittest.TestCase):
    def test_saved_layout_preview_scopes_account_language_and_default_view(self):
        with TemporaryDirectory() as folder:
            session = SharedSession(Mock(), Path(folder) / 'profile')
            path = Path(folder) / 'filter-layouts.json'
            store = LayoutStore(path)
            account = LayoutAccount('a', 'pl')
            store.save(account, 'incident', 'default', COLUMNS)
            store.save(account, 'sc_task', 'named_view', COLUMNS)
            store.save(LayoutAccount('b', 'pl'), 'sc_request', 'default', COLUMNS)
            session.layouts = LayoutStore(path)
            self.assertIsNone(session.saved_default_layouts())
            session.layout_account = account
            session.connected = True
            self.assertEqual(session.saved_default_layouts(), {
                'INC': (('Zgłaszający', 'caller_id'), ('Utworzono', 'sys_created_on')),
                'SCTASK': (), 'REQ': (), 'RITM': (),
            })
            self.assertIsNone(session.layouts.entries)
            session.layout_account = LayoutAccount('a', 'en')
            self.assertFalse(any(session.saved_default_layouts().values()))

    def test_default_layout_refresh_does_not_resume_on_a_different_account(self):
        from neto_incident_monitor.monitoring import ReadPart
        from neto_incident_monitor.read_errors import AuthenticationRequired, Cancelled

        session = SharedSession(Mock(), Path('unused'))
        session.active_job = Mock(id=17)
        account = session.layout_account = LayoutAccount('a', 'pl')
        part = ReadPart('default_layouts', account, {'requested_at': 1, 'completed': []})

        def authenticate(*_):
            session.layout_account = LayoutAccount('b', 'pl')
            return True

        with patch.object(session, 'update_layout_account'), \
                patch.object(session, 'filter_layout', side_effect=[COLUMNS, AuthenticationRequired()]) as read, \
                patch.object(session, 'authenticate', side_effect=authenticate) as restore:
            with self.assertRaises(Cancelled):
                session.refresh_default_layouts(Mock(), part, Event())
        restore.assert_called_once()
        self.assertEqual(read.call_count, 2)
        self.assertEqual(part.data['completed'], ['INC'])

    def test_address_preserves_order_and_rejects_unconfirmed_scope(self):
        self.assertEqual(metadata_from_address(DIRECT),
                         dict(table='incident', view='default', query='active=true^ORDERBYDESCopened_at'))
        for params in ('', 'sysparm_query=', 'sysparm_query=ORDERBYnumber', 'sysparm_query=invalid',
                       'sysparm_query=active=true&sysparm_fixed_query=state%3D2',
                       'sysparm_query=active=true&sysparm_query=active=false', 'sysparm_query=NQnumber=INC1'):
            with self.subTest(params=params), self.assertRaises(DashboardReadError):
                metadata_from_address(ORIGIN + '/incident_list.do?' + params)

    def test_shortcut_data_is_extracted_without_executing_scripts(self):
        statement = (r'''window.__initialRoutePayload = JSON.parse('{\x22__tinyId__\x22:\x22synthetic_id_1234\x22,'''
                     r'''\x22wasTinyURLResolved\x22:true,\x22params\x22:{\x22target\x22:'''
                     r'''\x22incident_list.do?sysparm_query=active%3Dtrue%5EORDERBYDESCopened_at\x22}}');''')
        html = f'<script>{statement}</script><script>window.__initialRoutePayload={{}};</script>'
        self.assertEqual(resolve_route_payload(SHORT, html), DIRECT)
        for malformed in (html + html, html.replace('true,', 'false,'), html.replace('synthetic_id', 'synthetic_no'),
                          html.replace('<script>', '<p>').replace('</script>', '</p>'),
                          html.replace('incident_list.do', '//elsewhere.invalid/incident_list.do')):
            with self.subTest(malformed=malformed), self.assertRaisesRegex(DashboardReadError, 'filter_short_link'):
                resolve_route_payload(SHORT, malformed)

    def test_saved_query_certifies_only_the_current_address_instance_and_account(self):
        definition = dict(metadata_from_address(DIRECT), version=2, source_url=DIRECT, instance='id', account='a')
        entry = dict(url=DIRECT, filter_instance='id', list_definition=definition)
        self.assertEqual(saved_query(entry, 'a'), definition)
        self.assertIsNone(saved_query(entry, 'b'))
        self.assertIsNone(saved_query(dict(entry, filter_instance='different'), 'a'))
        self.assertIsNone(saved_query(dict(entry, url=DIRECT + '&sysparm_view=other'), 'a'))

    def test_field_schema_follows_a_real_reference_type_and_rejects_unknown_fields(self):
        spec = {'incident': {'sys_id': {}, 'caller_id': {'type': 'reference', 'reference': 'sys_user'}},
                'sys_user': {'company': {}}}
        schemas = {}
        with patch('neto_incident_monitor.filter_conditions.field_metadata',
                   side_effect=lambda *args: {'columns': spec[args[-1]]}) as meta:
            validate_fields(Mock(), Event(), Mock(), dict(table='incident', query='caller_id.companyISNOTEMPTY'), schemas)
            for query in ('unknown=true', 'caller_id.wrong=true', 'sys_id.name=123'):
                with self.assertRaisesRegex(DashboardReadError, 'filter_query_scope'):
                    validate_fields(Mock(), Event(), Mock(), dict(table='incident', query=query), schemas)
            self.assertEqual([call.args[-1] for call in meta.call_args_list], ['incident', 'sys_user'])

    def test_catalog_predicates_check_each_use_and_reuse_metadata_across_tables(self):
        date_var, text_var, group = '1' * 32, '2' * 32, '3' * 32
        definitions = {date_var: '9', text_var: '6'}
        cache = {}
        date = 'variables.' + date_var + 'RELATIVELT@dayofweek@ago@'
        text = 'variables.' + text_var

        def catalog(*args):
            identifier = args[-1]
            if identifier not in definitions:
                raise DashboardReadError('filter_variable_missing', retryable=False)
            return dict(sys_id=identifier, type=definitions[identifier], active='true', cat_item='', variable_set=group)

        with patch('neto_incident_monitor.filter_conditions.field_metadata',
                   return_value={'columns': {'sys_id': {}, 'active': {}}}) as fields, \
             patch('neto_incident_monitor.filter_conditions.catalog_variable_metadata', side_effect=catalog) as read:
            for table, days in (('sc_task', 3), ('sc_req_item', 4), ('sc_task', 7)):
                query = f'active=true^{date}{days}^OR{text}ISNOTEMPTY^NQactive=false^{text}ISEMPTY'
                result = validate_fields(Mock(), Event(), Mock(), dict(table=table, query=query), cache)
                self.assertEqual(result['version'], 1)
            self.assertEqual([call.args[-1] for call in read.call_args_list], [date_var, text_var])
            self.assertEqual([call.args[-1] for call in fields.call_args_list], ['sc_task', 'sc_req_item'])
            failures = (
                ('incident', date + '3', 'filter_variable_context'),
                ('sc_task', date + '0', 'filter_condition_value'),
                ('sc_task', date.replace('@dayofweek@', '@hour@') + '3', 'filter_condition_value'),
                ('sc_task', date.replace(date_var, '4' * 32) + '3', 'filter_variable_missing'),
                ('sc_task', date + '3^ORDERBYvariables.' + date_var, 'filter_condition_operator'),
                ('sc_task', date + '3^ORvariables.' + date_var + 'ISEMPTY', 'filter_condition_operator'),
            )
            for table, condition, code in failures:
                with self.subTest(table=table, code=code), self.assertRaisesRegex(DashboardReadError, code):
                    validate_fields(Mock(), Event(), Mock(), dict(table=table, query=f'active=true^{condition}'), cache)

    def test_catalog_set_membership_is_required_for_an_explicit_item(self):
        variable, item, group = '1' * 32, '2' * 32, '3' * 32
        metadata = dict(table='sc_req_item', query=f'cat_item={item}^variables.{variable}ISEMPTY')
        with patch('neto_incident_monitor.filter_conditions.field_metadata',
                   return_value={'columns': {'cat_item': {}, 'sys_id': {}}}), \
             patch('neto_incident_monitor.filter_conditions.catalog_variable_metadata',
                   return_value=dict(sys_id=variable, type='6', active='true', cat_item='', variable_set=group)), \
             patch('neto_incident_monitor.filter_conditions.catalog_set_membership', side_effect=[False, True]) as membership:
            with self.assertRaisesRegex(DashboardReadError, 'filter_variable_context'):
                validate_fields(Mock(), Event(), Mock(), metadata, {})
            validate_fields(Mock(), Event(), Mock(), metadata, {})
            self.assertEqual([call.args[-2:] for call in membership.call_args_list], [(item, group)] * 2)

    def test_field_comparison_checks_both_operands_and_compatible_references(self):
        fields = {'sys_id': {}, 'caller_id': {'type': 'reference', 'reference': 'sys_user'},
                  'opened_by': {'type': 'reference', 'reference': {'table': 'sys_user'}},
                  'assignment_group': {'type': 'reference', 'reference': 'sys_user_group'}}
        with patch('neto_incident_monitor.filter_conditions.field_metadata', return_value={'columns': fields}):
            metadata = dict(table='incident', query='caller_idSAMEASopened_by^NQcaller_idNSAMEASopened_by')
            self.assertEqual(validate_fields(Mock(), Event(), Mock(), metadata, {})['version'], 1)
            for rhs, reason in [('unknown', 'filter_query_scope'), ('assignment_group', 'filter_condition_operator')]:
                with self.assertRaisesRegex(FilterConditionError, reason) as caught:
                    validate_fields(Mock(), Event(), Mock(), dict(metadata, query='caller_idSAMEAS' + rhs), {})
                self.assertEqual(caught.exception.field, 'caller_id')

    def test_stored_complex_definition_revalidates_at_expiry_without_losing_preview(self):
        query = 'active=true^variables.' + '1' * 32 + 'RELATIVELT@dayofweek@ago@4'
        url = ORIGIN + '/sc_task_list.do?' + urlencode(dict(sysparm_query=query))
        entry = dict(url=url, list_definition=dict(metadata_from_address(url), version=2, source_url=url,
                                                   instance=None, account='a'))
        self.assertIsNone(saved_query(entry, 'a'))
        self.assertEqual(saved_query(entry, 'a', for_display=True)['query'], query)
        entry['list_definition']['validation'] = {'version': 1, 'valid_until': 120}
        with patch('neto_incident_monitor.filter_metadata.time', return_value=100):
            self.assertEqual(saved_query(entry, 'a')['query'], query)
        with patch('neto_incident_monitor.filter_metadata.time', return_value=120):
            self.assertIsNone(saved_query(entry, 'a'))
            self.assertEqual(saved_query(entry, 'a', for_display=True)['query'], query)

    def test_parser_keeps_groups_and_sort_directives_distinct(self):
        conditions, ordering = parse_query('active=true^ORactive=false^NQnumberLIKEINC^EQ^ORDERBYDESCnumber')
        self.assertEqual([(x.join, x.group) for x in conditions], [(None, 0), ('OR', 0), ('NQ', 1)])
        self.assertEqual(ordering, ['number', 'sys_id'])

    def test_empty_incident_assignee_is_prepared_for_all_address_formats(self):
        raw = 'assigned_to=^active=true^ORassigned_to=^NQassigned_to=^ORDERBYDESCnumber^EQ'
        prepared = ('assigned_toISEMPTY^active=true^ORassigned_toISEMPTY^NQassigned_toISEMPTY'
                    '^ORDERBYDESCnumber^ORDERBYsys_id')
        target = 'incident_list.do?' + urlencode(dict(sysparm_query=raw))
        direct = ORIGIN + '/' + target
        wrapper = ORIGIN + '/now/nav/ui/classic/params/target/' + quote(target, safe='')
        payload = json.dumps({'__tinyId__': SHORT.rsplit('/', 1)[1], 'wasTinyURLResolved': True,
                              'params': {'target': target}})
        html = f"<script>window.__initialRoutePayload = JSON.parse('{payload}');</script>"
        self.assertEqual(api_query(raw, table='incident'), (prepared, False))
        self.assertEqual(api_query(prepared, table='incident'), (prepared, False))
        conditions, sort = parse_query(raw, table='incident')
        self.assertEqual([(item.operator, item.join, item.group) for item in conditions if item.field == 'assigned_to'],
                         [('ISEMPTY', None, 0), ('ISEMPTY', 'OR', 0), ('ISEMPTY', 'NQ', 1)])
        self.assertEqual(sort, ['number', 'sys_id'])

        def respond(_script, request):
            route = request['route']
            if route == urlsplit(SHORT).path:
                return {'status': 200, 'result': html}
            if route == '/api/now/ui/meta/incident':
                return {'status': 200, 'next': False,
                        'result': {'columns': {field: {} for field in ('assigned_to', 'active', 'number', 'sys_id')}}}
            self.assertEqual(route, '/api/now/table/incident')
            self.assertEqual(request['params']['sysparm_query'], prepared)
            return {'status': 200, 'next': False, 'result': [], 'total': '0'}

        for url in (direct, wrapper, SHORT):
            with self.subTest(url_kind=urlsplit(url).path):
                page, stop, log = Mock(), Event(), Mock()
                page.evaluate.side_effect = respond
                if url != SHORT:
                    self.assertEqual(metadata_from_address(url)['query'], raw)
                definition, resolved = discover_query(page, stop, log, {'url': url}, 'a', {})
                self.assertEqual(definition['query'], raw)
                self.assertEqual(read_filter_records(page, stop, log, dict(definition, columns=[])), {})
                entry = json.loads(json.dumps(dict(url=url, list_definition=definition, resolved_list_url=resolved)))
                self.assertEqual(saved_query(entry, 'a', for_display=True)['query'], raw)
                page.evaluate.reset_mock()
                self.assertEqual(read_filter_records(page, stop, log, dict(saved_query(entry, 'a'), columns=[])), {})
                page.evaluate.assert_called_once()

    def test_empty_assignment_alias_has_exact_field_operator_value_and_table_boundaries(self):
        unchanged = ('assigned_toISEMPTY', 'assigned_to=' + 'a' * 32, 'assigned_to=puste', 'assigned_to= ',
                     'short_descriptionLIKEassigned_to=')
        for query in unchanged:
            with self.subTest(query=query):
                facts = {}
                self.assertEqual(api_query(query, table='incident', facts=facts)[0], query + '^ORDERBYsys_id')
                self.assertEqual(facts, {})
                parse_query(query, table='incident')
        malformed = [('incident', query) for query in ('assigned_to!=', 'location=', 'caller_id.assigned_to=',
                                                       'GOTOassigned_to=')]
        malformed += [(table, 'assigned_to=') for table in ('sc_task', 'sc_request', 'sc_req_item', None)]
        for table, query in malformed:
            with self.subTest(table=table, query=query), self.assertRaisesRegex(FilterConditionError,
                                                                              'filter_condition_value'):
                parse_query(query, table=table)
        with self.assertRaisesRegex(FilterConditionError, 'filter_query_scope'):
            parse_query('ORassigned_to=', table='incident')

    def test_discovery_reports_the_first_invalid_condition_before_requesting_metadata(self):
        cases = (
            ('active=true^ORcaller_id=^NQlocationLIKE', 'filter_condition_value', 'caller_id'),
            ('active=true^NQlocationLIKE', 'filter_condition_value', 'location'),
            ('active=true^RLQUERYincident.parent,>=1^ENDRLQUERY', 'filter_condition_operator', None),
            ('active=true^unreadable', 'filter_query_scope', None),
            ('active=true^^locationLIKEExample', 'api_configuration', None),
        )
        for query, reason, field in cases:
            with self.subTest(query=query):
                target = 'incident_list.do?' + urlencode(dict(sysparm_query=query, sysparm_view='example'))
                url = ORIGIN + '/now/nav/ui/classic/params/target/' + quote(target, safe='')
                page = Mock()
                with self.assertRaises(FilterConditionError) as caught:
                    discover_query(page, Event(), Mock(), {'url': url}, 'account', {})
                error = caught.exception
                self.assertEqual((error.reason, error.field, error.table, error.view),
                                 (reason, field, 'incident', 'example'))
                self.assertFalse(error.retryable)
                page.evaluate.assert_not_called()
        conditions, _ = parse_query('assigned_toISEMPTY')
        self.assertEqual((conditions[0].field, conditions[0].operator), ('assigned_to', 'ISEMPTY'))

    def test_field_problem_reports_the_condition_with_the_original_table_and_view(self):
        fields = {'sys_id': {}, 'active': {}, 'assignment_group': {'type': 'reference', 'reference': 'sys_user_group'}}
        cases = (
            ('incident', 'active=true^ORunknown_field=example', 'filter_query_scope', 'unknown_field'),
            ('incident', 'assignment_group.unknown=example', 'filter_query_scope', 'assignment_group.unknown'),
            ('sc_task', 'activeRELATIVELT@dayofweek@ago@4', 'filter_condition_operator', 'active'),
        )
        with patch('neto_incident_monitor.filter_conditions.field_metadata', return_value={'columns': fields}):
            for table, query, reason, field in cases:
                with self.subTest(query=query):
                    with self.assertRaisesRegex(FilterConditionError, reason) as caught:
                        validate_fields(Mock(), Event(), Mock(), dict(table=table, query=query, view='named'), {})
                    self.assertEqual((caught.exception.field, caught.exception.table, caught.exception.view),
                                     (field, table, 'named'))

    def test_definition_transport_failures_and_cancellation_remain_separate_from_condition_errors(self):
        page, stop, diagnostics = Mock(), Event(), Mock()
        for response, reason in (({'status': 403}, 'api_access'), ({'issue': 'network'}, 'api_network'),
                                 ({'status': 200, 'result': {}}, 'api_schema'),
                                 ({'status': 200, 'result': {}, 'next': False}, 'filter_query_scope')):
            with self.subTest(reason=reason):
                page.evaluate.return_value = response
                with self.assertRaisesRegex(DashboardReadError, reason) as caught:
                    discover_query(page, stop, diagnostics, {'url': DIRECT}, 'account', {})
                self.assertNotIsInstance(caught.exception, FilterConditionError)
        page.evaluate.return_value = {'status': 401}
        with self.assertRaises(AuthenticationRequired):
            discover_query(page, stop, diagnostics, {'url': DIRECT}, 'account', {})
        page.evaluate.reset_mock()
        stop.set()
        with self.assertRaises(Cancelled):
            discover_query(page, stop, diagnostics, {'url': DIRECT}, 'account', {})
        page.evaluate.assert_not_called()

    def test_uncertified_directives_and_list_context_have_distinct_errors(self):
        with self.assertRaisesRegex(DashboardReadError, 'filter_context_unsupported'):
            metadata_from_address(DIRECT + '&sysparm_fixed_query=state%3D1')
        for query in ('123TEXTQUERY321=example', 'active=true^RLQUERYincident.parent,>=1^ENDRLQUERY'):
            with self.assertRaisesRegex(DashboardReadError, 'filter_condition_operator'):
                parse_query(query)

    def test_metadata_refusal_is_correlated_and_does_not_repeat_during_backoff(self):
        from neto_incident_monitor.login_diagnostics import LoginDiagnostics, _logger

        variable = 'a' * 32
        url = ORIGIN + '/sc_task_list.do?' + urlencode(dict(sysparm_query=f'variables.{variable}ISEMPTY'))
        page = Mock()
        cache = {}

        def respond(_script, request):
            if request['route'] == '/api/now/ui/meta/sc_task':
                return {'status': 200, 'result': {'columns': {'sys_id': {}}}, 'next': False}
            self.assertEqual(request['route'], '/api/now/table/item_option_new/' + variable)
            return {'status': 403}

        page.evaluate.side_effect = respond
        diagnostics = LoginDiagnostics(source='filter_read', request_id=17)
        with self.assertLogs(_logger, level='INFO') as captured:
            for fresh in (False, False, True):
                with self.assertRaisesRegex(DashboardReadError, 'filter_variable_access') as caught:
                    discover_query(page, Event(), diagnostics, {'url': url}, 'account', cache, fresh=fresh)
                self.assertNotIsInstance(caught.exception, FilterConditionError)
        routes = [call.args[1]['route'] for call in page.evaluate.call_args_list]
        self.assertEqual(routes.count('/api/now/table/item_option_new/' + variable), 1)
        records = [json.loads(record.getMessage()) for record in captured.records]
        results = [r for r in records if r['event'] == 'filter_condition_metadata'
                   and r.get('condition_kind') == 'catalog_variable']
        self.assertEqual([r['reused'] for r in results], [False, True, True])
        self.assertTrue(all(r['request_id'] == 17 and r['read_reason'] == 'filter_variable_access' for r in results))
        self.assertNotIn(variable, '\n'.join(captured.output))

    def test_validated_catalog_query_is_sent_in_full_and_the_saved_copy_needs_one_request(self):
        variable = '5' * 32
        query = f'active=true^variables.{variable}RELATIVELT@dayofweek@ago@4^ORDERBYDESCnumber'
        url = ORIGIN + '/sc_task_list.do?' + urlencode(dict(sysparm_query=query))
        page = Mock()

        def respond(_script, request):
            route = request['route']
            if route == '/api/now/ui/meta/sc_task':
                return {'status': 200, 'next': False, 'result': {'columns': {key: {} for key in ('sys_id', 'number', 'active')}}}
            if route == '/api/now/table/item_option_new/' + variable:
                return {'status': 200, 'next': False, 'result': dict(sys_id=variable, type='9', active='true',
                                                                    cat_item='6' * 32, variable_set='')}
            self.assertEqual(route, '/api/now/table/sc_task')
            self.assertEqual(request['params']['sysparm_query'], query + '^ORDERBYsys_id')
            return {'status': 200, 'next': False, 'result': [], 'total': '0'}

        page.evaluate.side_effect = respond
        log, stop = Mock(), Event()
        metadata, _ = discover_query(page, stop, log, {'url': url}, 'account', {})
        entry = {'url': url, 'list_definition': json.loads(json.dumps(metadata))}
        page.evaluate.reset_mock()
        saved = saved_query(entry, 'account')
        self.assertEqual(saved['query'], query)
        self.assertEqual(read_filter_records(page, stop, log, dict(saved, columns=[])), {})
        page.evaluate.assert_called_once()

    def test_layout_is_ordered_and_independent_of_hidden_required_fields(self):
        self.assertEqual(parse_layout(LAYOUT), (COLUMNS, False))
        profile = update_profile(None, COLUMNS)
        self.assertEqual(profile['visible'], ['caller', 'created'])
        self.assertEqual(load_profiles({DIRECT: profile})[DIRECT], profile)
        for malformed in (LAYOUT.replace('status="200"', 'status="403"'),
                          LAYOUT.replace('value="sys_created_on"', 'value="caller_id"'),
                          '<!DOCTYPE xml>' + LAYOUT):
            with self.assertRaisesRegex(DashboardReadError, 'filter_definition_columns'):
                parse_layout(malformed)

    def test_unconfirmed_named_layout_cannot_use_the_standard_layout_as_evidence(self):
        with patch('neto_incident_monitor.filter_layouts.list_layout', return_value=LAYOUT) as fetch:
            with self.assertRaisesRegex(DashboardReadError, 'filter_layout_view'):
                fetch_layout(Mock(), Event(), Mock(), 'incident', 'missing')
        self.assertEqual([call.args[-2] for call in fetch.call_args_list], ['missing', ''])

    def test_failed_refresh_preserves_last_layout_and_isolates_accounts_and_languages(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'filter-layouts.json'
            session = SharedSession(Mock(), Path(folder) / 'profile')
            session.layouts = LayoutStore(path)
            account = LayoutAccount('a', 'pl')
            session.layout_account = account
            diagnostics = Mock()
            session.layouts.save(account, 'incident', 'default', COLUMNS)
            session.layouts = LayoutStore(path)
            with patch('neto_incident_monitor.shared_session.fetch_layout', side_effect=DashboardReadError('api_access')) as fetch:
                with self.assertRaises(DashboardReadError):
                    session.filter_layout(Mock(), Event(), diagnostics, 'incident', 'default', refresh=True)
                self.assertEqual(session.filter_layout(Mock(), Event(), diagnostics, 'incident', 'default'), COLUMNS)
                fetch.assert_called_once()
            self.assertIsNone(session.layouts.get(LayoutAccount('b', 'pl'), 'incident', 'default'))
            self.assertIsNone(session.layouts.get(LayoutAccount('a', 'en'), 'incident', 'default'))

    def test_multiple_requests_for_the_same_layout_reuse_the_completed_refresh(self):
        with TemporaryDirectory() as folder:
            session = SharedSession(Mock(), Path(folder) / 'profile')
            session.layouts = LayoutStore(Path(folder) / 'filter-layouts.json')
            session.layout_account = LayoutAccount('a', 'pl')
            session.default_layouts.add('incident')
            with patch('neto_incident_monitor.shared_session.fetch_layout', return_value=COLUMNS) as fetch:
                for _ in range(2):
                    self.assertEqual(session.filter_layout(Mock(), Event(), Mock(), 'incident', 'default',
                                                           refresh=True, requested_at=1), COLUMNS)
                fetch.assert_called_once()
            self.assertNotIn('incident', session.default_layouts)

    def test_corrupt_cache_can_be_replaced_by_the_first_verified_layout(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'filter-layouts.json'
            path.write_text('invalid json', encoding='utf-8')
            account = LayoutAccount('a', 'pl')
            store = LayoutStore(path)
            self.assertIsNone(store.get(account, 'sc_task', 'default'))
            store.save(account, 'sc_task', 'default', COLUMNS)
            self.assertEqual(LayoutStore(path).get(account, 'sc_task', 'default'), COLUMNS)

    def test_prefetch_timeout_does_not_interrupt_the_browser_session(self):
        session = SharedSession(Mock(), Path('unused'))
        session.log = Mock()
        session.connected = True
        session.default_layouts.update(('incident', 'sc_task'))
        with patch.object(session, 'filter_layout', side_effect=BudgetExpired('synthetic')):
            session.prefetch_layout(Mock())
        self.assertTrue(session.connected)
        self.assertEqual(session.default_layouts, {'sc_task'})
        self.assertEqual(session.layout_attempts['incident', 'default'][1], 'api_timeout')

    def test_real_browser_transport_reads_metadata_and_records_without_navigating_the_list(self):
        from playwright.sync_api import sync_playwright
        from neto_incident_monitor.favorites import HOME

        requests = []
        short_path = urlsplit(SHORT).path
        target = DIRECT.removeprefix(ORIGIN + '/')
        payload = dict(__tinyId__='synthetic_id_1234', wasTinyURLResolved=True, params={'target': target})

        def respond(route):
            path = urlsplit(route.request.url).path
            requests.append((route.request.method, path))
            if path == '/now/sow/home':
                route.fulfill(content_type='text/html', body='<script>window.g_ck="synthetic";</script>')
            elif path == short_path:
                payload_literal = json.dumps(json.dumps(payload))
                route.fulfill(content_type='text/html',
                              body=f'<script>window.__initialRoutePayload=JSON.parse({payload_literal});</script>')
            elif path == '/api/now/ui/meta/incident':
                route.fulfill(json={'result': {'columns': {key: {} for key in ('sys_id', 'active', 'opened_at')}}})
            elif path == '/xmlhttp.do':
                route.fulfill(content_type='text/xml', body=LAYOUT)
            elif path == '/api/now/table/incident':
                route.fulfill(json={'result': []}, headers={'X-Total-Count': '0'})
            else:
                route.abort()

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.route('**/*', respond)
                page.goto(HOME)
                stop, log = Event(), Mock()
                metadata, direct = discover_query(page, stop, log, {'url': SHORT}, 'a', {})
                self.assertEqual(direct, DIRECT)
                columns = fetch_layout(page, stop, log, 'incident', 'default')
                self.assertEqual(columns, COLUMNS)
                self.assertEqual(read_filter_records(page, stop, log, dict(metadata, columns=columns)), {})
                self.assertEqual(requests, [('GET', '/now/sow/home'), ('GET', short_path),
                    ('GET', '/api/now/ui/meta/incident'), ('POST', '/xmlhttp.do'), ('GET', '/api/now/table/incident')])
                self.assertEqual(page.url, HOME)
                self.assertEqual(len(page.context.pages), 1)
            finally:
                browser.close()
