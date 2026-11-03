import json
import threading
import unittest
from unittest.mock import Mock, patch
from playwright.sync_api import TimeoutError, Error
from neto_incident_monitor.section_runner import run_section
from neto_incident_monitor.read_budget import BudgetExpired
from neto_incident_monitor.login_diagnostics import LoginDiagnostics, _logger
from neto_incident_monitor.pagination import Cancelled, AuthenticationRequired
from neto_incident_monitor.browser_actions import navigate_page


class RecoveryTests(unittest.TestCase):
    def test_total_budget_is_not_restarted_on_retry(self):
        clock = [0]
        calls = []
        def read():
            calls.append(True)
            clock[0] += 35
            if len(calls) == 1:
                raise TimeoutError('PRIVATE_PASSWORD')
            return {'value': 0}  # Exceeds the total budget, even though it returned.
        with patch('neto_incident_monitor.read_budget.monotonic', side_effect=lambda: clock[0]), \
             patch('neto_incident_monitor.section_runner.monotonic', side_effect=lambda: clock[0]):
            with self.assertRaises(BudgetExpired):
                run_section(Mock(), threading.Event(), read, LoginDiagnostics(), Mock(), Mock(), lambda v: True)
        self.assertEqual(len(calls), 2)

    def test_login_time_is_excluded_and_cancelled_login_is_not_retried(self):
        clock = [0]
        reader = Mock(side_effect=[AuthenticationRequired(), {'value': 0}])
        def login():
            clock[0] += 600
            return True
        with patch('neto_incident_monitor.read_budget.monotonic', side_effect=lambda: clock[0]), \
             patch('neto_incident_monitor.section_runner.monotonic', side_effect=lambda: clock[0]):
            self.assertEqual(run_section(Mock(), threading.Event(), reader, LoginDiagnostics(), login, Mock(), lambda v: True), {'value': 0})
        reader = Mock(side_effect=AuthenticationRequired())
        with self.assertRaises(Cancelled):
            run_section(Mock(), threading.Event(), reader, LoginDiagnostics(), lambda: False, Mock(), lambda v: True)
        self.assertEqual(reader.call_count, 1)

    def test_recovered_navigation_logs_safe_cause_and_final_success(self):
        reader = Mock(side_effect=[Error('interrupted by another navigation PRIVATE_USER SAMLRequest=PRIVATE_TOKEN'), {'value': 0}])
        with self.assertLogs(_logger, level='INFO') as captured:
            run_section(Mock(), threading.Event(), reader, LoginDiagnostics(section='threatened'), Mock(), Mock(), lambda v: True)
        rows = [json.loads(r.getMessage()) for r in captured.records]
        self.assertTrue(any(r['event'] == 'section_read_retry' and r['read_reason'] == 'navigation_interrupted' for r in rows))
        self.assertEqual(rows[-1]['event'], 'section_read_complete')
        self.assertNotIn('PRIVATE_', str(captured.output))
        self.assertNotIn('SAMLRequest', str(captured.output))

    def test_interrupted_navigation_that_committed_is_not_sent_twice(self):
        page = Mock()
        page.main_frame = object()
        callbacks = {}
        page.on.side_effect = lambda event, callback: callbacks.update({event: callback})
        def goto(*args, **kwargs):
            callbacks['framenavigated'](page.main_frame)
            raise Error('interrupted by another navigation')
        page.goto.side_effect = goto
        navigate_page(page, 'https://adeo.service-now.com/', threading.Event())
        page.goto.assert_called_once()
        page.remove_listener.assert_called_once()

    def test_delayed_commit_after_interrupted_navigation_is_observed(self):
        page = Mock()
        page.main_frame = object()
        listeners, ticks = {}, []
        page.on.side_effect = lambda event, callback: listeners.update({event: callback})
        page.goto.side_effect = Error('interrupted by another navigation')
        def later(milliseconds):
            ticks.append(milliseconds)
            if len(ticks) == 2:
                listeners['framenavigated'](page.main_frame)
        page.wait_for_timeout.side_effect = later
        navigate_page(page, 'https://adeo.service-now.com/', threading.Event())
        self.assertEqual(len(ticks), 2)
        page.goto.assert_called_once()
        page.remove_listener.assert_called_once()
