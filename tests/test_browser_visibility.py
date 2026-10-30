import unittest
from unittest.mock import Mock, patch

from neto_incident_monitor.app import wait_for_login


class BrowserVisibilityTests(unittest.TestCase):
    def test_failed_native_show_is_retried_until_confirmed(self):
        page = Mock()
        page.is_closed.return_value = False
        stop = Mock()
        stop.is_set.side_effect = [False, False, False, True]
        window = Mock()
        window.is_visible.side_effect = [False, False, True]
        with patch('neto_incident_monitor.app.authentication_page', return_value=True), \
                patch('neto_incident_monitor.app.time.monotonic', return_value=30), \
                patch('neto_incident_monitor.app.set_chromium_window_state'), \
                patch('neto_incident_monitor.login_diagnostics.LoginDiagnostics') as diagnostics:
            with patch('neto_incident_monitor.app.time.monotonic', side_effect=[0, 30, 32]):
                self.assertFalse(wait_for_login(page, 'https://adeo.service-now.com/incident_list.do',
                                                stop, browser_window=window))
        self.assertEqual(window.show.call_count, 2)
        events = [call.args[0] for call in diagnostics.return_value.record.call_args_list]
        self.assertIn('manual_login_show_retry', events)
        self.assertIn('manual_login_shown', events)

    def test_automatic_step_error_does_not_prevent_manual_window(self):
        page = Mock()
        page.is_closed.return_value = False
        stop = Mock()
        stop.is_set.side_effect = [False, True]
        window = Mock()
        window.is_visible.return_value = True
        activity = Mock()
        with patch('neto_incident_monitor.app.authentication_page', return_value=True), \
                patch('neto_incident_monitor.app.time.monotonic', return_value=30), \
                patch('neto_incident_monitor.app.set_chromium_window_state'), \
                patch('neto_incident_monitor.automatic_login.AutomaticLogin') as automatic:
            automatic.return_value.step.side_effect = RuntimeError('document changed')
            automatic.return_value.blocked = True
            self.assertFalse(wait_for_login(page, 'https://adeo.service-now.com/incident_list.do',
                                            stop, auto_login=True, browser_window=window, on_activity=activity))
        window.show.assert_called_once()
        window.show.assert_called_with(activate=True)
        page.bring_to_front.assert_called_once()
        activity.assert_called_with('Wymagane ręczne logowanie', 'waiting')

    def test_manual_login_focuses_immediately_when_automatic_login_is_disabled(self):
        page = Mock()
        page.is_closed.return_value = False
        stop = Mock()
        stop.is_set.side_effect = [False, True]
        with patch("neto_incident_monitor.app.authentication_page", return_value=True), \
                patch("neto_incident_monitor.app.time.monotonic", side_effect=[0, 0]), \
                patch("neto_incident_monitor.app.set_chromium_window_state", return_value=True) as state:
            self.assertFalse(wait_for_login(page, "https://adeo.service-now.com/incident_list.do", stop, False, True))
            state.assert_called_once_with(page, "normal")
            page.bring_to_front.assert_called_once()

    def test_restored_session_stays_in_background(self):
        page = Mock()
        page.is_closed.return_value = False
        page.frames = [Mock(url="https://adeo.service-now.com/incident_list.do")]
        stop = Mock()
        stop.is_set.return_value = False
        with patch("neto_incident_monitor.app.authentication_page", return_value=False), \
                patch("neto_incident_monitor.app.collect", return_value={"INC1": {}}), \
                patch("neto_incident_monitor.app.minimize_chromium") as minimize:
            self.assertTrue(wait_for_login(page, "https://adeo.service-now.com/incident_list.do", stop, True, True))
            minimize.assert_called_once_with(page)
            page.bring_to_front.assert_not_called()
