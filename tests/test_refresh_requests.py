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
        self.enterContext(patch('neto_incident_monitor.login_diagnostics.LOG_DIR', self.folder))
        self.addCleanup(close_diagnostics)
        self.enterContext(patch('neto_incident_monitor.app.STATE', self.folder / 'seen.json'))
        self.enterContext(patch('neto_incident_monitor.analytics_config.load_config', return_value={}))
        self.enterContext(patch('neto_incident_monitor.shared_session.authentication_required', return_value=False))
        app_time = self.enterContext(patch('neto_incident_monitor.app.time', wraps=time))
        app_time.monotonic.side_effect = lambda: self.clock
        threat_time = self.enterContext(patch('neto_incident_monitor.threatened_read.time', wraps=time))
        threat_time.monotonic.side_effect = lambda: self.clock
        for module in ('shared_session', 'read_budget', 'section_runner'):
            self.enterContext(patch(f'neto_incident_monitor.{module}.monotonic', side_effect=lambda: self.clock))
        self.session.start_cycle([], {'inc': 3600, 'task': 3600, 'threatened': 60})

    def prepare_read(self, event):
        if event[0] == 'session_prepare_read':
            self.app.handle_session_event(*event)

    def serve_until_idle(self):
        with patch('neto_incident_monitor.browser_actions.wait_for_browser_cycle', side_effect=Cancelled) as wait:
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
            self.assertEqual(self.session.cycle.deadlines['threatened'], 140)
            self.clock = 142
            self.assertEqual(self.serve_until_idle(), 60)
        self.assertEqual(order, ['threatened', 1, 2, 'threatened', 3, 'threatened'])
        schedule = self.diagnostic_entries('threatened_schedule')
        self.assertEqual([(entry['delay_reason'], entry['lateness_ms']) for entry in schedule],
                         [('filter', 10_000), ('idle', 2_000)])

    def test_overdue_during_dashboard_runs_once_and_logs_dashboard_delay(self):
        app = self.app
        self.session.cycle.schedule_next('threatened', -50)
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
        self.assertEqual(self.session.cycle.deadlines['threatened'], 195)
        schedule, = self.diagnostic_entries('threatened_schedule')
        self.assertEqual(schedule['delay_reason'], 'dashboard')
        self.assertEqual(schedule['lateness_ms'], 120_000)
        self.assertEqual(schedule['interval_s'], 60)
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
            self.assertEqual(self.session.cycle.deadlines['threatened'], 180)
            self.clock = 179
            self.assertEqual(self.serve_until_idle(), 1)
            self.assertEqual(len(attempts), 1)
            self.assertTrue(app.request_refresh('threatened'))
            self.assertEqual(self.serve_until_idle(), 60)
            self.assertEqual(self.session.cycle.deadlines['threatened'], 259)
            saved = app.history.threatened_snapshot(with_summary=True)
            self.assertEqual(saved[1]['counters'], dict.fromkeys(KEYS, 0))
            self.clock = 258
            self.assertEqual(self.serve_until_idle(), 1)
            self.assertEqual(len(attempts), 2)
            self.clock = 259
            self.assertEqual(self.serve_until_idle(), 60)
            self.assertEqual(self.session.cycle.deadlines['threatened'], 339)
            self.assertEqual(app.history.threatened_snapshot(with_summary=True), saved)
            self.session.stop_cycle()
            self.clock = 500
            self.serve_until_idle()
        self.assertEqual(attempts, [(100, 1), (179, 2), (259, 3)])
        log = (self.folder / 'login-diagnostics.jsonl').read_text(encoding='utf-8')
        self.assertNotIn('SYNTHETIC_PRIVATE_SCHEDULE_DATA', log)
        self.assertEqual([entry['outcome'] for entry in self.diagnostic_entries('threatened_read_finished')],
                         ['error', 'returned', 'error'])

    def test_saved_interval_retimes_idle_and_running_threat_reads_from_completion(self):
        cycle = self.session.cycle
        self.clock = 100
        read_times = []

        def threats(*_args):
            read_times.append(self.clock)
            self.clock += 5
            if len(read_times) == 2:
                self.session.update_intervals({**cycle.intervals, 'threatened': 45})
            return dict.fromkeys(KEYS, 0), {}

        with patch('neto_incident_monitor.threatened_api.read_threats', side_effect=threats):
            self.assertEqual(self.serve_until_idle(), 60)
            self.clock = 120
            self.session.update_intervals({**cycle.intervals, 'threatened': 20})
            self.assertEqual(self.serve_until_idle(), 5)
            self.assertEqual(cycle.deadlines['threatened'], 125)
            self.clock = 125
            self.assertEqual(self.serve_until_idle(), 45)
        self.assertEqual(read_times, [100, 125])
        self.assertEqual(cycle.last_finished['threatened'], 130)
        self.assertEqual(cycle.deadlines['threatened'], 175)
        self.session.log.record.assert_any_call('schedule_interval_change', interval_stage='applied',
                                               schedule_kind='threatened', previous_interval_s=60,
                                               interval_s=20, batch_active=False)
        self.session.log.record.assert_any_call('schedule_interval_change', interval_stage='applied',
                                               schedule_kind='threatened', previous_interval_s=20,
                                               interval_s=45, batch_active=True)

    def test_full_read_sets_threat_deadline_before_remaining_filter_parts_finish(self):
        app = self.app
        self.clock = 100
        cycle = self.session.cycle
        cycle.schedule_next('threatened', 90)
        app.filters = [{'name': 'A', 'url': 'https://adeo.service-now.com/incident_list.do?sysparm_query=priority=1'}]
        app.update_session_filters()

        def filter_read(*_args, **_kwargs):
            self.clock += 25
            return 'success'

        def threats(*_args):
            self.clock += 5
            return dict.fromkeys(KEYS, 0), {}

        app.read_dashboard_request = Mock(return_value=True)
        app.read_filter = Mock(side_effect=filter_read)
        self.assertTrue(app.request_refresh('all'))
        with patch('neto_incident_monitor.threatened_api.read_threats', side_effect=threats):
            self.assertEqual(self.serve_until_idle(), 35)
        self.assertEqual(self.clock, 130)
        self.assertEqual(cycle.last_finished['threatened'], 105)
        self.assertEqual(cycle.deadlines['threatened'], 165)

    def test_stopped_automatic_read_does_not_set_restarted_cycle_deadline(self):
        previous_cycle = self.session.cycle
        self.clock = 100
        attempts = []

        def threats(_page, _stop, diagnostics, _config):
            attempts.append(diagnostics.context['request_id'])
            if len(attempts) == 1:
                self.session.stop_cycle()
                self.clock = 110
                self.session.start_cycle([], {**previous_cycle.intervals, 'threatened': 90})
            return dict.fromkeys(KEYS, 0), {}

        with patch('neto_incident_monitor.threatened_api.read_threats', side_effect=threats):
            self.assertEqual(self.serve_until_idle(), 90)
        self.assertEqual(attempts, [1, 2])
        self.assertNotIn('threatened', previous_cycle.last_finished)
        self.assertEqual(self.session.cycle.deadlines['threatened'], 200)
        self.assertEqual([entry['outcome'] for entry in self.diagnostic_entries('threatened_read_finished')],
                         ['cancelled', 'returned'])

    def test_overdue_dashboard_runs_once_between_filters_after_due_threats(self):
        app = self.app
        order = []
        app.filters = [{'name': str(i), 'url': f'https://adeo.service-now.com/incident_list.do?sysparm_query=priority={i}'}
                       for i in range(1, 3)]
        app.update_session_filters()
        self.clock = 100
        self.session.start_cycle([], {'inc': 3600, 'task': 3600, 'dashboard': 60, 'threatened': 60})

        def dashboard(*_args, **_kwargs):
            order.append('dashboard')
            self.clock += 10
            return True

        def filter_read(_page, _url, _name, index, *_args, **_kwargs):
            order.append(index)
            if index == 1:
                self.clock += 200
            return 'success'

        def threats(*_args):
            order.append('threatened')
            return dict.fromkeys(KEYS, 0), {}

        app.read_dashboard_request = Mock(side_effect=dashboard)
        app.read_filter = Mock(side_effect=filter_read)
        with patch('neto_incident_monitor.threatened_api.read_threats', side_effect=threats):
            self.assertEqual(self.serve_until_idle(), 50)
            self.assertEqual(order, ['dashboard', 'threatened', 1, 'threatened', 'dashboard', 2])
            self.assertEqual(self.session.cycle.deadlines['dashboard'], 380)
            self.assertEqual(self.session.cycle.deadlines['inc'], 3920)
            timing = app.read_dashboard_request.call_args.kwargs['schedule']
            self.assertEqual(timing['lateness_ms'], 140_000)
            self.assertEqual(timing['delay_reason'], 'threatened')

            self.session.update_intervals({'inc': 3600, 'task': 3600, 'dashboard': 15, 'threatened': 60})
            self.assertEqual(self.serve_until_idle(), 15)
            self.assertEqual(self.session.cycle.deadlines['dashboard'], 335)


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
