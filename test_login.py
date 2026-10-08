import threading
import unittest
from unittest.mock import Mock, patch
from app import wait_for_login


class LoginTests(unittest.TestCase):
    def test_browser_minimize_is_independent_of_auto_login(self):
        for automatic_enabled in (False, True):
            for minimize_enabled in (False, True):
                with self.subTest(auto_login=automatic_enabled, minimize=minimize_enabled), \
                     patch('app.authentication_page', return_value=False), \
                     patch('app.collect', return_value={'INC1234567': {}}), \
                     patch('app.minimize_chromium') as minimize:
                    page = self.page()
                    wait_for_login(page, 'https://example.service-now.com/incident_list.do',
                                   threading.Event(), automatic_enabled, minimize_enabled)
                    if minimize_enabled:
                        minimize.assert_called_once_with(page)
                    else:
                        minimize.assert_not_called()

    def test_minimize_targets_current_browser_window(self):
        from app import minimize_chromium
        page = self.page()
        session = page.context.new_cdp_session.return_value
        session.send.return_value = {'windowId': 42}
        minimize_chromium(page)
        session.send.assert_any_call('Browser.setWindowBounds',
                                    {'windowId': 42, 'bounds': {'windowState': 'minimized'}})
        session.detach.assert_called_once()

    def page(self):
        page = Mock()
        page.is_closed.return_value = False
        page.frames = [Mock(url='https://example.service-now.com/incident_list.do')]
        return page

    def test_login_transition_does_not_interrupt_sso(self):
        page = self.page()
        with patch('app.authentication_page', side_effect=[True, True, False]), \
             patch('app.collect', return_value={'INC1234567': {}}), patch('app.navigate') as navigate:
            self.assertTrue(wait_for_login(page, 'https://example.service-now.com/incident_list.do', threading.Event()))
            navigate.assert_not_called()
            self.assertEqual(page.wait_for_timeout.call_count, 2)

    def test_empty_list_and_cached_session_are_ready(self):
        with patch('app.authentication_page', return_value=False), patch('app.collect', return_value={}), \
             patch('app.empty_list', return_value=True):
            self.assertTrue(wait_for_login(self.page(), 'https://example.service-now.com/incident_list.do', threading.Event()))

    def test_stop_interrupts_unrecognized_list(self):
        stop = threading.Event()
        page = self.page()
        page.wait_for_timeout.side_effect = lambda _: stop.set()
        with patch('app.authentication_page', return_value=False), patch('app.collect', return_value={}), \
             patch('app.empty_list', return_value=False):
            self.assertFalse(wait_for_login(page, 'https://example.service-now.com/incident_list.do', stop))

    def test_authenticated_home_is_opened_as_list(self):
        page = self.page()
        page.frames = [Mock(url='https://example.service-now.com/home.do')]
        def navigate(*_):
            page.frames = [Mock(url='https://example.service-now.com/incident_list.do')]
        with patch('app.authentication_page', return_value=False), patch('app.navigate', side_effect=navigate), \
             patch('app.collect', return_value={'INC1234567': {}}):
            self.assertTrue(wait_for_login(page, 'https://example.service-now.com/incident_list.do', threading.Event()))

    def test_closed_browser_is_reported(self):
        page = self.page()
        page.is_closed.return_value = True
        with self.assertRaises(RuntimeError):
            wait_for_login(page, 'https://example.service-now.com/incident_list.do', threading.Event())
