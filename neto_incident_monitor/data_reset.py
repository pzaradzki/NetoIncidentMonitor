"""Recoverable reset of the current installation's local runtime data."""
from pathlib import Path
import os
import re
import shutil
import stat

from neto_incident_monitor.runtime_paths import DATA, FROZEN

RUNTIME_NAMES = {
    "config.json", "config.tmp", "seen.json", "seen.tmp", "history.json", "history.tmp",
    "dashboard-cache.json", "dashboard-cache.tmp", "browser-profile",
    "history.state.sqlite3", "history.state.sqlite3-journal",
    "history.state.sqlite3-wal", "history.state.sqlite3-shm",
}
RUNTIME_EXTRA = re.compile(r"(?:(?:monitor\.log|login-diagnostics\.jsonl)(?:\.[1-9]\d*)?|dashboard-cache\.json\.[a-zA-Z0-9_-]+\.tmp)\Z")


def reject_redirect(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        raise OSError("Unsafe reset path")


def check_tree(path):
    reject_redirect(path)
    if path.is_dir():
        for child in path.iterdir():
            check_tree(child)


class DataReset:
    def __init__(self, data=DATA, packaged=FROZEN):
        self.data = Path(data).absolute()
        self.packaged = packaged
        self.marker = self.data.with_name(self.data.name + ".reset-pending")
        self.staging = self.data.with_name(self.data.name + ".reset-data")

    def pending(self):
        reject_redirect(self.marker)
        return self.marker.exists()

    def request(self):
        self.validate_paths()
        if self.staging.exists() or self.pending():
            raise OSError("Reset already pending")
        with self.marker.open("xb") as marker:
            marker.flush()
            os.fsync(marker.fileno())

    def validate_paths(self):
        for path in (*self.data.parents, self.data, self.marker, self.staging):
            reject_redirect(path)

    def finish(self):
        if not self.pending():
            return
        self.validate_paths()
        if not self.marker.is_file() or self.marker.stat().st_size != 0:
            raise OSError("Invalid reset marker")
        if self.packaged:
            if self.data.exists():
                check_tree(self.data)
                self.data.rename(self.staging)
        elif self.data.exists():
            targets = [path for path in self.data.iterdir()
                       if path.name in RUNTIME_NAMES or RUNTIME_EXTRA.fullmatch(path.name)]
            for path in targets:
                check_tree(path)
            self.staging.mkdir(exist_ok=True)
            for path in targets:
                path.rename(self.staging / path.name)
        if self.staging.exists():
            check_tree(self.staging)
            shutil.rmtree(self.staging)
        from neto_incident_monitor.startup import set_windows_startup
        set_windows_startup(False, packaged=self.packaged)
        self.marker.unlink()


def finish_with_retry(reset):
    import tkinter as tk
    from neto_incident_monitor.widgets import confirm_dialog

    while True:
        try:
            reset.finish()
            return True
        except OSError:
            window = tk.Tk()
            window.withdraw()
            try:
                retry = confirm_dialog(
                    window, "Nie udało się usunąć danych",
                    "Zamknij programy korzystające z danych monitora i ponów operację. "
                    "Po zamknięciu aplikacja ponowi reset przed następnym uruchomieniem monitoringu.",
                    confirm_text="Ponów", cancel_text="Zamknij",
                )
            finally:
                window.destroy()
            if not retry:
                return False
