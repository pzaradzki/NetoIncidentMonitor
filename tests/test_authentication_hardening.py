import json
import logging
import queue
import sys
import threading
import unittest
import runpy
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from playwright.sync_api import sync_playwright, Locator, TimeoutError, Error
from neto_incident_monitor.app import App, open_login_target, wait_for_login, LoginTargetUnavailable
from neto_incident_monitor.authentication import authentication_required, login_surface, install_input_guard
from neto_incident_monitor.automatic_login import AutomaticLogin
from neto_incident_monitor.login_diagnostics import LoginDiagnostics, safe_facts, error_facts, _logger
from neto_incident_monitor.pagination import AuthenticationRequired
from neto_incident_monitor.safe_logging import SafeExceptionFormatter


TARGET = 'https://adeo.service-now.com/incident_list.do'


class AuthenticationHardeningTests(unittest.TestCase):
    def test_inline_login_and_foreign_frames_are_detected(self):
        frame = Mock()
        frame.locator.return_value.count.return_value = 1
        page = Mock(url=TARGET, frames=[frame])
        self.assertTrue(authentication_required(page, TARGET))
        frame.locator.return_value.count.return_value = 0
        self.assertFalse(authentication_required(page, TARGET))

    def test_popup_detection_ignores_unrelated_tabs(self):
        page = Mock(url=TARGET)
        popup = Mock(url='https://idpb2e.adeo.com/login')
        popup.is_closed.return_value = False
        popup.opener.return_value = None
        page.context.pages = [page, popup]
        self.assertIs(login_surface(page, TARGET), page)
        popup.opener.return_value = page
        self.assertIs(login_surface(page, TARGET), popup)
        popup.is_closed.return_value = True
        self.assertIs(login_surface(page, TARGET), page)

    def test_initial_timeout_preserves_sso_form(self):
        page = Mock(url='https://idpb2e.adeo.com/login')
        with patch('neto_incident_monitor.app.navigate', side_effect=TimeoutError('PRIVATE_TOKEN')) as navigate:
            self.assertTrue(open_login_target(page, TARGET, threading.Event()))
        navigate.assert_called_once()

    def test_initial_network_failure_has_bounded_retries(self):
        page = Mock(url='chrome-error://chromewebdata/')
        with patch('neto_incident_monitor.app.navigate', side_effect=Error('PRIVATE_TOKEN')) as navigate:
            with self.assertRaises(LoginTargetUnavailable):
                open_login_target(page, TARGET, threading.Event())
        self.assertEqual(navigate.call_count, 3)

    def test_stop_during_navigation_retry_prevents_further_attempts(self):
        stop = threading.Event()
        page = Mock(url='about:blank')
        page.wait_for_timeout.side_effect = lambda _: stop.set()
        with patch('neto_incident_monitor.app.navigate', side_effect=Error('offline')) as navigate:
            self.assertFalse(open_login_target(page, TARGET, stop))
        navigate.assert_called_once()

    def test_confirmed_window_is_not_restored_again_when_user_minimizes(self):
        page = Mock()
        page.is_closed.return_value = False
        stop = Mock()
        stop.is_set.side_effect = [False, False, False, True]
        window = Mock()
        window.is_visible.side_effect = [True, False]
        with patch('neto_incident_monitor.app.authentication_page', return_value=True), \
                patch('neto_incident_monitor.app.time.monotonic', side_effect=[0, 21]), \
                patch('neto_incident_monitor.app.set_chromium_window_state'):
            self.assertFalse(wait_for_login(page, TARGET, stop, browser_window=window))
        window.show.assert_called_once()
        self.assertEqual(window.is_visible.call_count, 1)

    def test_failed_window_restoration_alerts_once_and_stops_stealing_focus(self):
        page = Mock()
        page.is_closed.return_value = False
        stop = Mock()
        stop.is_set.side_effect = [False] * 5 + [True]
        window = Mock()
        window.is_visible.return_value = False
        alert = Mock()
        with patch('neto_incident_monitor.app.authentication_page', return_value=True), \
                patch('neto_incident_monitor.app.time.monotonic', side_effect=[0, 21, 23, 25, 27]), \
                patch('neto_incident_monitor.app.set_chromium_window_state'):
            self.assertFalse(wait_for_login(page, TARGET, stop, browser_window=window,
                                            on_visibility_failure=alert))
        self.assertEqual(window.show.call_count, 3)
        alert.assert_called_once()

    def test_unrecognized_list_ends_with_actionable_error(self):
        page = Mock(url=TARGET, frames=[Mock(url=TARGET)])
        page.is_closed.return_value = False
        with patch('neto_incident_monitor.app.authentication_page', return_value=False), \
                patch('neto_incident_monitor.app.collect', return_value={}), \
                patch('neto_incident_monitor.app.empty_list', return_value=False), \
                patch('neto_incident_monitor.app.time.monotonic', side_effect=[0, 0, 181]):
            with self.assertRaises(LoginTargetUnavailable):
                wait_for_login(page, TARGET, threading.Event())

    def test_repeated_list_inspection_errors_do_not_bypass_deadline(self):
        page = Mock(url=TARGET, frames=[Mock(url=TARGET)])
        page.is_closed.return_value = False
        with patch('neto_incident_monitor.app.authentication_page', return_value=False), \
                patch('neto_incident_monitor.app.collect', side_effect=Error('PRIVATE_TOKEN')), \
                patch('neto_incident_monitor.app.time.monotonic', side_effect=range(0, 1000, 100)):
            with self.assertRaises(LoginTargetUnavailable):
                wait_for_login(page, TARGET, threading.Event())

    def test_diagnostic_allowlist_discards_arbitrary_credentials(self):
        secret = 'PRIVATE_LOGIN_PASSWORD_TOKEN'
        self.assertEqual(safe_facts({'login': secret, 'password': secret, 'url': secret,
                                    'reason': secret, 'origin': secret, 'tile': secret, 'tile_state': secret,
                                    'score_source': secret, 'button_available': secret, 'value': 123,
                                    'password_count': secret, 'error_type': secret}),
                         {'error_type': 'Error'})
        with self.assertLogs(_logger, level='INFO') as captured:
            log = LoginDiagnostics()
            log.record('blocked', reason=secret, login=secret)
            log.record(secret, password=secret)
        self.assertNotIn(secret, '\n'.join(captured.output))

    def test_error_classification_does_not_retain_sensitive_message(self):
        for message, expected in (
                ('ProcessSingleton PRIVATE_LOGIN', 'profile_locked'),
                ("Executable doesn't exist PRIVATE_PASSWORD", 'browser_missing'),
                ('net::ERR_CERT_AUTHORITY_INVALID PRIVATE_TOKEN', 'network_tls'),
                ('Execution context was destroyed PRIVATE_TOKEN', 'document_changed'),
                ('strict mode violation PRIVATE_LOGIN', 'ambiguous_locator')):
            facts = safe_facts(error_facts(Error(message)))
            self.assertEqual(facts['error_category'], expected)
            self.assertNotIn('PRIVATE_', json.dumps(facts))

    def test_readiness_diagnostics_keep_only_fixed_codes(self):
        from neto_incident_monitor.login_diagnostics import readiness_facts
        for message, expected in (
                ('overlay intercepts pointer events PRIVATE_TOKEN', 'covered'),
                ('element is not stable PRIVATE_PASSWORD', 'unstable'),
                ('element is outside of the viewport PRIVATE_LOGIN', 'outside_viewport')):
            facts = readiness_facts(Error(message))
            self.assertEqual(facts['readiness_reason'], expected)
            self.assertEqual(safe_facts(facts), facts)
            with self.assertLogs(_logger, level='INFO') as captured:
                LoginDiagnostics().record('submit_waiting_ready', **facts)
            self.assertNotIn('PRIVATE_', '\n'.join(captured.output))

    def test_browser_launch_failure_does_not_expose_exception_in_monitor_log(self):
        app = App.__new__(App)
        app.stop = threading.Event()
        app.events = queue.Queue()
        playwright = MagicMock()
        playwright.__enter__.return_value.chromium.launch_persistent_context.side_effect = Error(
            'ProcessSingleton PRIVATE_LOGIN PRIVATE_PASSWORD SAMLRequest=PRIVATE_TOKEN')
        with patch('playwright.sync_api.sync_playwright', return_value=playwright), \
                patch('neto_incident_monitor.filter_state.FilterState'), \
                self.assertLogs('servicenow', level='ERROR') as monitor, \
                self.assertLogs(_logger, level='INFO') as diagnostic:
            app._monitor_browser({})
        self.assertNotIn('PRIVATE_', '\n'.join(monitor.output + diagnostic.output))
        self.assertIn('profile_locked', '\n'.join(diagnostic.output))

    def test_exception_formatter_excludes_message_source_and_cached_trace(self):
        try:
            raise RuntimeError('PRIVATE_PASSWORD SAMLRequest=PRIVATE_TOKEN')
        except RuntimeError:
            record = logging.LogRecord('servicenow', logging.ERROR, __file__, 1,
                                       'Stały komunikat', (), sys.exc_info())
        record.exc_text = 'PRIVATE_CACHED_EXCEPTION'
        result = SafeExceptionFormatter('%(message)s').format(record)
        self.assertNotIn('PRIVATE_', result)
        self.assertIn('RuntimeError', result)
        self.assertIn('test_authentication_hardening.py', result)

    def test_console_capture_never_persists_raw_library_output(self):
        launcher = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'launcher.pyw'),
                                 run_name='test_launcher')
        stream = launcher['LogStream'](logging.ERROR)
        secret = 'PRIVATE_LOGIN PRIVATE_PASSWORD SAMLRequest=PRIVATE_TOKEN'
        with self.assertLogs('console', level='ERROR') as captured:
            self.assertEqual(stream.write(secret), len(secret))
        self.assertNotIn('PRIVATE_', '\n'.join(captured.output))

    def test_network_diagnostics_store_category_without_url_or_failure_message(self):
        page = Mock()
        callbacks = {}
        page.on.side_effect = lambda event, callback: callbacks.update({event: callback})
        with self.assertLogs(_logger, level='INFO') as captured:
            diagnostics = LoginDiagnostics()
            detach = diagnostics.attach(page)
            request = Mock(resource_type='document', failure='net::ERR_NAME_NOT_RESOLVED PRIVATE_PASSWORD')
            callbacks['requestfailed'](request)
            callbacks['response'](Mock(request=request, status=403))
            detach()
        output = '\n'.join(captured.output)
        self.assertNotIn('PRIVATE_', output)
        self.assertIn('dns', output)
        self.assertIn('403', output)
        self.assertEqual(page.remove_listener.call_count, 3)
        records = [json.loads(r.getMessage()) for r in captured.records]
        self.assertEqual(len({r['trace'] for r in records}), 1)
        self.assertEqual([r['sequence'] for r in records], [1, 2, 3])

    def test_dashboard_reauthenticates_once_and_retries_interrupted_section(self):
        from neto_incident_monitor.dashboard import TITLES, HELD_TITLES, REQUEST_TITLES
        for repeated_failure in (False, True):
            with self.subTest(repeated_failure=repeated_failure):
                app = App.__new__(App)
                app.stop = threading.Event()
                app.events = queue.Queue()
                app.dashboard_requests = queue.Queue()
                app.dashboard_requests.put((1, 2026, 10))
                app.monitor_settings = {'urls': [TARGET]}
                app.restore_login = Mock(return_value=True)
                result = {t: 0 for t in TITLES}
                attempts = [AuthenticationRequired(), AuthenticationRequired() if repeated_failure else result]
                with patch('neto_incident_monitor.dashboard.read_dashboard', side_effect=attempts) as read, \
                        patch('neto_incident_monitor.dashboard.read_held_dashboard', return_value={t: 0 for t in HELD_TITLES}), \
                        patch('neto_incident_monitor.dashboard.read_requests_dashboard', return_value={t: 0 for t in REQUEST_TITLES}):
                    app.read_dashboard_request(Mock())
                self.assertEqual(read.call_count, 2)
                app.restore_login.assert_called_once()
                results = [value for kind, value in app.events.queue if kind == 'dashboard_result']
                self.assertEqual(bool(results[-1][4]), repeated_failure)

    def test_typing_during_automatic_click_prevents_submission_and_manual_click_still_works(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                context = browser.new_context()
                install_input_guard(context)
                page = context.new_page()
                page.route('**/*', lambda route: route.fulfill(
                    content_type='text/html; charset=utf-8', body='<input type="password" value="dummy">'
                    '<button onclick="window.clicks=(window.clicks||0)+1">Zaloguj się</button>'))
                page.goto('https://idpb2e.adeo.com/login')
                automatic = AutomaticLogin()
                automatic.account_clicked = True
                original_click = Locator.click
                def click(locator, **kwargs):
                    if not kwargs.get('trial'):
                        page.locator('input[type=password]').press('x')
                    original_click(locator, **kwargs)
                with patch.object(Locator, 'click', click):
                    automatic.step(page)
                self.assertFalse(page.evaluate('!!window.clicks'))
                automatic.step(page)
                self.assertTrue(automatic.blocked)
                page.get_by_role('button').click()
                self.assertEqual(page.evaluate('window.clicks'), 1)
            finally:
                browser.close()

    def test_automatic_form_submit_is_not_misclassified_as_manual(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                context = browser.new_context()
                install_input_guard(context)
                page = context.new_page()
                page.route('**/*', lambda route: route.fulfill(
                    content_type='text/html; charset=utf-8',
                    body='<form onsubmit="event.preventDefault();window.sends=(window.sends||0)+1">'
                         '<input type="password" value="dummy"><button>Zaloguj się</button></form>'))
                page.goto('https://idpb2e.adeo.com/login')
                automatic = AutomaticLogin()
                automatic.account_clicked = True
                automatic.step(page)
                automatic.step(page)
                self.assertTrue(automatic.submitted)
                self.assertFalse(automatic.blocked)
                self.assertEqual(page.evaluate('window.sends'), 1)
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main()
