import json
import queue
import tempfile
import threading
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from neto_incident_monitor.app import App
from neto_incident_monitor.favorites import classify, commit_selection
from neto_incident_monitor.favorites_worker import read_on_session
from neto_incident_monitor.read_errors import Cancelled
from neto_incident_monitor.login_diagnostics import _logger


def item(name='Filtr A', href='/incident_list.do?sysparm_query=active%3Dtrue'):
    return dict(source_id='synthetic', name=name, href=href, groups=['Grupa A'])


class FavoritesModelTests(unittest.TestCase):
    def test_bare_menu_links_resolve_from_tenant_root_and_deduplicate(self):
        query='?sysparm_query=short_descriptionLIKE%C5%82%C3%B3d%C5%BA%5Eactive%3Dtrue&sysparm_view=default'
        rows=classify([item(href='incident_list.do'+query),
            item(href='/incident_list.do'+query),item(href='sc_task_list.do'),
            item(href='sc_request_list.do'),item(href='sc_req_item_list.do'),
            item(href='home.do'),item(href='$knowledge.do'),
            item(href='https://example.com/incident_list.do')],[])
        self.assertEqual([r['status'] for r in rows],
            ['ready','existing','ready','ready','ready','unsupported','unsupported','invalid'])
        self.assertEqual(rows[0]['url'],'https://adeo.service-now.com/incident_list.do'+query)
        self.assertEqual([r['kind'] for r in rows[:5]],['INC','INC','SCTASK','REQ','RITM'])

    def test_validation_relative_links_duplicates_unicode_and_foreign_targets(self):
        rows = classify([item(),item(),item('Filtr A','/sc_task_list.do'),
            item('Wiedza','/$knowledge.do'),item('Obcy','https://example.com/incident_list.do'),
            item('Kod','javascript:alert(1)'),item('Błędny','https://['),
            item('Polski','/incident_list.do?sysparm_query=short_descriptionLIKE%C5%82%C3%B3d%C5%BA')], [])
        self.assertEqual([r['status'] for r in rows], ['ready','existing','ready','unsupported','invalid','invalid','invalid','ready'])
        self.assertTrue(rows[0]['url'].startswith('https://adeo.service-now.com/incident_list.do?'))
        self.assertIn('%C5%82', rows[-1]['url'])

    def test_commit_keeps_existing_and_disables_new_entries(self):
        app = Mock(filters=[dict(name='Istniejący',url='https://adeo.service-now.com/sc_task_list.do')])
        old = list(app.filters)
        with patch('neto_incident_monitor.app.read_json', return_value={}):
            self.assertEqual(commit_selection(app,[item(),item()],{0,1}),1)
        self.assertEqual(app.filters[0], old[0])
        for key in ('enabled','notify_windows','notify_teams','notify_google_chat'):
            self.assertIs(app.filters[-1][key],False)
        app.persist_filters.assert_called_once()

    def test_commit_rechecks_duplicates_added_after_preview(self):
        app = Mock(filters=[])
        items = [item(), item('Filtr B', '/sc_task_list.do')]
        preview = classify(items, app.filters)
        self.assertEqual([row['status'] for row in preview], ['ready', 'ready'])
        existing = {'name': 'Dodany podczas podglądu', 'url': preview[0]['url'], 'enabled': True}
        app.filters = [existing]

        with patch('neto_incident_monitor.app.read_json', return_value={}):
            self.assertEqual(commit_selection(app, items, {0, 1}), 1)

        self.assertEqual(app.filters[0], existing)
        self.assertEqual(app.filters[1]['url'], preview[1]['url'])
        self.assertFalse(app.filters[1]['enabled'])
        app.persist_filters.assert_called_once()

    def test_failed_save_preserves_memory_and_allows_retry(self):
        app = Mock(filters=[])
        original = app.filters
        app.persist_filters.side_effect = OSError('SYNTHETIC_SECRET')
        with patch('neto_incident_monitor.app.read_json', return_value={}):
            with self.assertRaises(OSError):
                commit_selection(app,[item()],{0})
            self.assertIs(app.filters, original)
            app.persist_filters.side_effect=None
            self.assertEqual(commit_selection(app,[item()],{0}),1)

    def test_external_config_change_is_not_overwritten(self):
        app=Mock(filters=[])
        with patch('neto_incident_monitor.app.read_json', return_value={'filters':[dict(name='Inny',url='https://adeo.service-now.com/incident_list.do')]}):
            with self.assertRaises(ValueError):
                commit_selection(app,[item()],{0})
        app.persist_filters.assert_not_called()

    def test_short_address_is_not_resolved_by_navigating(self):
        row=classify([item(href='/now/nav/ui/classic/__tinyId__/abcdefghijklmnop')],[])[0]
        self.assertEqual(row['status'],'ready')
        self.assertEqual(row['kind'],'Skrót')

    def test_real_atomic_save_failure_preserves_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'config.json'
            path.write_text('{"filters": [], "urls": []}',encoding='utf-8')
            before=path.read_bytes()
            app=App.__new__(App);app.filters=[]
            with patch('neto_incident_monitor.app.CONFIG',path), \
                 patch('pathlib.Path.replace',side_effect=PermissionError('SYNTHETIC_SECRET')):
                with self.assertRaises(OSError):
                    commit_selection(app,[item()],{0})
            self.assertEqual(app.filters,[])
            self.assertEqual(path.read_bytes(),before)
            self.assertFalse(path.with_suffix('.tmp').exists())


class FavoritesRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.page = Mock()
        self.stop = threading.Event()
        self.session = Mock(active_job=Mock(id=17))
        self.request = {'id': 'a' * 32, 'events': queue.Queue()}
        self.favorites = {'status': 200, 'result': {'favorites': [
            {'id': 'synthetic', 'title': 'Filtr A', 'url': '/incident_list.do'},
        ]}, 'next': False, 'total': None}

    def read(self):
        return read_on_session(self.page, self.request, self.session, self.stop)

    def test_transient_failure_and_expired_session_share_one_retry_budget(self):
        self.page.evaluate.side_effect = [{'status': 503}, {'status': 401}, self.favorites]
        self.session.authenticate.return_value = True
        with self.assertLogs(_logger, level='INFO') as captured:
            self.assertTrue(self.read())
        self.session.authenticate.assert_called_once_with(self.page, self.stop)
        self.assertEqual(self.page.evaluate.call_count, 3)
        events = list(self.request['events'].queue)
        self.assertIn(('a' * 32, 'status', 'Oczekiwanie na logowanie do ServiceNow…'), events)
        self.assertEqual(events[-1][2][0], 'success')
        records = [json.loads(record.getMessage()) for record in captured.records]
        self.assertTrue(all(row.get('import_id') == 'a' * 32 and row.get('request_id') == 17 for row in records))
        self.assertTrue(any(row.get('read_reason') == 'api_service' for row in records))
        self.assertTrue(any(row['event'] == 'favorites_end' and row['outcome'] == 'returned' for row in records))

    def test_access_denial_and_rate_limit_finish_without_retry(self):
        for status, message in ((403, 'odmówił dostępu'), (429, 'ograniczył liczbę żądań')):
            with self.subTest(status=status):
                self.page.evaluate.reset_mock(return_value=True)
                self.page.evaluate.return_value = {'status': status}
                self.assertFalse(self.read())
                self.page.evaluate.assert_called_once()
                token, kind, (outcome, text) = list(self.request['events'].queue)[-1]
                self.assertEqual((token, kind, outcome), ('a' * 32, 'result', 'error'))
                self.assertIn(message, text)
        self.session.authenticate.assert_not_called()

    def test_cancellation_during_login_cannot_publish_partial_or_successful_preview(self):
        self.page.evaluate.return_value = {'status': 401}
        def cancel(*_):
            self.stop.set()
            return True
        self.session.authenticate.side_effect = cancel
        with self.assertRaises(Cancelled):
            self.read()
        self.assertEqual(self.page.evaluate.call_count, 1)
        self.assertTrue(all(event[1] == 'status' for event in self.request['events'].queue))


