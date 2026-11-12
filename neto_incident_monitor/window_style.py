"""Style and activate native Windows windows."""
import ctypes
import sys
import tkinter as tk
from ctypes import wintypes
from neto_incident_monitor.theme import BG, TEXT


def colorref(value):
    red, green, blue = (int(value[i:i + 2], 16) for i in (1, 3, 5))
    return red | (green << 8) | (blue << 16)


def _frame_handle(user32, window):
    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetAncestor.restype = wintypes.HWND
    return user32.GetAncestor(window.winfo_id(), 2)


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
