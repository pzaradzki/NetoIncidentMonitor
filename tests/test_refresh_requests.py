import queue
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from neto_incident_monitor.app import App
from neto_incident_monitor.history import History
from neto_incident_monitor.monitoring import RefreshControl


class RefreshRequestsTests(unittest.TestCase):
    def test_periodic_threats_interrupt_only_between_filters_and_determine_sleep(self):
        for slow_dashboard in (False, True):
            with self.subTest(slow_dashboard=slow_dashboard), tempfile.TemporaryDirectory() as folder:
                app = App.__new__(App)
                app.stop, app.events = threading.Event(), queue.Queue()
                app.threatened_requests = queue.Queue()
                app.threatened_requests.put(1)
                app.schedule = Mock(woken_by_request=False)
                urls = ['https://adeo.service-now.com/incident_list.do?sysparm_query=priority=' + str(i) for i in range(3)]
                app.filters = [dict(name=str(i), url=url) for i, url in enumerate(urls)]
                app.disabled_filter_urls = frozenset()
                app.history = History(Path(folder) / 'history.json')
                app.restore_login = Mock(return_value=True)
                clock, order = [0], []
                def dashboard(page):
                    order.append('dashboard')
                    if slow_dashboard:
                        clock[0] += 130
                app.read_dashboard_request = Mock(side_effect=dashboard)
                def threats(*args):
                    self.assertTrue(app.refresh_coordinator().busy)
                    order.append('threatened')
                    clock[0] += 5
                    return dict.fromkeys(('P1', 'P2', 'P3', 'P4', 'P5', 'Podjęcie'), 0)
                def read(page, url, *args, **kwargs):
                    order.append(urls.index(url))
                    clock[0] += 35
                    return {}, 1
                page = Mock()
                page.is_closed.return_value = False
                context = Mock(pages=[page])
                playwright = MagicMock()
                playwright.__enter__.return_value.chromium.launch_persistent_context.return_value = context
                with patch('playwright.sync_api.sync_playwright', return_value=playwright), \
                        patch('neto_incident_monitor.browser_window.BrowserWindow'), \
                        patch('neto_incident_monitor.app.STATE', Path(folder) / 'seen.json'), \
                        patch('neto_incident_monitor.app.navigate'), \
                        patch('neto_incident_monitor.app.time.monotonic', side_effect=lambda: clock[0]), \
                        patch('neto_incident_monitor.threatened.read_threatened_dashboard', side_effect=threats), \
                        patch('neto_incident_monitor.app.read_all', side_effect=read), \
                        patch('neto_incident_monitor.app.wait_for_browser_cycle', return_value=True) as wait:
                    app.monitor(dict(urls=urls, filters=app.filters, interval=3600, task_interval=3600))
                expected = ['threatened', 'dashboard']
                if slow_dashboard:
                    expected += ['threatened']  # One overdue run, not a backlog of two.
                expected += [0, 1, 'threatened', 2]
                self.assertEqual(order, expected)
                self.assertEqual(wait.call_args.args[2], 25)
                self.assertEqual(app.threatened_next_read - clock[0], 25)

    def test_threat_timer_counts_from_completion_after_error_and_manual_read(self):
        app = App.__new__(App)
        app.stop, app.events, app.threatened_requests = threading.Event(), queue.Queue(), queue.Queue()
        clock = [100]
        def fail(*args):
            clock[0] += 20
            raise ValueError('fixture')
        with patch('neto_incident_monitor.app.time.monotonic', side_effect=lambda: clock[0]), \
                patch('neto_incident_monitor.threatened.read_threatened_dashboard', side_effect=fail) as read:
            app.threatened_requests.put(1)
            app.read_threatened_request(Mock())
            self.assertEqual(app.threatened_next_read, 180)
            clock[0] = 179
            app.read_due_threatened(Mock())
            self.assertEqual(read.call_count, 1)
            app.threatened_requests.put(2)  # Manual refresh resets the same timer.
            app.read_threatened_request(Mock())
            self.assertEqual(app.threatened_next_read, 259)
            clock[0] = 259
            app.read_due_threatened(Mock())
            self.assertEqual(app.threatened_next_read, 339)
            self.assertEqual(read.call_count, 3)
            self.assertEqual(app.threatened_last_request, 2)
            clock[0] = 500
            app.stop.set()
            app.read_due_threatened(Mock())
            self.assertEqual(read.call_count, 3)

    def test_manual_requests_share_lock_but_open_stays_available(self):
        for scope in ('all', 'dashboard', 'threatened', 'filter'):
            with self.subTest(scope=scope):
                app = App.__new__(App)
                app.worker = Mock()
                app.worker.is_alive.return_value = True
                app.stop = threading.Event()
                app.auth_waiting = app.quitting = False
                app.filters = [dict(name='A', url='selected', enabled=True)]
                app.selected_filter_url = Mock(return_value='selected')
                app.check_button = Mock()
                app.refresh_filter_button = Mock()
                app.open_filter_button = Mock()
                app.dashboard_view = Mock()
                app.threatened_view = Mock(pending=False)
                app.schedule = Mock()
                app.status = Mock()
                self.assertTrue(app.request_refresh(scope))
                self.assertFalse(app.request_refresh('all'))
                self.assertEqual(app.refresh_coordinator().current(),
                                 (scope, 'selected' if scope == 'filter' else None))
                app.check_button.configure.assert_called_with(state='disabled')
                app.refresh_filter_button.configure.assert_called_with(state='disabled')
                app.dashboard_view.refresh_button.configure.assert_called_with(state='disabled')
                app.threatened_view.refresh_button.configure.assert_called_with(state='disabled')
                app.open_filter_button.configure.assert_called_with(state='normal')
                self.assertEqual(app.dashboard_view.request_refresh.call_count, int(scope in ('all', 'dashboard')))
                self.assertEqual(app.threatened_view.request_refresh.call_count, int(scope in ('all', 'threatened')))
                app.schedule.request.assert_called_once()
                app.refresh_coordinator().finish()
                app.update_refresh_controls()
                app.check_button.configure.assert_called_with(state='normal')
                app.stop.set()
                app.update_refresh_controls()
                app.check_button.configure.assert_called_with(state='disabled')
                app.open_filter_button.configure.assert_called_with(state='normal')

    def test_reservation_rejects_overlap_and_preserves_target(self):
        control = RefreshControl()
        self.assertTrue(control.reserve('filter', 'selected'))
        self.assertFalse(control.reserve('all'))
        self.assertEqual(control.scheduled(), ('filter', 'selected'))
        control.finish()
        self.assertEqual(control.scheduled(), ('scheduled', None))
        self.assertTrue(control.busy)

    def test_worker_obeys_scope_and_full_order(self):
        for scope, expected in (
            ('all', ['threatened', 'dashboard', 'A', 'B']),
            ('dashboard', ['dashboard']),
            ('threatened', ['threatened']),
            ('filter', ['B']),
        ):
            with self.subTest(scope=scope), tempfile.TemporaryDirectory() as folder:
                app = App.__new__(App)
                app.stop = threading.Event()
                app.events = queue.Queue()
                app.schedule = Mock(woken_by_request=True)
                urls = ['https://adeo.service-now.com/incident_list.do?sysparm_query=priority=1',
                        'https://adeo.service-now.com/incident_list.do?sysparm_query=priority=2']
                app.filters = [dict(name=name, url=url) for name, url in zip(('A', 'B'), urls)]
                app.disabled_filter_urls = frozenset()
                app.history = History(Path(folder) / 'history.json')
                app.refresh_coordinator().reserve(scope, urls[1] if scope == 'filter' else None)
                order = []
                app.restore_login = Mock(return_value=True)
                app.read_threatened_request = Mock(side_effect=lambda page: order.append('threatened'))
                app.read_dashboard_request = Mock(side_effect=lambda page: order.append('dashboard'))
                page = Mock()
                page.is_closed.return_value = False
                context = Mock(pages=[page])
                playwright = MagicMock()
                playwright.__enter__.return_value.chromium.launch_persistent_context.return_value = context
                def read(page, url, *args, **kwargs):
                    self.assertTrue(app.refresh_coordinator().busy)
                    order.append('A' if url == urls[0] else 'B')
                    return {}, 1
                with patch('playwright.sync_api.sync_playwright', return_value=playwright), \
                        patch('neto_incident_monitor.browser_window.BrowserWindow'), \
                        patch('neto_incident_monitor.app.STATE', Path(folder) / 'seen.json'), \
                        patch('neto_incident_monitor.app.navigate'), \
                        patch('neto_incident_monitor.app.read_all', side_effect=read), \
                        patch('neto_incident_monitor.app.wait_for_browser_cycle', return_value=True):
                    app.monitor(dict(urls=urls, filters=app.filters, interval=60, task_interval=60))
                self.assertEqual(order, expected)
                self.assertFalse(app.refresh_coordinator().busy)

    def test_selected_filter_opens_without_monitoring(self):
        app = App.__new__(App)
        url = 'https://adeo.service-now.com/incident_list.do?sysparm_query=state=1'
        app.selected_filter_url = Mock(return_value=url)
        with patch('neto_incident_monitor.app.webbrowser.open') as opened:
            app.open_selected_filter()
        self.assertEqual(opened.call_count, 1)
        self.assertIn('incident_list.do', opened.call_args.args[0])
        self.assertIn('state', opened.call_args.args[0])
