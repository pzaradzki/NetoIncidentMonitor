import queue
import threading
import unittest
from unittest.mock import Mock, patch

from playwright.sync_api import sync_playwright, Locator, TimeoutError
from neto_incident_monitor.app import App, BrowserClosedError, LoginPopupClosed, wait_for_login
from neto_incident_monitor.authentication import install_input_guard, authenticated_session, manual_handoff
from neto_incident_monitor.automatic_login import AutomaticLogin
from neto_incident_monitor.browser_policy import BrowserOptions, BrowserRuntime
from neto_incident_monitor.browser_actions import navigate_page, wait_control
from neto_incident_monitor.pagination import Cancelled

TARGET = 'https://adeo.service-now.com/incident_list.do'


class LoginTransitionTests(unittest.TestCase):
    def runtime(self, settings):
        options = BrowserOptions(settings)
        window = Mock()
        state = Mock()
        runtime = BrowserRuntime(Mock(), options, Mock(return_value=window), state, Mock(), Mock())
        return runtime, options, window, state

    def test_login_and_dashboard_stay_visible_until_filters_start(self):
        runtime, options, window, state = self.runtime({'hide_browser': True, 'minimize_browser': True})
        runtime.set_activity('login')
        window.hide.assert_not_called()
        window.show.assert_called_with(activate=False)
        runtime.complete_login()
        window.hide.assert_not_called()
        runtime.set_activity('dashboard')
        window.show.assert_called_with(activate=False)
        runtime.set_activity('filters')
        window.hide.assert_called_once()
        window.reset_mock()
        # A manual dashboard refresh restores the already hidden native window.
        runtime.set_activity('dashboard')
        window.show.assert_called_once_with(activate=False)
        window.hide.assert_not_called()
        runtime.page.bring_to_front.assert_not_called()
        runtime.set_activity('filters')
        window.hide.assert_called_once()

    def test_visible_phases_do_not_repeat_focus_or_apply_hide_setting_changes(self):
        runtime, options, window, state = self.runtime({})
        runtime.set_activity('dashboard')
        runtime.page.bring_to_front.reset_mock()
        state.reset_mock()
        options.update(hide_browser=True, minimize_browser=True)
        runtime.commands.put('hide')
        runtime.tick()
        runtime.tick()
        window.hide.assert_not_called()
        runtime.page.bring_to_front.assert_not_called()
        state.assert_not_called()
        runtime.set_activity('filters')
        window.hide.assert_called_once()

    def test_only_explicit_show_activates_browser_during_visible_phase(self):
        runtime, _, window, _ = self.runtime({'hide_browser': True})
        runtime.set_activity('login')
        runtime.page.bring_to_front.assert_not_called()
        window.show.assert_called_with(activate=False)
        runtime.commands.put('show')
        runtime.tick()
        window.show.assert_called_with(activate=True)
        runtime.page.bring_to_front.assert_called_once()
        runtime.tick()
        runtime.page.bring_to_front.assert_called_once()
        runtime.set_activity('dashboard')
        window.show.assert_called_with(activate=False)
        runtime.page.bring_to_front.assert_called_once()

    def test_filter_visibility_uses_latest_preferences_after_dashboard(self):
        for minimized in (False, True):
            runtime, options, window, state = self.runtime({'hide_browser': True})
            runtime.set_activity('login')
            runtime.set_activity('dashboard')
            options.update(hide_browser=False, minimize_browser=minimized)
            runtime.tick()
            runtime.set_activity('filters')
            window.hide.assert_not_called()
            if minimized:
                window.minimize.assert_called_once()
            else:
                window.show.assert_called_with(activate=False)
            runtime.page.bring_to_front.assert_not_called()

    def test_reauthentication_is_visible_and_restores_dashboard_phase(self):
        runtime, options, window, state = self.runtime({'hide_browser': True})
        runtime.set_activity('filters')
        runtime.set_activity('login')
        runtime.manual_required = True
        runtime.complete_login()
        self.assertEqual(runtime.activity, 'login')
        self.assertFalse(runtime.manual_required)
        window.reset_mock()
        runtime.set_activity('dashboard')
        window.hide.assert_not_called()
        window.show.assert_called_with(activate=False)

    def test_dashboard_requests_show_browser_for_every_section_including_manual_refresh(self):
        from neto_incident_monitor.dashboard import TITLES, HELD_TITLES, REQUEST_TITLES
        app = App.__new__(App)
        app.stop = threading.Event()
        app.events = queue.Queue()
        app.dashboard_requests = queue.Queue()
        runtime, _, window, state = self.runtime({'hide_browser': True})
        app.browser_runtime = runtime
        for request in (1, 2):
            runtime.set_activity('filters')
            app.dashboard_requests.put((request, 2026, 10))
            def values(titles):
                self.assertEqual(runtime.activity, 'dashboard')
                window.show.assert_called_with(activate=False)
                return dict.fromkeys(titles, 0)
            with patch('neto_incident_monitor.dashboard.read_dashboard', side_effect=lambda *args: values(TITLES)), \
                    patch('neto_incident_monitor.dashboard.read_held_dashboard', side_effect=lambda *args: values(HELD_TITLES)), \
                    patch('neto_incident_monitor.dashboard.read_requests_dashboard', side_effect=lambda *args: values(REQUEST_TITLES)):
                app.read_dashboard_request(runtime.page)
            self.assertEqual(runtime.activity, 'dashboard')
        window.reset_mock()
        app.read_dashboard_request(runtime.page)  # No queued request: no phase change.
        window.show.assert_not_called()
        window.hide.assert_not_called()

    def test_visibility_preferences_apply_immediately_and_hiding_has_priority(self):
        runtime, options, window, state = self.runtime({})
        runtime.tick()
        state.assert_called_with(runtime.page, 'normal')
        options.update(minimize_browser=True)
        runtime.tick()
        state.assert_called_with(runtime.page, 'minimized')
        options.update(hide_browser=True)
        runtime.tick()
        window.hide.assert_called_once()
        options.update(hide_browser=False, minimize_browser=False)
        runtime.tick()
        window.show.assert_called_once_with(activate=False)

    def test_manual_login_defers_hiding_until_completion(self):
        runtime, options, window, state = self.runtime({})
        runtime.tick()
        runtime.manual_required = True
        options.update(hide_browser=True)
        runtime.tick()
        window.hide.assert_not_called()
        runtime.complete_login()
        window.hide.assert_called_once()

    def test_auto_login_toggle_does_not_change_visibility(self):
        runtime, options, window, state = self.runtime({})
        runtime.tick()
        state.reset_mock()
        options.update(auto_login=True)
        runtime.tick()
        self.assertTrue(runtime.options.snapshot()['auto_login'])
        state.assert_not_called()
        window.show.assert_not_called()

    def test_explicit_show_can_recover_manual_window_without_allowing_hide(self):
        runtime, options, window, state = self.runtime({'hide_browser': True})
        runtime.tick()
        runtime.manual_required = True
        window.reset_mock()
        runtime.commands.put('hide')
        runtime.commands.put('show')
        runtime.tick()
        window.hide.assert_not_called()
        window.show.assert_called_once_with(activate=True)
        runtime.page.bring_to_front.assert_called_once()

    def test_crash_loop_stops_after_three_backoffs(self):
        app = App.__new__(App)
        app.stop = threading.Event()
        app.events = queue.Queue()
        app._monitor_browser = Mock(side_effect=BrowserClosedError('closed'))
        with patch.object(app.stop, 'wait', return_value=False) as wait, \
                patch('neto_incident_monitor.app.time.monotonic', return_value=100):
            app.monitor({})
        self.assertEqual(app._monitor_browser.call_count, 4)
        self.assertEqual([call.args[0] for call in wait.call_args_list], [2, 4, 8])
        self.assertTrue(any(kind == 'interruption' for kind, _ in app.events.queue))

    def test_restart_budget_recovers_after_quiet_window(self):
        app = App.__new__(App)
        app.stop = threading.Event()
        app.events = queue.Queue()
        app._monitor_browser = Mock(side_effect=[BrowserClosedError('closed')] * 4 + [None])
        with patch.object(app.stop, 'wait', return_value=False) as wait, \
                patch('neto_incident_monitor.app.time.monotonic', side_effect=[0, 61, 122, 183]):
            app.monitor({})
        self.assertEqual(app._monitor_browser.call_count, 5)
        self.assertEqual([call.args[0] for call in wait.call_args_list], [2, 2, 2, 2])

    def test_slow_navigation_can_be_cancelled_without_reissuing_request(self):
        page = Mock()
        stop = threading.Event()
        page.goto.side_effect = TimeoutError('slow connection')
        page.wait_for_timeout.side_effect = lambda _: stop.set()
        with self.assertRaises(Cancelled):
            navigate_page(page, TARGET, stop)
        page.goto.assert_called_once()
        self.assertEqual(page.goto.call_args.kwargs['timeout'], 1000)

    def test_waiting_for_control_can_be_cancelled(self):
        control = Mock()
        stop = threading.Event()
        def timeout(**kwargs):
            stop.set()
            raise TimeoutError('pending')
        control.wait_for.side_effect = timeout
        with self.assertRaises(Cancelled):
            wait_control(control, stop)
        control.wait_for.assert_called_once_with(state='visible', timeout=500)

    def test_session_confirmation_does_not_require_first_filter_records(self):
        frame = Mock(url=TARGET)
        frame.locator.return_value.count.return_value = 0
        frame.evaluate.return_value = True
        page = Mock(url=TARGET, frames=[frame])
        page.is_closed.return_value = False
        with patch('neto_incident_monitor.app.collect', side_effect=AssertionError('Must not read filter to confirm session')):
            self.assertTrue(wait_for_login(page, TARGET, threading.Event()))
        self.assertTrue(authenticated_session(page, TARGET))

    def test_popup_closed_without_session_has_explicit_cancellation(self):
        page = Mock(url=TARGET)
        page.is_closed.return_value = False
        popup = Mock(url='https://idpb2e.adeo.com/login')
        popup.is_closed.return_value = True
        with patch('neto_incident_monitor.authentication.login_surface', return_value=popup), \
                patch('neto_incident_monitor.authentication.authenticated_session', return_value=False), \
                patch('neto_incident_monitor.app.time.monotonic', return_value=0):
            with self.assertRaises(LoginPopupClosed):
                wait_for_login(page, TARGET, threading.Event())

    def test_popup_cancel_stops_monitor_and_keeps_explanatory_status(self):
        app = App.__new__(App)
        app.stop = threading.Event()
        app.events = queue.Queue()
        app.browser_window = None
        with patch('neto_incident_monitor.app.wait_for_login', side_effect=LoginPopupClosed('Zamknięto okno logowania.')):
            self.assertFalse(app.restore_login(Mock(), TARGET, {}))
        self.assertTrue(app.stop.is_set())
        self.assertEqual(app.login_cancel_message, 'Zamknięto okno logowania.')

    def test_stale_identity_in_original_tab_does_not_hide_popup_cancellation(self):
        page = Mock(url=TARGET)
        page.is_closed.return_value = False
        popup = Mock(url='https://idpb2e.adeo.com/login')
        popup.is_closed.return_value = True
        with patch('neto_incident_monitor.authentication.login_surface', return_value=popup), \
                patch('neto_incident_monitor.authentication.authenticated_session', return_value=True):
            with self.assertRaises(LoginPopupClosed):
                wait_for_login(page, TARGET, threading.Event())

    def test_authenticated_popup_resumes_original_tab(self):
        page = Mock(url=TARGET, frames=[Mock(url=TARGET)])
        page.is_closed.return_value = False
        popup = Mock(url=TARGET)
        popup.is_closed.return_value = False
        with patch('neto_incident_monitor.authentication.login_surface', side_effect=[popup, page]), \
                patch('neto_incident_monitor.authentication.authenticated_session', return_value=True), \
                patch('neto_incident_monitor.app.authentication_page', return_value=False), \
                patch('neto_incident_monitor.app.navigate') as navigate:
            self.assertTrue(wait_for_login(page, TARGET, threading.Event()))
        navigate.assert_called_once()

    def test_live_toggle_reuses_guard_when_automatic_login_is_reenabled(self):
        runtime, options, _, _ = self.runtime({'auto_login': False})
        page = Mock(url='https://idpb2e.adeo.com/login')
        page.is_closed.return_value = False
        page.evaluate.return_value = False
        stop = threading.Event()
        ticks = [0]
        def pulse(_):
            ticks[0] += 1
            if ticks[0] == 1:
                options.update(auto_login=True)
            else:
                stop.set()
        page.wait_for_timeout.side_effect = pulse
        with patch('neto_incident_monitor.automatic_login.AutomaticLogin') as automatic, \
                patch('neto_incident_monitor.app.time.monotonic', return_value=0):
            automatic.return_value.blocked = False
            self.assertFalse(wait_for_login(page, TARGET, stop, runtime=runtime))
        automatic.assert_called_once()
        automatic.return_value.step.assert_called_once()

    def test_manual_link_submit_survives_navigation_and_form_replacement_is_safe(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                context = browser.new_context()
                install_input_guard(context)
                page = context.new_page()
                html = '<input type="password" value="dummy"><a id="signOnButton" onclick="window.clicks=(window.clicks||0)+1">Zaloguj się</a>'
                context.route('**/*', lambda route: route.fulfill(content_type='text/html; charset=utf-8', body=html))
                page.goto('https://idpb2e.adeo.com/login')
                page.locator('#signOnButton').click()
                self.assertTrue(manual_handoff(page))
                automatic = AutomaticLogin()
                automatic.account_clicked = True
                automatic.step(page)
                self.assertTrue(automatic.blocked)
                self.assertEqual(page.evaluate('window.clicks'), 1)
                page.goto('https://idpb2e.adeo.com/next')
                again = AutomaticLogin()
                again.account_clicked = True
                again.step(page)
                self.assertTrue(again.blocked)
                self.assertFalse(page.evaluate('!!window.clicks'))

                # A fresh page has no manual handoff, but a replaced form still
                # invalidates permission obtained from the previous selection.
                fresh = context.new_page()
                fresh.goto('https://idpb2e.adeo.com/login')
                fresh.locator('input').evaluate("el => el.value = ''")
                automatic = AutomaticLogin()
                automatic.account_clicked = True
                automatic.step(fresh)
                fresh.locator('input').evaluate("el => el.outerHTML = '<input type=password value=dummy>'")
                automatic.step(fresh)
                self.assertTrue(automatic.blocked)
                self.assertFalse(automatic.account_clicked)
                self.assertFalse(fresh.evaluate('!!window.clicks'))
                fresh.evaluate('''() => {
                    window.__netoLoginDelivery = {active: true};
                    window.__netoAccountClick = true;
                    window.dispatchEvent(new PageTransitionEvent('pageshow', {persisted: true}));
                }''')
                self.assertFalse(fresh.evaluate('window.__netoLoginDelivery.active'))
                self.assertFalse(fresh.evaluate('window.__netoAccountClick'))
                self.assertTrue(manual_handoff(fresh))
                fresh.locator('#signOnButton').click()
                self.assertEqual(fresh.evaluate('window.clicks'), 1)

                navigated = context.new_page()
                navigated.goto('https://idpb2e.adeo.com/login')
                navigated.locator('input').evaluate("el => el.value = ''")
                pending = AutomaticLogin()
                pending.account_clicked = True
                pending.step(navigated)
                navigated.reload()
                pending.step(navigated)
                self.assertTrue(pending.blocked)
                self.assertFalse(pending.account_clicked)
            finally:
                browser.close()

    def test_automatic_account_selection_can_submit_its_own_transition_form(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                context = browser.new_context()
                install_input_guard(context)
                page = context.new_page()
                html = '''<body>WITAMY<form onsubmit="event.preventDefault();window.selected=true">
                    <ul id="existingAccountsSelectionList"><li class="identifier-first__account-item">
                    <div class="identifier-first__account-name" onclick="this.closest('form').requestSubmit()">TEST</div>
                    </li></ul></form></body>'''
                page.route('**/*', lambda route: route.fulfill(content_type='text/html; charset=utf-8', body=html))
                page.goto('https://idpb2e.adeo.com/login')
                automatic = AutomaticLogin()
                automatic.step(page)
                self.assertTrue(page.evaluate('window.selected'))
                self.assertTrue(automatic.account_clicked)
                self.assertFalse(manual_handoff(page))
            finally:
                browser.close()

    def test_two_clicks_during_submission_deliver_only_one_activation(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                context = browser.new_context()
                install_input_guard(context)
                page = context.new_page()
                page.route('**/*', lambda route: route.fulfill(content_type='text/html; charset=utf-8',
                    body='<input type="password" value="dummy"><a id="signOnButton" onclick="window.clicks=(window.clicks||0)+1">Zaloguj się</a>'))
                page.goto('https://idpb2e.adeo.com/login')
                automatic = AutomaticLogin()
                automatic.account_clicked = True
                original = Locator.click
                def two_clicks(locator, **kwargs):
                    original(locator, **kwargs)
                    original(locator, **kwargs)
                with patch.object(Locator, 'click', two_clicks):
                    automatic.step(page)
                self.assertEqual(page.evaluate('window.clicks'), 1)

                # Disabling automation after inspection, before the click,
                # must prevent sending the next command.
                fresh = context.new_page()
                fresh.route('**/*', lambda route: route.fulfill(content_type='text/html; charset=utf-8',
                    body='<input type="password" value="dummy"><button onclick="window.sent=true">Zaloguj się</button>'))
                fresh.goto('https://idpb2e.adeo.com/login')
                disabled = AutomaticLogin(enabled=Mock(side_effect=[True, False]))
                disabled.account_clicked = True
                disabled.step(fresh)
                self.assertFalse(disabled.submitted)
                self.assertFalse(fresh.evaluate('!!window.sent'))
            finally:
                browser.close()
