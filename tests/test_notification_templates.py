import json
import tkinter as tk
import unittest
from unittest.mock import Mock

from neto_incident_monitor.notification_templates import render, validate, slices
from neto_incident_monitor.teams_notifications import payload, message_chunks
from neto_incident_monitor.google_chat_notifications import payloads


class TemplateTests(unittest.TestCase):
    def test_friendly_names_keep_stable_fields_after_header_change(self):
        config = {'message': '{lista incydentów}', 'item': '{Numer} — {Krótki opis}',
                  'bindings': {'Numer': 'number', 'Krótki opis': 'short_description'}}
        rows = [{'number': 'INC1', '_values': {'short_description': 'Opis'}}]
        self.assertEqual(render(config, 'Filtr', rows), 'INC1 — Opis')
        self.assertEqual(validate(config['message'], config['item'],
                                  [{'key': 'number', 'label': 'Number'},
                                   {'key': 'short_description', 'label': 'Nowa nazwa'}], config['bindings']), [])

    def test_two_levels_dynamic_fields_no_recursive_expansion(self):
        settings = {'message': '{filtr}: {liczba}\n{lista incydentów}\nKoniec',
                    'item': '{number}: {custom.field} / {missing}'}
        rows = [{'number': 'INC1', '_values': {'custom.field': '{filtr}'}},
                {'number': 'SCTASK2', '_values': {'custom.field': 'B'}}]
        self.assertEqual(render(settings, 'A', rows), 'A: 2\nINC1: {filtr} / \nSCTASK2: B / \nKoniec')
        settings['item'] += '\n'
        self.assertIn('INC1: {filtr} / \n\nSCTASK2:', render(settings, 'A', rows))
        self.assertEqual(validate(settings['message'], settings['item'],
                                  [{'key': 'number'}, {'key': 'custom.field'}]), ['missing'])
        with self.assertRaises(ValueError):
            validate('Brak listy', settings['item'], [])

    def test_links_in_arbitrary_positions_and_untrusted_markup(self):
        url = 'https://adeo.service-now.com/incident.do?sys_id=123'
        text = 'Zgłoszenie: INC123 — <users/all> **opis**'
        teams = payload('', text, {'INC123': url})
        self.assertTrue(teams['text'].startswith('Zgłoszenie: <a href='))
        self.assertIn('[INC123]', teams['attachments'][0]['content']['body'][0]['text'])
        chat = payloads('', text, {'INC123': url})[0]['text']
        self.assertTrue(chat.startswith('Zgłoszenie: <https://'))
        self.assertNotIn('<users/all>', chat)
        self.assertNotIn('**opis**', chat)
        self.assertNotIn('<a ', payload('', text, {'INC123': 'javascript:x'})['text'])

    def test_teams_chunks_preserve_text_and_bound_payload(self):
        text = ('Zażółć <>& ' * 300 + '\n') * 30
        chunks = list(message_chunks('', text))
        self.assertGreater(len(chunks), 1)
        self.assertEqual(''.join(chunks), text)
        self.assertTrue(all(len(json.dumps(payload('', chunk)).encode()) <= 25000 for chunk in chunks))
        boundary = 'x' * 995 + ' INC1234567890 ' + 'y' * 2000
        parts = list(slices(boundary, 1000))
        self.assertEqual(''.join(parts), boundary)
        self.assertTrue(any('INC1234567890' in part for part in parts))
        long_chat = 'Zażółć ' * 3000
        self.assertEqual(''.join(p['text'].replace('\n', '') for p in payloads('', long_chat)), long_chat)

    def test_channel_specific_format_and_windows_unchanged(self):
        from neto_incident_monitor.app import App
        app = App.__new__(App)
        app.filters = [{'url': 'A', 'name': 'Filter', 'notification_templates': {
            'teams_webhook': {'enabled': True, 'message': '{filtr}\n{lista incydentów}', 'item': '{number}: {x}'}}}]
        app.teams_enabled = app.google_chat_enabled = Mock()
        app.teams_enabled.get.return_value = True
        app.notify = Mock(); app.notify.get.return_value = False
        app.teams_webhook = app.google_chat_webhook = 'destination'
        app.teams_sender = Mock(); app.google_chat_sender = Mock()
        app.notify_filter('A', [{'number': 'INC1', '_values': {'x': 'dynamic'}}])
        self.assertEqual(app.teams_sender.submit.call_args.args[1:], ('', 'Filter\nINC1: dynamic'))
        self.assertEqual(app.google_chat_sender.submit.call_args.args[1], 'Filter · 1')

    def test_standard_is_identical_for_inc_and_tasks_and_counts_unique_records(self):
        from neto_incident_monitor.notification_templates import standard
        for prefix in ('INC', 'SCTASK'):
            first = {'number': prefix + '1', 'short_description': 'Pierwszy'}
            self.assertEqual(standard('Filtr', [first]), ('Filtr · 1', prefix + '1 - Pierwszy'))
            second = {'number': prefix + '2', 'short_description': 'Drugi'}
            self.assertEqual(standard('Filtr', [first, first, second]),
                             ('Filtr · 2', prefix + '1 - Pierwszy\n' + prefix + '2 - Drugi'))

    def test_editor_draft_preview_toggle_and_column_insertion(self):
        from neto_incident_monitor.notification_template_ui import build_editor
        from tkinter import ttk
        from neto_incident_monitor.widgets import RoundedButton
        root = tk.Tk(); root.withdraw()
        try:
            config = {'enabled': True, 'message': '{lista incydentów}', 'item': '{number}'}
            panel = ttk.Frame(root); panel.pack()
            draft, preview = build_editor(panel, config, [{'key': 'x', 'label': 'Własna kolumna'}], 'Filter')
            def all_children(parent):
                for child in parent.winfo_children():
                    yield child
                    yield from all_children(child)
            button = next(w for w in all_children(panel) if isinstance(w, RoundedButton) and w.text == 'Wstaw')
            button.invoke()
            self.assertIn('{Własna kolumna}', draft()['item'])
            self.assertIn('Przykład: Własna kolumna', preview())
            self.assertEqual(config['item'], '{number}')
            toggle = next(w for w in all_children(panel) if isinstance(w, ttk.Checkbutton))
            toggle.invoke(); self.assertFalse(draft()['enabled'])
            toggle.invoke(); self.assertTrue(draft()['enabled'])
        finally:
            root.destroy()

    def test_nested_apply_parent_cancel_and_save_rollback(self):
        from neto_incident_monitor.filter_settings import show_filter_settings
        from neto_incident_monitor.widgets import RoundedButton
        from tkinter import ttk
        from unittest.mock import patch
        root = tk.Tk(); root.withdraw()
        try:
            app = Mock(root=root)
            app.filters = [{'url': 'A', 'name': 'Filter'}]
            app.column_profiles = {'A': {'schema': [{'key': 'number', 'label': 'Numer'}]}}
            app.notify.get.return_value = False
            app.teams_enabled.get.return_value = True
            app.google_chat_enabled.get.return_value = False
            def descendants(parent):
                for child in parent.winfo_children():
                    yield child
                    yield from descendants(child)
            def button(parent, label):
                return next(w for w in descendants(parent) if isinstance(w, RoundedButton) and w.text == label)
            def open_draft(name, apply=True):
                show_filter_settings(app, 0)
                parent = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel))
                next(w for w in descendants(parent) if isinstance(w, RoundedButton) and w.icon == 'gear').invoke()
                child = next(w for w in parent.winfo_children() if isinstance(w, tk.Toplevel))
                button(child, 'Dodaj').invoke()
                editor = next(w for w in child.winfo_children() if isinstance(w, tk.Toplevel))
                next(w for w in descendants(editor) if isinstance(w, ttk.Entry)).insert(0, name)
                button(editor, 'Zapisz szablon').invoke()
                self.assertTrue(any(v['name'] == name for v in app.notification_library.values()))
                button(child, 'Zastosuj' if apply else 'Anuluj').invoke()
                return parent
            parent = open_draft('Zachowany', apply=False)
            self.assertNotIn('notification_templates', app.filters[0])
            button(parent, 'Anuluj').invoke()
            self.assertNotIn('notification_templates', app.filters[0])
            self.assertTrue(any(v['name'] == 'Zachowany' for v in app.notification_library.values()))
            app.persist_filters.assert_called_once()
            parent = open_draft('Wspólny')
            selected_id = app.filters[0]['notification_templates']['teams_webhook']['template_id']
            self.assertEqual(app.notification_library[selected_id]['name'], 'Wspólny')
            app.persist_filters.side_effect = OSError('failure')
            with patch('neto_incident_monitor.filter_settings.messagebox.showerror'):
                button(parent, 'Zapisz').invoke()
            self.assertEqual(app.filters[0]['notification_templates']['teams_webhook']['template_id'], selected_id)
            app.persist_filters.side_effect = None
            button(parent, 'Zapisz').invoke()
            identity = app.filters[0]['notification_templates']['teams_webhook']['template_id']
            self.assertEqual(app.notification_library[identity]['name'], 'Wspólny')
        finally:
            root.destroy()
