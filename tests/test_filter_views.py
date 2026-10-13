import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from neto_incident_monitor.app import App
from neto_incident_monitor.widgets import Toggle


class FilterViewTests(unittest.TestCase):
    def test_selection_scopes_both_tables_and_read_actions(self):
        root = tk.Tk()
        try:
            with tempfile.TemporaryDirectory() as folder:
                settings = {"filters": [{"name": "A", "url": "https://example.test/a"},
                                        {"name": "B", "url": "https://example.test/b"}]}
                with patch("neto_incident_monitor.app.read_json", return_value=settings):
                    app = App(root, history_path=Path(folder)/"history.json", enable_tray=False)
                root.update()
                self.assertFalse(app.clear_history_button.winfo_manager())
                app.events.put(("filter_updating", app.filters[1]["url"]))
                app.drain()
                self.assertEqual(app.filter_table.updating_item, "1")
                app.events.put(("filter_updating", None))
                app.drain()
                self.assertIsNone(app.filter_table.updating_item)
                first_url = app.filters[0]["url"]
                second_url = app.filters[1]["url"]
                app.filter_visible_columns = {first_url: ["number", "state"], second_url: ["number", "short_description"]}
                app.filter_table.selection_set("1")
                self.assertEqual(app.visible_columns, ["number", "short_description"])
                app.filter_table.selection_set("0")
                self.assertEqual(app.visible_columns, ["number", "state"])
                app.visible_columns = list(app.legacy_visible_columns)
                app.filters[1]["url"] = "https://example.test/sc_task_list.do"
                app.filter_table.selection_set("1")
                self.assertIn("requested_for", app.applicable_columns())
                self.assertNotIn("caller", app.applicable_columns())
                self.assertNotIn("parent_incident", app.applicable_columns())
                app.filters[1]["url"] = second_url
                app.filter_visible_columns = {}
                app.filter_table.selection_set("0")
                app.tabs.select(1)
                root.update()
                self.assertEqual(app.clear_history_button.winfo_manager(), "pack")
                app.tabs.select(0)
                root.update()
                self.assertFalse(app.clear_history_button.winfo_manager())
                for i, entry in enumerate(app.filters, 1):
                    incident = {"number": "INC1", "url": entry["url"], "short_description": entry["name"]}
                    app.history.add(incident, entry["name"], entry["url"])
                    app.snapshots[i] = {"INC1": incident}
                app.filter_selected()
                self.assertNotIn("filter", app.current_table["columns"])
                self.assertEqual(app.current_table.set(app.current_table.get_children()[0], "short_description"), "A")
                app.mark_all()
                self.assertFalse(app.history.snapshot(app.filters[1]["url"])["INC1"]["read"])
                app.filter_table.selection_set("1")
                self.assertEqual(app.current_table.set(app.current_table.get_children()[0], "short_description"), "B")
                self.assertEqual(app.table.set(app.table.get_children()[0], "short_description"), "B")
                self.assertEqual(app.unread_count.get(), "1")
                with patch("neto_incident_monitor.app.save_json") as save:
                    app.highlight_unread.set(False)
                    self.assertNotIn("read", app.applicable_columns())
                    self.assertFalse(save.call_args.args[1]["highlight_unread"])
                    self.assertFalse(app.mark_all_button.winfo_manager())
                    for table in (app.current_table, app.table):
                        self.assertNotIn("read", table["displaycolumns"])
                        self.assertNotIn("unread", table.item(table.get_children()[0], "tags"))
                    app.mark_all()
                    self.assertFalse(app.history.snapshot(app.filters[1]["url"])["INC1"]["read"])
                    app.highlight_unread.set(True)
                    self.assertIn("read", app.applicable_columns())
                    self.assertEqual(app.mark_all_button.winfo_manager(), "pack")
                    self.assertIn("unread", app.table.item(app.table.get_children()[0], "tags"))
                with patch("neto_incident_monitor.app.save_json"):
                    app.notify.set(False)
                    app.teams_enabled.set(False)
                app.configure_filter_notifications("1")
                root.update()
                dialog = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel) and w.title()=="Powiadomienia filtra")
                def descendants(widget):
                    for child in widget.winfo_children():
                        yield child
                        yield from descendants(child)
                toggles = [w for w in descendants(dialog) if isinstance(w, Toggle)]
                self.assertEqual([w.enabled for w in toggles], [False, False, True])
                dialog.destroy()
        finally:
            for timer in root.tk.call("after", "info"):
                root.after_cancel(timer)
            root.destroy()

    def test_notification_channels_and_filter_names_are_independent(self):
        app = App.__new__(App)
        app.filters = [{"name": "A", "url": "A", "notify_windows": True, "notify_teams": False},
                       {"name": "B", "url": "B", "notify_windows": False, "notify_teams": True}]
        app.notify = Mock(); app.notify.get.return_value = True
        app.teams_enabled = Mock(); app.teams_enabled.get.return_value = True
        app.teams_webhook = "webhook"
        app.teams_sender = Mock(); app.root = Mock()
        incident = {"number": "INC1", "location": "Store", "short_description": "Description"}
        with patch("plyer.notification.notify") as notify:
            app.notify_filter("A", [incident])
            self.assertEqual(notify.call_args.kwargs["title"], "A")
            self.assertEqual(notify.call_args.kwargs["message"], "Wykryto incydent\nINC1 - Store - Description")
            app.teams_sender.submit.assert_not_called()
            app.notify_filter("B", [incident])
            self.assertEqual(notify.call_count, 1)
            app.teams_sender.submit.assert_called_once_with("webhook", "B", "Wykryto incydent\nINC1 - Store - Description")
            app.teams_enabled.get.return_value = False
            app.notify_filter("B", [incident])
            self.assertEqual(app.teams_sender.submit.call_count, 1)
