import ctypes
import sys
import tempfile
import unittest
from ctypes import wintypes

from playwright.sync_api import sync_playwright
from neto_incident_monitor.browser_window import BrowserWindow


@unittest.skipUnless(sys.platform == 'win32', 'Native Windows window test')
class BrowserWindowTests(unittest.TestCase):
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
                page.wait_for_timeout(300)
                self.assertEqual(visibility(), [False])
                self.assertEqual(page.evaluate('2 + 2'), 4)
                window.show()
                page.wait_for_timeout(300)
                self.assertEqual(visibility(), [True])
                window.hide()
                page.wait_for_timeout(300)
                self.assertEqual(visibility(), [False])
            finally:
                context.close()
