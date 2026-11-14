import threading
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from neto_incident_monitor.analytics_api import ORIGIN, get, read_counts, summarize_month
from neto_incident_monitor.analytics_config import monthly_query, request_queries
from neto_incident_monitor.dashboard_api import read_held, read_month, read_requests
from neto_incident_monitor.dashboard_context import DashboardReadError
from neto_incident_monitor.history import History
from neto_incident_monitor.login_diagnostics import safe_facts
from neto_incident_monitor.pagination import AuthenticationRequired, Cancelled
from neto_incident_monitor.threatened_api import read_threats


CONFIG = dict(locations=['1' * 32], assignees=['2' * 32], monthly_group='3' * 32,
              l1_group_name='Example', smartphone_variable='4' * 32,
              smartphone_description='Example Task', threatened_group='5' * 32,
              held_metric='7' * 32)
AS_OF = datetime(2026, 10, 1, 13, 0, tzinfo=timezone.utc)


def row(index, *, target='resolution', deadline='2026-10-01 13:20:00'):
    return {'sys_id': f'{index:032x}', 'task': {'value': '6' * 32}, 'task.number': 'INC100',
            'task.priority': '2', 'sla.target': target, 'planned_end_time': deadline,
            'business_time_left': {'display_value': '20 minut'}, 'business_percentage': '90.5'}


