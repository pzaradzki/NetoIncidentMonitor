import queue
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from neto_incident_monitor.app import App
from neto_incident_monitor.dashboard import REQUEST_TITLES
from neto_incident_monitor.browser_actions import Cancelled


class DrilldownWorkerTests(unittest.TestCase):
    def app(self):
        return SimpleNamespace(quitting=False, stop=threading.Event(), worker=Mock(),
                               schedule=Mock(), events=queue.Queue(),
                               dashboard_drilldown_requests=queue.Queue(maxsize=1))

    def test_click_queues_once_and_wakes_worker(self):
        app = self.app()
        request = (object(), 'requests', REQUEST_TITLES[-1], None)
        self.assertTrue(App.request_dashboard_drilldown(app, request))
        self.assertFalse(App.request_dashboard_drilldown(app, request))
        app.schedule.request.assert_called_once_with()
        self.assertIs(app.dashboard_drilldown_requests.get_nowait(), request)
        for state in ('stopped', 'quitting', 'dead'):
            app.stop.clear()
            app.quitting = state == 'quitting'
            app.worker.is_alive.return_value = state != 'dead'
            if state == 'stopped':
                app.stop.set()
            self.assertFalse(App.request_dashboard_drilldown(app, request))
            self.assertTrue(app.dashboard_drilldown_requests.empty())

    def test_worker_resolves_only_requested_tile_and_returns_correlated_result(self):
        app = self.app()
        page = object()
        token = object()
        request = (token, 'requests', REQUEST_TITLES[-1], None)
        with patch('neto_incident_monitor.dashboard_drilldown.collect_drilldown', return_value='synthetic') as collect, \
                patch('neto_incident_monitor.login_diagnostics.LoginDiagnostics'):
            App.read_dashboard_drilldown(app, page)
            collect.assert_not_called()
            app.dashboard_drilldown_requests.put(request)
            App.read_dashboard_drilldown(app, page)
            self.assertEqual(collect.call_args.args[:4], (page, 'requests', REQUEST_TITLES[-1], app.stop))
            self.assertEqual(app.events.get_nowait(), ('dashboard_drilldown_result', (token, 'synthetic')))
            self.assertTrue(app.dashboard_drilldown_requests.empty())

    def test_error_and_cancellation_finish_request_without_exposing_exception(self):
        for error in (Cancelled(), RuntimeError('SYNTHETIC_PRIVATE_SECRET')):
            app = self.app()
            token = object()
            app.dashboard_drilldown_requests.put((token, 'requests', REQUEST_TITLES[-1], None))
            with patch('neto_incident_monitor.dashboard_drilldown.collect_drilldown', side_effect=error), \
                    patch('neto_incident_monitor.login_diagnostics.LoginDiagnostics') as diagnostics:
                App.read_dashboard_drilldown(app, object())
                self.assertEqual(app.events.get_nowait(), ('dashboard_drilldown_result', (token, None)))
                self.assertNotIn('SYNTHETIC_PRIVATE_SECRET', str(diagnostics.mock_calls))
