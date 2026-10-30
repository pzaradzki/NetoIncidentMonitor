"""Control only native windows owned by our Chromium browser process."""
import ctypes
from time import monotonic, sleep
from ctypes import wintypes


def _restore_foreground(api, hwnd):
    """Restore focus without changing global Windows foreground-lock settings."""
    current_thread = ctypes.WinDLL('kernel32').GetCurrentThreadId()
    foreground_thread = api.GetWindowThreadProcessId(api.GetForegroundWindow(), None)
    api.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
    api.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND,
                                wintypes.UINT, wintypes.UINT, wintypes.UINT]
    message = wintypes.MSG()
    api.PeekMessageW(ctypes.byref(message), None, 0, 0, 0)
    attached = False
    try:
        if foreground_thread and foreground_thread != current_thread:
            attached = bool(api.AttachThreadInput(current_thread, foreground_thread, True))
        api.SetForegroundWindow(hwnd)
    finally:
        if attached:
            api.AttachThreadInput(current_thread, foreground_thread, False)


class BrowserWindow:
    def __init__(self, browser, visibility_changed=None):
        from neto_incident_monitor.browser_icon import BrowserIcon
        self._icon = BrowserIcon()
        self.visible = True
        self._passive_ready = False
        self.visibility_changed = visibility_changed or (lambda: None)
        session = browser.new_browser_cdp_session()
        try:
            processes = session.send("SystemInfo.getProcessInfo")["processInfo"]
            self.pid = next(int(p["id"]) for p in processes if p["type"] == "browser")
        finally:
            session.detach()

    def _apply(self, show, activate=True, asynchronous=False):
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user32.ShowWindowAsync.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                      ctypes.c_int, ctypes.c_int, ctypes.c_uint]
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.IsWindow.argtypes = [wintypes.HWND]
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.IsIconic.argtypes = [wintypes.HWND]
        visible = []

        @callback_type
        def visit(hwnd, _):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            name = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, name, len(name))
            if pid.value == self.pid and name.value == "Chrome_WidgetWin_1":
                # The GUI's emergency reveal must remain asynchronous even
                # when the Chromium message loop is unresponsive.
                if not asynchronous:
                    self._icon.apply(hwnd)
                if show is not None:
                    command = 7 if show == 'minimized' else (9 if activate else 4) if show else 0
                    if asynchronous:
                        user32.ShowWindowAsync(hwnd, command)
                    elif show and not activate:
                        user32.ShowWindow(hwnd, command)
                        if show != 'minimized':
                            # Keep automatic browser work below existing app
                            # windows; never make Chromium topmost.
                            user32.SetWindowPos(hwnd, 1, 0, 0, 0, 0, 0x1 | 0x2 | 0x10)
                    else:
                        if show and activate:
                            user32.ShowWindow(hwnd, command)
                        else:
                            user32.ShowWindowAsync(hwnd, command)
                    if show and show != 'minimized' and activate:
                        _restore_foreground(user32, hwnd)
                visible.append(bool(user32.IsWindowVisible(hwnd)) and not user32.IsIconic(hwnd))
            return True

        user32.EnumWindows(visit, 0)
        return any(visible)

    def is_visible(self):
        """Check native visibility, including whether Chromium is minimized."""
        visible = self._apply(None)
        if visible != self.visible:
            self.visible = visible
            self.visibility_changed()
        return visible

    def hide(self):
        self._apply(False)
        self.visible = False
        self.visibility_changed()

    def reveal(self):
        """Post a native show request without waiting for Playwright or Chrome."""
        self._apply(True, activate=True, asynchronous=True)
        self.visibility_changed()

    def show(self, activate=True):
        if not activate and self._passive_ready and self.is_visible():
            return True
        api = ctypes.WinDLL('user32')
        api.GetForegroundWindow.restype = wintypes.HWND
        api.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        api.IsWindow.argtypes = [wintypes.HWND]
        api.SetForegroundWindow.argtypes = [wintypes.HWND]
        foreground = api.GetForegroundWindow() if not activate else None
        self._apply(True, activate=activate)
        if foreground:
            # Chrome may post a delayed activation after restoring an iconic
            # window. Protect only this short automatic transition and only
            # undo activation by our own browser PID, not another user's app.
            deadline = monotonic() + 1
            while monotonic() < deadline:
                current = api.GetForegroundWindow()
                pid = wintypes.DWORD()
                api.GetWindowThreadProcessId(current, ctypes.byref(pid))
                if current != foreground and pid.value == self.pid and api.IsWindow(foreground):
                    _restore_foreground(api, foreground)
                sleep(0.02)
        self.visible = self.is_visible()
        self._passive_ready = True
        self.visibility_changed()
        return self.visible

    def minimize(self):
        self._apply('minimized', activate=False)
        self.visible = False
        self.visibility_changed()
