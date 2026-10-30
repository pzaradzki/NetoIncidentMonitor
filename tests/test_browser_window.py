import ctypes
import os
import sys
import tempfile
import unittest
import tkinter as tk
from ctypes import wintypes
from pathlib import Path

from playwright.sync_api import sync_playwright
from neto_incident_monitor.browser_window import BrowserWindow


@unittest.skipUnless(sys.platform == 'win32', 'Native Windows window test')
class BrowserWindowTests(unittest.TestCase):
    def test_neto_icon_is_limited_to_owned_browser_and_survives_navigation(self):
        from neto_incident_monitor.browser_icon import icon_handles, APP_NAME, browser_launch_options, THEME
        api = ctypes.WinDLL('user32')
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        api.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
        api.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        api.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        api.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        api.SendMessageW.restype = wintypes.LPARAM
        api.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]

        def title(hwnd):
            text = ctypes.create_unicode_buffer(512)
            api.GetWindowTextW(hwnd, text, len(text))
            return text.value

        def windows(pid):
            result = []
            @callback_type
            def visit(hwnd, _):
                owner = wintypes.DWORD()
                name = ctypes.create_unicode_buffer(256)
                api.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
                api.GetClassNameW(hwnd, name, len(name))
                if owner.value == pid and name.value == 'Chrome_WidgetWin_1':
                    result.append(hwnd)
                return True
            api.EnumWindows(visit, 0)
            return result

        with tempfile.TemporaryDirectory() as profile, tempfile.TemporaryDirectory() as other_profile, sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(
                profile, headless=False, **browser_launch_options())
            other = playwright.chromium.launch_persistent_context(other_profile, headless=False)
            try:
                window, other_window = BrowserWindow(context.browser), BrowserWindow(other.browser)
                owned, foreign = windows(window.pid), windows(other_window.pid)
                self.assertTrue(owned)
                self.assertTrue(foreign)
                # The declarative theme must not recolor page content or gain
                # access to authentication pages through scripts/permissions.
                import json
                manifest = json.loads((THEME / 'manifest.json').read_text(encoding='utf-8'))
                self.assertEqual(set(manifest), {'manifest_version', 'name', 'version', 'description', 'theme'})
                before = [api.SendMessageW(hwnd, 0x7f, 1, 0) for hwnd in foreign]
                foreign_titles = [title(hwnd) for hwnd in foreign]
                owned_titles = [title(hwnd) for hwnd in owned]
                self.assertEqual(owned_titles, [APP_NAME] * len(owned))
                window.is_visible()
                self.assertEqual([title(hwnd) for hwnd in owned], owned_titles)
                for hwnd in owned:
                    for kind, expected in enumerate(icon_handles()):
                        self.assertEqual(api.SendMessageW(hwnd, 0x7f, kind, 0), expected)
                context.pages[0].goto('data:text/html,<title>Fixture</title><body style="background:white;color:black">Ready</body>')
                self.assertEqual(context.pages[0].locator('body').evaluate(
                    '(el)=>[getComputedStyle(el).backgroundColor,getComputedStyle(el).color]'),
                    ['rgb(255, 255, 255)', 'rgb(0, 0, 0)'])
                context.pages[0].wait_for_timeout(100)
                navigated_titles = [title(hwnd) for hwnd in owned]
                self.assertEqual(navigated_titles, [APP_NAME] * len(owned))
                context.pages[0].evaluate("document.title = 'Changed by page script'")
                context.pages[0].wait_for_timeout(100)
                self.assertEqual([title(hwnd) for hwnd in owned], navigated_titles)
                second = context.new_page()
                second.goto('data:text/html,<title>Second tab</title>')
                second.bring_to_front()
                second.wait_for_timeout(100)
                self.assertEqual(second.title(), 'Second tab')
                self.assertEqual([title(hwnd) for hwnd in owned], navigated_titles)
                window.hide()
                self.assertFalse(window.is_visible())
                window.show(activate=False)
                self.assertTrue(window.is_visible())
                self.assertEqual(context.pages[0].title(), 'Changed by page script')
                self.assertEqual([title(hwnd) for hwnd in owned], navigated_titles)
                self.assertEqual([title(hwnd) for hwnd in foreign], foreign_titles)
                self.assertEqual([api.SendMessageW(hwnd, 0x7f, 1, 0) for hwnd in foreign], before)
                for hwnd in owned:
                    self.assertEqual(api.SendMessageW(hwnd, 0x7f, 1, 0), icon_handles()[1])
            finally:
                other.close()
                context.close()
            preferences = json.loads((Path(profile) / 'Default' / 'Preferences').read_text(encoding='utf-8'))
            theme_preferences = preferences['extensions']['theme']
            self.assertTrue(theme_preferences['id'])
            self.assertEqual(Path(theme_preferences['pack']), THEME)

    def test_foreground_input_attachment_is_always_detached(self):
        from unittest.mock import Mock, patch, call
        from neto_incident_monitor.browser_window import _restore_foreground
        api, kernel = Mock(), Mock()
        kernel.GetCurrentThreadId.return_value = 1
        api.GetWindowThreadProcessId.return_value = 2
        api.AttachThreadInput.return_value = True
        api.SetForegroundWindow.side_effect = RuntimeError('fixture')
        with patch('neto_incident_monitor.browser_window.ctypes.WinDLL', return_value=kernel):
            with self.assertRaises(RuntimeError):
                _restore_foreground(api, 10)
        self.assertEqual(api.AttachThreadInput.call_args_list, [call(1, 2, True), call(1, 2, False)])

    def test_passive_show_keeps_foreground_and_supports_browser_actions(self):
        api = ctypes.WinDLL('user32')
        api.GetForegroundWindow.restype = wintypes.HWND
        api.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        def owner(hwnd):
            pid = wintypes.DWORD()
            api.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            return pid.value
        root = tk.Tk()
        root.geometry('320x140+30+30')
        root.update()
        self.addCleanup(root.destroy)
        with tempfile.TemporaryDirectory() as profile, sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(profile, headless=False,
                                                                     args=['--start-minimized'])
            try:
                window = BrowserWindow(context.browser)
                page = context.pages[0]
                for previous_state in ('minimized', 'hidden'):
                    window.minimize() if previous_state == 'minimized' else window.hide()
                    page.wait_for_timeout(200)
                    self.assertFalse(window.is_visible(), previous_state + ' before restore')
                    root.deiconify()
                    root.lift()
                    root.focus_force()
                    root.update()
                    foreground = api.GetForegroundWindow()
                    if owner(foreground) != os.getpid():
                        self.skipTest('Windows did not grant foreground to the test app; passive focus cannot be measured reliably')
                    window.show(activate=False)
                    page.wait_for_timeout(200)
                    self.assertTrue(window.is_visible(), previous_state)
                    current = api.GetForegroundWindow()
                    self.assertEqual(current, foreground, (previous_state, owner(foreground), owner(current), window.pid))
                    page.set_content('<input><button onclick="window.clicks=1">Test</button>')
                    page.locator('input').fill('fixture')
                    page.get_by_role('button').click()
                    self.assertEqual(page.evaluate('window.clicks'), 1)
                    self.assertEqual(api.GetForegroundWindow(), foreground, 'automated input')
            finally:
                context.close()

    def test_activity_restores_real_window_and_hides_only_for_filters(self):
        from unittest.mock import Mock
        from neto_incident_monitor.browser_policy import BrowserOptions, BrowserRuntime
        from neto_incident_monitor.app import set_chromium_window_state
        with tempfile.TemporaryDirectory() as profile, sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(profile, headless=False)
            try:
                page = context.pages[0]
                window = BrowserWindow(context.browser)
                options = BrowserOptions({'hide_browser': True, 'minimize_browser': True})
                runtime = BrowserRuntime(page, options, lambda: window,
                                         set_chromium_window_state, Mock(), Mock())
                for activity, visible in (('login', True), ('dashboard', True),
                                          ('filters', False), ('dashboard', True),
                                          ('login', True), ('filters', False)):
                    runtime.set_activity(activity)
                    page.wait_for_timeout(200)
                    self.assertEqual(window.is_visible(), visible, activity)
                    runtime.tick()
                    self.assertEqual(window.is_visible(), visible, activity)
                options.update(hide_browser=False, minimize_browser=False)
                runtime.tick()
                page.wait_for_timeout(200)
                self.assertTrue(window.is_visible())
            finally:
                context.close()

    def test_hide_restore_keeps_browser_operational(self):
        with tempfile.TemporaryDirectory() as profile, sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(profile, headless=False,
                                                                     args=['--start-minimized'])
            try:
                window = BrowserWindow(context.browser)
                page = context.pages[0]
                user32 = ctypes.WinDLL('user32')
                callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
                user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
                user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
                user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
                user32.IsWindowVisible.argtypes = [wintypes.HWND]
                def visibility():
                    results = []
                    @callback_type
                    def visit(hwnd, _):
                        pid = wintypes.DWORD()
                        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                        name = ctypes.create_unicode_buffer(256)
                        user32.GetClassNameW(hwnd, name, 256)
                        if pid.value == window.pid and name.value == 'Chrome_WidgetWin_1':
                            results.append(bool(user32.IsWindowVisible(hwnd)))
                        return True
                    user32.EnumWindows(visit, 0)
                    return results
                window.hide()
                self.assertFalse(window.visible)
                page.wait_for_timeout(300)
                self.assertEqual(visibility(), [False])
                self.assertEqual(page.evaluate('2 + 2'), 4)
                # Login must remain usable while the native Chromium window is hidden.
                from neto_incident_monitor.automatic_login import AutomaticLogin
                page.route('**/*', lambda route: route.fulfill(body='OK', content_type='text/html'))
                page.goto('https://idpb2e.adeo.com/login')
                page.set_content('<input type="password" value="dummy"><button '
                                 'onclick="window.clicks=(window.clicks||0)+1">Zaloguj się</button>')
                automatic = AutomaticLogin()
                automatic.account_clicked = True
                automatic.step(page)
                self.assertTrue(automatic.submitted)
                self.assertEqual(page.evaluate('window.clicks'), 1)
                window.show()
                page.wait_for_timeout(300)
                self.assertTrue(window.is_visible())
                self.assertEqual(visibility(), [True])
                window.hide()
                page.wait_for_timeout(300)
                self.assertEqual(visibility(), [False])
            finally:
                context.close()
