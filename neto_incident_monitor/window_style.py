"""Style and activate native Windows windows."""
import ctypes
import os
import sys
import tkinter as tk
from ctypes import wintypes
from dataclasses import dataclass
from neto_incident_monitor.theme import BG, TEXT


def colorref(value):
    red, green, blue = (int(value[i:i + 2], 16) for i in (1, 3, 5))
    return red | (green << 8) | (blue << 16)


def _frame_handle(user32, window):
    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetAncestor.restype = wintypes.HWND
    return user32.GetAncestor(window.winfo_id(), 2)


def window_is_foreground(window):
    if sys.platform != 'win32':
        focused = window.focus_displayof()
        return focused is not None and focused.winfo_toplevel() is window
    user32 = ctypes.WinDLL('user32')
    user32.GetForegroundWindow.restype = wintypes.HWND
    hwnd = _frame_handle(user32, window)
    return bool(hwnd and user32.GetForegroundWindow() == hwnd)


def restore_foreground(api, hwnd):
    """Restore focus without changing global Windows foreground-lock settings."""
    api.GetForegroundWindow.restype = wintypes.HWND
    api.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    api.SetForegroundWindow.argtypes = [wintypes.HWND]
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


def activate_window(window):
    """Activate the mapped Tk frame and confirm Windows gave it the foreground."""
    if sys.platform != 'win32':
        window.focus_force()
        return window.focus_displayof() is not None
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    hwnd = _frame_handle(user32, window)
    if not hwnd:
        return False
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    if user32.GetForegroundWindow() != hwnd:
        user32.SetForegroundWindow(hwnd)
        if user32.GetForegroundWindow() != hwnd:
            restore_foreground(user32, hwnd)
    if user32.GetForegroundWindow() != hwnd:
        return False
    window.focus_force()
    return True


@dataclass(frozen=True)
class WindowPresentation:
    exposure: str
    foreground: bool = False


