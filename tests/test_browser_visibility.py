import unittest
from unittest.mock import Mock, patch

from neto_incident_monitor.app import wait_for_login


class BrowserVisibilityTests(unittest.TestCase):
    def test_manual_login_restores_window_after_redirect_grace_period(self):
        page = Mock()
        page.is_closed.return_value = False
        stop = Mock()
        stop.is_set.side_effect = [False, True]
        with patch("neto_incident_monitor.app.authentication_page", return_value=True), \
                patch("neto_incident_monitor.app.time.monotonic", side_effect=[0, 6]), \
                patch("neto_incident_monitor.app.set_chromium_window_state") as state:
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
