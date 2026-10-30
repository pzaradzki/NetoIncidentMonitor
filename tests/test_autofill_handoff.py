import threading
import unittest
from unittest.mock import Mock, patch
from playwright.sync_api import sync_playwright
from neto_incident_monitor.app import wait_for_login
from neto_incident_monitor.automatic_login import AutomaticLogin
from neto_incident_monitor.authentication import install_input_guard


class AutofillHandoffTests(unittest.TestCase):
    def test_five_seconds_start_on_ready_field_and_show_does_not_block_late_autofill(self):
        for mode in ('late_autofill', 'manual_input'):
            with self.subTest(mode=mode), sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    context = browser.new_context()
                    install_input_guard(context)
                    page = context.new_page()
                    page.route('**/*', lambda route: route.fulfill(body='''<body><input type="password" disabled>
                        <button onclick="window.clicks=(window.clicks||0)+1">Zaloguj się</button></body>''', content_type='text/html; charset=utf-8'))
                    page.goto('https://idpb2e.adeo.com/login')
                    clock = [0]
                    diagnostics = Mock()
                    automatic = AutomaticLogin(diagnostics)
                    automatic.step(page)
                    self.assertIsNone(automatic.prefill_since)
                    page.locator('input').evaluate('el => el.disabled=false')
                    stop = threading.Event()
                    window = Mock()
                    window.is_visible.return_value = True
                    activity = Mock()
                    ticks = [0]
                    def show(**kwargs):
                        self.assertEqual(clock[0], 5)
                        self.assertFalse(automatic.blocked)
                        if mode == 'manual_input':
                            page.locator('input').fill('synthetic-test-value')
                        else:
                            page.locator('input').evaluate('''el => {
                                el.value='synthetic-test-value';
                                const matches=el.matches.bind(el);
                                el.matches=selector => selector===':-webkit-autofill' || matches(selector);
                            }''')
                    window.show.side_effect = show
                    def tick(milliseconds):
                        ticks[0] += 1
                        if ticks[0] == 1:
                            self.assertFalse(automatic.autofill_wait_expired)
                            window.show.assert_not_called()
                            clock[0] = 5
                        else:
                            clock[0] = 6
                        if ticks[0] >= 3:
                            stop.set()
                    with patch('neto_incident_monitor.automatic_login.monotonic', side_effect=lambda: clock[0]), \
                            patch('neto_incident_monitor.automatic_login.AutomaticLogin', return_value=automatic), \
                            patch.object(page, 'wait_for_timeout', side_effect=tick):
                        self.assertFalse(wait_for_login(page, 'https://adeo.service-now.com/incident_list.do',
                                                       stop, auto_login=True, browser_window=window,
                                                       on_activity=activity))
                    window.show.assert_called_once_with(activate=True)
                    self.assertEqual(automatic.submitted, mode == 'late_autofill',
                                     [c.args[0] for c in diagnostics.record.call_args_list])
                    self.assertEqual(automatic.blocked, mode == 'manual_input')
                    self.assertEqual(page.evaluate('window.clicks||0'), 1 if mode == 'late_autofill' else 0)
                finally:
                    browser.close()
