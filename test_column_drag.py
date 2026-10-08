import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch
from app import App
from columns import DEFAULT


class ColumnDragTests(unittest.TestCase):
    def test_drag_persists_order_without_sorting_and_click_still_sorts(self):
        root = tk.Tk()
        try:
            with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
                with patch('app.read_json', return_value={}):
                    app = App(root, history_path=Path(folder)/'history.json', enable_tray=False)
                root.update()
                table = app.current_table
                def x_for(column):
                    for x in range(10, table.winfo_width()-10):
                        if table.identify_region(x, 10)=='heading' and app.column_at(table,x)==column:
                            return x + 12
                    self.fail('Header not visible: '+column)
                x = x_for('number')
                table.event_generate('<ButtonPress-1>',x=x,y=10)
                table.event_generate('<ButtonRelease-1>',x=x,y=10)
                root.update()
                self.assertEqual(table.sort_column,'number')
                self.assertFalse(table.sort_descending)
                original = tuple(table['displaycolumns'])
                target = x_for('priority')
                with patch('app.read_json', return_value={'notify':False}), patch('app.save_json') as saved:
                    table.event_generate('<ButtonPress-1>',x=x,y=10)
                    table.event_generate('<B1-Motion>',x=target,y=10)
                    root.update_idletasks()
                    self.assertTrue(table.column_drop_marker.winfo_ismapped())
                    marker_x = table.column_drop_marker.winfo_x()
                    self.assertGreater(marker_x, target)
                    table.event_generate('<B1-Motion>',x=target,y=55)
                    root.update_idletasks()
                    self.assertFalse(table.column_drop_marker.winfo_ismapped())
                    table.event_generate('<B1-Motion>',x=target,y=10)
                    table.event_generate('<ButtonRelease-1>',x=target,y=10)
                    root.update()
                    self.assertFalse(table.column_drop_marker.winfo_ismapped())
                self.assertEqual(table.sort_column,'number')
                self.assertFalse(table.sort_descending)
                self.assertNotEqual(tuple(table['displaycolumns']),original)
                self.assertGreater(tuple(table['displaycolumns']).index('number'),tuple(table['displaycolumns']).index('priority'))
                settings = saved.call_args.args[1]
                self.assertFalse(settings['notify'])
                app.apply_visible_columns()
                self.assertEqual(tuple(table['displaycolumns'])[:4],('state','caller','priority','number'))
                self.assertIn('description',settings['column_order']['shared'])
                self.assertNotIn('history',settings['column_order'])
                # Hidden and restored columns keep the saved relative order.
                app.visible_columns = [c for c in DEFAULT if c!='priority']
                app.apply_visible_columns()
                app.visible_columns = list(DEFAULT)
                app.apply_visible_columns()
                self.assertEqual(tuple(table['displaycolumns'])[:4],('state','caller','priority','number'))
                for timer in root.tk.call('after','info'):
                    root.after_cancel(timer)
                root.destroy()
                root = tk.Tk()
                with patch('app.read_json',return_value=settings):
                    other = App(root,history_path=Path(folder)/'other.json',enable_tray=False)
                self.assertEqual(tuple(other.current_table['displaycolumns'])[:4],('state','caller','priority','number'))
        finally:
            root.update_idletasks()
            for timer in root.tk.call('after','info'):
                root.after_cancel(timer)
            root.destroy()

    def test_drag_cancel_and_save_failure_do_not_change_order(self):
        root = tk.Tk()
        try:
            with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
                with patch('app.read_json',return_value={}):
                    app=App(root,history_path=Path(folder)/'history.json',enable_tray=False)
                root.update()
                table=app.current_table
                original=tuple(table['displaycolumns'])
                with patch('app.read_json',return_value={}), patch('app.save_json',side_effect=OSError('disk full')), patch('app.messagebox.showerror') as error:
                    app.reorder_column(table,'number','priority')
                self.assertEqual(tuple(table['displaycolumns']),original)
                self.assertEqual(app.column_orders,{})
                error.assert_called_once()
                table.event_generate('<ButtonPress-1>',x=20,y=10)
                table.event_generate('<B1-Motion>',x=450,y=10)
                root.focus_force()
                table.focus_set()
                root.update()
                table.event_generate('<Escape>')
                table.event_generate('<ButtonRelease-1>',x=450,y=10)
                root.update()
                self.assertEqual(tuple(table['displaycolumns']),original)
        finally:
            root.update_idletasks()
            for timer in root.tk.call('after','info'):
                root.after_cancel(timer)
            root.destroy()
