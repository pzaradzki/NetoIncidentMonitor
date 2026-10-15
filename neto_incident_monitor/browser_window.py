"""Control only native windows owned by our Chromium browser process."""
import ctypes
from ctypes import wintypes


class BrowserWindow:
    def __init__(self, browser, visibility_changed=None):
        self.visible = True
        self.visibility_changed = visibility_changed or (lambda: None)
        session = browser.new_browser_cdp_session()
        try:
            processes = session.send("SystemInfo.getProcessInfo")["processInfo"]
            self.pid = next(int(p["id"]) for p in processes if p["type"] == "browser")
        finally:
            session.detach()

    def _apply(self, show):
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user32.ShowWindowAsync.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]

        @callback_type
        def visit(hwnd, _):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            name = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, name, len(name))
            if pid.value == self.pid and name.value == "Chrome_WidgetWin_1":
                user32.ShowWindowAsync(hwnd, 9 if show else 0)
                if show:
                    user32.SetForegroundWindow(hwnd)
            return True

        user32.EnumWindows(visit, 0)

    def hide(self):
        self._apply(False)
        self.visible = False
        self.visibility_changed()

    def show(self):
        self._apply(True)
        self.visible = True
        self.visibility_changed()
