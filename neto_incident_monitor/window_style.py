"""Style native Windows captions without replacing window-manager behavior."""
import ctypes
import sys
import tkinter as tk
from ctypes import wintypes
from neto_incident_monitor.theme import BG, TEXT


def colorref(value):
    red, green, blue = (int(value[i:i + 2], 16) for i in (1, 3, 5))
    return red | (green << 8) | (blue << 16)


def apply_window_style(window):
    if sys.platform != "win32" or not window.winfo_exists():
        return
    from neto_incident_monitor.runtime_paths import ROOT
    icon = ROOT / "assets" / "netology-icon.ico"
    if icon.exists():
        window.iconbitmap(str(icon))
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetAncestor.restype = wintypes.HWND
    hwnd = user32.GetAncestor(window.winfo_id(), 2)
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
