import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import Mock, patch

from neto_incident_monitor.google_chat_ui import show_config
from neto_incident_monitor.filter_settings import show_filter_settings
from neto_incident_monitor.widgets import RoundedButton, Toggle
from tests.test_google_chat import URL


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


class GoogleChatUITests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.app = Mock()
        self.app.root = self.root
        self.app.google_chat_webhook = ''
        self.app.google_chat_enabled = tk.BooleanVar(value=False)
        self.app.saved_google_chat = False, ''
        self.app.saving_google_chat = False
        self.style = ttk.Style(self.root)
        self.style.configure('App.TCheckbutton')

    def tearDown(self):
        for timer in self.root.tk.call('after', 'info'):
            self.root.after_cancel(timer)
        self.root.destroy()

    def test_configuration_masks_url_and_test_does_not_require_global_enable(self):
        failures = []
        def operate():
            dialog = next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel))
            try:
                widgets = list(descendants(dialog))
                field = next(w for w in widgets if isinstance(w, ttk.Entry))
                self.assertEqual(field.cget('show'), '•')
                field.insert(0, URL)
                next(w for w in widgets if isinstance(w, RoundedButton) and w.text == 'Wyślij test').invoke()
                self.app.google_chat_sender.submit.assert_called_once_with(URL, 'Test powiadomień ServiceNow', 'Połączenie z aplikacją działa.', True)
                next(w for w in widgets if isinstance(w, RoundedButton) and w.text == 'Zapisz').invoke()
            except Exception as error:
                failures.append(error)
                dialog.destroy()
        self.root.after(100, operate)
        with patch('neto_incident_monitor.app.read_json', return_value={}), \
             patch('neto_incident_monitor.app.save_json') as save:
            show_config(self.app)
            self.assertFalse(failures, failures)
            self.assertEqual(save.call_args.args[1], {'google_chat_enabled': False, 'google_chat_webhook': URL})

    def test_filter_google_chat_toggle_is_enabled_independently_and_saved(self):
        self.app.filters = [{'name': 'Test', 'url': 'filter'}]
        self.app.notify = tk.BooleanVar(value=False)
        self.app.teams_enabled = tk.BooleanVar(value=False)
        self.app.google_chat_enabled.set(True)
        show_filter_settings(self.app, 0)
        self.root.update()
        dialog = next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel))
        widgets = list(descendants(dialog))
        toggles = [w for w in widgets if isinstance(w, Toggle)]
        self.assertEqual(len(toggles), 3)
        labels = [w.cget('text') for w in widgets if isinstance(w, ttk.Label)]
        self.assertNotIn('Powiadomienia Windows', labels)
        self.assertNotIn('Powiadomienia Microsoft Teams', labels)
        self.assertIn('Powiadomienia Google Chat', labels)
        self.assertTrue(toggles[0].variable.get())
        toggles[0].toggle()
        next(w for w in widgets if isinstance(w, RoundedButton) and w.text == 'Zapisz').invoke()
        self.assertFalse(self.app.filters[0]['notify_google_chat'])
        self.app.persist_filters.assert_called_once()

    def test_hidden_channels_keep_preferences_when_saved_and_reopened(self):
        self.app.filters = [{'name': 'Test', 'url': 'filter',
                             'notify_windows': True, 'notify_teams': False,
                             'notify_google_chat': True}]
        self.app.notify = tk.BooleanVar(value=False)
        self.app.teams_enabled = tk.BooleanVar(value=False)
        show_filter_settings(self.app, 0)
        dialog = next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel))
        widgets = list(descendants(dialog))
        self.assertEqual(len([w for w in widgets if isinstance(w, Toggle)]), 2)
        next(w for w in widgets if isinstance(w, RoundedButton) and w.text == 'Zapisz').invoke()
        for key, expected in [('notify_windows', True), ('notify_teams', False), ('notify_google_chat', True)]:
            self.assertEqual(self.app.filters[0][key], expected)
        self.app.notify.set(True)
        self.app.teams_enabled.set(True)
        self.app.google_chat_enabled.set(True)
        show_filter_settings(self.app, 0)
        dialog = next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel))
        toggles = [w for w in descendants(dialog) if isinstance(w, Toggle)]
        self.assertEqual([w.variable.get() for w in toggles[:3]], [True, False, True])