class AnalyticsApiTests(unittest.TestCase):
    def test_dashboard_and_one_page_of_threats_make_nine_api_calls(self):
        page = Mock()
        page.evaluate.side_effect = [
            dict(status=200, result=[], next=False),
            *[dict(status=200, result={'stats': {'count': '0'}}, next=False)] * 7,
            dict(status=200, result=[], next=False, total='0'),
        ]
        args = (page, threading.Event(), Mock(), CONFIG)
        read_month(*args, 2026, 10)
        read_held(*args, {})
        read_requests(*args, {})
        read_threats(*args, as_of=AS_OF)
        paths = [call.args[1]['route'] for call in page.evaluate.call_args_list]
        self.assertEqual(paths, ['/api/now/stats/task_sla', *['/api/now/stats/incident_metric'] * 2,
                                 *['/api/now/stats/sc_task'] * 5, '/api/now/table/task_sla'])
        page.goto.assert_not_called()

    def test_filter_parameters_differ_by_period_and_reject_untrusted_values(self):
        self.assertIn("2028-02-29", monthly_query(CONFIG, 2028, 2))
        self.assertIn('^assigned_toISEMPTY', request_queries(CONFIG)['Nieprzypisane wnioski L1'])
        with self.assertRaises(DashboardReadError):
            monthly_query(dict(CONFIG, assignees=['^NQactive=true']), 2026, 10)

    def test_grouping_counts_rows_across_categories_and_rejects_duplicates(self):
        def group(priority, breached, count):
            return {'groupby_fields': [{'field': 'task.priority', 'value': priority},
                                       {'field': 'has_breached', 'value': breached}],
                    'stats': {'count': count}}

        groups = [group('2', 'true', '5'), group('2', 'false', 186), group('', 'false', 2)]
        result = summarize_month(groups)
        self.assertEqual(result['Liczba zgłoszeń'], 193)
        self.assertEqual(result['Zgłoszenia P2'], 191)
        self.assertEqual(result['Przekroczone P2'], 5)
        self.assertEqual(result['Zgłoszenia P1'], 0)
        self.assertFalse(any(summarize_month([]).values()))
        with self.assertRaises(DashboardReadError):
            summarize_month(groups + groups[:1])

    def test_failed_count_is_retried_without_repeating_completed_requests(self):
        page, stop, diagnostics = Mock(), threading.Event(), Mock()
        completed = {}
        page.evaluate.side_effect = [
            dict(status=200, next=False, result={'stats': {'count': '9'}}),
            dict(issue='timeout'),
            dict(status=200, next=False, result={'stats': {'count': '35'}}),
        ]
        args = (page, stop, diagnostics, 'held', 'incident_metric', {'first': 'a', 'second': 'b'}, completed)
        with self.assertRaisesRegex(DashboardReadError, 'api_timeout'):
            read_counts(*args)
        self.assertEqual(read_counts(*args), {'first': 9, 'second': 35})
        queries = [call.args[1]['params']['sysparm_query'] for call in page.evaluate.call_args_list]
        self.assertEqual(queries, ['a', 'b', 'b'])

    def test_access_errors_and_cancellation_preserve_separate_outcomes(self):
        page, stop, diagnostics = Mock(), threading.Event(), Mock()
        args = (page, stop, diagnostics, 'sla', '/api/now/stats/task_sla', {'sysparm_query': 'synthetic-secret'})
        page.evaluate.return_value = {'status': 403}
        with self.assertRaises(DashboardReadError) as caught:
            get(*args)
        self.assertFalse(caught.exception.retryable)
        self.assertEqual(caught.exception.reason, 'api_access')
        facts = safe_facts(diagnostics.record.call_args.kwargs)
        self.assertEqual(facts['read_reason'], 'api_access')
        self.assertNotIn('synthetic-secret', str(diagnostics.record.call_args_list))
        page.evaluate.return_value = {'status': 401}
        with self.assertRaises(AuthenticationRequired):
            get(*args)
        page.evaluate.side_effect = lambda *_: stop.set()
        with self.assertRaises(Cancelled):
            get(*args)

    def test_empty_result_requires_total_and_consistent_pagination(self):
        page = Mock()
        page.evaluate.return_value = dict(status=200, next=False, result=[], total='0')
        scores, incidents = read_threats(page, threading.Event(), Mock(), CONFIG, as_of=AS_OF)
        self.assertFalse(any(scores.values()))
        self.assertEqual(incidents, {})
        self.assertEqual(page.evaluate.call_count, 1)
        page.evaluate.return_value['total'] = '2'
        with self.assertRaises(DashboardReadError):
            read_threats(page, threading.Event(), Mock(), CONFIG, as_of=AS_OF)

    def test_multipage_snapshot_keeps_fixed_filters_and_groups_slas_per_incident(self):
        page = Mock()
        first = row(1)
        second = row(2, target='response', deadline='2026-10-01 12:00:00')
        page.evaluate.side_effect = [
            dict(status=200, next=True, result=[first], total='2'),
            dict(status=200, next=False, result=[second], total='2'),
        ]
        with patch('neto_incident_monitor.threatened_api.PAGE_SIZE', 1):
            scores, incidents = read_threats(page, threading.Event(), Mock(), CONFIG, as_of=AS_OF)
        self.assertEqual((scores['P2'], scores['Podjęcie']), (1, 1))
        self.assertEqual(incidents['INC100']['categories'], ['P2', 'Podjęcie'])
        self.assertEqual(incidents['INC100']['sla'], second['sys_id'])
        first_call, second_call = [call.args[1]['params'] for call in page.evaluate.call_args_list]
        self.assertEqual(first_call['sysparm_query'], second_call['sysparm_query'])
        self.assertEqual(second_call['sysparm_offset'], '1')
        self.assertEqual(first_call['sysparm_query'].count('task.active=true'), 6)

    def test_boundary_and_invalid_page_are_never_accepted(self):
        page = Mock()
        page.evaluate.return_value = dict(status=200, next=False, total='1',
                                          result=[row(1, deadline='2026-10-01 15:00:00')])
        with self.assertRaisesRegex(DashboardReadError, 'api_filter_mismatch'):
            read_threats(page, threading.Event(), Mock(), CONFIG, as_of=AS_OF)
        page.evaluate.side_effect = [
            dict(status=200, next=True, total='2', result=[row(1)]),
            dict(status=200, next=False, total='2', result=[row(1)]),
        ]
        with patch('neto_incident_monitor.threatened_api.PAGE_SIZE', 1), self.assertRaises(DashboardReadError):
            read_threats(page, threading.Event(), Mock(), CONFIG, as_of=AS_OF)

    def test_complete_threat_snapshot_reuses_presence_with_no_duplicate_alerts_after_restart(self):
        page = Mock()
        page.evaluate.return_value = dict(status=200, next=False, total='1', result=[row(1)])
        _, incidents = read_threats(page, threading.Event(), Mock(), CONFIG, as_of=AS_OF)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'history.json'
            history = History(path)
            prepare = Mock(return_value=({'example': True},))
            checkpoint = Mock()
            snapshot, arrivals = history.commit_threatened(incidents, 100, checkpoint, prepare)
            self.assertEqual(arrivals, 1)
            self.assertEqual(snapshot['INC100']['appearances'], 1)
            history = History(path)
            self.assertEqual(history.commit_threatened(incidents, 101, checkpoint, prepare)[1], 0)
            page.evaluate.return_value = dict(status=200, next=False, total='1', result=[])
            with self.assertRaises(DashboardReadError):
                read_threats(page, threading.Event(), Mock(), CONFIG, as_of=AS_OF)
            self.assertTrue(history.threatened_snapshot()['INC100']['present'])
            history.commit_threatened({}, 102, checkpoint, prepare)
            snapshot, arrivals = history.commit_threatened(incidents, 103, checkpoint, prepare)
            self.assertEqual((snapshot['INC100']['appearances'], arrivals), (2, 1))
            self.assertEqual(len(history.pending_alerts()), 2)

    def test_session_loss_discards_partial_pages(self):
        page = Mock()
        page.evaluate.side_effect = [
            dict(status=200, next=True, total='2', result=[row(1)]),
            dict(status=401),
            dict(status=200, next=False, total='1', result=[row(2)]),
        ]
        args = (page, threading.Event(), Mock(), CONFIG)
        with patch('neto_incident_monitor.threatened_api.PAGE_SIZE', 1):
            with self.assertRaises(AuthenticationRequired):
                read_threats(*args, as_of=AS_OF)
            scores, _ = read_threats(*args, as_of=AS_OF)
        self.assertEqual(scores['P2'], 1)
        self.assertEqual([call.args[1]['params']['sysparm_offset']
                          for call in page.evaluate.call_args_list], ['0', '1', '0'])

    def test_browser_fetch_uses_existing_card_and_session_and_does_not_follow_redirect(self):
        from playwright.sync_api import sync_playwright

        observed = []
        with sync_playwright() as playwright, playwright.chromium.launch() as browser:
            context = browser.new_context()
            page = context.new_page()
            context.add_cookies([dict(name='fixture_session', value='fixture', url=ORIGIN)])

            def route(connection):
                url = connection.request.url
                if '/stats/' in url:
                    headers = connection.request.all_headers()
                    observed.append((headers.get('x-usertoken'), headers.get('cookie')))
                    if 'redirect_test=true' in url:
                        connection.fulfill(status=302, headers={'Location': ORIGIN + '/unexpected'})
                    else:
                        connection.fulfill(json={'result': {'stats': {'count': '1'}}})
                elif url.endswith('/now/sow/home'):
                    connection.fulfill(content_type='text/html', body='<script>window.g_ck="fixture-token";</script>')
                else:
                    observed.append(('unexpected', None))
                    connection.abort()

            context.route('**/*', route)
            page.goto(ORIGIN + '/now/sow/home')
            args = (page, threading.Event(), Mock(), 'sla', '/api/now/stats/task_sla')
            self.assertEqual(get(*args, {})['result']['stats']['count'], '1')
            with self.assertRaises(AuthenticationRequired):
                get(*args, {'redirect_test': 'true'})
            self.assertEqual(context.pages, [page])
            self.assertEqual(page.url, ORIGIN + '/now/sow/home')
        self.assertEqual(observed, [('fixture-token', 'fixture_session=fixture')] * 2)
