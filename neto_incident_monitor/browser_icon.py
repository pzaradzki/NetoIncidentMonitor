"""Neto branding for application-owned Chromium windows (Windows only)."""
import ctypes
import logging
from ctypes import wintypes
from functools import lru_cache
from time import monotonic
from uuid import UUID

from neto_incident_monitor.runtime_paths import ROOT

APP_ID = 'NetoIncidentMonitor.Chromium'
APP_NAME = 'Neto Browser'
ICON = ROOT / 'assets' / 'netology-icon.ico'
THEME = ROOT / 'assets' / 'neto-browser-theme'


def browser_launch_options():
    """Load the bundled, declarative UI theme only in our Chromium profile."""
    return {
        'ignore_default_args': ['--disable-extensions'],
        'args': ['--start-minimized', f'--window-name={APP_NAME}',
                 f'--disable-extensions-except={THEME}', f'--load-extension={THEME}'],
    }


class PropertyKey(ctypes.Structure):
    _fields_ = [('fmtid', ctypes.c_ubyte * 16), ('pid', wintypes.DWORD)]


class VariantValue(ctypes.Union):
    _fields_ = [('text', ctypes.c_wchar_p),
                ('storage', ctypes.c_byte * (16 if ctypes.sizeof(ctypes.c_void_p) == 8 else 8))]


class PropVariant(ctypes.Structure):
    _anonymous_ = ('value',)
    _fields_ = [('vt', ctypes.c_ushort), ('reserved', ctypes.c_ushort * 3),
                ('value', VariantValue)]


def set_taskbar_identity(hwnd):
    """Keep Chrome's relaunch command; brand the taskbar name, icon and group."""
    ole = ctypes.OleDLL('ole32')
    try:
        initialized = ole.CoInitializeEx(None, 2)
    except OSError as error:
        # Playwright or another caller may already use a different COM
        # apartment. Reuse it without uninitializing somebody else's COM.
        if getattr(error, 'winerror', None) != -2147417850:  # RPC_E_CHANGED_MODE
            raise
        initialized = None
    store = ctypes.c_void_p()
    try:
        shell = ctypes.OleDLL('shell32')
        shell.SHGetPropertyStoreForWindow.argtypes = [wintypes.HWND, ctypes.c_void_p,
                                                      ctypes.POINTER(ctypes.c_void_p)]
        iid = (ctypes.c_ubyte * 16).from_buffer_copy(UUID('886d8eeb-8cf2-4446-8d02-cdba1dbdcf99').bytes_le)
        shell.SHGetPropertyStoreForWindow(hwnd, ctypes.byref(iid), ctypes.byref(store))
        table = ctypes.cast(store, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        set_value = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p,
                                      ctypes.POINTER(PropertyKey), ctypes.POINTER(PropVariant))(table[6])
        get_value = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p,
                                      ctypes.POINTER(PropertyKey), ctypes.POINTER(PropVariant))(table[5])
        ole.PropVariantClear.argtypes = [ctypes.POINTER(PropVariant)]
        fmtid = (ctypes.c_ubyte * 16).from_buffer_copy(UUID('9f4c2855-9f79-4b39-a8d0-e1d42de1d5f3').bytes_le)
        # Relaunch properties precede the ID so Explorer sees the Neto icon
        # when it creates the separate taskbar group. VT_LPWSTR is borrowed
        # only for SetValue; the window's property store copies the string.
        for pid, text in ((3, str(ICON) + ',0'), (4, APP_NAME), (5, APP_ID)):
            key = PropertyKey(fmtid, pid)
            current = PropVariant()
            try:
                result = get_value(store, ctypes.byref(key), ctypes.byref(current))
                unchanged = result >= 0 and current.vt == 31 and current.text == text
            finally:
                ole.PropVariantClear(ctypes.byref(current))
            if unchanged:
                continue
            value = PropVariant()
            value.vt = 31
            value.text = text
            result = set_value(store, ctypes.byref(key), ctypes.byref(value))
            if result < 0:
                raise OSError('Window branding property could not be set')
    finally:
        if store:
            ctypes.WINFUNCTYPE(wintypes.ULONG, ctypes.c_void_p)(table[2])(store)
        if initialized in (0, 1):
            ole.CoUninitialize()


@lru_cache(maxsize=1)
def icon_handles():
    # Windows keeps using these handles after WM_SETICON. Retain the two
    # handles for the application lifetime, also across browser restarts.
    api = ctypes.WinDLL('user32', use_last_error=True)
    api.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                              ctypes.c_int, ctypes.c_int, wintypes.UINT]
    api.LoadImageW.restype = wintypes.HANDLE
    handles = tuple(api.LoadImageW(None, str(ICON), 1, size, size, 0x10) for size in (16, 32))
    if not all(handles):
        for handle in handles:
            if handle:
                api.DestroyIcon.argtypes = [wintypes.HANDLE]
                api.DestroyIcon(handle)
        raise ctypes.WinError(ctypes.get_last_error())
    return handles


class BrowserIcon:
    def __init__(self):
        self._checked = {}
        self._warned = False

    def apply(self, hwnd):
        """Reapply after Chrome updates its window; never block on a hung UI."""
        now = monotonic()
        if now - self._checked.get(hwnd, -10) < 2:
            return
        self._checked[hwnd] = now
        try:
            api = ctypes.WinDLL('user32', use_last_error=True)
            api.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT,
                wintypes.WPARAM, wintypes.LPARAM, wintypes.UINT, wintypes.UINT,
                ctypes.POINTER(ctypes.c_size_t)]
            api.SendMessageTimeoutW.restype = wintypes.LPARAM
            result = ctypes.c_size_t()
            # Chrome owns its caption and changes it on navigation. Keep the
            # stable application name in Shell metadata only; WM_SETTEXT here
            # causes visible flicker as Chrome restores the active tab title.
            for kind, handle in enumerate(icon_handles()):
                if not api.SendMessageTimeoutW(hwnd, 0x80, kind, handle, 0x2, 50,
                                               ctypes.byref(result)):
                    raise OSError('Window icon message timed out')
            set_taskbar_identity(hwnd)
        except (OSError, ValueError):
            if not self._warned:
                logging.getLogger(__name__).warning('Nie udało się ustawić nazwy lub ikony Neto dla Chromium.')
                self._warned = True
