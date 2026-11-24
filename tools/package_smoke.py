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
    from neto_incident_monitor import __version__
    result = {"frozen": bool(getattr(sys, "frozen", False)),
              "version": __version__}
    try:
        window = tk.Tk()
        window.withdraw()
        with tempfile.TemporaryDirectory(prefix="sn-smoke-") as directory:
            app = App(window, history_path=Path(directory) / "history.json", apply_startup=False)
            window.update()
            result["window_title"] = window.title()
            assert window.title() == f"Neto Incident Monitor v{__version__}"
            result["ui"] = "ok"
            from neto_incident_monitor.theme import SURFACE
            for tile in app.threatened_view.tiles:
                assert all(widget.cget('background') == SURFACE for widget in (tile, *tile.labels))
            result["metric_backgrounds"] = "ok"
            if app.tray:
                app.tray.stop()
        window.destroy()
        if result['frozen']:
            from datetime import datetime, timezone
            from neto_incident_monitor.analytics_config import (PACKAGED_CONFIG, SCOPE_KEYS, dashboard_scope,
                                                               has_dashboard_scope, held_queries, load_config,
                                                               lost_incidents_query, monthly_query, request_queries,
                                                               stale_l1_query)
            from neto_incident_monitor.threatened_api import build_query

            config = load_config()
            defaults = load_config(PACKAGED_CONFIG)
            assert not set(SCOPE_KEYS).intersection(defaults)
            result['dashboard_scope_present'] = has_dashboard_scope(config)
            local_path = DATA / 'dashboard-api.json'
            result['dashboard_local_config_present'] = local_path.is_file()
            if local_path.is_file():
                local = load_config(local_path)
                assert dashboard_scope(config) == dashboard_scope(local)
                overrides = sorted(key for key in defaults.keys() & local.keys() if local[key] != defaults[key])
                assert all(config[key] == local[key] for key in overrides)
                result['dashboard_local_overrides'] = overrides
            else:
                assert not result['dashboard_scope_present']
                config = {**config, 'assignees': ['1' * 32], 'locations': ['2' * 32]}
                result['dashboard_local_overrides'] = []
            monthly_query(config, 2026, 11, unassigned=True)
            lost_incidents_query(config)
            held_queries(config)
            stale_l1_query(config)
            request_queries(config)
            build_query(config, datetime(2026, 11, 1, tzinfo=timezone.utc))
            result['dashboard_config'] = 'ok'
        from neto_incident_monitor.data_validation import preflight, StartupDataError
        with tempfile.TemporaryDirectory(prefix='sn-validation-') as directory:
            config = Path(directory) / 'config.json'
            config.write_text('{invalid', encoding='utf-8')
            try:
                preflight(config, Path(directory) / 'history.json')
                raise AssertionError('Invalid configuration accepted')
            except StartupDataError as error:
                assert error.category == 'invalid'
                assert config.read_text(encoding='utf-8') == '{invalid'
                result['startup_validation'] = 'ok'
        with sync_playwright() as playwright:
            executable = Path(playwright.chromium.executable_path).resolve()
            result['browser_from_bundle'] = executable.is_relative_to((ROOT / 'browsers').resolve())
            if result['frozen']:
                assert result['browser_from_bundle'] and executable.is_file()
            browser = playwright.chromium.launch(headless=True, channel='chromium', executable_path=str(executable))
            try:
                page = browser.new_page(offline=True)
                page.set_content("<title>Bundle OK</title><p>Offline test</p>")
                assert page.title() == "Bundle OK"
                result["browser"] = "ok"
                result["browser_version"] = browser.version
            finally:
                browser.close()
        result["ok"] = True
    except Exception as error:
        result["ok"] = False
        result["error_type"] = type(error).__name__
        raise
    finally:
        output.write_text(json.dumps(result, indent=2), encoding="utf-8")
