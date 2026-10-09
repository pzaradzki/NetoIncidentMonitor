import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from neto_incident_monitor.app import App
from neto_incident_monitor.widgets import FilterList


class FilterReorderTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()

    def tearDown(self):
        for timer in self.root.tk.call("after", "info"):
            self.root.after_cancel(timer)
        self.root.destroy()

    def test_drag_marker_drop_and_controls(self):
        table = FilterList(self.root)
        table.pack()
        for i in range(3):
            table.insert("", "end", str(i), (f"Filter {i}",))
        table.on_reorder = Mock()
        table.on_settings = Mock()
        table.on_toggle = Mock()
        self.root.update()
        event = lambda x, y: SimpleNamespace(x=x, y=y)
        table.select_at(event(30, 20))
        table.drag_motion(event(30, 23))
        self.assertFalse(table.find_withtag("drop_marker"))
        table.drag_motion(event(30, 110))
        self.assertEqual(len(table.find_withtag("drop_marker")), 3)
        self.assertEqual(table.coords(table.find_withtag("drop_marker")[0])[1], 96)
        table.drag_end(event(30, 110))
        table.on_reorder.assert_called_once_with("0", 2)
        self.assertFalse(table.find_withtag("drop_marker"))
        for x, callback in [(table.winfo_width()-56, table.on_settings),
                            (table.winfo_width()-20, table.on_toggle)]:
            table.select_at(event(x, 20))
            table.drag_motion(event(x, 110))
            self.assertIsNone(table.drag)
            callback.assert_called_once_with("0")
        table.select_at(event(30, 20))
        table.drag_motion(event(30, 110))
        table.drag_end(event(-10, 110))
        self.assertEqual(table.on_reorder.call_count, 1)
        table.select_at(event(30, 20))
        table.drag_motion(event(30, 110))
        table.drag_cancel()
        self.assertFalse(table.find_withtag("drop_marker"))

    def test_persistence_and_queued_reads_follow_filter_identity(self):
        settings = {"filters": [{"name": name, "url": f"https://example.test/{name}"}
                                for name in ("A", "B", "C")]}
        with tempfile.TemporaryDirectory() as folder, \
                patch("neto_incident_monitor.app.read_json", return_value=settings), \
                patch("neto_incident_monitor.app.save_json") as save:
            app = App(self.root, history_path=Path(folder)/"history.json", enable_tray=False)
            app.worker = Mock()
            app.worker.is_alive.return_value = True
            app.filter_table.selection_set("0")
            url = app.selected_filter_url()
            app.snapshots = {1: {"INC1": {"number": "INC1", "url": url}}}
            app.column_availability = {1: {"number", "state"}}
            app.reorder_filter("0", 3)
            self.assertEqual([f["name"] for f in app.filters], ["B", "C", "A"])
            self.assertEqual(save.call_args.args[1]["urls"], [f["url"] for f in app.filters])
            self.assertEqual(app.selected_filter_url(), url)
            self.assertIn(3, app.snapshots)
            self.assertEqual(app.column_availability[3], {"number", "state"})
            app.events.put(("snapshot", (url, {"INC2": {"number": "INC2", "url": url}})))
            app.drain()
            self.assertIn("INC2", app.snapshots[3])
            self.assertNotIn(1, app.snapshots)
            with patch.object(app, "persist_filters", side_effect=OSError("disk full")), \
                    patch("neto_incident_monitor.app.messagebox.showerror") as error:
                app.reorder_filter("2", 0)
                self.assertEqual([f["name"] for f in app.filters], ["B", "C", "A"])
                self.assertEqual(app.selected_filter_url(), url)
                error.assert_called_once()

    def test_drag_above_short_list_keeps_rows_at_top(self):
        table = FilterList(self.root)
        table.configure(height=16)
        table.pack()
        for i in range(2):
            table.insert("", "end", str(i), (f"Filter {i}",))
        self.root.update()
        table.select_at(SimpleNamespace(x=30, y=60))
        for y in (10, -10, -50, -100):
            table.drag_motion(SimpleNamespace(x=30, y=y))
            self.assertEqual(table.canvasy(0), 0)
            self.assertEqual(table.drag["slot"], 0)
        table.drag_cancel()
        table.yview_scroll(-1, "units")
        self.assertEqual(table.canvasy(0), 0)
