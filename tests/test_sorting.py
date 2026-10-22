import tkinter as tk
import unittest
from tkinter import ttk
from unittest.mock import Mock
from neto_incident_monitor.app import App


class SortingTests(unittest.TestCase):
    def test_current_lists_default_to_highest_number(self):
        root = tk.Tk()
        root.withdraw()
        try:
            app = App.__new__(App)
            app.items, app.row_numbers = {}, {}
            app.history = Mock()
            app.history.snapshot.return_value = {}
            app.selected_filter_url = Mock(return_value='filter')
            app.selected_filter_index = Mock(return_value=1)
            app.filters = [{'name': 'Test'}]
            app.current_table = app.make_table(ttk.Frame(root), False)
            for prefix in ('INC', 'SCTASK'):
                app.snapshots = {1: {prefix+number: {'number': prefix+number, 'url': 'https://adeo.service-now.com/task'}
                                     for number in ('9', '11', '10')}}
                app.refresh_current()
                expected = [prefix+'11', prefix+'10', prefix+'9']
                self.assertEqual([app.current_table.set(item, 'number') for item in app.current_table.get_children()], expected)
                for _ in range(3):
                    app.toggle_sort(app.current_table, 'number')
                self.assertEqual([app.current_table.set(item, 'number') for item in app.current_table.get_children()], expected)
        finally:
            for timer in root.tk.call('after', 'info'):
                root.after_cancel(timer)
            root.destroy()

    def test_headers_cycle_and_refresh_preserves_sort(self):
        root = tk.Tk()
        root.withdraw()
        try:
            app = App.__new__(App)
            for history in (False, True):
                frame = ttk.Frame(root)
                table = app.make_table(frame, history)
                for index, (number, priority, created) in enumerate([
                    ("INC0000003", "10 — test", "2026-10-07 11:00:00"),
                    ("INC0000001", "2 — wysokie", "2026-10-06 11:00:00"),
                    ("INC0000002", "—", "—")]):
                    values = ("Przeczytany", number, "Opis", priority, "Gdańsk", created)
                    if history:
                        values = ("07.10.2026 11:00", *values)
                    table.insert("", "end", iid=str(index), values=values)
                table.default_order = table.get_children()
                table.selection_set("1")
                def click(column):
                    root.tk.call(table.heading(column, "command"))
                click("priority")
                self.assertEqual(table.get_children(), ("1", "0", "2"))
                click("priority")
                self.assertEqual(table.get_children(), ("0", "1", "2"))
                click("priority")
                self.assertEqual(table.get_children(), ("0", "1", "2"))
                self.assertIsNone(table.sort_column)
                click("number")
                self.assertEqual(table.get_children(), ("1", "2", "0"))
                # Simulate a refresh replacing IDs in the default data order.
                values = table.item("0", "values")
                table.insert("", "end", iid="new", values=values)
                table.default_order = ("new", "0", "1", "2")
                app.apply_sort(table)
                self.assertEqual(table.get_children(), ("1", "2", "new", "0"))
                click("created")
                self.assertFalse(table.sort_descending)
                self.assertEqual(table.get_children()[0], "1")
                self.assertEqual(table.get_children()[-1], "2")
                self.assertEqual(table.selection(), ("1",))
                # Every header, including history's detected timestamp, is clickable.
                for column in table["columns"]:
                    self.assertTrue(table.heading(column, "command"))
                frame.destroy()
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
