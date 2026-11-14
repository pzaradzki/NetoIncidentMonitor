import json
import logging
from pathlib import Path
import queue
import threading
import tempfile
import unittest
from unittest.mock import Mock, patch

from playwright.sync_api import TimeoutError

from neto_incident_monitor.login_diagnostics import LoginDiagnostics, _logger
from neto_incident_monitor.pagination import AuthenticationRequired, Cancelled
from neto_incident_monitor.read_budget import CURRENT, RECOVERY
from neto_incident_monitor.section_runner import run_section


class SectionLoginRecoveryTests(unittest.TestCase):
    def run_sequence(self, sequence, restore=None, section='sla'):
        reader = Mock(side_effect=sequence)
        restore = restore or Mock(return_value=True)
        states = Mock()
        with self.assertLogs(_logger, level='INFO') as logs:
            result = run_section(Mock(), threading.Event(), reader,
                LoginDiagnostics(source='dashboard', section=section, request_id=41),
                restore, states, lambda value: value == {'value': 0})
        return result, reader, restore, states, [json.loads(r.getMessage()) for r in logs.records]

    def test_timeout_then_authentication_recovers_and_completes(self):
        for section in ('sla', 'threatened'):
            with self.subTest(section=section):
                result, reader, restore, states, records = self.run_sequence([
                    TimeoutError('PRIVATE_SECRET'), AuthenticationRequired(), {'value': 0}], section=section)
                self.assertEqual(result, {'value': 0})
                self.assertEqual(reader.call_count, 3)
                restore.assert_called_once()
                self.assertIn(unittest.mock.call('Oczekuje'), states.call_args_list)
                self.assertEqual(records[-1]['event'], 'section_read_complete')
                start = next(r for r in records if r['event'] == 'section_login_recovery_start')
                end = next(r for r in records if r['event'] == 'section_login_recovery_end')
                self.assertEqual(start['attempt'], 2)
                self.assertEqual(end['outcome'], 'returned')
                self.assertGreaterEqual(end['duration_ms'], 0)
                retry = next(r for r in records if r['event'] == 'section_read_retry' and
                             r['read_reason'] == 'authentication_required')
                self.assertEqual(retry['attempt'], 2)
                self.assertEqual(len({r['read_id'] for r in records}), 1)
                self.assertTrue(all(r['request_id'] == 41 for r in records))
                self.assertNotIn('PRIVATE_SECRET', json.dumps(records))

    def test_authentication_then_timeout_uses_independent_retry(self):
        _, reader, restore, _, _ = self.run_sequence([
            AuthenticationRequired(), TimeoutError('synthetic'), {'value': 0}])
        self.assertEqual(reader.call_count, 3)
        restore.assert_called_once()

    def test_repeated_authentication_and_timeouts_are_bounded(self):
        for sequence, reads, logins in (
                ([TimeoutError('synthetic')] * 3, 2, 0),
                ([AuthenticationRequired()] * 3, 2, 1),
                ([AuthenticationRequired(), TimeoutError('synthetic'), TimeoutError('synthetic')], 3, 1)):
            reader, restore, diagnostics = Mock(side_effect=sequence), Mock(return_value=True), Mock()
            with self.subTest(reads=reads, logins=logins), self.assertRaises((TimeoutError, AuthenticationRequired)):
                run_section(Mock(), threading.Event(), reader, diagnostics, restore, Mock(), lambda v: True)
            self.assertEqual(reader.call_count, reads)
            self.assertEqual(restore.call_count, logins)
            final = [c for c in diagnostics.record.call_args_list if c.args[0] == 'section_read_error'][-1]
            self.assertTrue(final.kwargs['final_failure'])

    def test_login_wait_is_excluded_without_resetting_active_budget(self):
        clock, remaining, recovery = [0], [], []
        def read():
            remaining.append(round(CURRENT.get().end - clock[0]))
            recovery.append(RECOVERY.get())
            clock[0] += 5
            if len(remaining) == 1:
                raise TimeoutError('synthetic')
            if len(remaining) == 2:
                raise AuthenticationRequired()
            return {'value': 0}
        def restore():
            clock[0] += 600
            return True
        with patch('neto_incident_monitor.section_runner.monotonic', side_effect=lambda: clock[0]), \
                patch('neto_incident_monitor.read_budget.monotonic', side_effect=lambda: clock[0]):
            _, _, _, _, records = self.run_sequence(read, restore)
        self.assertEqual(remaining, [39, 55, 50])
        self.assertEqual(recovery, [False, True, True])
        self.assertEqual(records[-1]['active_ms'], 15000)
        self.assertEqual(records[-1]['login_wait_ms'], 600000)

    def test_expired_budget_prevents_another_reader_or_login(self):
        for error in (TimeoutError('synthetic'), AuthenticationRequired()):
            clock = [0]
            def read():
                clock[0] = 61
                raise error
            reader, restore = Mock(side_effect=read), Mock(return_value=True)
            with self.subTest(error=type(error).__name__), \
                    patch('neto_incident_monitor.section_runner.monotonic', side_effect=lambda: clock[0]), \
                    patch('neto_incident_monitor.read_budget.monotonic', side_effect=lambda: clock[0]), \
                    self.assertRaises((TimeoutError, AuthenticationRequired)):
                run_section(Mock(), threading.Event(), reader, Mock(), restore, Mock(), lambda v: True)
            reader.assert_called_once()
            restore.assert_not_called()

    def test_stop_refusal_and_login_errors_prevent_resuming(self):
        for mode in ('stop', 'refusal', 'error', 'cancelled'):
            stop = threading.Event()
            reader = Mock(side_effect=[AuthenticationRequired(), {'value': 0}])
            def restore():
                if mode == 'stop':
                    stop.set()
                    return True
                if mode == 'error':
                    raise ValueError('PRIVATE_SECRET')
                if mode == 'cancelled':
                    raise Cancelled()
                return False
            with self.subTest(mode=mode), self.assertLogs(_logger, level='INFO') as logs, \
                    self.assertRaises((Cancelled, ValueError)):
                run_section(Mock(), stop, reader, LoginDiagnostics(section='sla'), restore, Mock(), lambda v: True)
            reader.assert_called_once()
            records = [json.loads(r.getMessage()) for r in logs.records]
            end = next(r for r in records if r['event'] == 'section_login_recovery_end')
            self.assertEqual(end['outcome'], 'error' if mode == 'error' else 'cancelled')
            self.assertNotIn('PRIVATE_SECRET', json.dumps(records))

    def test_recovery_diagnostics_are_written_safely_to_disk(self):
        from neto_incident_monitor.safe_logging import DiagnosticFileHandler
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'diagnostics.jsonl'
            handler = DiagnosticFileHandler(path, maxBytes=100000, backupCount=1, encoding='utf-8')
            handler.setFormatter(logging.Formatter('%(message)s'))
            try:
                with patch.object(_logger, 'handlers', [handler]):
                    diagnostics = LoginDiagnostics(source='dashboard', section='sla', request_id=41)
                    run_section(Mock(), threading.Event(), Mock(side_effect=[
                        TimeoutError('PRIVATE_SECRET'), AuthenticationRequired(), {'value': 0}]),
                        diagnostics, Mock(return_value=True), Mock(), lambda v: True)
            finally:
                handler.close()
            records = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
            self.assertNotIn('PRIVATE_SECRET', path.read_text(encoding='utf-8'))
            self.assertTrue(all(r['request_id'] == 41 for r in records))
            for field in ('run_id', 'read_id', 'trace'):
                self.assertEqual(len({r[field] for r in records}), 1)
            self.assertEqual(records[-1]['event'], 'section_read_complete')
            self.assertEqual(records[-1]['attempt'], 3)
            self.assertEqual(sum(r['event'] == 'section_login_recovery_start' for r in records), 1)
            self.assertEqual(sum(r['event'] == 'section_login_recovery_end' for r in records), 1)

    def test_browser_close_during_login_requeues_same_dashboard(self):
        from neto_incident_monitor.app import App, BrowserClosedError
        app = App.__new__(App)
        app.stop, app.events, app.dashboard_requests = threading.Event(), queue.Queue(), queue.Queue()
        request = (41, 2026, 11)
        app.dashboard_requests.put(request)
        app.monitor_settings = {'urls': ['https://adeo.service-now.com/incident_list.do']}
        app.restore_login = Mock(side_effect=BrowserClosedError('PRIVATE_SECRET'))
        with patch('neto_incident_monitor.analytics_config.load_config', return_value={}), \
                patch('neto_incident_monitor.dashboard_api.read_month', side_effect=AuthenticationRequired()), \
                patch('neto_incident_monitor.dashboard_api.read_held') as held, \
                self.assertRaises(BrowserClosedError):
            app.read_dashboard_request(Mock())
        self.assertEqual(app.dashboard_requests.get_nowait(), request)
        self.assertTrue(app.dashboard_requests.empty())
        held.assert_not_called()
        self.assertEqual([v for kind, v in app.events.queue if kind == 'dashboard_updating'],
                         [(*request, 'running'), (*request, 'retrying')])

    def test_recovered_dashboard_keeps_request_and_continues_other_sections(self):
        from neto_incident_monitor.app import App
        from neto_incident_monitor.dashboard import TITLES, HELD_TITLES, REQUEST_TITLES
        app = App.__new__(App)
        app.stop, app.events, app.dashboard_requests = threading.Event(), queue.Queue(), queue.Queue()
        app.dashboard_requests.put((41, 2026, 11))
        app.monitor_settings = {'urls': ['https://adeo.service-now.com/incident_list.do']}
        app.restore_login = Mock(return_value=True)
        with patch('neto_incident_monitor.analytics_config.load_config', return_value={}), \
                patch('neto_incident_monitor.dashboard_api.read_month', side_effect=[
                TimeoutError('synthetic'), AuthenticationRequired(), dict.fromkeys(TITLES, 0)]) as sla, \
                patch('neto_incident_monitor.dashboard_api.read_held', return_value=dict.fromkeys(HELD_TITLES, 0)) as held, \
                patch('neto_incident_monitor.dashboard_api.read_requests', return_value=dict.fromkeys(REQUEST_TITLES, 0)) as requests:
            app.read_dashboard_request(Mock())
        self.assertEqual(sla.call_count, 3)
        app.restore_login.assert_called_once()
        held.assert_called_once()
        requests.assert_called_once()
        events = list(app.events.queue)
        statuses = [value for kind, value in events if kind == 'dashboard_section_status']
        self.assertTrue(all(value[0] == 41 for value in statuses))
        self.assertFalse(any(value[2] == 'Błąd odczytu' for value in statuses))
        results = [value for kind, value in events if kind == 'dashboard_result']
        self.assertTrue(all(value[:3] == (41, 2026, 11) for value in results))
        self.assertEqual(set(results[-1][3]), set(TITLES) | set(HELD_TITLES) | set(REQUEST_TITLES))
        self.assertEqual([value[-1] for kind, value in events if kind == 'dashboard_updating'], ['running', 'finished'])
        self.assertTrue(app.dashboard_requests.empty())
