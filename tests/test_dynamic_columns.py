import copy
import tempfile
import tkinter as tk
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from neto_incident_monitor.app import App
from neto_incident_monitor.filter_definition import read_list_headers
from neto_incident_monitor.list_context import ListTarget
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
    def test_real_servicenow_headers_exclude_controls_and_search_row(self):
        from playwright.sync_api import sync_playwright
        fixture = (Path(__file__).parent/'fixtures'/'incident_headers.html').read_text(encoding='utf-8')
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.route('https://adeo.service-now.com/**', lambda r: r.fulfill(body=''))
                page.goto(URL)
                for table_name in ('incident', 'sc_task'):
                    html = fixture.replace('incident', table_name)
                    page.set_content('<table>'+html+'</table>')
                    for search_visible in (True, False):
                        page.locator('.list_header_search_row').evaluate('(el, show) => el.style.display = show ? "" : "none"', search_visible)
                        schema = read_list_headers(ListTarget.find(page, URL))['schema']
                        self.assertEqual(len(schema), 14)
                        self.assertEqual(schema[0], {'key': 'number', 'label': 'Numer', 'field': 'number'})
                        self.assertIn({'key': 'sn:u_ci_category', 'label': 'CI category', 'field': 'u_ci_category'}, schema)
                        self.assertNotIn('sn:search', {column['key'] for column in schema})
                        self.assertFalse(any('przeszukiwania' in column['label'] for column in schema))
                    page.locator('thead').evaluate('el => el.appendChild(el.rows[0].cloneNode(true))')
                    with self.assertRaisesRegex(Exception, 'Ambiguous ServiceNow column headers'):
                        read_list_headers(ListTarget.find(page, URL))
            finally:
                browser.close()

    def test_changed_set_resets_but_source_reordering_preserves_preferences(self):
        profile = update_profile(None, SCHEMA)
        self.assertEqual(profile['visible'], ['number', 'sn:u_custom', 'state'])
        self.assertEqual(profile['order'][-len(LOCAL_KEYS):], LOCAL_KEYS)
        profile['visible'] = ['state', 'time']
        profile['order'].reverse()
        profile['widths'] = {'state': 211}
        reordered = update_profile(load_profiles({URL: profile})[URL], list(reversed(SCHEMA)), incident_list=True)
        self.assertEqual(reordered['order'], profile['order'])
        self.assertEqual(reordered['visible'], profile['visible'])
        self.assertEqual(reordered['widths'], profile['widths'])
        changed = update_profile(profile, SCHEMA[:2], incident_list=True)
        self.assertEqual(changed['visible'], ['number', 'sn:u_custom'])
        self.assertEqual(changed['order'][-len(LOCAL_KEYS):], LOCAL_KEYS)
        self.assertEqual(changed['widths'], {})
        added = update_profile(profile, SCHEMA + [{'key': 'sn:added', 'label': 'Nowa'}])
        self.assertEqual(added['visible'], [c['key'] for c in added['schema']])
        self.assertEqual(load_profiles({URL: profile})[URL], profile)
        self.assertEqual(load_profiles({URL: {'schema': None}}), {})

    def test_definition_refresh_preserves_shared_columns_and_adds_new_ones(self):
        profile = update_profile(None, SCHEMA)
        profile['visible'] = ['state', 'time']
        profile['order'] = ['state', 'number', 'sn:u_custom', *LOCAL_KEYS]
        profile['widths'] = {'state': 211, 'sn:u_custom': 123}
        schema = [SCHEMA[0], SCHEMA[2], {'key': 'sn:added', 'label': 'Nowa'}]
        refreshed = update_profile(profile, schema, preserve_layout=True)
        self.assertEqual(refreshed['visible'], ['state', 'time', 'sn:added'])
        self.assertEqual(refreshed['order'], ['state', 'number', *LOCAL_KEYS, 'sn:added'])
        self.assertEqual(refreshed['widths'], {'state': 211})

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
                schema = read_list_headers(ListTarget.find(page, URL))['schema']
                self.assertEqual([c['key'] for c in schema], ['sn:u_custom', 'number', 'state'])
                self.assertEqual(schema[0]['field'], 'u_custom')
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
        for table in (app.current_table, app.table):
            self.assertEqual(tuple(table['displaycolumns']), ('age_minutes', 'number', 'sn:u_custom', 'state'))
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
        self.assertEqual(tuple(app.current_table['displaycolumns']), ('age_minutes', 'number', 'sn:u_custom'))
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
        self.assertEqual(stored['filter_column_profiles'][URL]['order'],
                         ['age_minutes', *[c['key'] for c in SCHEMA], 'time'])
        self.assertEqual(set(app.visible_columns), {'age_minutes', *(c['key'] for c in SCHEMA)})
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
            app.reorder_column(app.table, 'time', 'age_minutes')
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

    def test_separator_double_click_fits_left_column_and_persists(self):
        self.accept()
        app = self.app
        table = app.current_table
        text = 'Długi opis zawartości ' * 20
        table.insert('', 'end', values=app.table_values(table, {'number': 'INC1234567', '_values': {'sn:u_custom': text}}, ''))
        table.column('sn:u_custom', width=80)
        self.root.update()
        x = sum(table.column(key, 'width') for key in ('age_minutes', 'number', 'sn:u_custom'))
        self.assertEqual(table.identify_region(x, 10), 'separator')
        with patch('neto_incident_monitor.app.read_json', return_value={}), patch('neto_incident_monitor.app.save_json') as save, patch('neto_incident_monitor.app.webbrowser.open') as opened:
            result = app.open_incident(SimpleNamespace(widget=table, x=x, y=10))
        self.assertEqual(result, 'break')
        opened.assert_not_called()
        from tkinter.font import Font
        from tkinter import ttk
        font = Font(table, font=ttk.Style(table).lookup('Treeview', 'font'))
        width = table.column('sn:u_custom', 'width')
        self.assertEqual(width, font.measure(text) + 16)
        self.assertGreater(width, 1500)
        self.assertEqual(app.table.column('sn:u_custom', 'width'), width)
        self.assertEqual(save.call_args.args[1]['filter_column_profiles'][URL]['widths']['sn:u_custom'], width)
        app.filter_selected()
        self.assertEqual(table.column('sn:u_custom', 'width'), width)
        self.assertEqual(table.column('number', 'width'), 125)
