from contextlib import nullcontext
from concurrent.futures import Future
import json
from pathlib import Path
import queue
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, Mock, patch

from neto_incident_monitor.app import App
from neto_incident_monitor.dashboard import TITLES, HELD_TITLES, REQUEST_TITLES
from neto_incident_monitor.history import History
from neto_incident_monitor.threatened import KEYS


class UpdateOrderTests(unittest.TestCase):
    def run_cycle(self, scope='startup', dashboard=True, mode='success', periodic=False):
        with tempfile.TemporaryDirectory() as folder:
            app = App.__new__(App)
            app.stop, app.events = threading.Event(), queue.Queue()
            app.schedule = Mock(woken_by_request=False)
            url = 'https://adeo.service-now.com/incident_list.do'
            app.filters = [dict(name='Synthetic', url=url)]
            app.disabled_filter_urls = frozenset()
            app.history = History(Path(folder)/'history.json')
            app.dashboard_requests, app.threatened_requests = queue.Queue(), queue.Queue()
            if dashboard:
                app.dashboard_requests.put((1, 2026, 11))
            if scope != 'dashboard':
                app.threatened_requests.put(1)
            if periodic:
                app.threatened_last_request, app.threatened_next_read = 1, 10
            app.refresh_coordinator().reserve(scope)
            clock, order = [0], []
            app.restore_login = Mock(return_value=True)
            page = Mock(url=url)
            page.is_closed.return_value = False
            playwright = MagicMock()
            playwright.__enter__.return_value.chromium.launch_persistent_context.return_value = Mock(pages=[page])
            def sla(*args):
                order.append('dashboard')
                self.assertTrue(app.refresh_coordinator().busy)
                clock[0] += 130
                if mode == 'recovery':
                    from playwright.sync_api import TimeoutError
                    from neto_incident_monitor.pagination import AuthenticationRequired
                    if order.count('dashboard') == 1:
                        raise TimeoutError('Synthetic document timeout')
                    if order.count('dashboard') == 2:
                        raise AuthenticationRequired()
                if mode == 'stop':
                    app.stop.set()
                if mode == 'error':
                    raise ValueError('Synthetic dashboard failure')
                return dict.fromkeys(TITLES, 0)
            def threatened(*args):
                order.append('threatened')
                self.assertTrue(app.refresh_coordinator().busy)
                return dict.fromkeys(KEYS, 0)
            def filters(*args, **kwargs):
                order.append('filter')
                self.assertTrue(app.refresh_coordinator().busy)
                return {}, 1
            with patch('playwright.sync_api.sync_playwright', return_value=playwright), \
                    patch('neto_incident_monitor.browser_policy.BrowserRuntime') as runtime, \
                    patch('neto_incident_monitor.app.navigate'), \
                    patch('neto_incident_monitor.app.STATE', Path(folder)/'seen.json'), \
                    patch('neto_incident_monitor.app.time.monotonic', side_effect=lambda: clock[0]), \
                    patch('neto_incident_monitor.dashboard.read_dashboard', side_effect=sla), \
                    patch('neto_incident_monitor.dashboard.read_held_dashboard', return_value=dict.fromkeys(HELD_TITLES, 0)), \
                    patch('neto_incident_monitor.dashboard.read_requests_dashboard', return_value=dict.fromkeys(REQUEST_TITLES, 0)), \
                    patch('neto_incident_monitor.threatened.read_threatened_dashboard', side_effect=threatened), \
                    patch('neto_incident_monitor.app.read_all', side_effect=filters), \
                    patch('neto_incident_monitor.app.wait_for_browser_cycle', return_value=True), \
                    self.assertLogs('neto.login_diagnostics', level='INFO') as logs:
                runtime.return_value.dashboard_read.side_effect = lambda *args: nullcontext()
                app.monitor(dict(urls=[url], filters=app.filters, interval=60, task_interval=60))
            self.assertFalse(app.refresh_coordinator().busy)
            return order, [json.loads(record.getMessage()) for record in logs.records]

    def test_startup_and_all_use_dashboard_then_threats_then_filters(self):
        for scope in ('startup', 'all'):
            with self.subTest(scope=scope):
                order, _ = self.run_cycle(scope)
                self.assertEqual(order, ['dashboard', 'threatened', 'filter'])

    def test_no_startup_dashboard_request_skips_dashboard(self):
        order, _ = self.run_cycle(dashboard=False)
        self.assertEqual(order, ['threatened', 'filter'])

    def test_dashboard_section_error_does_not_block_other_work(self):
        order, _ = self.run_cycle(mode='error')
        self.assertEqual(order, ['dashboard', 'threatened', 'filter'])

    def test_dashboard_login_recovery_finishes_before_threats_and_filters(self):
        order, records = self.run_cycle(mode='recovery')
        self.assertEqual(order, ['dashboard', 'dashboard', 'dashboard', 'threatened', 'filter'])
        recovery = [r for r in records if r['event'] == 'section_login_recovery_end']
        self.assertEqual(len(recovery), 1)
        self.assertEqual(recovery[0]['outcome'], 'returned')

    def test_stop_in_dashboard_prevents_threats_and_filters(self):
        order, _ = self.run_cycle(mode='stop')
        self.assertEqual(order, ['dashboard'])

    def test_overdue_during_dashboard_runs_once_and_logs_dashboard_delay(self):
        order, records = self.run_cycle(scope='dashboard', periodic=True)
        self.assertEqual(order, ['dashboard', 'threatened'])
        schedule = next(r for r in records if r['event'] == 'threatened_schedule')
        self.assertEqual(schedule['delay_reason'], 'dashboard')
        self.assertEqual(schedule['lateness_ms'], 120000)

    def test_startup_message_matches_actual_dashboard_request(self):
        import tkinter as tk
        url = 'https://adeo.service-now.com/incident_list.do'
        for saved in ({}, {'dashboard_auto_refresh': False}, {'dashboard_auto_refresh': True}):
            enabled = saved.get('dashboard_auto_refresh', False)
            with self.subTest(saved=saved), tempfile.TemporaryDirectory() as folder:
                root = tk.Tk()
                app = None
                try:
                    settings = dict(filters=[dict(name='Synthetic', url=url)], **saved)
                    with patch('neto_incident_monitor.app.read_json', return_value=settings), \
                            patch('neto_incident_monitor.app.save_json'), \
                            patch('neto_incident_monitor.dashboard_cache.load_snapshot', return_value=None):
                        app = App(root, history_path=Path(folder)/'history.json', enable_tray=False, apply_startup=False)
                        done = Future()
                        done.set_result(None)
                        with patch.object(app.alert_writer, 'submit', return_value=done), \
                                patch('neto_incident_monitor.app.threading.Thread'):
                            app.start()
                        self.assertEqual(app.dashboard_requests.qsize(), int(enabled))
                        self.assertEqual(app.threatened_requests.qsize(), 1)
                        message = app.threatened_view.message.get()
                        self.assertIn('po dashboardzie i przed filtrami' if enabled else 'przed filtrami', message)
                        self.assertEqual('dashboardzie' in message, enabled)
                finally:
                    if app is not None:
                        app.teams_sender.stop()
                        app.google_chat_sender.stop()
                        app.history_writer.shutdown(wait=True)
                        app.alert_writer.shutdown(wait=True)
                    root.destroy()

    def test_full_refresh_message_describes_new_sequence(self):
        app = App.__new__(App)
        app.worker = Mock()
        app.worker.is_alive.return_value = True
        app.stop = threading.Event()
        app.auth_waiting = app.quitting = False
        app.dashboard_view, app.threatened_view = Mock(), Mock()
        app.schedule, app.status, app.update_refresh_controls = Mock(), Mock(), Mock()
        self.assertTrue(app.request_refresh('all'))
        self.assertIn('dashboard → incydenty zagrożone → filtry', app.status.set.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
