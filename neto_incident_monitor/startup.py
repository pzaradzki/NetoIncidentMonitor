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


def set_windows_startup(enabled):
    import winreg
    name = "NetoIncidentMonitor" if getattr(sys, "frozen", False) else "NetoIncidentMonitorSource"
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, startup_command())
        else:
            try:
                winreg.DeleteValue(key, name)
            except FileNotFoundError:
                pass
