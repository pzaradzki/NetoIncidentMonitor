import json
import queue
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from neto_incident_monitor.dashboard_context import DashboardReadError
from neto_incident_monitor.filter_api import FilterListLimitExceeded, read_filter_records
from neto_incident_monitor.filter_definition import ready_definition
from neto_incident_monitor.login_diagnostics import LoginDiagnostics
from neto_incident_monitor.read_errors import Cancelled
from tests.list_fixture import URL


def filter_definition(url):
    table = url.split('/')[-1].split('_list.do')[0]
    query = parse_qs(urlsplit(url).query, keep_blank_values=True).get('sysparm_query', ['active=true'])[0]
    return {'version': 1, 'source_url': url, 'instance': None, 'view': '',
            'query': query, 'table': table,
            'columns': [{'key': 'number', 'field': 'number', 'label': 'Numer'}]}


class FilterApiTests(unittest.TestCase):
    def test_ritm_workflow_column_can_be_unavailable_without_hiding_a_required_field(self):
        definition = dict(table='sc_req_item', query='number=RITM1', columns=[
            {'key': 'sn:cat_item.workflow', 'field': 'cat_item.workflow'},
            {'key': 'short_description', 'field': 'short_description'},
        ])
        row = {'number': 'RITM1', 'sys_id': '1' * 32, 'short_description': ''}
        page = Mock()
        page.evaluate.return_value = dict(status=200, result=[row], next=False, total='1')
        diagnostics = Mock()
        records = read_filter_records(page, threading.Event(), diagnostics, definition)
        self.assertEqual(records['RITM1']['_values'], {'short_description': ''})
        fields = page.evaluate.call_args.args[1]['params']['sysparm_fields'].split(',')
        self.assertIn('cat_item.workflow', fields)
        self.assertEqual(diagnostics.record.call_args.kwargs['optional_field_omissions'], 1)
        del row['short_description']
        with self.assertRaisesRegex(DashboardReadError, 'api_schema'):
            read_filter_records(page, threading.Event(), diagnostics, definition)

    def test_definition_is_bound_to_conditions_and_rejects_related_list_context(self):
        self.assertTrue(ready_definition(dict(url=URL, list_definition=filter_definition(URL))))
        self.assertFalse(ready_definition(dict(url=URL, list_definition=dict(filter_definition(URL), query=''))))
        related = URL + '&sysparm_fixed_query=state%3D1'
        self.assertFalse(ready_definition(dict(url=related, list_definition=filter_definition(related))))

    def test_table_errors_do_not_turn_into_empty_snapshots(self):
        definition = filter_definition('https://adeo.service-now.com/sc_task_list.do')
        args = (Mock(), threading.Event(), Mock(), definition)
        for status, error in ((403, 'api_access'), (429, 'api_rate_limit'), (414, 'api_http')):
            with self.subTest(status=status):
                args[0].evaluate.return_value = {'status': status}
                with self.assertRaisesRegex(DashboardReadError, error):
                    read_filter_records(*args)

    def test_all_record_tables_use_display_values_and_validated_links(self):
        tables = {'incident': 'INC', 'sc_request': 'REQ', 'sc_req_item': 'RITM', 'sc_task': 'SCTASK'}
        for table, prefix in tables.items():
            with self.subTest(table=table):
                page = Mock()
                definition = filter_definition(f'https://adeo.service-now.com/{table}_list.do')
                definition['columns'].append(
                    {'key': 'assigned_to', 'field': 'assigned_to', 'label': 'Przypisano'})
                number = prefix + '1234567'
                row = {'number': number, 'sys_id': '1' * 32,
                       'assigned_to': {'value': '2' * 32, 'display_value': 'Osoba testowa'}}
                if table == 'incident':
                    row['sys_created_on'] = {'value': '2026-01-01 12:00:00',
                                             'display_value': '01.01.2026 13:00:00'}
                page.evaluate.return_value = dict(status=200, result=[row], next=False, total='1')
                result = read_filter_records(page, threading.Event(), Mock(), definition)
                self.assertEqual(result[number]['assigned_to'], 'Osoba testowa')
                self.assertTrue(result[number]['url'].endswith(f'/{table}.do?sys_id=' + '1' * 32))
                self.assertEqual(page.evaluate.call_args.args[1]['route'], '/api/now/table/' + table)
                if table == 'incident':
                    self.assertEqual(result[number]['_created_utc'], '2026-01-01T12:00:00Z')

    def test_cancellation_after_response_rejects_snapshot(self):
        definition = filter_definition('https://adeo.service-now.com/sc_request_list.do')
        page, stop = Mock(), threading.Event()
        row = {'number': 'REQ1', 'sys_id': '1' * 32}

        def reply(*_):
            stop.set()
            return dict(status=200, result=[row], next=False, total='1')

        page.evaluate.side_effect = reply
        with self.assertRaises(Cancelled):
            read_filter_records(page, stop, Mock(), definition)
        page.evaluate.assert_called_once()

    def test_shared_filter_retries_once_after_recovering_session(self):
        from neto_incident_monitor.app import App
        from neto_incident_monitor.filter_layouts import LayoutAccount
        from neto_incident_monitor.filter_metadata import metadata_from_address
        from neto_incident_monitor.filter_state import FilterState
        from neto_incident_monitor.history import History
        from neto_incident_monitor.monitoring import Health, ReadPart

        url = 'https://adeo.service-now.com/sc_request_list.do?sysparm_query=active%3Dtrue'
        row = {'number': 'REQ1', 'sys_id': '1' * 32}
        later = {'number': 'REQ2', 'sys_id': '2' * 32}
        expired = dict(status=401)
        last = dict(status=200, result=[row, later], next=False, total='2')
        for response, expected in ((last, True), (expired, False)):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory:
                directory = Path(directory)
                app = App.__new__(App)
                app.events = queue.Queue()
                app.history = History(directory / 'history.json')
                entry = dict(metadata_from_address(url), source_url=url, version=2, account='a')
                app.filters = [{'name': 'Synthetic', 'url': url, 'list_definition': entry}]
                app.disabled_filter_urls = frozenset()
                app.filter_revisions = {url: object()}
                app.monitor_generation = object()
                app.browser_runtime = None
                part = ReadPart('filter', (url, app.filter_revisions[url]),
                                {'name': 'Synthetic', 'index': 1, 'resolved': url, 'scheduled': True})
                app.session = Mock(manual_filter_parts={url: part}, active_job=None, connected=True,
                                   legacy_membership=FilterState(directory / 'legacy.json'), health=Health(),
                                   layout_account=LayoutAccount('a', 'pl'), layout_generation=object())
                app.session.filter_layout.return_value = filter_definition(url)['columns']
                app.session.authenticate.return_value = True
                page = Mock()
                page.is_closed.return_value = False
                page.evaluate.side_effect = [expired, response]
                stop = threading.Event()
                self.assertEqual(app.execute_session_part(page, part, stop, 'manual'), expected)
                app.session.authenticate.assert_called_once_with(page, stop)
                self.assertEqual(page.evaluate.call_count, 2)
                self.assertEqual(page.evaluate.call_args_list[0], page.evaluate.call_args_list[1])
                self.assertEqual(set(app.history.snapshot(url)), {'REQ1', 'REQ2'} if expected else set())
                if not expected:
                    self.assertFalse(app.session.connected)

    def test_preserves_query_groups_and_reads_1000_records_with_one_request(self):
        url = 'https://adeo.service-now.com/sc_req_item_list.do'
        definition = filter_definition(url)
        definition['query'] = 'active=true^ORpriority=2^NQstate=1^ORDERBYDESCnumber^EQ'
        rows = [{'number': f'RITM{i}', 'sys_id': f'{i:032x}'} for i in range(1000, 0, -1)]
        with patch('neto_incident_monitor.filter_api.get',
                   return_value={'total': '1000', 'next': False, 'result': rows}) as get:
            records = read_filter_records(Mock(), threading.Event(), Mock(), definition)
        self.assertEqual(list(records), [row['number'] for row in rows])
        get.assert_called_once()
        params = get.call_args.args[5]
        self.assertEqual(params['sysparm_limit'], '1000')
        self.assertNotIn('sysparm_offset', params)
        self.assertEqual(params['sysparm_query'], 'active=true^ORpriority=2^NQstate=1^ORDERBYDESCnumber^ORDERBYsys_id')

    def test_request_state_preserves_existing_template_field(self):
        definition = filter_definition('https://adeo.service-now.com/sc_request_list.do')
        definition['columns'].append({'key': 'sn:request_state', 'label': 'Stan', 'field': 'request_state'})
        page = Mock()
        row = dict(number='REQ1', sys_id='1' * 32, request_state={'display_value': 'W trakcie', 'value': '2'})
        page.evaluate.return_value = dict(status=200, result=[row], next=False, total='1')
        record = read_filter_records(page, threading.Event(), Mock(), definition)['REQ1']
        self.assertEqual(record['state'], 'W trakcie')
        self.assertEqual(record['_values']['sn:request_state'], 'W trakcie')

    def test_short_page_is_incomplete_and_confirmed_zero_is_empty(self):
        definition = filter_definition('https://adeo.service-now.com/sc_request_list.do')
        args = (Mock(), threading.Event(), Mock(), definition)
        with patch('neto_incident_monitor.filter_api.get', return_value={'total': '1', 'next': False, 'result': []}):
            with self.assertRaisesRegex(DashboardReadError, 'api_incomplete'):
                read_filter_records(*args)
        with patch('neto_incident_monitor.filter_api.get', return_value={'total': '0', 'next': False, 'result': []}):
            self.assertEqual(read_filter_records(*args), {})

    def test_duplicate_records_next_page_and_wrong_record_type_are_incomplete(self):
        definition = filter_definition('https://adeo.service-now.com/sc_request_list.do')
        row = {'number': 'REQ1', 'sys_id': '1' * 32}
        other = {'number': 'REQ2', 'sys_id': '2' * 32}
        for reply in (dict(result=[row, row], next=False, total='2'),
                      dict(result=[row, other], next=True, total='2'),
                      dict(result=[dict(other, number='INC2')], next=False, total='1')):
            with self.subTest(reply=reply), \
                    patch('neto_incident_monitor.filter_api.get', return_value=reply):
                with self.assertRaisesRegex(DashboardReadError, 'api_incomplete'):
                    read_filter_records(Mock(), threading.Event(), Mock(), definition)

    def test_missing_field_rejects_result_instead_of_returning_blank_value(self):
        definition = filter_definition('https://adeo.service-now.com/incident_list.do')
        row = {'number': 'INC1', 'sys_id': '1' * 32}
        with patch('neto_incident_monitor.filter_api.get', return_value={'total': '1', 'next': False, 'result': [row]}):
            with self.assertRaisesRegex(DashboardReadError, 'api_schema'):
                read_filter_records(Mock(), threading.Event(), Mock(), definition)

    def test_failed_page_keeps_safe_counts_and_correlation_in_diagnostics(self):
        definition = filter_definition('https://adeo.service-now.com/sc_task_list.do')
        definition['query'] = 'short_description=synthetic_private_condition'
        page = Mock()
        page.evaluate.return_value = dict(status=200, result=[], next=False, total='2')
        with self.assertLogs('neto.login_diagnostics', level='INFO') as captured:
            log = LoginDiagnostics(source='filter_read', request_id=7)
            with self.assertRaisesRegex(DashboardReadError, 'api_incomplete'):
                read_filter_records(page, threading.Event(), log, definition)
        self.assertNotIn('synthetic_private_condition', '\n'.join(captured.output))
        rows = [json.loads(record.getMessage()) for record in captured.records]
        page_log = next(row for row in rows if row['event'] == 'filter_api_page')
        self.assertEqual((page_log['request_id'], page_log['api_target'], page_log['outcome'],
                          page_log['total_rows'], page_log['row_count'], page_log['page_size'],
                          page_log['api_list_check']), (7, 'sc_task', 'error', 2, 0, 1000, 'record_count'))

    def test_large_lists_are_rejected_after_one_request(self):
        definition = filter_definition('https://adeo.service-now.com/sc_task_list.do')
        for count in (1001, 6817, 80000):
            with self.subTest(count=count), patch('neto_incident_monitor.filter_api.get', return_value={
                'total': str(count), 'next': True, 'result': [{}] * 1000,
            }) as get:
                with self.assertRaises(FilterListLimitExceeded) as rejected:
                    read_filter_records(Mock(), threading.Event(), Mock(), definition)
                self.assertEqual(rejected.exception.total, count)
                self.assertFalse(rejected.exception.retryable)
                get.assert_called_once()

    def test_only_complete_api_reads_commit_history_and_alert_with_hidden_field(self):
        from neto_incident_monitor.app import App
        from neto_incident_monitor.filter_state import FilterState
        from neto_incident_monitor.history import History
        from neto_incident_monitor.monitoring import Health, ReadPart

        url = 'https://adeo.service-now.com/sc_task_list.do'
        definition = filter_definition(url)
        definition['columns'].append({'key': 'assigned_to', 'field': 'assigned_to', 'label': 'Przypisano'})
        with tempfile.TemporaryDirectory() as directory:
            history_path = Path(directory) / 'history.json'
            app = App.__new__(App)
            app.events = queue.Queue()
            app.browser_runtime = None
            app.disabled_filter_urls = frozenset()
            app.filters = [{'url': url, 'list_definition': definition, 'notification_templates': {
                'teams_webhook': {'template_id': 'synthetic-template'}}}]
            app.column_profiles = {url: {'visible': ['number']}}
            app.notification_library = {
                'synthetic-template': {'message': '{lista elementów}', 'item': '{number} {assigned_to}'}}
            app.history = History(history_path)
            app.alert_writer = Mock()
            app.submit_alert_delivery = Mock()
            app.alert_routes = Mock(return_value={'teams': ('synthetic-destination', None)})
            page = Mock()
            page.is_closed.return_value = False
            stop = threading.Event()
            membership = FilterState(history_path.with_name('seen.json'))
            health = Health()
            app.session = Mock()
            app.session.filter_is_current.return_value = True
            app.read_shared_filter_definition = Mock(return_value=definition)
            part = ReadPart('filter', (url, None))

            def read(result, total):
                page.evaluate.return_value = dict(status=200, result=result, next=False, total=str(total))
                return app.read_filter(page, url, 'Synthetic', 1, membership, health,
                                       {}, None, stop, part=part)

            first = dict(number='SCTASK1', sys_id='1' * 32, assigned_to='Synthetic first')
            second = dict(number='SCTASK2', sys_id='2' * 32, assigned_to='Synthetic second')
            self.assertEqual(read([first], 1), 'success')
            self.assertEqual(app.history.pending_alerts(), [])
            self.assertEqual(read([second], 2), 'error')
            page.evaluate.reset_mock()
            self.assertEqual(read([second], 1001), 'rejected')
            page.evaluate.assert_called_once()
            reopened = History(history_path)
            self.assertEqual(reopened.membership[url]['present'], ['SCTASK1'])
            self.assertEqual(set(reopened.snapshot(url)), {'SCTASK1'})
            self.assertEqual(reopened.pending_alerts(), [])
            self.assertEqual(read([first, second], 2), 'success')
            reopened = History(history_path)
            self.assertEqual(reopened.membership[url]['present'], ['SCTASK1', 'SCTASK2'])
            self.assertEqual(reopened.snapshot(url)['SCTASK2']['incident']['_values']['assigned_to'], 'Synthetic second')
            _, alert = reopened.pending_alerts()[0]
            self.assertEqual(alert['message'], 'SCTASK2 Synthetic second')
            app.submit_alert_delivery.assert_called_once()
