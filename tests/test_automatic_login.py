import unittest
from unittest.mock import Mock, patch
from playwright.sync_api import sync_playwright, Locator, TimeoutError as PlaywrightTimeoutError
from neto_incident_monitor.automatic_login import AutomaticLogin


class AutomaticLoginTests(unittest.TestCase):
    def test_submit_retry_requires_proof_that_no_activation_was_delivered(self):
        form = '''<input readonly value="account"><input type="password" value="dummy">
            <button onclick="window.clicks=(window.clicks||0)+1">Zaloguj się</button>'''
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.route('**/*', lambda route: route.fulfill(body='OK', content_type='text/html'))
                page.goto('https://idpb2e.adeo.com/login')
                original_click = Locator.click
                for mode in ('undelivered', 'delivered', 'new_document', 'bounded', 'late_activation', 'late_navigation'):
                    with self.subTest(mode=mode):
                        page.set_content(form)
                        page.evaluate('window.clicks = 0')
                        automatic = AutomaticLogin()
                        automatic.account_clicked = True
                        attempts = []
                        def click(locator, **kwargs):
                            attempts.append(kwargs['timeout'])
                            if mode == 'delivered':
                                original_click(locator, **kwargs)
                            if mode == 'new_document':
                                page.evaluate('delete window.__netoLoginDelivery')
                            if len(attempts) == 1 or mode == 'bounded':
                                raise PlaywrightTimeoutError('simulated click timeout')
                            original_click(locator, **kwargs)
                        with patch.object(Locator, 'click', new=click), \
                             patch('neto_incident_monitor.automatic_login.monotonic', return_value=0) as clock:
                            if mode in ('delivered', 'new_document'):
                                with self.assertRaises(PlaywrightTimeoutError):
                                    automatic.step(page)
                                self.assertTrue(automatic.submitted)
                                clock.return_value = 3
                                automatic.step(page)
                                self.assertEqual(len(attempts), 1)
                                self.assertEqual(page.evaluate('window.clicks'), int(mode == 'delivered'))
                            else:
                                automatic.step(page)
                                self.assertFalse(automatic.submitted)
                                clock.return_value = 1
                                automatic.step(page)
                                self.assertEqual(len(attempts), 1)
                                if mode == 'late_activation':
                                    page.locator('button').evaluate('el => el.click()')
                                elif mode == 'late_navigation':
                                    page.evaluate('delete window.__netoLoginDelivery')
                                clock.return_value = 2
                                automatic.step(page)
                                if mode in ('late_activation', 'late_navigation'):
                                    self.assertTrue(automatic.submitted)
                                    self.assertEqual(len(attempts), 1)
                                    self.assertEqual(page.evaluate('window.clicks'), int(mode == 'late_activation'))
                                elif mode == 'bounded':
                                    clock.return_value = 4
                                    automatic.step(page)
                                    self.assertTrue(automatic.blocked)
                                    clock.return_value = 6
                                    automatic.step(page)
                                    self.assertEqual(len(attempts), 3)
                                    self.assertEqual(page.evaluate('window.clicks'), 0)
                                else:
                                    self.assertTrue(automatic.submitted)
                                    automatic.step(page)
                                    self.assertEqual(len(attempts), 2)
                                    self.assertEqual(page.evaluate('window.clicks'), 1)
                            self.assertTrue(all(timeout == 5000 for timeout in attempts))
            finally:
                browser.close()

    def test_locked_remembered_account_without_autofill_marker(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.route('**/*', lambda route: route.fulfill(body='OK', content_type='text/html'))
                page.goto('https://idpb2e.adeo.com/resumeSAML20/idp/SSO.ping')
                form = '''<form><input readonly value="test-account"><input type="password" value="dummy">
                    <button type="button" onclick="window.clicks=(window.clicks||0)+1">Zaloguj się</button></form>'''
                page.set_content(form)
                automatic = AutomaticLogin()
                with patch('neto_incident_monitor.automatic_login.monotonic', return_value=0):
                    automatic.step(page)
                self.assertFalse(automatic.submitted)
                with patch('neto_incident_monitor.automatic_login.monotonic', return_value=6):
                    automatic.step(page)
                    automatic.step(page)
                self.assertEqual(page.evaluate('window.clicks'), 1)
                page.set_content(form)
                automatic = AutomaticLogin()
                with patch('neto_incident_monitor.automatic_login.monotonic', return_value=0):
                    automatic.step(page)
                page.locator('input[type=password]').press('End')
                page.locator('input[type=password]').press('x')
                with patch('neto_incident_monitor.automatic_login.monotonic', return_value=6):
                    automatic.step(page)
                self.assertTrue(automatic.blocked)
                self.assertFalse(automatic.submitted)
            finally:
                browser.close()

    def test_stalled_submission_is_reported_without_resubmitting(self):
        page = Mock(url='https://idpb2e.adeo.com/login')
        page.locator.return_value.inner_text.return_value = 'WITAMY'
        automatic = AutomaticLogin()
        automatic.submitted = True
        automatic.submitted_at = 0
        with patch('neto_incident_monitor.automatic_login.monotonic', return_value=31):
            automatic.step(page)
            automatic.step(page)
        self.assertTrue(automatic.blocked)
        self.assertIn('30 sekund', automatic.reason)
        page.get_by_role.assert_not_called()

    def test_insecure_login_page_is_not_inspected(self):
        page = Mock(url='http://idpb2e.adeo.com/login')
        AutomaticLogin().step(page)
        page.locator.assert_not_called()

    def test_mfa_after_submission_is_reported(self):
        page = Mock(url='https://idpb2e.adeo.com/login')
        page.locator.return_value.inner_text.return_value = 'Wprowadź kod weryfikacyjny'
        automatic = AutomaticLogin()
        automatic.submitted = True
        automatic.step(page)
        self.assertTrue(automatic.blocked)
        page.get_by_role.assert_not_called()

    def test_resumed_login_waits_for_browser_autofill_and_submits_once(self):
        page = Mock(url='https://idpb2e.adeo.com/resumeSAML20/idp/SSO.ping')
        body, passwords, anchor, buttons = Mock(), Mock(), Mock(), Mock()
        body.inner_text.return_value = 'WITAMY'
        passwords.count.return_value = 1
        passwords.first.evaluate.side_effect = [False, True, True]
        anchor.count.return_value = 0
        buttons.count.return_value = 1
        buttons.first.is_visible.return_value = True
        buttons.first.is_enabled.return_value = True
        buttons.first.evaluate.return_value = False
        page.locator.side_effect = lambda selector: body if selector=='body' else passwords if 'password' in selector else anchor
        page.get_by_role.return_value = buttons
        automatic = AutomaticLogin()
        automatic.step(page)
        self.assertFalse(automatic.blocked)
        automatic.step(page)
        automatic.step(page)
        self.assertTrue(automatic.submitted)
        buttons.first.click.assert_called_once()

    def test_failed_account_click_does_not_mark_selection_complete(self):
        page = Mock(url='https://idpb2e.adeo.com/login')
        body, passwords, accounts, name = Mock(), Mock(), Mock(), Mock()
        body.inner_text.return_value = 'WITAMY'
        passwords.count.return_value = 0
        accounts.count.return_value = 1
        accounts.first.locator.return_value = name
        name.count.return_value = 1
        name.is_visible.return_value = True
        name.click.side_effect = [RuntimeError('page transitioning'), None]
        page.locator.side_effect = lambda selector: body if selector=='body' else passwords if 'password' in selector else accounts
        automatic = AutomaticLogin()
        with patch('neto_incident_monitor.automatic_login.monotonic', side_effect=[0, 5]):
            automatic.step(page)
            self.assertFalse(automatic.account_clicked)
            automatic.step(page)
            self.assertTrue(automatic.account_clicked)
        self.assertEqual(name.click.call_count, 2)

    def test_welcome_screen_retries_are_delayed_and_bounded(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.route('**/*', lambda route: route.fulfill(body='OK', content_type='text/html'))
                page.goto('https://idpb2e.adeo.com/login')
                page.set_content('''<body>WITAMY<ul id="existingAccountsSelectionList">
                    <li class="identifier-first__account-item"><div class="identifier-first__account-name"
                    onclick="window.selected=(window.selected||0)+1">TEST USER</div></li></ul></body>''')
                automatic = AutomaticLogin()
                with patch('neto_incident_monitor.automatic_login.monotonic', side_effect=[0, 1, 5, 10, 15]):
                    for _ in range(5):
                        automatic.step(page)
                self.assertEqual(page.evaluate('window.selected'), 3)
                self.assertTrue(automatic.blocked)
                self.assertFalse(automatic.submitted)
            finally:
                browser.close()

    def test_manual_form_is_never_submitted_when_user_types(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.route('**/*', lambda route: route.fulfill(body='OK', content_type='text/html'))
            page.goto('https://idpb2e.adeo.com/login')
            page.set_content('''<input id="username"><input id="password" type="password">
                <a id="signOnButton" onclick="window.clicks=(window.clicks||0)+1">Zaloguj się</a>''')
            automatic = AutomaticLogin()
            automatic.step(page)
            page.locator('#username').fill('manual-user')
            page.locator('#password').fill('dummy')
            automatic.step(page)
            self.assertTrue(automatic.blocked)
            self.assertFalse(automatic.submitted)
            self.assertFalse(page.evaluate('!!window.clicks'))
            # Even an already filled form without a remembered-account selection
            # must stay manual from its first observation.
            automatic = AutomaticLogin()
            automatic.step(page)
            self.assertFalse(automatic.submitted)
            self.assertFalse(page.evaluate('!!window.clicks'))
            browser.close()

    def test_real_browser_autofill_single_attempt_and_safe_fallbacks(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.route('**/*', lambda route: route.fulfill(body='<body>WITAMY</body>', content_type='text/html'))
            page.goto('https://idpb2.adeo.com/login')
            form = """<body>WITAMY<input type='password' value='dummy'>
                <button onclick='window.clicks=(window.clicks||0)+1'>Zaloguj się</button></body>"""
            page.set_content(form)
            automatic = AutomaticLogin()
            automatic.account_clicked = True
            automatic.step(page)
            automatic.step(page)
            self.assertEqual(page.evaluate('window.clicks'), 1)
            page.set_content(form.replace("value='dummy'", "value=''"))
            automatic = AutomaticLogin()
            automatic.step(page)
            self.assertFalse(automatic.submitted)
            page.set_content(form.replace('WITAMY', 'Nieprawidłowe hasło'))
            automatic.step(page)
            self.assertTrue(automatic.blocked)
            page.set_content(form)
            automatic.step(page)
            self.assertFalse(automatic.submitted)
            page.set_content("<body>WITAMY<div onclick='window.selected=true'><span>12345678</span></div></body>")
            automatic = AutomaticLogin()
            automatic.step(page)
            self.assertFalse(page.evaluate('!!window.selected'))
            page.set_content('<body>WITAMY<span>12345678</span><span>87654321</span></body>')
            automatic = AutomaticLogin()
            automatic.step(page)
            self.assertFalse(automatic.account_clicked)
            page.set_content('''<body>WITAMY<ul id="existingAccountsSelectionList">
                <li class="identifier-first__account-item" onclick="window.accountSelected=(window.accountSelected||0)+1">
                  <div class="identifier-first__account-name" title="12345678">TEST USER<br>12345678</div>
                  <div class="identifier-first__remove-account" onclick="window.removed=true;event.stopPropagation()"></div>
                </li></ul></body>''')
            automatic = AutomaticLogin()
            automatic.step(page)
            automatic.step(page)
            self.assertEqual(page.evaluate('window.accountSelected'), 1)
            self.assertFalse(page.evaluate('!!window.removed'))
            page.locator('#existingAccountsSelectionList').evaluate('el => el.appendChild(el.firstElementChild.cloneNode(true))')
            automatic = AutomaticLogin()
            automatic.step(page)
            self.assertFalse(automatic.account_clicked)
            page.set_content('''<body>WITAMY<input type="password" value="dummy">
                <span id="signOnButtonSpan"><a class="btn btn-success ping-button normal allow"
                id="signOnButton" title="Zaloguj się" onclick="window.anchorClicks=(window.anchorClicks||0)+1">
                Zaloguj się</a></span></body>''')
            automatic = AutomaticLogin()
            automatic.account_clicked = True
            automatic.step(page)
            automatic.step(page)
            self.assertEqual(page.evaluate('window.anchorClicks'), 1)
            page.locator('#signOnButton').evaluate("el => el.setAttribute('aria-disabled','true')")
            automatic = AutomaticLogin()
            automatic.step(page)
            self.assertFalse(automatic.submitted)
            page.goto('https://other.example/login')
            page.set_content(form)
            automatic.step(page)
            self.assertFalse(automatic.submitted)
            browser.close()
