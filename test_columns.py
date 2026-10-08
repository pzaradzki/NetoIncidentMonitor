import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch
from app import App, collect
from columns import DEFAULT


class ColumnTests(unittest.TestCase):
    def test_browser_detects_empty_columns_and_separates_descriptions(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                headers = '<tr><th name="incident.cmdb_ci">Objęty element konfiguracji</th><th name="incident.assignment_group">Grupa przypisania</th><th name="incident.description">Opis</th><th name="incident.number">Numer</th><th name="incident.short_description">Krótki opis</th><th name="incident.sys_updated_on">Zaktualizowano</th><th name="incident.state">Stan</th><th name="incident.caller_id">Zgłaszający</th><th name="incident.assigned_to">Przypisane do</th><th name="incident.parent_incident">Incydent nadrzędny</th><th name="incident.location" style="display:none">Lokalizacja</th></tr>'
                page.set_content('<table>' + headers + '</table>')
                available = set()
                self.assertEqual(collect(page, available), {})
                self.assertIn('description', available)
                self.assertNotIn('location', available)
                page.set_content('<table>' + headers + '<tr><td>Drukarka</td><td>LMPL-L1-Support</td><td>Pełny opis</td><td><a href="https://example.com/incident.do">INC1234567</a></td><td>Krótki opis testowy</td><td>2026-10-08 12:00:00</td><td>Nowy</td><td>Anna</td><td></td><td><a href="https://example.com/incident.do">INC7654321</a></td><td style="display:none">Sklep</td></tr></table>')
                rows = collect(page)
                self.assertEqual(set(rows), {'INC1234567'})
                row = rows['INC1234567']
                for key, value in {'configuration_item': 'Drukarka', 'assignment_group': 'LMPL-L1-Support', 'description': 'Pełny opis', 'short_description': 'Krótki opis testowy', 'updated': '2026-10-08 12:00:00', 'state': 'Nowy', 'caller': 'Anna', 'assigned_to': '', 'parent_incident': 'INC7654321'}.items():
                    self.assertEqual(row[key], value)
            finally:
                browser.close()

    def test_availability_hides_missing_without_forgetting_preference(self):
        root = tk.Tk()
        root.withdraw()
        try:
            with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
                with patch('app.read_json', return_value={'visible_columns': [*DEFAULT, 'state', 'description']}):
                    app = App(root, history_path=Path(folder)/'history.json', enable_tray=False)
                app.column_availability = {1: {'number', 'short_description', 'state'}}
                app.apply_visible_columns()
                self.assertIn('state', app.current_table['displaycolumns'])
                self.assertNotIn('description', app.current_table['displaycolumns'])
                self.assertIn('description', app.visible_columns)
                app.column_availability[2] = {'number', 'description'}
                app.apply_visible_columns()
                self.assertIn('description', app.current_table['displaycolumns'])
                app.column_availability[1].remove('state')
                app.apply_visible_columns()
                self.assertNotIn('state', app.current_table['displaycolumns'])
                app.history.add({'number':'INC1234567','url':'https://example.com/incident.do', 'description':'Opis', '_available_columns':['number','description']}, 'Filtr', 'https://example.com')
                app.apply_visible_columns()
                self.assertIn('description', app.table['displaycolumns'])
                self.assertNotIn('state', app.table['displaycolumns'])
                self.assertTrue(app.history.snapshot()['INC1234567']['incident']['description'])
        finally:
            root.update_idletasks()
            for timer in root.tk.call("after", "info"):
                root.after_cancel(timer)
            root.destroy()

    def test_picker_saves_unavailable_selection_and_shows_warning(self):
        from widgets import RoundedButton
        root = tk.Tk()
        try:
            with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
                with patch('app.read_json', return_value={}):
                    app = App(root, history_path=Path(folder)/'history.json', enable_tray=False)
                app.column_availability = {1: {'number', 'short_description', 'state'}}
                app.configure_columns()
                root.update()
                dialog = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel) and w.title()=="Widoczne kolumny")
                def descendants(widget):
                    for child in widget.winfo_children():
                        yield child
                        yield from descendants(child)
                checks = {w.cget('text'):w for w in descendants(dialog) if w.winfo_class()=='TCheckbutton'}
                self.assertFalse(checks['Opis'].instate(['disabled']))
                self.assertFalse(checks['Numer'].instate(['disabled']))
                self.assertEqual(app.column_badges['description'].winfo_manager(), 'grid')
                checks['Opis'].invoke()
                self.assertTrue(checks['Stan'].instate(['selected']))
                with patch('app.read_json', return_value={'teams_enabled':True}), patch('app.save_json') as save:
                    next(w for w in descendants(dialog) if isinstance(w, RoundedButton) and w.text=='Zapisz').invoke()
                stored = save.call_args.args[1]
                self.assertIn('state', stored['visible_columns'])
                self.assertIn('description', stored['visible_columns'])
                self.assertNotIn('description', app.current_table['displaycolumns'])
                self.assertTrue(stored['teams_enabled'])
                self.assertIn('state', app.current_table['displaycolumns'])
                self.assertIn('priority', app.visible_columns)
                self.assertNotIn('priority', app.current_table['displaycolumns'])
                app.configure_columns()
                root.update()
                dialog = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel) and w.title()=="Widoczne kolumny")
                buttons = {w.text:w for w in descendants(dialog) if isinstance(w, RoundedButton)}
                buttons['Przywróć domyślne'].invoke()
                self.assertIn('state', app.visible_columns)  # No change until Save.
                with patch('app.read_json', return_value={}), patch('app.save_json') as save:
                    buttons['Zapisz'].invoke()
                self.assertEqual(set(save.call_args.args[1]['visible_columns']), set(DEFAULT))
                self.assertEqual(set(app.visible_columns), set(DEFAULT))
                self.assertEqual(save.call_args.args[1]['column_order'], {})
                self.assertEqual(tuple(app.current_table['displaycolumns']), ('number', 'state', 'short_description'))
        finally:
            root.update_idletasks()
            for timer in root.tk.call("after", "info"):
                root.after_cancel(timer)
            root.destroy()
