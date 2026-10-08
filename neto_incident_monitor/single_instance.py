"""Windows per-workspace mutex and foreground-request event."""
import ctypes
from ctypes import wintypes
import hashlib
from pathlib import Path


class SingleInstance:
    def __init__(self, workspace):
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        self.kernel.CreateMutexW.restype = wintypes.HANDLE
        self.kernel.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
        self.kernel.CreateEventW.restype = wintypes.HANDLE
        self.kernel.SetEvent.argtypes = [wintypes.HANDLE]
        self.kernel.SetEvent.restype = wintypes.BOOL
        self.kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.kernel.WaitForSingleObject.restype = wintypes.DWORD
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        digest = hashlib.sha256(str(Path(workspace).resolve()).casefold().encode()).hexdigest()[:24]
        prefix = "Local\\ServiceNowMonitor_" + digest
        # Create the event first: the second process can signal it during startup.
        self.event = self.kernel.CreateEventW(None, False, False, prefix + "_show")
        if not self.event:
            raise ctypes.WinError(ctypes.get_last_error())
        ctypes.set_last_error(0)
        self.mutex = self.kernel.CreateMutexW(None, False, prefix)
        error = ctypes.get_last_error()
        if not self.mutex:
            self.kernel.CloseHandle(self.event)
            raise ctypes.WinError(error)
        self.primary = error != 183

    def request_show(self):
        if not self.kernel.SetEvent(self.event):
            raise ctypes.WinError(ctypes.get_last_error())

    def poll(self):
        return self.kernel.WaitForSingleObject(self.event, 0) == 0

    def close(self):
        for name in ("mutex", "event"):
            handle = getattr(self, name, None)
            if handle:
                self.kernel.CloseHandle(handle)
                setattr(self, name, None)
