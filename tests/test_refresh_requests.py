import json
import tempfile
import threading
import time
import unittest
from itertools import count
from pathlib import Path
from unittest.mock import Mock, patch

from neto_incident_monitor.app import App
from neto_incident_monitor.history import History
from neto_incident_monitor.login_diagnostics import close_diagnostics
from neto_incident_monitor.monitoring import Schedule
from neto_incident_monitor.read_errors import Cancelled
from neto_incident_monitor.shared_session import SharedSession
from neto_incident_monitor.threatened import KEYS


class ThreatenedScheduleTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.clock = 0
        app = self.app = App.__new__(App)
        app.stop = threading.Event()
        app.quitting = False
        app.session_state = 'ready'
        app.threatened_next_read = None
        app.schedule = Schedule()
        app.filters = []
        app.filter_revisions = {}
        app.disabled_filter_urls = frozenset()
        app.monitor_generation = object()
        app.history = History(self.folder / 'history.json')
        app.alert_writer = Mock()
        app.update_refresh_controls = Mock()
        period = (2026, 11)
        app.dashboard_view = Mock(active_request=(41, *period))
        app.dashboard_view.selected_period.return_value = period
        ids = count(1)
        app.threatened_view = Mock(pending=False)
        app.threatened_view.request_refresh.side_effect = lambda **_kwargs: next(ids)
        app.events = Mock()
        app.events.put.side_effect = self.prepare_read
        session = self.session = app.session = SharedSession(app, self.folder / 'profile')
        session.ready_once = session.connected = True
        session.log = Mock()
        self.page = Mock()
        self.page.is_closed.return_value = False
        close_diagnostics()
        self.enterContext(patch('neto_incident_monitor.login_diagnostics.DATA', self.folder))
        self.addCleanup(close_diagnostics)
        self.enterContext(patch('neto_incident_monitor.app.STATE', self.folder / 'seen.json'))
        self.enterContext(patch('neto_incident_monitor.analytics_config.load_config', return_value={}))
        self.enterContext(patch('neto_incident_monitor.shared_session.authentication_required', return_value=False))
        app_time = self.enterContext(patch('neto_incident_monitor.app.time', wraps=time))
        app_time.monotonic.side_effect = lambda: self.clock
        for module in ('shared_session', 'read_budget', 'section_runner'):
            self.enterContext(patch(f'neto_incident_monitor.{module}.monotonic', side_effect=lambda: self.clock))
        self.session.start_cycle([], {'inc': 3600, 'task': 3600})

    def prepare_read(self, event):
        if event[0] == 'session_prepare_read':
            self.app.handle_session_event(*event)

    def serve_until_idle(self):
        with patch('neto_incident_monitor.app.wait_for_browser_cycle', side_effect=Cancelled) as wait:
            with self.assertRaises(Cancelled):
                self.session.serve(self.page)
        wait.assert_called_once()
        return wait.call_args.args[2]

    def diagnostic_entries(self, event):
        log = (self.folder / 'login-diagnostics.jsonl').read_text(encoding='utf-8')
        entries = [json.loads(line) for line in log.splitlines()]
        return [entry for entry in entries if entry['event'] == event]

    def test_periodic_threats_interrupt_only_between_filters_and_determine_sleep(self):
        app = self.app
        order = []
        app.filters = [{'name': str(i), 'url': f'https://adeo.service-now.com/incident_list.do?sysparm_query=priority={i}'}
                       for i in range(1, 4)]
        app.update_session_filters()

        def read_filter(_page, _url, _name, index, *_args, **_kwargs):
            order.append(index)
            self.clock += 35
            return 'success'

        def threats(*_args):
            order.append('threatened')
            self.clock += 5
            return dict.fromkeys(KEYS, 0), {}

        app.read_filter = Mock(side_effect=read_filter)
        with patch('neto_incident_monitor.threatened_api.read_threats', side_effect=threats):
            self.assertEqual(self.serve_until_idle(), 25)
            self.assertEqual(order, ['threatened', 1, 2, 'threatened', 3])
            self.assertEqual(app.threatened_next_read, 140)
            self.clock = 142
            self.assertEqual(self.serve_until_idle(), 60)
        self.assertEqual(order, ['threatened', 1, 2, 'threatened', 3, 'threatened'])
        schedule = self.diagnostic_entries('threatened_schedule')
        self.assertEqual([(entry['delay_reason'], entry['lateness_ms']) for entry in schedule],
                         [('filter', 10_000), ('idle', 2_000)])

    def test_overdue_during_dashboard_runs_once_and_logs_dashboard_delay(self):
        app = self.app
        app.threatened_next_read = 10
        order = []

        def dashboard(*_args, **_kwargs):
            order.append('dashboard')
            self.clock += 130
            return True

        def threats(*_args):
            order.append('threatened')
            self.clock += 5
            return dict.fromkeys(KEYS, 0), {}

        app.read_dashboard_request = Mock(side_effect=dashboard)
        self.assertTrue(app.request_refresh('dashboard'))
        with patch('neto_incident_monitor.threatened_api.read_threats', side_effect=threats):
            self.assertEqual(self.serve_until_idle(), 60)
        self.assertEqual(order, ['dashboard', 'threatened'])
        self.assertEqual(app.threatened_next_read, 195)
        schedule, = self.diagnostic_entries('threatened_schedule')
        self.assertEqual(schedule['delay_reason'], 'dashboard')
        self.assertEqual(schedule['lateness_ms'], 120_000)
        self.assertEqual(schedule['request_id'], 1)
        self.assertTrue(schedule['run_id'] and schedule['read_id'])
        completed, = self.diagnostic_entries('threatened_details_complete')
        for field in ('run_id', 'read_id', 'request_id'):
            self.assertEqual(completed[field], schedule[field])

    def test_threat_timer_counts_from_completion_after_error_and_manual_read(self):
        app = self.app
        self.clock = 100
        attempts = []

        def threats(_page, _stop, diagnostics, _config):
            attempts.append((self.clock, diagnostics.context['request_id']))
            self.clock += 20
            if len(attempts) != 2:
                raise ValueError('SYNTHETIC_PRIVATE_SCHEDULE_DATA')
            return dict.fromkeys(KEYS, 0), {}

        with patch('neto_incident_monitor.threatened_api.read_threats', side_effect=threats):
            self.assertEqual(self.serve_until_idle(), 60)
            self.assertEqual(app.threatened_next_read, 180)
            self.clock = 179
            self.assertEqual(self.serve_until_idle(), 1)
            self.assertEqual(len(attempts), 1)
            self.assertTrue(app.request_refresh('threatened'))
            self.assertEqual(self.serve_until_idle(), 60)
            self.assertEqual(app.threatened_next_read, 259)
            saved = app.history.threatened_snapshot(with_summary=True)
            self.assertEqual(saved[1]['counters'], dict.fromkeys(KEYS, 0))
            self.clock = 258
            self.assertEqual(self.serve_until_idle(), 1)
            self.assertEqual(len(attempts), 2)
            self.clock = 259
            self.assertEqual(self.serve_until_idle(), 60)
            self.assertEqual(app.threatened_next_read, 339)
            self.assertEqual(app.history.threatened_snapshot(with_summary=True), saved)
            self.session.stop_cycle()
            self.clock = 500
            self.serve_until_idle()
        self.assertEqual(attempts, [(100, 1), (179, 2), (259, 3)])
        log = (self.folder / 'login-diagnostics.jsonl').read_text(encoding='utf-8')
        self.assertNotIn('SYNTHETIC_PRIVATE_SCHEDULE_DATA', log)


class RefreshRequestsTests(unittest.TestCase):
    def test_selected_filter_opens_without_monitoring(self):
        app = App.__new__(App)
        url = 'https://adeo.service-now.com/incident_list.do?sysparm_query=state=1'
        app.selected_filter_url = Mock(return_value=url)
        with patch('neto_incident_monitor.app.webbrowser.open') as opened:
            app.open_selected_filter()
        self.assertEqual(opened.call_count, 1)
        self.assertIn('incident_list.do', opened.call_args.args[0])
        self.assertIn('state', opened.call_args.args[0])
