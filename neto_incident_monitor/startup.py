"""Per-user Windows startup registration; no administrator rights required."""
import subprocess
import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def startup_command():
    if getattr(sys, "frozen", False):
        return subprocess.list2cmdline([sys.executable])
    python = Path(sys.executable)
    window_python = python.with_name("pythonw.exe")
    return subprocess.list2cmdline([str(window_python if window_python.exists() else python),
                                   str(Path(__file__).resolve().parent.parent / "launcher.pyw")])


def startup_entry_name(packaged=None):
    if packaged is None:
        packaged = getattr(sys, "frozen", False)
    return "NetoIncidentMonitor" if packaged else "NetoIncidentMonitorSource"


def windows_startup_status():
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_QUERY_VALUE) as key:
            command, value_type = winreg.QueryValueEx(key, startup_entry_name())
    except FileNotFoundError:
        return "disabled"
    return "current" if value_type == winreg.REG_SZ and command == startup_command() else "stale"


def set_windows_startup(enabled, *, packaged=None):
    import winreg

    name = startup_entry_name(packaged)
    if enabled:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, startup_command())
    else:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, name)
        except FileNotFoundError:
            pass


def reconcile_windows_startup():
    status = windows_startup_status()
    if status == "stale":
        set_windows_startup(True)
        return "repaired"
    return status
