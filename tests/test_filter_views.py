import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from neto_incident_monitor.app import App
from neto_incident_monitor.widgets import Toggle


class FilterViewTests(unittest.TestCase):
    def test_filter_list_icons_follow_global_and_saved_filter_settings(self):
        from tkinter import ttk
        from neto_incident_monitor.widgets import RoundedButton

        settings = {'notify': True, 'google_chat_enabled': True, 'teams_enabled': True,
                    'filters': [{'name': 'Lista A', 'url': 'https://adeo.service-now.com/incident_list.do',
                                 'notify_windows': False, 'notify_teams': False},
                                {'name': 'Lista wyłączona', 'url': 'https://adeo.service-now.com/sc_task_list.do',
                                 'enabled': False, 'notify_google_chat': False}]}
        root = tk.Tk()
        try:
            with tempfile.TemporaryDirectory() as directory, \
                    patch('neto_incident_monitor.app.read_json', return_value=settings), \
                    patch('neto_incident_monitor.app.save_json'):
                app = App(root, history_path=Path(directory) / 'history.json', enable_tray=False, apply_startup=False)
                root.update()
                table = app.filter_table

                def images():
                    return [table.itemcget(item, 'image') for item in table.find_withtag('notification_icon')]

                def image(channel, active):
                    return str(table.notification_icon(channel, active))

                windows_gray, windows_color = image('windows', False), image('windows', True)
                chat_color, chat_gray = image('google_chat', True), image('google_chat', False)
                teams_gray, teams_color = image('teams', False), image('teams', True)
                self.assertEqual(images(), [windows_gray, chat_color, teams_gray, windows_color, chat_gray, teams_color])

                table.updating_item = '0'
                app.splitter.event_generate('<ButtonPress-1>', x=1, y=5)
                app.splitter.event_generate('<ButtonRelease-1>', x=-160, y=5)
                root.update()
                self.assertEqual(app.sidebar_canvas.winfo_width(), 235)
                icon = table.find_withtag('notification_icon')[0]
                status = next(item for item in table.find_all()
                              if table.type(item) == 'text' and table.itemcget(item, 'text') == 'Aktualizuje')
                name = next(item for item in table.find_all()
                            if table.type(item) == 'text' and table.itemcget(item, 'text') == 'Lista A')
                self.assertLess(table.bbox(icon)[3], table.bbox(status)[1])
                self.assertLess(table.bbox(name)[3], table.bbox(status)[1])

                app.google_chat_enabled.set(False)
                self.assertEqual(images(), [windows_gray, teams_gray, windows_color, teams_color])

                app.configure_filter_notifications('0')
                dialog = next(widget for widget in root.winfo_children()
                              if isinstance(widget, tk.Toplevel) and widget.title() == 'Ustawienia filtra')
                panel = dialog.winfo_children()[0]
                windows_row = next(row for row in panel.winfo_children() if any(
                    isinstance(label, ttk.Label) and label.cget('text') == 'Powiadomienia Windows'
                    for label in row.winfo_children()))
                next(widget for widget in windows_row.winfo_children() if isinstance(widget, Toggle)).toggle()
                self.assertEqual(images()[0], windows_gray)
                next(widget for row in panel.winfo_children() for widget in row.winfo_children()
                     if isinstance(widget, RoundedButton) and widget.text == 'Zapisz').invoke()
                self.assertEqual(images(), [windows_color, teams_gray, windows_color, teams_color])

                app.notify.set(False)
                app.teams_enabled.set(False)
                self.assertEqual(images(), [])
        finally:
            for timer in root.tk.call('after', 'info'):
                root.after_cancel(timer)
            root.destroy()

    def test_filter_webhook_inputs_validate_save_and_clear(self):
        from neto_incident_monitor.filter_settings import show_filter_settings
        from neto_incident_monitor.widgets import RoundedButton
        from tkinter import ttk
        root = tk.Tk()
        try:
            app = Mock(root=root)
            app.filters = [{'name': 'A', 'url': 'A'}]
            app.notify.get.return_value = False
            app.teams_enabled.get.return_value = True
            app.google_chat_enabled.get.return_value = True
            def descendants(widget):
                for child in widget.winfo_children():
                    yield child
                    yield from descendants(child)
            def button(widget, text):
                return next(w for w in descendants(widget) if isinstance(w, RoundedButton) and w.text == text)
            def open_channel(dialog, channel):
                gears = [w for w in descendants(dialog) if isinstance(w, RoundedButton) and w.icon == 'gear']
                self.assertEqual(len(gears), 2)
                gear = next(w for w in gears if any(
                    isinstance(label, ttk.Label) and label.cget('text') == f'Powiadomienia {channel}'
                    for label in w.master.winfo_children()))
                self.assertEqual(int(gear.grid_info()['column']), 1)
                self.assertEqual(int(gear.cget('width')), 36)
                gear.invoke()
                child = next(w for w in dialog.winfo_children() if isinstance(w, tk.Toplevel))
                field = next(w for w in descendants(child) if isinstance(w, ttk.Entry))
                self.assertTrue(field.cget('show'))
                return child, field
            show_filter_settings(app, 0)
            root.update()
            dialog = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel))
            self.assertFalse(any(isinstance(w, ttk.Entry) for w in descendants(dialog)))
            child, field = open_channel(dialog, 'Microsoft Teams')
            field.insert(0, 'http://invalid.example')
            with patch('neto_incident_monitor.filter_settings.messagebox.showerror') as error:
                button(child, 'Zastosuj').invoke()
            error.assert_called_once()
            app.persist_filters.assert_not_called()
            button(child, 'Anuluj').invoke()
            self.assertIs(root.grab_current(), dialog)
            teams = 'https://test.api.powerplatform.com/invoke?sig=dummy'
            chat = 'https://chat.googleapis.com/v1/spaces/test/messages?key=dummy&token=dummy'
            for channel, value in [('Microsoft Teams', teams), ('Google Chat', chat)]:
                child, field = open_channel(dialog, channel)
                field.insert(0, value)
                button(child, 'Zastosuj').invoke()
            self.assertEqual(app.filters[0]['teams_webhook'], teams)
            button(dialog, 'Anuluj').invoke()
            self.assertEqual(app.filters[0]['teams_webhook'], teams)
            self.assertEqual(app.filters[0]['google_chat_webhook'], chat)
            show_filter_settings(app, 0)
            dialog = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel))
            app.persist_filters.side_effect = OSError('failure')
            with patch('neto_incident_monitor.filter_settings.messagebox.showerror'):
                button(dialog, 'Zapisz').invoke()
            self.assertEqual(app.filters[0]['teams_webhook'], teams)
            app.persist_filters.side_effect = None
            button(dialog, 'Zapisz').invoke()
            self.assertEqual(app.filters[0]['teams_webhook'], teams)
            self.assertEqual(app.filters[0]['google_chat_webhook'], chat)
            show_filter_settings(app, 0)
            dialog = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel))
            # Cancelling the nested editor preserves its previous value.
            child, field = open_channel(dialog, 'Microsoft Teams')
            field.delete(0, 'end')
            button(child, 'Anuluj').invoke()
            child, field = open_channel(dialog, 'Microsoft Teams')
            self.assertEqual(field.get(), teams)
            button(child, 'Anuluj').invoke()
            for channel in ('Microsoft Teams', 'Google Chat'):
                child, field = open_channel(dialog, channel)
                field.delete(0, 'end')
                button(child, 'Zastosuj').invoke()
            button(dialog, 'Zapisz').invoke()
            self.assertEqual(app.filters[0]['teams_webhook'], '')
            self.assertEqual(app.filters[0]['google_chat_webhook'], '')
        finally:
            root.destroy()

    def test_per_filter_webhooks_override_globals_and_empty_uses_global(self):
        from neto_incident_monitor.secret_config import UnavailableSecret
        app = App.__new__(App)
        app.filters = [{'url': 'A', 'name': 'A', 'teams_webhook': 'teams-custom', 'google_chat_webhook': 'chat-custom'},
                       {'url': 'B', 'name': 'B', 'teams_webhook': '', 'google_chat_webhook': ''}]
        app.notify = Mock(); app.notify.get.return_value = False
        app.teams_enabled = Mock(); app.teams_enabled.get.return_value = True
        app.google_chat_enabled = Mock(); app.google_chat_enabled.get.return_value = True
        app.teams_webhook = 'teams-global'; app.google_chat_webhook = 'chat-global'
        app.teams_sender = Mock(); app.google_chat_sender = Mock()
        incident = {'number': 'INC1234567'}
        for url, teams, chat in [('A', 'teams-custom', 'chat-custom'), ('B', 'teams-global', 'chat-global')]:
            app.notify_filter(url, [incident], manual=True)
            self.assertEqual(app.teams_sender.submit.call_args.args[0], teams)
            self.assertEqual(app.google_chat_sender.submit.call_args.args[0], chat)
        app.filters[0]['teams_webhook'] = UnavailableSecret({})
        count = app.teams_sender.submit.call_count
        app.notify_filter('A', [incident])
        self.assertEqual(app.teams_sender.submit.call_count, count)
        app.teams_enabled.get.return_value = False
        app.google_chat_enabled.get.return_value = False
        count = app.google_chat_sender.submit.call_count
        app.notify_filter('A', [incident])
        self.assertEqual(app.google_chat_sender.submit.call_count, count)

    def test_legacy_read_settings_are_removed_on_config_roundtrip(self):
        import json
        from neto_incident_monitor.app import read_json, save_json

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            config = {
                "notification_revision": "0123456789abcdef0123456789abcdef",
                "highlight_unread": True,
                "visible_columns": ["read", "number"],
                "column_widths": {"read": 140, "number": 155},
                "filter_visible_columns": {"A": ["number", "read"]},
                "filter_column_profiles": {"A": {
                    "schema": [{"key": "number"}, {"key": "read"}],
                    "order": ["read", "number", "time"],
                    "visible": ["number", "read"],
                    "widths": {"read": 140, "number": 155},
                }},
            }
            path.write_text(json.dumps(config), encoding="utf-8")
            with patch("neto_incident_monitor.app.CONFIG", path):
                loaded = read_json(path, {})
                self.assertEqual(json.loads(path.read_text(encoding="utf-8")), config)
                save_json(path, loaded)
                self.assertEqual(read_json(path, {}), loaded)
            self.assertNotIn("highlight_unread", loaded)
            self.assertEqual(loaded["visible_columns"], ["number"])
            self.assertEqual(loaded["column_widths"], {"number": 155})
            self.assertEqual(loaded["filter_visible_columns"], {"A": ["number"]})
            self.assertEqual(loaded["filter_column_profiles"]["A"], {
                "schema": [{"key": "number"}], "order": ["number", "time"],
                "visible": ["number"], "widths": {"number": 155},
            })

    def test_selection_scopes_both_tables_and_read_actions(self):
        root = tk.Tk()
        try:
            with tempfile.TemporaryDirectory() as folder:
                settings = {"highlight_unread": True, "filters": [{"name": "A", "url": "https://adeo.service-now.com/incident_list.do?fixture=a"},
                                        {"name": "B", "url": "https://adeo.service-now.com/incident_list.do?fixture=b"}]}
                with patch("neto_incident_monitor.app.read_json", return_value=settings):
                    app = App(root, history_path=Path(folder)/"history.json", enable_tray=False)
                root.update()
                self.assertFalse(app.clear_history_button.winfo_manager())
                app.events.put(("filter_updating", app.filters[1]["url"]))
                app.drain()
                self.assertEqual(app.filter_table.updating_item, "1")
                app.events.put(("filter_updating", None))
                app.drain()
                self.assertIsNone(app.filter_table.updating_item)
                first_url = app.filters[0]["url"]
                second_url = app.filters[1]["url"]
                from neto_incident_monitor.dynamic_columns import update_profile
                app.column_profiles = {url: update_profile(None, [{"key": k, "label": k} for k in keys])
                                       for url, keys in [(first_url, ["number", "state"]), (second_url, ["number", "short_description"]) ]}
                app.filter_table.selection_set("1")
                self.assertEqual(app.visible_columns, ["number", "short_description"])
                app.filter_table.selection_set("0")
                self.assertEqual(app.visible_columns, ["number", "state"])
                app.visible_columns = list(app.legacy_visible_columns)
                app.filters[1]["url"] = "https://adeo.service-now.com/sc_task_list.do"
                app.filter_table.selection_set("1")
                with patch("neto_incident_monitor.app.save_json"):
                    app.accept_column_schema(app.selected_filter_url(), [{"key": k, "label": k} for k in ["number", "requested_for"]])
                self.assertEqual(tuple(app.current_table['displaycolumns']), ('number', 'requested_for'))
                self.assertIn("requested_for", app.applicable_columns())
                self.assertNotIn("caller", app.applicable_columns())
                self.assertNotIn("parent_incident", app.applicable_columns())
                app.filters[1]["url"] = second_url
                app.filter_visible_columns = {}
                app.filter_table.selection_set("0")
                app.tabs.select(1)
                root.update()
                self.assertEqual(app.clear_history_button.winfo_manager(), "pack")
                app.tabs.select(0)
                root.update()
                self.assertFalse(app.clear_history_button.winfo_manager())
                for i, entry in enumerate(app.filters, 1):
                    incident = {"number": "INC1", "url": entry["url"], "short_description": entry["name"]}
                    app.history.add(incident, entry["name"], entry["url"])
                    app.snapshots[i] = {"INC1": incident}
                app.filter_selected()
                self.assertNotIn("filter", app.current_table["columns"])
                self.assertEqual(app.current_table.set(app.current_table.get_children()[0], "short_description"), "A")
                app.filter_table.selection_set("1")
                self.assertEqual(app.current_table.set(app.current_table.get_children()[0], "short_description"), "B")
                self.assertEqual(app.table.set(app.table.get_children()[0], "short_description"), "B")
                for table in (app.current_table, app.table):
                    self.assertNotIn("read", table["columns"])
                    self.assertNotIn("unread", table.item(table.get_children()[0], "tags"))
                with patch("neto_incident_monitor.app.save_json"):
                    app.notify.set(False)
                    app.teams_enabled.set(False)
                app.filters[1]["allow_large_list"] = True
                self.assertTrue(app.configure_filter_button.enabled)
                app.configure_filter_button.invoke()
                root.update()
                dialog = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel) and w.title()=="Ustawienia filtra")
                def descendants(widget):
                    for child in widget.winfo_children():
                        yield child
                        yield from descendants(child)
                toggles = [w for w in descendants(dialog) if isinstance(w, Toggle)]
                self.assertEqual([w.enabled for w in toggles], [True, True])
                self.assertTrue(toggles[1].variable.get())
                toggles[1].toggle()
                from neto_incident_monitor.widgets import RoundedButton
                with patch.object(app, "persist_filters") as persist:
                    next(w for w in descendants(dialog) if isinstance(w, RoundedButton) and w.text=="Zapisz").invoke()
                    persist.assert_called_once()
                self.assertFalse(app.filters[1]["allow_large_list"])
        finally:
            for timer in root.tk.call("after", "info"):
                root.after_cancel(timer)
            root.destroy()

    def test_notification_channels_and_filter_names_are_independent(self):
        app = App.__new__(App)
        app.filters = [{"name": "A", "url": "A", "notify_windows": True, "notify_teams": False},
                       {"name": "B", "url": "B", "notify_windows": False, "notify_teams": True}]
        app.notify = Mock(); app.notify.get.return_value = True
        app.teams_enabled = Mock(); app.teams_enabled.get.return_value = True
        app.google_chat_enabled = Mock(); app.google_chat_enabled.get.return_value = False
        app.teams_webhook = "webhook"
        app.teams_sender = Mock(); app.root = Mock()
        incident = {"number": "INC1", "location": "Store", "short_description": "Description"}
        with patch("plyer.notification.notify") as notify:
            app.notify_filter("A", [incident])
            self.assertEqual(notify.call_args.kwargs["title"], "A · 1")
            self.assertEqual(notify.call_args.kwargs["message"], "INC1 - Description")
            app.teams_sender.submit.assert_not_called()
            app.notify_filter("B", [incident])
            self.assertEqual(notify.call_count, 1)
            app.teams_sender.submit.assert_called_once_with("webhook", "B · 1", "INC1 - Description")
            app.teams_enabled.get.return_value = False
            app.notify_filter("B", [incident])
            self.assertEqual(app.teams_sender.submit.call_count, 1)
