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
            self.root.tk.call("after", "cancel", timer)
        self.root.destroy()

    def test_many_filters_toggle_keeps_scroll_and_reuses_card_images(self):
        filters = [{'name': f'Filter {i}', 'url': f'https://adeo.service-now.com/incident_list.do?fixture={i}'} for i in range(100)]
        with tempfile.TemporaryDirectory() as directory, \
                patch('neto_incident_monitor.app.read_json', return_value={'filters': filters}), \
                patch('neto_incident_monitor.app.save_json') as save:
            app = App(self.root, history_path=Path(directory) / 'history.json', enable_tray=False, apply_startup=False)
            self.root.geometry('1440x900')
            self.root.update()
            table = app.filter_table
            table.yview_moveto(.5)
            self.root.update()
            position = table.yview()
            with patch.object(table, 'replace_rows', wraps=table.replace_rows) as replace, \
                    patch.object(table, 'card_image', wraps=table.card_image) as render, \
                    patch.object(table, 'on_select', wraps=table.on_select) as selected, \
                    patch.object(app, 'persist_filters', wraps=app.persist_filters) as persist:
                for item in ('51', '52', '53', '52'):
                    app.toggle_filter(item)
                    self.root.update()
                    self.assertEqual(table.yview(), position)
                replace.assert_not_called()
                self.assertLessEqual(render.call_count, 8)
                self.assertEqual(selected.call_count, 4)
                self.assertEqual(persist.call_count, 4)
            self.assertFalse(app.filters[51]['enabled'])
            self.assertTrue(app.filters[52]['enabled'])
            self.assertFalse(app.filters[53]['enabled'])
            self.assertEqual(table.selection(), ('52',))
            self.assertTrue(save.called)
            self.assertGreaterEqual(table.master.grid_slaves(row=1, column=1)[0].winfo_x() - table.winfo_width(), 8)
            app.refresh_filters()
            self.root.update()
            self.assertEqual(table.yview(), position)
            before = dict(table.enabled_rows)
            revisions = dict(app.filter_revisions)
            with patch.object(app, 'persist_filters', side_effect=PermissionError('synthetic failure')), \
                    patch('neto_incident_monitor.app.messagebox.showerror') as error:
                app.toggle_filter('51')
            error.assert_called_once()
            self.assertFalse(app.filters[51]['enabled'])
            self.assertEqual(table.enabled_rows, before)
            self.assertEqual(app.filter_revisions, revisions)
            self.assertEqual(table.yview(), position)

    def test_filter_scrollbar_hides_when_all_rows_fit(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            filters = [{'name': f'Filter {i}', 'url': f'https://adeo.service-now.com/incident_list.do?fixture=list&id={i}'} for i in range(6)]
            with patch('neto_incident_monitor.app.read_json', return_value={'filters': filters}):
                app = App(self.root, history_path=Path(directory) / 'history.json', enable_tray=False, apply_startup=False)
            self.root.geometry('1440x900')
            self.root.update()
            self.assertGreaterEqual(app.filter_table.winfo_height(), 6 * FilterList.ROW)
            self.assertEqual(app.filter_scroll.winfo_manager(), '')
            app.filters += [{'name': f'More {i}', 'url': f'https://adeo.service-now.com/incident_list.do?fixture=more&id={i}'} for i in range(30)]
            app.refresh_filters()
            self.root.update()
            self.assertEqual(app.filter_scroll.winfo_manager(), 'grid')
            app.filter_table.yview_moveto(1)
            app.filters = app.filters[:2]
            app.refresh_filters()
            self.root.update()
            self.assertEqual(app.filter_scroll.winfo_manager(), '')
            self.assertEqual(app.filter_table.yview(), (0.0, 1.0))

    def test_drag_marker_drop_and_controls(self):
        table = FilterList(self.root)
        table.pack()
        for i in range(3):
            table.insert("", "end", str(i), (f"Filter {i}",))
        table.on_reorder = Mock()
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
        # The former bell area now selects the filter normally.
        table.select_at(event(table.winfo_width()-56, 20))
        self.assertEqual(table.selection(), ("0",))
        self.assertIsNotNone(table.drag)
        table.drag_cancel()
        table.select_at(event(table.winfo_width()-20, 20))
        self.assertIsNone(table.drag)
        table.on_toggle.assert_called_once_with("0")
        table.select_at(event(30, 20))
        table.drag_motion(event(30, 110))
        table.drag_end(event(-10, 110))
        self.assertEqual(table.on_reorder.call_count, 1)
        table.select_at(event(30, 20))
        table.drag_motion(event(30, 110))
        table.drag_cancel()
        self.assertFalse(table.find_withtag("drop_marker"))

    def test_persistence_and_queued_reads_follow_filter_identity(self):
        settings = {"filters": [{"name": name, "url": f"https://adeo.service-now.com/incident_list.do?name={name}"}
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
