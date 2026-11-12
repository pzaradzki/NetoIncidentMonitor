import json
import queue
import tempfile
import threading
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from playwright.sync_api import TimeoutError
from neto_incident_monitor.app import App
from neto_incident_monitor.favorites import classify, commit_selection
from neto_incident_monitor.favorites_worker import collect_with_recovery, run_import
from neto_incident_monitor.pagination import AuthenticationRequired, Cancelled
from neto_incident_monitor.read_budget import CURRENT, BudgetExpired
from neto_incident_monitor.login_diagnostics import LoginDiagnostics, _logger


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
    def test_shared_budget_is_not_reset_and_login_time_is_excluded(self):
        clock=[0];budgets=[];attempt=[0]
        def read(*args):
            budgets.append(CURRENT.get());attempt[0]+=1;clock[0]+=2
            if attempt[0]==1:raise TimeoutError('synthetic')
            if attempt[0]==2:raise AuthenticationRequired()
            return [item()]
        def restore():clock[0]+=100;return True
        with patch('neto_incident_monitor.read_budget.monotonic',side_effect=lambda:clock[0]), \
             patch('neto_incident_monitor.favorites_worker.monotonic',side_effect=lambda:clock[0]), \
             patch('neto_incident_monitor.favorites_worker.navigate_page'), \
             patch('neto_incident_monitor.favorites_worker.read_favorites',side_effect=read):
            collect_with_recovery(Mock(),threading.Event(),Mock(),restore,Mock())
        self.assertTrue(all(b is budgets[0] for b in budgets))
        self.assertEqual(budgets[0].end,130)
        self.assertEqual(clock[0],106)

    def test_exhausted_budget_does_not_start_another_attempt(self):
        clock=[0]
        def read(*args):clock[0]=31;return [item()]
        with patch('neto_incident_monitor.read_budget.monotonic',side_effect=lambda:clock[0]), \
             patch('neto_incident_monitor.favorites_worker.navigate_page'), \
             patch('neto_incident_monitor.favorites_worker.read_favorites',side_effect=read) as reader:
            with self.assertRaises(BudgetExpired):
                collect_with_recovery(Mock(),threading.Event(),Mock(),Mock(),Mock())
        self.assertEqual(reader.call_count,1)

    def test_timeout_then_login_then_success_has_three_reads_one_restore(self):
        stop=threading.Event();restore=Mock(return_value=True)
        with patch('neto_incident_monitor.favorites_worker.navigate_page'), \
             patch('neto_incident_monitor.favorites_worker.read_favorites',side_effect=[TimeoutError('SYNTHETIC_SECRET'),AuthenticationRequired(),[item()]]) as read:
            rows=collect_with_recovery(Mock(),stop,Mock(),restore,Mock())
        self.assertEqual(rows,[item()]);self.assertEqual(read.call_count,3)
        restore.assert_called_once()

    def test_repeated_login_is_final(self):
        with patch('neto_incident_monitor.favorites_worker.navigate_page'), \
             patch('neto_incident_monitor.favorites_worker.read_favorites',side_effect=AuthenticationRequired()) as read:
            restore=Mock(return_value=True)
            with self.assertRaises(AuthenticationRequired):
                collect_with_recovery(Mock(),threading.Event(),Mock(),restore,Mock())
        self.assertEqual(read.call_count,2);restore.assert_called_once()

    def test_stop_during_login(self):
        stop=threading.Event()
        def restore():stop.set();return True
        with patch('neto_incident_monitor.favorites_worker.navigate_page'), \
             patch('neto_incident_monitor.favorites_worker.read_favorites',side_effect=AuthenticationRequired()) as read:
            with self.assertRaises(Cancelled):
                collect_with_recovery(Mock(),stop,Mock(),restore,Mock())
        self.assertEqual(read.call_count,1)

    def test_two_timeouts_are_final(self):
        with patch('neto_incident_monitor.favorites_worker.navigate_page'), \
             patch('neto_incident_monitor.favorites_worker.read_favorites',side_effect=TimeoutError('SYNTHETIC_SECRET')) as reader:
            with self.assertRaises(TimeoutError):
                collect_with_recovery(Mock(),threading.Event(),Mock(),Mock(),Mock())
        self.assertEqual(reader.call_count,2)

    def test_run_import_closes_resources_before_publishing_result(self):
        context,page,runtime=Mock(),Mock(),Mock()
        context.pages=[]
        context.new_page.return_value=page
        events=Mock()
        def emit(value):
            if value[1]=='result':
                context.close.assert_called_once();runtime.close.assert_called_once()
                page.close.assert_called_once()
        events.put.side_effect=emit
        with patch('playwright.sync_api.sync_playwright'), \
             patch('neto_incident_monitor.browser_session.open_context',return_value=context), \
             patch('neto_incident_monitor.browser_session.create_runtime',return_value=runtime), \
             patch('neto_incident_monitor.favorites_worker.collect_with_recovery',return_value=[item()]), \
             patch('neto_incident_monitor.favorites_worker.LoginDiagnostics'):
            run_import(events,threading.Event(),{},Path('synthetic-profile'),'a'*32)
        context.new_page.assert_called_once()
        page.set_viewport_size.assert_not_called()

    def test_diagnostics_serialize_only_allowed_context(self):
        with self.assertLogs(_logger,level='INFO') as captured:
            log=LoginDiagnostics(source='favorites',import_id='a'*32)
            log.record('favorites_stage',import_stage='complete',item_count=36,group_count=5,
                       name='SYNTHETIC_SECRET',href='https://example.com/SYNTHETIC_SECRET')
            log.record('favorites_error',import_reason='unsupported',outcome='error')
        rows=[json.loads(r.getMessage()) for r in captured.records]
        row=next(r for r in rows if r['event']=='favorites_stage')
        self.assertEqual(row['import_id'],'a'*32)
        self.assertEqual(row['item_count'],36)
        self.assertEqual(row['import_stage'],'complete')
        self.assertNotIn('SYNTHETIC_SECRET',str(captured.output))


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

    def open(self):
        def run(events,stop,settings,profile,token):
            events.put((token,'result',('success',[item(),item(href='/sc_task_list.do')])) )
        with patch('neto_incident_monitor.favorites_worker.run_import',side_effect=run):
            self.app.import_favorites()
            view=self.app.favorites_import
            view.worker.join(timeout=3)
        view.window.after_cancel(view.timer);view.timer=None
        view.poll()
        return view

    def test_preview_starts_unselected_and_search_selection_preserves_order(self):
        view=self.open()
        self.assertEqual(view.chosen,set())
        self.app.start()  # The completed preview still reserves the operation.
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

    def test_cancel_waits_until_worker_releases_profile(self):
        entered=threading.Event();released=threading.Event()
        self.addCleanup(released.set)
        def run(events,stop,*args):entered.set();stop.wait(3);released.wait(3)
        with patch('neto_incident_monitor.favorites_worker.run_import',side_effect=run):
            self.app.import_favorites();view=self.app.favorites_import
            self.assertTrue(entered.wait(2))
            view.cancel()
            self.assertIs(self.app.favorites_import,view)
            released.set()
            view.worker.join(3)
            view.window.after_cancel(view.timer);view.timer=None
            view.poll()
        self.assertIsNone(self.app.favorites_import)
        self.app.persist_filters.assert_not_called()
