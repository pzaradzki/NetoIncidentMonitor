import threading
import unittest
from unittest.mock import Mock, patch

from playwright.sync_api import Error, TimeoutError
from neto_incident_monitor.browser_rendering import HiddenRendering, dashboard_target
from neto_incident_monitor.dashboard import DASHBOARD_URL, check_category
from neto_incident_monitor.dashboard_context import DashboardReadError
from neto_incident_monitor.browser_policy import BrowserRuntime, BrowserOptions
from neto_incident_monitor.pagination import Cancelled, AuthenticationRequired
from neto_incident_monitor.login_diagnostics import safe_facts, EVENTS


class RenderingTests(unittest.TestCase):
    def setUp(self):
        self.page = Mock(url=DASHBOARD_URL)
        self.page.is_closed.return_value = False
        self.log = Mock()
        self.guard = HiddenRendering(self.log)
        self.client = self.page.context.new_cdp_session.return_value
        self.auth = patch('neto_incident_monitor.authentication.authentication_required', return_value=False)
        self.auth.start()
        self.addCleanup(self.auth.stop)
        self.session = patch('neto_incident_monitor.authentication.authenticated_session', return_value=True)
        self.session.start()
        self.addCleanup(self.session.stop)
        self.addCleanup(self.guard.close)

    def test_unknown_session_defers_until_positive_confirmation(self):
        with patch('neto_incident_monitor.authentication.authenticated_session', return_value=False):
            self.guard.sync(self.page, True)
        self.page.context.new_cdp_session.assert_not_called()
        self.guard.sync(self.page, True)
        self.assertIsNotNone(self.guard.client)

    def test_only_exact_dashboard_origin_and_identity(self):
        for url in ('https://adeo.service-now.com.evil/now/platform-analytics-workspace/dashboards/',
                    'https://adeo.service-now.com/login.do', 'http' + DASHBOARD_URL[5:],
                    DASHBOARD_URL.replace('22361ad72b6a8b504b98f4c2c891bfab', 'other'),
                    DASHBOARD_URL.replace('.com/', '.com:444/'), 'https://[invalid'):
            self.assertFalse(dashboard_target(url))
        self.assertTrue(dashboard_target(DASHBOARD_URL))

    def test_one_session_ack_and_idempotent_cleanup(self):
        self.guard.sync(self.page, True)
        self.guard.sync(self.page, True)
        self.page.context.new_cdp_session.assert_called_once_with(self.page)
        self.guard.frame({'sessionId': 2, 'data': 'SYNTHETIC_SECRET'})
        self.client.send.assert_any_call('Page.screencastFrameAck', {'sessionId': 2})
        self.guard.close()
        self.guard.close()
        self.client.detach.assert_called_once()
        self.assertNotIn('SYNTHETIC_SECRET', str(self.log.record.call_args_list))
        self.log.record.assert_any_call('rendering_stop', rendering_reason='read_finished',
            duration_ms=unittest.mock.ANY, frame_count=1, ack_count=1, payload_bytes=16, cleanup_errors=0)

    def test_reentrant_stop_retains_its_own_start_time(self):
        self.guard.sync(self.page, True)
        def send(method, *args):
            if method == 'Page.stopScreencast':
                self.guard.stop('page_closed')
        self.client.send.side_effect = send
        self.guard.close()
        self.assertIsNone(self.guard.client)
        self.assertEqual(sum(c.args[0]=='rendering_stop' for c in self.log.record.call_args_list),1)

    def test_navigation_and_inline_auth_stop_capture(self):
        self.guard.sync(self.page, True)
        self.page.main_frame.url = 'https://adeo.service-now.com/login.do'
        self.guard.navigation(self.page.main_frame)
        self.assertIsNone(self.guard.client)
        self.guard.sync(self.page, True)
        with patch('neto_incident_monitor.authentication.authentication_required', return_value=True):
            self.guard.sync(self.page, True)
        self.assertIsNone(self.guard.client)

    def test_start_failure_does_not_retry_until_end_or_show(self):
        self.client.send.side_effect = Error('SYNTHETIC_TOKEN')
        for _ in range(2):
            with self.assertRaises(DashboardReadError) as caught:
                self.guard.sync(self.page, True)
            self.assertEqual(caught.exception.reason, 'rendering_unavailable')
            self.assertFalse(caught.exception.retryable)
        self.page.context.new_cdp_session.assert_called_once()
        self.assertNotIn('SYNTHETIC_TOKEN', str(self.log.record.call_args_list))
        self.client.send.side_effect = None
        self.guard.sync(self.page, False)
        self.guard.sync(self.page, True)
        self.assertIsNotNone(self.guard.client)

    def test_ack_failure_and_closed_target_do_not_escape_callback(self):
        self.guard.sync(self.page, True)
        self.client.send.side_effect = Error('SECRET')
        self.client.detach.side_effect = Error('SECRET')
        self.guard.frame({'sessionId': 1})
        with self.assertRaises(DashboardReadError):
            self.guard.sync(self.page, True)
        self.guard.close()
        self.assertFalse(self.guard.failed)

    def test_closed_page_is_left_to_existing_browser_recovery(self):
        self.guard.sync(self.page, True)
        self.guard.failed = True
        self.page.is_closed.return_value = True
        self.guard.sync(self.page, True)
        self.assertIsNone(self.guard.client)

    def test_page_replacement_and_broken_diagnostics(self):
        self.guard.sync(self.page, True)
        other = Mock(url='about:blank')
        self.log.record.side_effect = OSError('SYNTHETIC_SECRET')
        self.guard.sync(other, True)
        self.client.detach.assert_called_once()
        self.assertIsNone(self.guard.client)

    def test_runtime_show_override_survives_next_read_and_options_reset_it(self):
        options = BrowserOptions({'hide_browser': True})
        window = Mock()
        runtime = BrowserRuntime(self.page, options, lambda: window, Mock(), self.log, Mock())
        with runtime.dashboard_read(self.page, self.log):
            self.assertIsNotNone(runtime.rendering.client)
            runtime.commands.put('show')
            runtime.tick()
            self.assertIsNone(runtime.rendering.client)
        window.reset_mock()
        with runtime.dashboard_read(self.page, self.log):
            window.hide.assert_not_called()
            self.assertIsNone(runtime.rendering.client)
            options.update(minimize_browser=True)
            runtime.tick()
            self.assertIsNotNone(runtime.rendering.client)
        self.assertIsNone(runtime.rendering.client)

    def test_scope_stops_after_exception_and_manual_login_takes_focus_once(self):
        runtime = BrowserRuntime(self.page, BrowserOptions({'hide_browser': True}), Mock(), Mock(), self.log, Mock())
        with self.assertRaisesRegex(ValueError, 'original'):
            with runtime.dashboard_read(self.page, self.log):
                raise ValueError('original')
        self.assertIsNone(runtime.rendering.client)
        runtime.set_activity('dashboard')
        runtime.manual_required = True
        runtime.tick()
        runtime.tick()
        self.page.bring_to_front.assert_called_once()
        self.assertIsNone(runtime.rendering.client)

    def test_failed_hidden_read_can_be_retried_visibly_without_restart(self):
        runtime = BrowserRuntime(self.page, BrowserOptions({'hide_browser': True}), Mock(), Mock(), self.log, Mock())
        self.client.send.side_effect = Error('unsupported')
        with self.assertRaises(DashboardReadError):
            with runtime.dashboard_read(self.page, self.log):
                self.fail('Failed guard must not accept a read')
        runtime.commands.put('show')
        runtime.tick()
        with runtime.dashboard_read(self.page, self.log):
            self.assertIsNone(runtime.rendering.client)
        self.page.context.new_cdp_session.assert_called_once()

    def test_unavailable_rendering_is_not_retried_by_section_runner(self):
        from neto_incident_monitor.section_runner import run_section
        read = Mock(side_effect=DashboardReadError('rendering_unavailable', retryable=False))
        with self.assertRaises(DashboardReadError):
            run_section(self.page, threading.Event(), read, self.log, Mock(), Mock(), Mock())
        read.assert_called_once()

    def test_diagnostic_fields_are_explicitly_permitted(self):
        self.assertTrue({'rendering_start','rendering_stop','rendering_error','category_check_recovered','category_check_failed'} <= EVENTS)
        self.assertEqual(safe_facts({'rendering_reason':'ack_failed','ack_count':3,'payload_bytes':20,
            'cleanup_errors':1,'data':'SECRET','read_reason':'rendering_unavailable'}),
            {'rendering_reason':'ack_failed','ack_count':3,'payload_bytes':20,'cleanup_errors':1,'read_reason':'rendering_unavailable'})

    def test_serialized_diagnostics_never_contain_frame_or_error_payload(self):
        from neto_incident_monitor.login_diagnostics import LoginDiagnostics, _logger
        import json
        with self.assertLogs(_logger, level='INFO') as captured:
            self.guard.diagnostics = LoginDiagnostics(source='dashboard', section='sla')
            self.guard.sync(self.page, True)
            self.guard.frame({'sessionId':1,'data':'PRIVATE_PASSWORD_PRIVATE_TOKEN'})
            self.guard.close()
        records = [json.loads(record.getMessage()) for record in captured.records]
        end = next(r for r in records if r['event']=='rendering_stop')
        self.assertEqual(end['ack_count'],1)
        self.assertEqual(end['cleanup_errors'],0)
        self.assertNotIn('PRIVATE_', '\n'.join(captured.output))


class CategoryConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.page, self.checkbox, self.stop = Mock(), Mock(), threading.Event()
        self.error = Error('Locator.check: Clicking the checkbox did not change its state\nCall log: SECRET')

    def test_delivered_check_confirmed_without_second_click(self):
        self.checkbox.check.side_effect = self.error
        with patch('neto_incident_monitor.dashboard.read_control') as observe:
            check_category(self.checkbox, self.page, self.stop)
        self.checkbox.check.assert_called_once()
        observe.assert_called_once()

    def test_unconfirmed_check_retains_original_error(self):
        self.checkbox.check.side_effect = self.error
        with patch('neto_incident_monitor.dashboard.read_control', side_effect=TimeoutError('observation')):
            with self.assertRaises(Error) as result:
                check_category(self.checkbox, self.page, self.stop)
        self.assertIs(result.exception, self.error)
        self.checkbox.check.assert_called_once()

    def test_other_error_is_not_recovered(self):
        self.checkbox.check.side_effect = Error('detached')
        with patch('neto_incident_monitor.dashboard.read_control') as observe:
            with self.assertRaises(Error):
                check_category(self.checkbox, self.page, self.stop)
        observe.assert_not_called()

    def test_stop_and_authentication_are_not_masked(self):
        self.checkbox.check.side_effect = self.error
        for error in (Cancelled(), AuthenticationRequired()):
            with patch('neto_incident_monitor.dashboard.read_control', side_effect=error):
                with self.assertRaises(type(error)):
                    check_category(self.checkbox, self.page, self.stop)


class CategoryDOMTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def test_delayed_state_and_dom_replacement_need_only_one_click(self):
        for replacement in (False, True):
            with self.subTest(replacement=replacement):
                page = self.browser.new_page()
                try:
                    js = "this.outerHTML='<input id=c type=checkbox checked>'" if replacement else "this.checked=true"
                    page.set_content('<input id=c type=checkbox onclick="event.preventDefault();window.clicks=(window.clicks||0)+1;setTimeout(()=>{'+js+'},250)">')
                    with patch('neto_incident_monitor.dashboard.check_session'):
                        check_category(page.locator('#c'),page,threading.Event())
                    self.assertTrue(page.locator('#c').is_checked())
                    self.assertEqual(page.evaluate('window.clicks'),1)
                finally:
                    page.close()

    def test_real_failure_and_indeterminate_are_not_successes(self):
        for js in ('', 'setTimeout(()=>{this.checked=true;this.indeterminate=true},100)'):
            page = self.browser.new_page()
            try:
                page.set_content('<input id=c type=checkbox onclick="event.preventDefault();window.clicks=(window.clicks||0)+1;'+js+'">')
                with patch('neto_incident_monitor.dashboard.check_session'):
                    with self.assertRaises(Error):
                        check_category(page.locator('#c'),page,threading.Event())
                self.assertEqual(page.evaluate('window.clicks'),1)
            finally:
                page.close()
