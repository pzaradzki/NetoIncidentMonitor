import unittest
from unittest.mock import Mock, patch

from playwright.sync_api import Error
from neto_incident_monitor.browser_rendering import HiddenRendering
from neto_incident_monitor.favorites import HOME
from neto_incident_monitor.dashboard_context import DashboardReadError
from neto_incident_monitor.browser_policy import BrowserRuntime, BrowserOptions


class RenderingTests(unittest.TestCase):
    def setUp(self):
        self.page = Mock(url=HOME)
        self.page.is_closed.return_value = False
        self.log = Mock()
        self.guard = HiddenRendering(self.log, scope='favorites')
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
        self.log.record.assert_any_call('rendering_stop', rendering_scope='favorites', rendering_reason='read_finished',
            duration_ms=unittest.mock.ANY, frame_count=1, ack_count=1, cleanup_errors=0)

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

    def test_debug_toggle_keeps_manual_login_visible_and_updates_import_rendering(self):
        options = BrowserOptions({'hide_browser': True, 'auto_login': True})
        window = Mock()
        runtime = BrowserRuntime(self.page, options, lambda: window, Mock(), self.log, Mock())
        runtime.favorites_rendering = Mock()
        with runtime.favorites_read(self.page, self.log):
            options.toggle_debug_browser()
            runtime.tick()
            options.toggle_debug_browser()
            runtime.tick()
            self.assertEqual([call.args[1] for call in runtime.favorites_rendering.sync.call_args_list],
                             [True, False, True])

        options.toggle_debug_browser()
        runtime.set_activity('login')
        runtime.manual_required = True
        window.reset_mock()
        options.toggle_debug_browser()
        runtime.tick()
        window.hide.assert_not_called()
        self.assertFalse(runtime.debug_show_browser)

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
