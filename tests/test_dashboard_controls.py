import json
import queue
import threading
import unittest
from unittest.mock import Mock, patch

from playwright.sync_api import sync_playwright, TimeoutError
from neto_incident_monitor.app import App
from neto_incident_monitor.browser_actions import ACTION_TICK, ready_control
from neto_incident_monitor.dashboard import click_control, operation
from neto_incident_monitor.login_diagnostics import _logger
from neto_incident_monitor.pagination import Cancelled


class DashboardControlTests(unittest.TestCase):
    def test_late_overlay_is_waited_out_without_repeating_real_click(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.route('**/*', lambda route: route.fulfill(content_type='text/html', body='''
                    <button onclick="window.clicks=(window.clicks||0)+1">Period</button>
                    <div id="overlay" style="position:fixed;inset:0;background:white"></div>
                    <script>setTimeout(() => document.querySelector('#overlay').remove(), 3000)</script>'''))
                page.goto('https://adeo.service-now.com/test-dashboard')
                control = page.get_by_role('button', name='Period')
                with self.assertRaises(TimeoutError):
                    control.click(timeout=1000)
                self.assertFalse(page.evaluate('!!window.clicks'))
                click_control(control, page, threading.Event(), timeout=6000)
                self.assertEqual(page.evaluate('window.clicks'), 1)
            finally:
                browser.close()

    def test_date_field_can_become_editable_after_one_second(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.set_content('''<input readonly><script>
                    setTimeout(() => document.querySelector('input').readOnly = false, 1600)
                    </script>''')
                control = page.locator('input')
                ready_control(control, threading.Event(), timeout=5000, editable=True)
                control.fill('2026-10-01', timeout=1000)
                self.assertEqual(control.input_value(), '2026-10-01')
            finally:
                browser.close()

    def test_readiness_wait_can_be_cancelled_before_click(self):
        stop = threading.Event()
        control = Mock()
        control.click.side_effect = TimeoutError('overlay')
        token = ACTION_TICK.set(lambda: stop.set())
        try:
            with self.assertRaises(Cancelled):
                ready_control(control, stop)
        finally:
            ACTION_TICK.reset(token)
        control.click.assert_not_called()

    def test_error_diagnostics_identify_operation_without_dom_or_exception_text(self):
        app = App.__new__(App)
        app.stop = threading.Event()
        app.events = queue.Queue()
        app.dashboard_requests = queue.Queue()
        app.dashboard_requests.put((1, 2026, 10))
        def fail(*args):
            operation('fill_start')
            raise TimeoutError('PRIVATE_LOGIN PRIVATE_TOKEN')
        with patch('neto_incident_monitor.dashboard.read_dashboard', side_effect=fail), \
                self.assertLogs(_logger, level='INFO') as captured:
            app.read_dashboard_request(Mock())
        records = [json.loads(record.getMessage()) for record in captured.records]
        failure = next(record for record in records if record['event'] == 'section_read_error')
        self.assertEqual(failure['operation'], 'fill_start')
        self.assertNotIn('PRIVATE_', '\n'.join(captured.output))
