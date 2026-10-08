"""Offline diagnostics for the built EXE; never uses the user's browser profile."""
import json
import tempfile
from pathlib import Path


def main(output):
    import sys
    import tkinter as tk
    import pystray
    import plyer.platforms.win.notification
    from PIL import Image
    from playwright.sync_api import sync_playwright
    from neto_incident_monitor.runtime_paths import DATA, ROOT
    from neto_incident_monitor.app import App
    from neto_incident_monitor.history import History
    from neto_incident_monitor.tray import Tray
    result = {"frozen": bool(getattr(sys, "frozen", False)),
              "data": str(DATA), "bundle": str(ROOT)}
    try:
        window = tk.Tk()
        window.withdraw()
        with tempfile.TemporaryDirectory(prefix="sn-smoke-") as directory:
            app = App(window, history_path=Path(directory) / "history.json")
            window.update()
            result["ui"] = "ok"
            if app.tray:
                app.tray.stop()
        window.destroy()
        with sync_playwright() as playwright:
            result["browser_executable"] = playwright.chromium.executable_path
            browser = playwright.chromium.launch(headless=True, channel="chromium")
            page = browser.new_page()
            page.set_content("<title>Bundle OK</title><p>Offline test</p>")
            assert page.title() == "Bundle OK"
            result["browser"] = "ok"
            result["browser_version"] = browser.version
            browser.close()
        result["ok"] = True
    except Exception as error:
        result["ok"] = False
        result["error"] = str(error)
        raise
    finally:
        output.write_text(json.dumps(result, indent=2), encoding="utf-8")
