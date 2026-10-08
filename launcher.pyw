"""Window-only entry point with local rotating diagnostic logs."""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import runpy
import sys

from neto_incident_monitor.runtime_paths import ROOT, DATA


class LogStream:
    def __init__(self, level):
        self.level = level
        self.encoding = "utf-8"

    def write(self, message):
        if message.strip():
            logging.getLogger("console").log(self.level, message.rstrip())
        return len(message)

    def flush(self):
        for handler in logging.getLogger().handlers:
            handler.flush()

    def isatty(self):
        return False


def main():
    previous_stdout, previous_stderr = sys.stdout, sys.stderr
    handler = None
    try:
        data = DATA
        data.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(data / "monitor.log", maxBytes=2_000_000,
                                      backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)
        sys.stdout = LogStream(logging.INFO)
        sys.stderr = LogStream(logging.ERROR)
        logging.info("Uruchomienie aplikacji bez konsoli")
        if "--smoke-test" in sys.argv:
            from tools.package_smoke import main as smoke_main
            smoke_main(Path(sys.argv[sys.argv.index("--smoke-test") + 1]))
        else:
            from neto_incident_monitor.app import main as app_main
            app_main()
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
        logging.info("Zakończenie aplikacji")
        sys.stdout, sys.stderr = previous_stdout, previous_stderr
        if handler is not None:
            logging.getLogger().removeHandler(handler)
            handler.close()


if __name__ == "__main__":
    main()
