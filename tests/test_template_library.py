import tkinter as tk
import unittest
from unittest.mock import patch
from tkinter import ttk

from neto_incident_monitor.template_library import migrate, put, resolve, clear_missing


class LibraryTests(unittest.TestCase):
    def test_migration_reference_rename_and_delete(self):
        filters = [{'name': 'Filtr', 'notification_templates': {'teams_webhook': {
            'enabled': True, 'message': '{lista incydentów}', 'item': '{number}'}}}]
        library, migrated = migrate({}, filters)
        identity = migrated[0]['notification_templates']['teams_webhook']['template_id']
        self.assertTrue(resolve({'template_id': identity}, library)['enabled'])
        self.assertIn('message', filters[0]['notification_templates']['teams_webhook'])
        put(library, 'Nowa nazwa', 'Lista: {lista incydentów}', '{number}', identity)
        self.assertEqual(resolve({'template_id': identity}, library)['name'], 'Nowa nazwa')
        self.assertEqual(migrate(library, migrated), (library, migrated))
        with self.assertRaises(ValueError):
            put(library, 'STANDARDOWY', 'x', 'x')
        with self.assertRaises(ValueError):
            put(library, 'nowa nazwa', 'x', 'x')
        del library[identity]
        clear_missing(migrated, library)
        self.assertEqual(migrated[0]['notification_templates']['teams_webhook']['template_id'], '')

    def test_library_and_references_saved_together(self):
        from neto_incident_monitor.app import App
        app = App.__new__(App)
        app.notification_library = {'id': {'name': 'Wspólny', 'message': '{lista incydentów}', 'item': '{number}'}}
        app.filters = [{'name': 'A', 'url': 'A', 'notification_templates': {'teams_webhook': {'template_id': 'id'}}},
                       {'name': 'B', 'url': 'B', 'notification_templates': {'google_chat_webhook': {'template_id': 'id'}}}]
        with patch('neto_incident_monitor.app.read_json', return_value={}), patch('neto_incident_monitor.app.save_json') as save:
            app.persist_filters()
        settings = save.call_args.args[1]
        self.assertEqual(settings['notification_library'], app.notification_library)
        self.assertEqual(settings['filters'], app.filters)
        library, filters = migrate(settings['notification_library'], settings['filters'])
        put(library, 'Zmieniony', 'Nowe: {lista incydentów}', '{number}', 'id')
        for entry in filters:
            config = next(iter(entry['notification_templates'].values()))
            self.assertEqual(resolve(config, library)['name'], 'Zmieniony')
        library.clear()
        clear_missing(filters, library)
        self.assertTrue(all(not next(iter(entry['notification_templates'].values()))['template_id'] for entry in filters))

    def test_standard_buttons_and_confirmation_and_cancel(self):
        from neto_incident_monitor.template_library_ui import show_channel_settings
        from neto_incident_monitor.widgets import RoundedButton
        root = tk.Tk(); root.withdraw()
        try:
            library = {'id': {'name': 'Moje', 'message': '{lista incydentów}', 'item': '{number}'}}
            selected = {'template_id': ''}
            show_channel_settings(root, 'Teams', 'teams_webhook', tk.StringVar(value=''), selected, library=library)
            window = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel))
            def children(parent):
                for w in parent.winfo_children():
                    yield w
                    yield from children(w)
            def button(label):
                return next(w for w in children(window) if isinstance(w, RoundedButton) and w.text == label)
            self.assertFalse(button('Edytuj').enabled)
            self.assertFalse(button('Usuń').enabled)
            combo = next(w for w in children(window) if isinstance(w, ttk.Combobox))
            combo.current(1); combo.event_generate('<<ComboboxSelected>>')
            self.assertTrue(button('Edytuj').enabled)
            with patch('neto_incident_monitor.template_library_ui.confirmation.askyesno', return_value=False) as confirm:
                button('Usuń').invoke()
                confirm.assert_called_once()
            self.assertEqual(combo.get(), 'Moje')
            with patch('neto_incident_monitor.template_library_ui.confirmation.askyesno', return_value=True):
                button('Usuń').invoke()
            self.assertEqual(combo.get(), 'Standardowy')
            self.assertFalse(button('Usuń').enabled)
            button('Anuluj').invoke()
            self.assertIn('id', library)
            self.assertEqual(selected, {'template_id': ''})
        finally:
            root.destroy()
