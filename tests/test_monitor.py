import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from neto_incident_monitor.app import App, authentication_page, collect, empty_list, navigate, load_filters
from neto_incident_monitor.history import History

URL = "https://example.com/incident_list.do?sysparm_query=active%3Dtrue"


class MonitorTests(unittest.TestCase):
    def test_double_click_marks_only_opened_incident_read(self):
        for row, opened in (("row", True), ("row", False), ("", True)):
            with self.subTest(row=row, opened=opened):
                monitor = Mock()
                table = Mock()
                table.identify_row.return_value = row
                event = Mock(widget=table, y=42)
                monitor.items = {(table, "row"): URL}
                monitor.row_numbers = {(table, "row"): "INC1234567"}
                with patch("neto_incident_monitor.app.webbrowser.open", return_value=opened) as browser:
                    App.open_incident(monitor, event)
                if row and opened:
                    monitor.mark_read.assert_called_once_with(["INC1234567"])
                else:
                    monitor.mark_read.assert_not_called()
                if not row:
                    browser.assert_not_called()

    def test_history_survives_restart_and_deduplicates_filters(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path = Path(folder) / "history.json"
            history = History(path)
            incident = {"number": "INC0012345", "url": URL}
            self.assertTrue(history.add(incident, "Gdańsk", URL))
            self.assertTrue(history.add(incident, "Gdynia", URL + "&second=1"))
            self.assertEqual(history.unread(), 2)
            history = History(path)
            self.assertEqual(len(history.snapshot(URL)["INC0012345"]["filters"]), 1)
            history.mark_read(["INC0012345"])
            self.assertEqual(History(path).unread(), 0)
            self.assertFalse(history.add(incident, "Gdańsk", URL))
            self.assertEqual(history.unread(), 0)
            with patch.object(history, "_commit", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    history.add({"number": "INC0012346", "url": URL}, "Gdańsk", URL)
            self.assertNotIn("INC0012346", history.snapshot())
            with patch.object(history, "_commit", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    history.clear()
            self.assertIn("INC0012345", history.snapshot())
            history.clear()
            self.assertEqual(History(path).snapshot(), {})

    def test_existing_configuration_keeps_addresses(self):
        self.assertEqual(load_filters({"urls": [URL]}), [{"name": "Filtr 1", "url": URL}])
        named = [{"name": "Moje zgłoszenia", "url": URL}]
        self.assertEqual(load_filters({"urls": [URL], "filters": named}), named)

    def test_ui_snapshot_counters_and_status(self):
        import tkinter as tk
        import time
        root = tk.Tk()
        root.withdraw()
        temporary = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        try:
            with patch("neto_incident_monitor.app.read_json", return_value={"filters": [
                {"name": "Gdańsk", "url": URL},
                {"name": "Gdynia", "url": URL + "&second=1"}]}):
                monitor = App(root, history_path=Path(temporary.name) / "history.json", enable_tray=False)
            monitor.show_window = Mock()
            self.assertEqual(monitor.filter_count.get(), "2")
            self.assertEqual(int(monitor.filter_table.cget("height")), 2 * monitor.filter_table.ROW)
            self.assertEqual(monitor.filter_scroll.winfo_manager(), "")
            filters = list(monitor.filters)
            monitor.filters += [{"name": f"Lista {index}", "url": URL + f"&list={index}"} for index in range(4)]
            monitor.refresh_filters()
            self.assertEqual(int(monitor.filter_table.cget("height")), 4 * monitor.filter_table.ROW)
            self.assertEqual(monitor.filter_scroll.winfo_manager(), "grid")
            monitor.filters = filters
            monitor.refresh_filters()
            initial = monitor.notify.get()
            monitor.notify_check.toggle()
            self.assertEqual(monitor.notify.get(), not initial)
            monitor.notify_check.configure(state="disabled")
            monitor.notify_check.toggle()
            self.assertEqual(monitor.notify.get(), not initial)
            monitor.notify_check.configure(state="normal")
            monitor.notify_check.toggle()
            self.assertEqual(monitor.notify.get(), initial)
            incident = {"number": "INC0012345", "url": URL,
                        "short_description": "Problem z kasą", "priority": "2 — wysokie",
                        "location": "Gdańsk", "created": "2026-10-07 10:00:00"}
            monitor.history.add(incident, "Gdańsk", URL)
            monitor.history.add(incident, "Gdynia", URL + "&second=1")
            monitor.events.put(("snapshot", (1, {incident["number"]: incident})))
            monitor.events.put(("snapshot", (2, {incident["number"]: incident})))
            monitor.events.put(("incident", ("Gdańsk", incident, False)))
            monitor.events.put(("incident", ("Gdynia", incident, False)))
            monitor.events.put(("read", (time.time(), "Gdynia")))
            monitor.events.put(("waiting", (time.monotonic() + 60, False)))
            monitor.drain()
            self.assertEqual(monitor.current_count.get(), "1")
            self.assertEqual(monitor.new_count.get(), "1")
            self.assertEqual(len(monitor.current_table.get_children()), 1)
            row = monitor.current_table.get_children()[0]
            self.assertEqual(monitor.current_table.item(row, "values"),
                             ("Nieprzeczytany", "INC0012345", "Problem z kasą", "\u2003\u20022 — wysokie", "Gdańsk", "2026-10-07 10:00:00", *("—",) * 8))
            self.assertEqual(monitor.unread_count.get(), "1")
            self.assertEqual(len(monitor.table.get_children()), 1)
            self.assertIn("unread", monitor.current_table.item(row, "tags"))
            monitor.current_table.selection_set(row)
            monitor.mark_selected()
            self.assertEqual(monitor.unread_count.get(), "0")
            self.assertEqual(History(Path(temporary.name) / "history.json").unread(), 1)
            self.assertIn("Monitoring aktywny", monitor.phase.get())
            self.assertFalse(hasattr(monitor, "ready_button"))
            self.assertIn("za 60 s", monitor.countdown.get())
            monitor.events.put(("phase", "Oczekiwanie na logowanie"))
            monitor.drain()
            self.assertIsNone(monitor.next_check)
            self.assertIn("Oczekiwanie na logowanie", monitor.phase.get())
            self.assertTrue(monitor.auth_waiting)
            monitor.events.put(("waiting", (time.monotonic() + 60, True)))
            monitor.drain()
            self.assertIn("Błąd odczytu", monitor.phase.get())
            # Closing to the tray leaves the monitor running.
            monitor.tray = Mock()
            monitor.tray_ready = True
            monitor.hide_window()
            self.assertFalse(monitor.stop.is_set())
            self.assertEqual(root.state(), "withdrawn")
            monitor.events.put(("show", None))
            monitor.drain()
            monitor.show_window.assert_called()
            monitor.worker = Mock()
            monitor.worker.is_alive.return_value = True
            with patch("neto_incident_monitor.widgets.confirm_dialog", return_value=False) as confirm:
                monitor.clear_history()
                confirm.assert_called_once()
                self.assertEqual(len(monitor.history.snapshot()), 1)
            with patch("neto_incident_monitor.widgets.confirm_dialog", return_value=True), patch.object(
                    monitor.history, "clear", side_effect=OSError("disk full")), patch("neto_incident_monitor.app.messagebox.showerror") as error:
                monitor.clear_history()
                error.assert_called_once()
                self.assertEqual(len(monitor.history.snapshot()), 1)
            # An incident queued before the clear must not restore the deleted history.
            monitor.events.put(("incident", ("Gdańsk", incident, False)))
            with patch("neto_incident_monitor.widgets.confirm_dialog", return_value=True), patch("neto_incident_monitor.app.save_json") as state_write:
                monitor.clear_history()
                state_write.assert_not_called()
            monitor.drain()
            self.assertEqual(len(monitor.table.get_children()), 0)
            self.assertEqual(len(monitor.current_table.get_children()), 1)
            self.assertEqual(monitor.unread_count.get(), "0")
            self.assertEqual(History(Path(temporary.name) / "history.json").snapshot(URL), {})
            monitor.auth_waiting = False
            monitor.check_now()
            self.assertTrue(monitor.schedule.requested)
            monitor.schedule.consume()
            monitor.auth_waiting = True
            monitor.check_now()
            self.assertFalse(monitor.schedule.requested)
            with patch("plyer.notification.notify") as notification, patch.object(root, "bell"):
                monitor.interruption("Sesja wygasła")
                notification.assert_called_once()
            self.assertEqual(monitor.status.get(), "Sesja wygasła")
            with patch("neto_incident_monitor.app.save_json") as save:
                monitor.minimize_to_tray.set(True)
                self.assertTrue(save.call_args.args[1]["minimize_to_tray"])
            with patch.object(root, "state", return_value="iconic"), patch.object(monitor, "hide_window") as hide:
                monitor.handle_minimize()
                hide.assert_called_once()
                with patch("neto_incident_monitor.app.save_json"):
                    monitor.minimize_to_tray.set(False)
                monitor.handle_minimize()
                hide.assert_called_once()
            monitor.close()
            self.assertTrue(monitor.stop.is_set())
            self.assertTrue(monitor.quitting)
            monitor.tray.stop.assert_not_called()
            monitor.worker.is_alive.return_value = False
            with patch.object(root, "destroy") as destroy:
                monitor.finish_quit()
                destroy.assert_called_once()
            monitor.tray.stop.assert_called_once()
        finally:
            for timer in root.tk.call("after", "info"):
                root.after_cancel(timer)
            root.destroy()
            temporary.cleanup()

    def test_native_tray_lifecycle_and_badge(self):
        import queue
        from neto_incident_monitor.tray import Tray
        events = queue.Queue()
        tray = Tray(events)
        try:
            tray.start()
            kind, _ = events.get(timeout=5)
            self.assertEqual(kind, "tray_ready")
            self.assertTrue(tray.icon.visible)
            tray.update(3, "Monitoring aktywny")
            self.assertIn("nieprzeczytane: 3", tray.icon.title)
            # Exercise the menu dispatch without touching Tk from a tray thread.
            tray.icon.menu.items[0](tray.icon)
            self.assertEqual(events.get(timeout=2)[0], "show")
            tray.icon.menu.items[1](tray.icon)
            self.assertEqual(events.get(timeout=2)[0], "mark_all")
            tray.icon.menu.items[3](tray.icon)
            self.assertEqual(events.get(timeout=2)[0], "quit")
        finally:
            tray.stop()
        self.assertFalse(tray.icon.visible)

    def test_sso_navigation_does_not_cancel_login(self):
        page = Mock()
        page.goto.side_effect = RuntimeError("Navigation is interrupted by another navigation to https://idp.example.com/SSO.ping")
        navigate(page, URL)
        page.goto.assert_called_once()

    def test_unrelated_navigation_failure_is_not_hidden(self):
        page = Mock()
        page.goto.side_effect = RuntimeError("net::ERR_NAME_NOT_RESOLVED")
        with self.assertRaises(RuntimeError):
            navigate(page, URL)

    def test_authentication_redirect(self):
        self.assertTrue(authentication_page(Mock(url="https://idp.example.com/SSO.ping"), URL))
        self.assertTrue(authentication_page(Mock(url="https://example.com/login.do"), URL))
        self.assertFalse(authentication_page(Mock(url=URL), URL))

    def test_real_browser_empty_then_first_incident(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, timeout=15000)
            try:
                page = browser.new_page()
                page.set_default_timeout(5000)
                page.set_default_navigation_timeout(10000)
                page.route("https://example.com/**", lambda route: route.fulfill(
                    content_type="text/html; charset=utf-8", body="<div>Brak rekordów do wyświetlenia</div>"))
                navigate(page, URL)
                self.assertEqual(collect(page), {})
                self.assertTrue(empty_list(page, URL))
                self.assertFalse(empty_list(page, "https://other.example/incident_list.do"))
                # An empty baseline must allow the first later incident through.
                seen = {URL: []}
                page.set_content('<table><tr><th>Numer</th><th>Krótki opis</th></tr><tr><td><a href="/incident.do?sys_id=abc">INC0012345</a></td><td>Test</td></tr></table>')
                incidents = collect(page)
                self.assertEqual(set(incidents) - set(seen[URL]), {"INC0012345"})
                self.assertFalse(empty_list(page, URL))
                self.assertEqual(incidents["INC0012345"]["summary"], "Test")
                self.assertEqual(incidents["INC0012345"]["short_description"], "Test")
                # Links in navigation, parent-incident columns and descriptions
                # are not additional rows in the monitored incident list.
                page.set_content('''<a href="/incident.do">INC9999999</a>
                  <table><tr><th></th><th>Numer</th><th>Incydent nadrzędny</th></tr>
                    <tr><td><input type="checkbox"></td><td><a href="/incident.do?sys_id=1">INC7160057</a></td><td><a href="/incident.do?sys_id=4">INC7000000</a></td></tr>
                    <tr><td></td><td><a href="/incident.do?sys_id=2">INC7159884</a></td><td></td></tr>
                    <tr><td></td><td><a href="/incident.do?sys_id=3">INC7160026</a></td><td></td></tr>
                    <tr style="display:none"><td></td><td><a href="/incident.do">INC8888888</a></td><td></td></tr>
                  </table>''')
                self.assertEqual(set(collect(page)), {"INC7160057", "INC7159884", "INC7160026"})
                page.set_content('''<table><tr>
                    <th></th><th>Numer</th><th>Krótki opis</th><th>Priorytet</th><th>Lokalizacja</th><th>Utworzono</th>
                    </tr><tr><td>Wybierz rekord dotyczący czynności: INC7160057</td>
                    <td><a href="/incident.do?sys_id=1">INC7160057</a></td>
                    <td>Problem z kasą</td><td>2 — wysokie</td><td>STORE 003 GDAŃSK</td>
                    <td>2026-10-07<br>10:00:00</td></tr></table>''')
                result = collect(page)["INC7160057"]
                self.assertEqual(result["summary"], "Problem z kasą")
                self.assertEqual(result["priority"], "2 — wysokie")
                self.assertEqual(result["location"], "STORE 003 GDAŃSK")
                self.assertEqual(result["created"], "2026-10-07 10:00:00")
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
