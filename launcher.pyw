"""Window-only entry point with local rotating diagnostic logs."""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import runpy
import sys
import threading

from neto_incident_monitor.runtime_paths import ROOT, DATA
from neto_incident_monitor.safe_logging import SafeExceptionFormatter, thread_exception


class LogStream:
    def __init__(self, level):
        self.level = level
        self.encoding = "utf-8"

    def write(self, message):
        if message.strip():
            # Unhandled library output may contain request URLs or form values.
            logging.getLogger("console").log(self.level,
                "Przechwycono wyjście konsoli; treść pominięta (liczba znaków: %d).", len(message))
        return len(message)

    def flush(self):
        for handler in logging.getLogger().handlers:
            handler.flush()

    def isatty(self):
        return False


def main():
    previous_stdout, previous_stderr = sys.stdout, sys.stderr
    previous_thread_hook = threading.excepthook
    handler = None
    instance = None
    reset_requested = False
    smoke = "--smoke-test" in sys.argv
    try:
        if not smoke:
            from neto_incident_monitor.single_instance import SingleInstance
            from neto_incident_monitor.data_reset import DataReset, finish_with_retry
            instance = SingleInstance(DATA)
            if not instance.primary:
                instance.request_show()
                return
            if not finish_with_retry(DataReset()):
                return
        data = DATA
        data.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(data / "monitor.log", maxBytes=2_000_000,
                                      backupCount=3, encoding="utf-8")
        handler.setFormatter(SafeExceptionFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)
        threading.excepthook = thread_exception
        sys.stdout = LogStream(logging.INFO)
        sys.stderr = LogStream(logging.ERROR)
        from neto_incident_monitor import __version__
        from neto_incident_monitor.login_diagnostics import RUN_ID
        logging.info("Uruchomienie aplikacji: wersja=%s run_id=%s", __version__, RUN_ID)
        if smoke:
            from tools.package_smoke import main as smoke_main
            smoke_main(Path(sys.argv[sys.argv.index("--smoke-test") + 1]))
        else:
            from neto_incident_monitor.app import main as app_main
            reset_requested = app_main(instance)
    except Exception as exc:
        logging.exception("Błąd uruchomienia aplikacji")
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        try:
            messagebox.showerror("Neto Incident Monitor", f"Nie udało się uruchomić aplikacji: {exc}\n\nSzczegóły: {DATA / 'monitor.log'}", parent=root)
        finally:
            root.destroy()
    finally:
        logging.info("Zakończenie aplikacji: run_id=%s", locals().get("RUN_ID", "unavailable"))
        sys.stdout, sys.stderr = previous_stdout, previous_stderr
        threading.excepthook = previous_thread_hook
        if handler is not None:
            logging.getLogger().removeHandler(handler)
            handler.close()
        try:
            if reset_requested:
                from neto_incident_monitor.login_diagnostics import close_diagnostics
                close_diagnostics()
                finish_with_retry(DataReset())
        finally:
            if instance is not None:
                instance.close()


if __name__ == "__main__":
    main()
