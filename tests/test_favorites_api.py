import json
from threading import Event
import unittest
from unittest.mock import Mock, patch

from neto_incident_monitor import analytics_api, favorites_api
from neto_incident_monitor.dashboard_context import DashboardReadError
from neto_incident_monitor.favorites import classify
from neto_incident_monitor.login_diagnostics import LoginDiagnostics, _logger
from neto_incident_monitor.read_errors import AuthenticationRequired, Cancelled


def bookmark(identity='example', title='Przykład', url='incident_list.do?sysparm_query=active%3Dtrue'):
    return {'id': identity, 'title': title, 'url': url}


def api_reply(nodes, **headers):
    return {'status': 200, 'result': {'favorites': nodes}, 'next': False, 'total': None, **headers}


class FavoritesApiTests(unittest.TestCase):
    def setUp(self):
        self.page = Mock()
        self.stop = Event()
        self.log = Mock()

    def read(self, reply):
        self.page.evaluate.return_value = reply
        return favorites_api.read_favorites(self.page, self.stop, self.log)

    def test_single_request_preserves_group_order_and_applies_existing_url_classification(self):
        group = {'id': 'group', 'title': 'Grupa', 'favorites': [
            bookmark('short', 'Skrót', '/now/nav/ui/classic/__tinyId__/abcdefghijklmnop'),
            {'id': 'subgroup', 'title': 'Podgrupa', 'favorites': [bookmark('unsupported', 'Inna', '/home.do')]},
        ]}
        rows = self.read(api_reply([bookmark(), group, bookmark('request', 'Wniosek', '/sc_request_list.do')]))
        self.page.evaluate.assert_called_once()
        arguments = self.page.evaluate.call_args.args[1]
        self.assertEqual(arguments['route'], '/api/now/ui/navigator/favorites')
        self.assertEqual(arguments['params'], {})
        self.page.goto.assert_not_called()
        self.page.context.new_page.assert_not_called()
        self.assertEqual([row['source_id'] for row in rows], ['example', 'short', 'unsupported', 'request'])
        self.assertEqual([row['groups'] for row in rows], [[], ['Grupa'], ['Grupa', 'Podgrupa'], []])
        classified = classify(rows, [])
        self.assertEqual([row['status'] for row in classified], ['ready', 'ready', 'unsupported', 'ready'])
        self.log.record.assert_any_call('favorites_api_result', outcome='returned', item_count=4, group_count=2)

    def test_valid_empty_response_and_empty_groups(self):
        self.assertEqual(self.read(api_reply([])), [])
        self.assertEqual(self.read(api_reply([{'id': 'group', 'title': 'Grupa', 'favorites': []}])), [])

    def test_rejects_incomplete_or_ambiguous_response(self):
        for response, check in (
            ({**api_reply([]), 'result': {}}, 'shape'),
            (api_reply([bookmark(), {'id': 'missing', 'title': 'Bez adresu'}]), 'fields'),
            (api_reply([bookmark(), {**bookmark('both'), 'favorites': []}]), 'shape'),
            (api_reply([bookmark(), {'id': 'empty', 'title': 'Pusta', 'favorites': None}]), 'shape'),
            (api_reply([bookmark(), {'id': 'group', 'title': 'Grupa', 'favorites': [bookmark()]}]), 'record_identity'),
            (api_reply([bookmark()], next=True), 'next_page'),
            (api_reply([], total='0'), 'next_page'),
        ):
            with self.subTest(check=check, response=response), self.assertRaises(DashboardReadError) as caught:
                self.read(response)
            self.assertEqual(caught.exception.check, check)
            self.assertFalse(caught.exception.retryable)

    def test_limits_include_nested_entries_and_groups(self):
        group = {'id': 'group', 'title': 'Grupa', 'favorites': [bookmark('inside')]}
        with patch.object(favorites_api, 'MAX_NODES', 2), self.assertRaises(DashboardReadError):
            self.read(api_reply([group, bookmark()]))
        nested = {'id': 'outer', 'title': 'Zewnętrzna', 'favorites': [group]}
        with patch.object(favorites_api, 'MAX_GROUP_DEPTH', 1), self.assertRaises(DashboardReadError):
            self.read(api_reply([nested]))

    def test_transport_uses_common_error_classes_and_stops_before_browser_work(self):
        for reply in ({'status': 401}, {'issue': 'redirect'}):
            with self.subTest(reply=reply), self.assertRaises(AuthenticationRequired):
                self.read(reply)
        for status, reason in ((403, 'api_access'), (429, 'api_rate_limit'), (503, 'api_service')):
            with self.subTest(status=status), self.assertRaises(DashboardReadError) as caught:
                self.read({'status': status})
            self.assertEqual(caught.exception.reason, reason)
        self.page.evaluate.reset_mock()
        self.stop.set()
        with self.assertRaises(Cancelled):
            self.read(api_reply([]))
        self.page.evaluate.assert_not_called()

    def test_other_navigator_routes_and_parameters_are_rejected(self):
        for route, params in ((analytics_api.FAVORITES_ROUTE, {'user': 'other'}),
                              ('/api/now/ui/navigator/history', {})):
            with self.subTest(route=route), self.assertRaises(ValueError):
                analytics_api.get(self.page, self.stop, self.log, 'favorites', route, params)
        self.page.evaluate.assert_not_called()

    def test_diagnostics_serialize_safe_fields_and_accept_sink_failure(self):
        reply = api_reply([bookmark('PRIVATE_ID', 'PRIVATE_NAME', '/incident_list.do?PRIVATE_URL')])
        with self.assertLogs(_logger, level='INFO') as captured:
            self.log = LoginDiagnostics(source='favorites', import_id='a' * 32)
            self.read(reply)
            with self.assertRaises(DashboardReadError):
                self.read(api_reply([bookmark('PRIVATE_ID'), bookmark('PRIVATE_ID')]))
        records = [json.loads(record.getMessage()) for record in captured.records]
        self.assertTrue(all(record.get('import_id') == 'a' * 32 for record in records))
        self.assertTrue(any(record.get('api_target') == 'favorites' and record.get('http_status') == 200
                            for record in records))
        self.assertTrue(any(record.get('api_list_check') == 'record_identity' for record in records))
        self.assertNotIn('PRIVATE_', '\n'.join(captured.output))
        self.log = Mock()
        self.log.record.side_effect = OSError('synthetic sink unavailable')
        self.assertEqual(len(self.read(reply)), 1)