class FavoritesUITests(unittest.TestCase):
    def setUp(self):
        self.root=tk.Tk();self.root.withdraw()
        def destroy():
            for timer in self.root.tk.call('after','info'):
                self.root.tk.call('after','cancel',timer)
            self.root.destroy()
        self.addCleanup(destroy)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        with patch('neto_incident_monitor.app.read_json',return_value={}):
            self.app=App(self.root,history_path=Path(self.temp.name)/'history.json',enable_tray=False,apply_startup=False)
        self.app.filters=[]
        self.app.persist_filters=Mock()
        self.app.session = Mock(ready_once=True)
        self.app.session.cancel_pending.return_value = False
        self.app.session_state = 'ready'
        self.app.update_refresh_controls = Mock()

    def deliver(self, view, outcome):
        view.events.put((view.import_id, 'result', outcome))
        view.window.after_cancel(view.timer)
        view.timer = None
        view.poll()

    def open(self):
        self.app.import_favorites()
        view = self.app.favorites_import
        self.app.session.submit.assert_called_once_with('favorites', [view.part])
        self.deliver(view, ('success', [item(), item(href='/sc_task_list.do')]))
        return view

    def test_preview_starts_unselected_and_search_selection_preserves_order(self):
        view=self.open()
        self.assertEqual(view.chosen,set())
        self.app.import_favorites()  # The completed preview still reserves the importer.
        self.assertIs(self.app.favorites_import,view)
        view.toggle('1');view.toggle('0')
        with patch('neto_incident_monitor.app.read_json',return_value={}):
            view.accept()
        self.assertEqual([r['url'] for r in self.app.filters],
            ['https://adeo.service-now.com/incident_list.do?sysparm_query=active%3Dtrue','https://adeo.service-now.com/sc_task_list.do'])
        self.assertIsNone(self.app.favorites_import)

    def test_cancel_preview_never_saves(self):
        view=self.open();view.select_all(True);view.cancel()
        self.app.persist_filters.assert_not_called()
        self.assertEqual(self.app.filters,[])
        self.assertIsNone(self.app.favorites_import)

    def test_import_window_opens_centered_on_screen(self):
        self.root.geometry('800x600+0+0')
        self.root.deiconify()
        self.root.update_idletasks()
        view = self.open()
        window = view.window
        window.update_idletasks()
        width, height = window.winfo_width(), window.winfo_height()
        x = max(0, (window.winfo_screenwidth() - width) // 2)
        y = max(0, (window.winfo_screenheight() - height) // 2)
        self.assertTrue(window.winfo_ismapped())
        self.assertEqual(window.geometry(), f'{width}x{height}+{x}+{y}')
        view.cancel()

    def test_small_window_keeps_action_bar_inside_client_area(self):
        view=self.open()
        self.root.deiconify()
        view.window.geometry('750x300')
        self.root.update()
        footer=view.add.master
        self.assertTrue(footer.winfo_ismapped())
        self.assertGreater(footer.winfo_height(),20)
        self.assertLessEqual(footer.winfo_y()+footer.winfo_height(),view.window.winfo_height())
        self.assertTrue(view.cancel_button.winfo_ismapped())
        view.cancel()

    def test_heading_sort_changes_display_only_and_keeps_selection(self):
        view=self.open()
        view.rows[0]['name']='Zulu';view.rows[1]['name']='Alfa'
        view.chosen={0}
        view.sort_by('name')
        self.assertEqual(view.table.get_children(),('1','0'))
        view.sort_by('name')
        self.assertEqual(view.table.get_children(),('0','1'))
        view.sort_by('name')
        self.assertEqual(view.table.get_children(),('0','1'))
        self.assertEqual(view.chosen,{0})
        self.assertTrue(view.table.heading('name','command'))
        view.cancel()

    def test_checkboxes_use_theme_with_transparent_background(self):
        view=self.open()
        from PIL import ImageTk
        self.assertEqual(view.table.item('0','image'),(str(view.checkbox_images[0]),))
        for image in view.checkbox_images:
            pixels=ImageTk.getimage(image).convert('RGBA')
            self.assertEqual(pixels.getpixel((0,0))[3],0)
            self.assertEqual(pixels.getpixel((23,23))[3],0)
            self.assertEqual(pixels.getpixel((10,10))[3],255)
        view.toggle('0')
        self.assertEqual(view.table.item('0','image'),(str(view.checkbox_images[1]),))
        view.rows[1]['status']='unsupported';view.render()
        self.assertFalse(view.table.item('1','image'))
        view.cancel()

    def test_header_click_sorts_without_toggling_rows(self):
        view=self.open();self.root.deiconify()
        view.rows[0]['name']='Zulu';view.rows[1]['name']='Alfa';view.render()
        self.root.update()
        x=int(view.table.column('#0','width'))+20
        y=next(y for y in range(1,45) if view.table.identify_region(x,y)=='heading')
        view.table.event_generate('<Button-1>',x=x,y=y)
        view.table.event_generate('<ButtonRelease-1>',x=x,y=y)
        self.root.update()
        self.assertEqual(view.table.get_children(),('1','0'))
        self.assertEqual(view.chosen,set())
        view.cancel()

    def test_stale_result_cannot_replace_current_preview(self):
        view=self.open()
        view.events.put(('b'*32,'result',('success',[])))
        view.poll()
        self.assertEqual(len(view.rows),2)
        view.cancel()

    def test_save_failure_keeps_preview_and_selection(self):
        view=self.open();view.toggle('0')
        self.app.persist_filters.side_effect=PermissionError('SYNTHETIC_SECRET')
        with patch('neto_incident_monitor.app.read_json',return_value={}), \
             patch('neto_incident_monitor.favorites_ui.messagebox.showerror'):
            view.accept()
        self.assertIs(self.app.favorites_import,view)
        self.assertEqual(view.chosen,{0})
        self.assertEqual(self.app.filters,[])
        view.cancel()

    def test_cancel_active_import_ignores_result_and_does_not_stop_monitoring(self):
        self.app.import_favorites()
        view = self.app.favorites_import
        self.app.cycle_active = True
        view.cancel()
        self.assertTrue(view.stop.is_set())
        self.assertIs(self.app.favorites_import, view)
        self.deliver(view, ('success', [item()]))
        self.assertTrue(self.app.cycle_active)
        self.assertIsNone(self.app.favorites_import)
        self.app.persist_filters.assert_not_called()

    def test_cancel_pending_import_releases_dialog(self):
        self.app.session.cancel_pending.return_value = True
        self.app.import_favorites()
        view = self.app.favorites_import
        view.cancel()
        self.app.session.cancel_pending.assert_called_once_with(view.part)
        self.assertIsNone(self.app.favorites_import)
        self.app.persist_filters.assert_not_called()

    def test_empty_preview_has_its_own_message(self):
        self.app.import_favorites()
        view = self.app.favorites_import
        self.deliver(view, ('success', []))
        self.assertIn('nie ma zapisanych Ulubionych', view.status.get())
        self.assertFalse(view.add.enabled)
        view.cancel()
