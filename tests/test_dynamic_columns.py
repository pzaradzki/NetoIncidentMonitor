import copy
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from neto_incident_monitor.app import App, collect
from neto_incident_monitor.columns import ColumnDiscovery
from neto_incident_monitor.dynamic_columns import LOCAL_KEYS, load_profiles, update_profile
from neto_incident_monitor.widgets import RoundedButton

URL = 'https://adeo.service-now.com/incident_list.do?test=a'
OTHER = 'https://adeo.service-now.com/incident_list.do?test=b'
SCHEMA = [{'key': 'number', 'label': 'Numer'}, {'key': 'sn:u_custom', 'label': 'Pole własne'},
          {'key': 'state', 'label': 'Stan'}]


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


class ProfileTests(unittest.TestCase):
    def test_changed_set_resets_but_source_reordering_preserves_preferences(self):
        profile = update_profile(None, SCHEMA)
        self.assertEqual(profile['visible'], ['number', 'sn:u_custom', 'state'])
        self.assertEqual(profile['order'][-3:], LOCAL_KEYS)
        profile['visible'] = ['state', 'time']
        profile['order'].reverse()
        profile['widths'] = {'state': 211}
        reordered = update_profile(profile, list(reversed(SCHEMA)))
        self.assertEqual(reordered['order'], profile['order'])
        self.assertEqual(reordered['visible'], profile['visible'])
        self.assertEqual(reordered['widths'], profile['widths'])
        changed = update_profile(profile, SCHEMA[:2])
        self.assertEqual(changed['visible'], ['number', 'sn:u_custom'])
        self.assertEqual(changed['order'][-3:], LOCAL_KEYS)
        self.assertEqual(changed['widths'], {})
        added = update_profile(profile, SCHEMA + [{'key': 'sn:added', 'label': 'Nowa'}])
        self.assertEqual(added['visible'], [c['key'] for c in added['schema']])
        self.assertEqual(load_profiles({URL: profile})[URL], profile)
        self.assertEqual(load_profiles({URL: {'schema': None}}), {})

    def test_inconsistent_traversal_is_rejected(self):
        discovery = ColumnDiscovery()
        discovery.discover(SCHEMA)
        discovery.discover(list(reversed(SCHEMA)))
        with self.assertRaises(RuntimeError):
            discovery.discover(SCHEMA[:2])

    def test_reader_discovers_unknown_fields_in_empty_and_populated_list(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.route('https://adeo.service-now.com/**', lambda r: r.fulfill(body=''))
                page.goto(URL)
                headers = '<tr><th></th><th name="incident.u_custom">Pole własne</th><th name="incident.number">Numer</th><th name="incident.state">Stan</th><th name="incident.hidden" style="display:none">Ukryta</th></tr>'
                page.set_content('<table>'+headers+'</table>')
                discovery = ColumnDiscovery()
                self.assertEqual(collect(page, discovery), {})
                self.assertEqual([c['key'] for c in discovery.schema], ['sn:u_custom', 'number', 'state'])
                page.set_content('<table>'+headers+'<tr><td></td><td>Własna wartość</td><td><a href="/incident.do?sys_id=abc">INC1234567</a></td><td>Nowy</td><td style="display:none">Sekret</td></tr></table>')
                record = collect(page, discovery)['INC1234567']
                self.assertEqual(record['_values']['sn:u_custom'], 'Własna wartość')
                self.assertNotIn('sn:hidden', record['_values'])
            finally:
                browser.close()


class DynamicUITests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.folder = tempfile.TemporaryDirectory()
        with patch('neto_incident_monitor.app.read_json', return_value={
                'filters': [{'name': 'A', 'url': URL}, {'name': 'B', 'url': OTHER}]}):
            self.app = App(self.root, history_path=Path(self.folder.name)/'history.json', enable_tray=False)
        self.root.update()

    def tearDown(self):
        for timer in self.root.tk.call('after', 'info'):
            self.root.after_cancel(timer)
        self.root.destroy()
        self.folder.cleanup()

    def accept(self, url=URL, schema=SCHEMA):
        with patch('neto_incident_monitor.app.read_json', return_value={}), patch('neto_incident_monitor.app.save_json'):
            self.app.accept_column_schema(url, schema)

    def test_first_read_switching_reset_and_arbitrary_values(self):
        app = self.app
        self.assertFalse(app.columns_button.enabled)
        self.assertFalse(app.current_table['displaycolumns'])
        self.accept()
        self.assertTrue(app.columns_button.enabled)
        self.assertEqual(tuple(app.current_table['displaycolumns']), ('number', 'sn:u_custom', 'state'))
        incident = {'number': 'INC1234567', 'url': '', '_values': {'sn:u_custom': 'Test', 'state': 'Nowy'}}
        app.snapshots = {1: {incident['number']: incident}}
        app.history.add(incident, 'A', URL)
        app.filter_selected()
        for table in (app.current_table, app.table):
            self.assertEqual(table.set(table.get_children()[0], 'sn:u_custom'), 'Test')
        app.column_profile()['visible'] = ['state']
        app.filter_selected()
        self.accept(schema=list(reversed(SCHEMA)))
        self.assertEqual(tuple(app.current_table['displaycolumns']), ('state',))
        app.filter_table.selection_set('1')
        self.assertFalse(app.columns_button.enabled)
        self.accept(OTHER, SCHEMA[:2])
        app.filter_table.selection_set('0')
        self.assertEqual(tuple(app.current_table['displaycolumns']), ('state',))
        self.accept(schema=SCHEMA[:2])
        self.assertEqual(tuple(app.current_table['displaycolumns']), ('number', 'sn:u_custom'))
        self.assertNotIn('time', app.visible_columns)
        app.toggle_sort(app.current_table, 'sn:u_custom')
        self.accept(schema=SCHEMA[:1])
        self.assertIsNone(app.current_table.sort_column)
        self.assertEqual(tuple(app.current_table['displaycolumns']), ('number',))

    def test_picker_restore_cancel_and_save(self):
        self.accept()
        app = self.app
        app.column_profile()['visible'] = ['state', 'time']
        app.column_profile()['order'] = ['state', 'number', 'sn:u_custom'] + LOCAL_KEYS
        app.filter_selected()
        before = copy.deepcopy(app.column_profiles)
        app.configure_columns()
        self.root.update()
        dialog = next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel) and w.title() == "Widoczne kolumny")
        buttons = {w.text: w for w in descendants(dialog) if isinstance(w, RoundedButton)}
        self.assertTrue(any(w.winfo_class() == 'TSeparator' for w in descendants(dialog)))
        buttons['Przywróć domyślne'].invoke()
        self.assertEqual(app.column_profiles, before)
        buttons['Anuluj'].invoke()
        self.assertEqual(app.column_profiles, before)
        app.configure_columns()
        self.root.update()
        dialog = next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel) and w.title() == "Widoczne kolumny")
        buttons = {w.text: w for w in descendants(dialog) if isinstance(w, RoundedButton)}
        buttons['Przywróć domyślne'].invoke()
        with patch('neto_incident_monitor.app.read_json', return_value={'notify': True}), patch('neto_incident_monitor.app.save_json') as save:
            buttons['Zapisz'].invoke()
        stored = save.call_args.args[1]
        self.assertTrue(stored['notify'])
        self.assertEqual(stored['filter_column_profiles'][URL]['order'], [c['key'] for c in SCHEMA]+LOCAL_KEYS)
        self.assertEqual(set(app.visible_columns), {c['key'] for c in SCHEMA})
        self.assertNotIn('time', app.table['displaycolumns'])

    def test_schema_persistence_failure_keeps_previous_layout(self):
        self.accept()
        before = copy.deepcopy(self.app.column_profiles)
        with patch('neto_incident_monitor.app.read_json', return_value={}), patch('neto_incident_monitor.app.save_json', side_effect=OSError()):
            self.app.accept_column_schema(URL, SCHEMA[:2])
        self.assertEqual(self.app.column_profiles, before)

    def test_local_column_order_and_widths_are_scoped_to_filter(self):
        self.accept()
        self.accept(OTHER)
        app = self.app
        app.column_profile()['visible'].append('time')
        app.filter_selected()
        with patch('neto_incident_monitor.app.read_json', return_value={}), patch('neto_incident_monitor.app.save_json'):
            app.reorder_column(app.table, 'time', 'number')
            app.current_table.column('sn:u_custom', width=277)
            app.sync_column_widths(app.current_table)
        self.assertEqual(tuple(app.table['displaycolumns'])[0], 'time')
        self.assertEqual(app.table.column('sn:u_custom', 'width'), 277)
        saved = copy.deepcopy(app.column_profiles)
        app.filter_table.selection_set('1')
        self.assertEqual(app.current_table.column('sn:u_custom', 'width'), 180)
        self.assertNotIn('time', app.table['displaycolumns'])
        app.filter_table.selection_set('0')
        self.assertEqual(app.current_table.column('sn:u_custom', 'width'), 277)
        self.assertEqual(app.column_profiles, saved)