class MainWindowPresentation:
    """Present the main frame without activating it again on shell focus events."""

    def __init__(self, window):
        self.window = window
        self._raised = None
        self._api = None

    def _native(self):
        if self._api is None:
            api = ctypes.WinDLL('user32')
            hwnd = wintypes.HWND
            api.GetForegroundWindow.restype = hwnd
            api.IsWindowVisible.argtypes = [hwnd]
            api.IsWindowEnabled.argtypes = [hwnd]
            api.IsIconic.argtypes = [hwnd]
            api.GetWindowRect.argtypes = [hwnd, ctypes.POINTER(wintypes.RECT)]
            api.WindowFromPoint.argtypes = [wintypes.POINT]
            api.WindowFromPoint.restype = hwnd
            api.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
            api.MonitorFromPoint.restype = wintypes.HMONITOR
            api.GetWindowLongW.argtypes = [hwnd, ctypes.c_int]
            api.GetWindowLongW.restype = wintypes.LONG
            api.GetWindowThreadProcessId.argtypes = [hwnd, ctypes.POINTER(wintypes.DWORD)]
            api.SetWindowPos.argtypes = [hwnd, hwnd, ctypes.c_int, ctypes.c_int,
                                         ctypes.c_int, ctypes.c_int, wintypes.UINT]
            api.ShowWindow.argtypes = [hwnd, ctypes.c_int]
            self._api = api
        return self._api

    @staticmethod
    def _raise(api, hwnd, after):
        flags = 0x0001 | 0x0002 | 0x0010 | 0x0200  # NOSIZE | NOMOVE | NOACTIVATE | NOOWNERZORDER
        return bool(api.SetWindowPos(hwnd, after, 0, 0, 0, 0, flags))

    def activate(self):
        """Restore on explicit requests, then activate and raise the mapped frame."""
        if sys.platform != 'win32':
            self.window.lift()
            return activate_window(self.window)
        api = self._native()
        hwnd = _frame_handle(api, self.window)
        if not hwnd or not api.IsWindowVisible(hwnd):
            return False
        if api.IsIconic(hwnd):
            api.ShowWindow(hwnd, 9)  # SW_RESTORE
        if not activate_window(self.window):
            return False
        self._raise(api, hwnd, 0)  # HWND_TOP, within the window's current band
        return True

    def inspect(self):
        if sys.platform != 'win32':
            state = self.window.state()
            exposure = {'iconic': 'minimized', 'withdrawn': 'hidden'}.get(state, 'unavailable')
            return WindowPresentation(exposure, window_is_foreground(self.window))
        api = self._native()
        hwnd = _frame_handle(api, self.window)
        if not hwnd or not api.IsWindowVisible(hwnd):
            return WindowPresentation('hidden')
        if api.IsIconic(hwnd):
            return WindowPresentation('minimized')
        foreground = api.GetForegroundWindow() == hwnd
        bounds = wintypes.RECT()
        if not api.GetWindowRect(hwnd, ctypes.byref(bounds)) or (
                bounds.right <= bounds.left or bounds.bottom <= bounds.top):
            return WindowPresentation('unavailable', foreground)
        hits = []
        for x in (2, 4, 6):
            for y in (2, 4, 6):
                point = wintypes.POINT(bounds.left + (bounds.right - bounds.left) * x // 8,
                                       bounds.top + (bounds.bottom - bounds.top) * y // 8)
                if api.MonitorFromPoint(point, 0):  # MONITOR_DEFAULTTONULL
                    hit = api.WindowFromPoint(point)
                    hits.append(api.GetAncestor(hit, 2) if hit else None)
        if not hits:
            exposure = 'off_screen'
        elif all(hit == hwnd for hit in hits):
            exposure = 'exposed'
        elif hwnd in hits:
            exposure = 'partly_covered'
        elif len(hits) >= 5 and len(set(hits)) == 1 and hits[0] and api.GetWindowLongW(hits[0], -20) & 8:
            # A single topmost window covers all sampled points. Don't raise above our own dialogs.
            pid = wintypes.DWORD()
            api.GetWindowThreadProcessId(hits[0], ctypes.byref(pid))
            exposure = 'covered_topmost' if pid.value not in (0, os.getpid()) else 'covered'
        else:
            exposure = 'covered'
        return WindowPresentation(exposure, foreground)

    def uncover(self, presentation):
        """Borrow the topmost band only while the already active main frame is covered."""
        if (sys.platform != 'win32' or not presentation.foreground
                or presentation.exposure != 'covered_topmost' or self._raised is not None):
            return False
        api = self._native()
        hwnd = _frame_handle(api, self.window)
        if (not hwnd or api.GetForegroundWindow() != hwnd or api.IsIconic(hwnd) or not api.IsWindowEnabled(hwnd)
                or api.GetWindowLongW(hwnd, -20) & 8):  # GWL_EXSTYLE, WS_EX_TOPMOST
            return False
        if self._raise(api, hwnd, -1):  # HWND_TOPMOST
            self._raised = hwnd
            return True
        return False

    def release(self):
        if self._raised is not None and self._raise(self._native(), self._raised, -2):  # HWND_NOTOPMOST
            self._raised = None
            return True
        return False

    def raise_needs_release(self):
        if self._raised is None:
            return False
        api = self._native()
        return (api.GetForegroundWindow() != self._raised or api.IsIconic(self._raised)
                or not api.IsWindowVisible(self._raised))


def move_popup(window, x, y):
    """Use signed desktop coordinates, including monitors left of the primary."""
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                  ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    hwnd = _frame_handle(user32, window)
    user32.SetWindowPos(hwnd, None, x, y, 0, 0, 0x0015)  # NOSIZE | NOZORDER | NOACTIVATE


def apply_window_style(window):
    if sys.platform != "win32" or not window.winfo_exists():
        return
    from neto_incident_monitor.runtime_paths import ROOT
    icon = ROOT / "assets" / "netology-icon.ico"
    if icon.exists():
        window.iconbitmap(str(icon))
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    hwnd = _frame_handle(user32, window)
    if not hwnd:
        return
    dwm = ctypes.WinDLL("dwmapi")
    dwm.DwmSetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    dwm.DwmSetWindowAttribute.restype = ctypes.c_long
    # Unsupported attributes on older Windows versions are harmless no-ops.
    for attribute, value in ((20, 1), (34, colorref("#424751")),
                             (35, colorref(BG)), (36, colorref(TEXT))):
        data = wintypes.DWORD(value)
        dwm.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(data), ctypes.sizeof(data))


def install_window_style(root):
    def mapped(event):
        if isinstance(event.widget, (tk.Tk, tk.Toplevel)):
            event.widget.after_idle(lambda window=event.widget: apply_window_style(window))
    root.bind_class("Toplevel", "<Map>", mapped, add="+")
    root.bind("<Map>", mapped, add="+")
    root.after_idle(lambda: apply_window_style(root))
