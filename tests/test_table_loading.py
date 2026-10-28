import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from neto_incident_monitor.app import App
from neto_incident_monitor.dynamic_columns import update_profile

URL = 'https://adeo.service-now.com/incident_list.do?test=a'
OTHER = 'https://adeo.service-now.com/sc_request_list.do?test=b'


class TableLoadingTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.folder = tempfile.TemporaryDirectory()
        with patch('neto_incident_monitor.app.read_json', return_value={'filters': [
                {'name': 'A', 'url': URL}, {'name': 'B', 'url': OTHER}]}):
            self.app = App(self.root, history_path=Path(self.folder.name)/'history.json', enable_tray=False)
        schema = [{'key': 'number', 'label': 'Numer'}, {'key': 'short_description', 'label': 'Opis'}]
        self.app.column_profiles = {url: update_profile(None, schema) for url in (URL, OTHER)}
        self.root.update()

    def tearDown(self):
        self.app.stop_table_loads()
        for timer in self.root.tk.call('after', 'info'):
            self.root.after_cancel(timer)
        self.root.destroy()
        self.folder.cleanup()

    def wait(self, predicate, timeout=10):
        deadline = time.monotonic() + timeout
        while not predicate():
            self.root.update()
            if time.monotonic() > deadline:
                self.fail('Table loading did not complete')
            time.sleep(.002)

    def populate(self, count=3000):
        records = {}
        snapshots = {}
        for i in range(count):
            number = f'INC{i:07}'
            row = {'number': number, 'url': f'https://adeo.service-now.com/incident.do?sys_id={i}',
                   'short_description': f'Opis {i}'}
            records[URL+'\n'+number] = {'incident': row, 'read': i % 2 == 0, 'detected': i, 'filters': {URL: 'A'}}
            snapshots[number] = row
        self.app.history.records = records
        self.app.snapshots = {1: snapshots, 2: {'REQ0012345': {'number': 'REQ0012345', 'short_description': 'B'}}}

    def test_batches_yield_hidden_history_and_switch_cancel(self):
        self.populate()
        app = self.app
        pulses = []
        switched_during_loading = []
        def pulse():
            count = len(app.current_table.get_children())
            pulses.append(count)
            if 0 < count < 3000 and not switched_during_loading:
                # Observe and cancel from inside Tk's event loop. root.update()
                # can process several batches before returning on a busy machine.
                switched_during_loading.append(count)
                app.filter_table.selection_set('1')
            self.root.after(2, pulse)
        self.root.after(0, pulse)
        started = time.perf_counter()
        app.filter_selected()
        self.assertLess(time.perf_counter() - started, .3)
        self.wait(lambda: bool(switched_during_loading))
        self.assertLess(switched_during_loading[0], 3000)
        self.assertEqual(app.table.get_children(), ())
        self.wait(lambda: not app._table_jobs)
        self.assertEqual([app.current_table.set(i, 'number') for i in app.current_table.get_children()], ['REQ0012345'])
        self.assertGreater(len(pulses), 1)
        app.filter_table.selection_set('0')
        app.tabs.select(1)
        self.root.update()
        self.wait(lambda: not app._table_jobs)
        self.assertEqual(len(app.table.get_children()), 3000)
        self.assertEqual(app.table.set(app.table.get_children()[0], 'number'), 'INC0002999')
        self.assertFalse(app.table.load_dirty)
        self.assertEqual(app.table_load_status.get(), '')

    def test_sort_selection_and_replacement_during_loading(self):
        self.populate(500)
        app = self.app
        app.filter_selected()
        self.wait(lambda: not app._table_jobs)
        chosen = app.current_table.get_children()[0]
        number = app.current_table.set(chosen, 'number')
        app.current_table.selection_set(chosen)
        app.toggle_sort(app.current_table, 'number')
        self.wait(lambda: not app._table_jobs)
        self.assertEqual(app.current_table.set(app.current_table.get_children()[0], 'number'), 'INC0000000')
        self.assertEqual([app.current_table.set(i, 'number') for i in app.current_table.selection()], [number])
        app.refresh_current()
        app.snapshots[1] = {'INC9999999': {'number': 'INC9999999', 'short_description': 'Replacement'}}
        app.refresh_current()
        self.wait(lambda: not app._table_jobs)
        self.assertEqual(len(app.current_table.get_children()), 1)
        self.assertEqual(app.current_table.set(app.current_table.get_children()[0], 'number'), 'INC9999999')

    def test_double_click_opens_clicked_filter_not_previous_selection(self):
        app = self.app
        with patch('neto_incident_monitor.app.webbrowser.open') as browser:
            app.open_filter(SimpleNamespace(x=10, y=app.filter_table.ROW + 4))
            browser.assert_called_once_with(OTHER)
            browser.reset_mock()
            app.open_filter(SimpleNamespace(x=app.filter_table.winfo_width()-1, y=4))
            browser.assert_not_called()
