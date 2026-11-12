import threading
import time
import tkinter as tk
import unittest
import sys
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from neto_incident_monitor.app import App
from neto_incident_monitor.monitoring import ReadPart, ReadQueue
from neto_incident_monitor.shared_session import SharedSession


class ReadQueueTests(unittest.TestCase):
    def test_full_refresh_after_filter_change_uses_new_scope(self):
        queue = ReadQueue()
        dashboard, threats = ReadPart('dashboard', (2026, 11)), ReadPart('threatened')
        removed, remaining, added = (ReadPart('filter', (name, None)) for name in ('A', 'B', 'C'))
        first, _ = queue.submit('all', [dashboard, threats, removed, remaining])
        queue.discard_pending_filters({removed})
        parts = [dashboard, threats, remaining, added]
        self.assertFalse(queue.has_full_read(parts))
        second, merged = queue.submit('all', parts)
        self.assertNotEqual(second, first)
        self.assertFalse(merged)
        self.assertEqual(list(queue.take().parts), [dashboard, threats, remaining])
        self.assertTrue(queue.has_full_read(parts))

    def test_filter_added_to_running_batch_waits_for_next_deadline(self):
        from neto_incident_monitor.shared_session import MonitorCycle

        first, second, added = (ReadPart('filter', (name, None), {'kind': 'inc'}) for name in ('A', 'B', 'C'))
        cycle = MonitorCycle([], {'inc': 30, 'task': 90})
        with patch('neto_incident_monitor.shared_session.monotonic', return_value=10) as clock:
            self.assertEqual(cycle.next_filter((first, second)), first)
            cycle.filters.popleft()
            self.assertEqual(cycle.next_filter((first, second, added)), second)
            cycle.filters.popleft()
            cycle.finish_filter_batch()
            clock.return_value = 39
            self.assertIsNone(cycle.next_filter((first, second, added)))
            clock.return_value = 40
            cycle.next_filter((first, second, added))
            self.assertEqual(list(cycle.filters), [first, second, added])

    def test_deleting_active_filter_cancels_its_login_wait_and_runs_next_filter(self):
        app = Mock(threatened_next_read=None)
        session = SharedSession(app, Path('unused'))
        session.log = Mock()
        page = Mock()
        page.is_closed.return_value = False
        old = ReadPart('filter', ('A', None), {'scheduled': True})
        other = ReadPart('filter', ('B', None), {'scheduled': True})
        session.update_filters({'A': old, 'B': other})
        session.work.submit('filter', [old])
        session.work.submit('filter', [other])
        waiting = threading.Event()
        advanced = threading.Event()

        def authenticate(_page, stop):
            if not waiting.is_set():
                waiting.set()
                deadline = time.monotonic() + 2
                while not stop.is_set() and time.monotonic() < deadline:
                    time.sleep(.01)
                return not stop.is_set()
            return True

        def read(_page, part, _stop, _source):
            self.assertEqual(part, other)
            advanced.set()
            session.closed.set()
            return True

        session.authenticate = authenticate
        app.execute_session_part.side_effect = read
        worker = threading.Thread(target=session.serve, args=(page,), daemon=True)
        worker.start()
        try:
            self.assertTrue(waiting.wait(2))
            session.update_filters({'B': other})
            self.assertTrue(advanced.wait(3))
        finally:
            session.shutdown()
            worker.join(3)
        self.assertFalse(worker.is_alive())
        app.execute_session_part.assert_called_once()

    def test_queue_diagnostics_keep_request_id_and_do_not_log_filter_target(self):
        from neto_incident_monitor.login_diagnostics import _logger
        session = SharedSession(Mock(), Path('unused'))
        part = ReadPart('filter', ('https://example.test/PRIVATE_TEST_TOKEN', None))
        with self.assertLogs(_logger, level='INFO') as captured:
            job_id, _ = session.submit('filter', [part])
            session.submit('filter', [part])
        entries = [json.loads(line.getMessage()) for line in captured.records]
        updates = [entry for entry in entries if entry['event'] == 'refresh_queue']
        self.assertEqual([entry['queue_state'] for entry in updates], ['queued', 'merged'])
        self.assertTrue(all(entry['request_id'] == job_id for entry in updates))
        self.assertNotIn('PRIVATE_TEST_TOKEN', '\n'.join(captured.output))

    def test_full_read_merges_waiting_work_at_its_own_position(self):
        queue = ReadQueue()
        first = ReadPart('filter', ('A', None))
        second = ReadPart('filter', ('B', None))
        dashboard, threats, favorites = ReadPart('dashboard', (2026, 11)), ReadPart('threatened'), ReadPart('favorites', 'one')
        queue.submit('filter', [first])
        queue.take()
        queue.submit('dashboard', [dashboard])
        queue.submit('favorites', [favorites])
        queue.submit('threatened', [threats])
        full_id, merged = queue.submit('all', [dashboard, threats, first, second])
        self.assertTrue(merged)
        self.assertEqual(queue.submit('dashboard', [dashboard]), (full_id, True))
        queue.complete_part(first, manual=True, success=True)
        queue.finish()
        self.assertEqual(tuple(queue.take().parts), (favorites,))
        queue.complete_part(favorites, manual=True, success=True)
        queue.finish()
        self.assertEqual(tuple(queue.take().parts), (dashboard, threats, second))

    def test_cancelling_periodic_read_keeps_manual_request(self):
        queue = ReadQueue()
        dashboard = ReadPart('dashboard', (2026, 11))
        queue.submit('dashboard', [dashboard])
        queue.complete_part(dashboard, manual=False, success=False)
        self.assertEqual(tuple(queue.take().parts), (dashboard,))

    def test_scheduled_threats_and_filter_get_time_between_manual_requests(self):
        app = Mock(threatened_next_read=9)
        session = SharedSession(app, Path('unused'))
        session.log = Mock()
        session.filter_parts = (ReadPart('filter', ('A', None), {'kind': 'inc'}),)
        session.start_cycle([], {'inc': 30, 'task': 90})
        dashboard = ReadPart('dashboard', (2026, 11))
        session.work.submit('dashboard', [dashboard])
        with patch('neto_incident_monitor.shared_session.monotonic', return_value=10):
            self.assertEqual(session.next_part(session.cycle), (ReadPart('threatened'), 'threatened'))
            app.threatened_next_read = 70
            self.assertEqual(session.next_part(session.cycle), (dashboard, 'manual'))
            session.work.complete_part(dashboard, manual=True, success=True)
            session.work.submit('dashboard', [dashboard])
            self.assertEqual(session.next_part(session.cycle), (session.filter_parts[0], 'filter'))

    def test_stop_during_periodic_read_leaves_matching_manual_work(self):
        app = Mock(threatened_next_read=time.monotonic() + 60)
        session = SharedSession(app, Path('unused'))
        session.log = Mock()
        session.connected = True
        page = Mock()
        page.is_closed.return_value = False
        periodic_started = threading.Event()
        manual_finished = threading.Event()
        sources = []

        def read(_page, _part, stop, source):
            sources.append(source)
            if source == 'initial':
                periodic_started.set()
                until = time.monotonic() + 3
                while not stop.is_set() and time.monotonic() < until:
                    time.sleep(.01)
                return not stop.is_set()
            manual_finished.set()
            session.closed.set()
            return True

        app.execute_session_part.side_effect = read
        part = ReadPart('threatened')
        session.start_cycle([part], {'inc': 30, 'task': 90})
        with patch('neto_incident_monitor.shared_session.authentication_required', return_value=False):
            worker = threading.Thread(target=session.serve, args=(page,), daemon=True)
            worker.start()
            try:
                self.assertTrue(periodic_started.wait(2))
                session.work.submit('threatened', [part])
                session.stop_cycle()
                self.assertTrue(manual_finished.wait(2))
            finally:
                session.shutdown()
                worker.join(3)
        self.assertEqual(sources, ['initial', 'manual'])
        self.assertFalse(worker.is_alive())

    def test_after_process_failure_next_open_requires_explicit_reconnect(self):
        from neto_incident_monitor.app import BrowserClosedError
        app = Mock()
        session = SharedSession(app, Path('unused'))
        attempt_finished = threading.Event()

        def emit(event, _value=None):
            if event == 'session_problem':
                attempt_finished.set()

        session.emit = emit
        session.open_and_serve = Mock(side_effect=BrowserClosedError())
        with patch('neto_incident_monitor.shared_session.sync_playwright'):
            session.thread.start()
            try:
                self.assertTrue(attempt_finished.wait(2))
                session.open_and_serve.assert_called_once()
                attempt_finished.clear()
                self.assertFalse(attempt_finished.wait(.1))
                session.retry()
                self.assertTrue(attempt_finished.wait(2))
                self.assertEqual(session.open_and_serve.call_count, 2)
            finally:
                session.shutdown()
                session.thread.join(3)

    def test_full_read_satisfies_due_filter_batch_without_an_immediate_repeat(self):
        app = Mock(threatened_next_read=70)
        session = SharedSession(app, Path('unused'))
        session.log = Mock()
        part = ReadPart('filter', ('A', None), {'kind': 'inc'})
        session.filter_parts = (part,)
        session.start_cycle([], {'inc': 30, 'task': 90})
        session.work.submit('all', [part])
        with patch('neto_incident_monitor.shared_session.monotonic', return_value=10):
            self.assertEqual(session.next_part(session.cycle), (part, 'manual'))
            session.work.complete_part(part, manual=True, success=True)
            self.assertIsNone(session.next_part(session.cycle))
            self.assertEqual(session.cycle.deadlines['inc'], 40)


class PasswordSaveWaitTests(unittest.TestCase):
    def test_shutdown_releases_prompt_and_logs_cancellation(self):
        session = SharedSession(Mock(), Path('unused'))
        session.runtime = Mock()
        session.runtime.window.is_visible.return_value = True
        page = Mock()
        page.is_closed.return_value = False
        page.wait_for_timeout.side_effect = lambda _: session.shutdown()
        diagnostics = Mock()

        self.assertFalse(session.confirm_password_save(page, diagnostics))

        start, finish = [call.args[0] for call in session.app.events.put.call_args_list]
        self.assertEqual(start[0], 'session_password_save')
        self.assertEqual(finish[0], 'session_password_save_finished')
        self.assertIs(start[1], finish[1])
        self.assertTrue(finish[1]['done'].is_set())
        self.assertEqual(diagnostics.record.call_args.kwargs['password_save_choice'], 'cancelled')


class SharedApplicationTests(unittest.TestCase):
    def test_filter_buttons_work_during_monitoring_and_only_saved_changes_invalidate_work(self):
        from neto_incident_monitor.app import save_json
        from neto_incident_monitor.filter_state import FilterState
        from neto_incident_monitor.login_diagnostics import LoginDiagnostics
        from neto_incident_monitor.widgets import RoundedButton
        from tkinter import ttk

        first = 'https://adeo.service-now.com/incident_list.do?sysparm_query=active%3Dtrue'
        second = 'https://adeo.service-now.com/sc_task_list.do'
        replacement = 'https://adeo.service-now.com/incident_list.do?sysparm_query=active%3Dfalse'
        added = 'https://adeo.service-now.com/sc_request_list.do'
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            config = folder / 'config.json'
            root = tk.Tk()
            root.withdraw()
            try:
                with patch('neto_incident_monitor.app.CONFIG', config), \
                        patch('neto_incident_monitor.app.DATA', folder), \
                        patch('neto_incident_monitor.dashboard_cache.load_snapshot', return_value=None):
                    save_json(config, {'filters': [{'name': 'A', 'url': first}, {'name': 'B', 'url': second}]})
                    app = App(root, history_path=folder / 'history.json', enable_tray=False,
                              apply_startup=False, shared_session=True)
                    app.session.ready_once = True
                    app.handle_session_event('session_ready', None)
                    app.start_session_cycle()
                    self.assertTrue(app.cycle_active)
                    self.assertTrue(all(button.enabled for button in app.filter_buttons))

                    def save_dialog(edit, name, url):
                        app.filter_buttons[int(edit)].invoke()
                        title = 'Edytuj filtr' if edit else 'Dodaj filtr'
                        dialog = next(widget for widget in root.winfo_children()
                                      if isinstance(widget, tk.Toplevel) and widget.title() == title)
                        label = next(widget for widget in dialog.winfo_children() if isinstance(widget, ttk.Entry))
                        address = next(widget for widget in dialog.winfo_children() if isinstance(widget, tk.Text))
                        label.delete(0, 'end')
                        label.insert(0, name)
                        address.delete('1.0', 'end')
                        address.insert('1.0', url)
                        next(widget for widget in dialog.winfo_children()
                             if isinstance(widget, RoundedButton) and widget.text == 'Zapisz').invoke()
                        self.assertFalse(dialog.winfo_exists())

                    part = app.session.manual_filter_parts[app.selected_filter_url()]
                    app.session.submit('filter', [part])
                    save_dialog(True, 'Nowa nazwa', first)
                    self.assertEqual(app.session.manual_filter_parts[app.selected_filter_url()], part)
                    self.assertIn(part, app.session.work.pending_refreshes()[1])
                    with patch('neto_incident_monitor.app.save_json', side_effect=OSError('synthetic')), \
                            patch('neto_incident_monitor.app.messagebox.showerror') as error:
                        app.filter_buttons[2].invoke()
                    error.assert_called_once()
                    self.assertIn(part, app.session.work.pending_refreshes()[1])
                    self.assertEqual(app.filters[0]['name'], 'Nowa nazwa')

                    saved_snapshot = {'SCTASK1': {'number': 'SCTASK1', 'url': ''}}
                    app.snapshots[2] = saved_snapshot
                    save_dialog(True, 'Inny adres', replacement)
                    self.assertNotIn(part, app.session.work.pending_refreshes()[1])
                    self.assertTrue(app.request_refresh('filter'))
                    active_url = app.selected_filter_url()
                    active = app.session.manual_filter_parts[active_url]
                    record = LoginDiagnostics.record

                    def delete_before_history(diagnostics, event, **facts):
                        if event == 'filter_commit_start':
                            app.filter_buttons[2].invoke()
                        record(diagnostics, event, **facts)

                    page = Mock()
                    page.is_closed.return_value = False
                    with patch('neto_incident_monitor.app.read_all', return_value=({'INC1': {'number': 'INC1'}}, 1)), \
                            patch.object(LoginDiagnostics, 'record', autospec=True, side_effect=delete_before_history):
                        result = app.read_filter(page, active_url, 'Inny adres', 1, {},
                                                 FilterState(folder / 'seen.json'), app.session.health,
                                                 {}, set(), {}, app.monitor_generation, threading.Event(), part=active)
                    self.assertEqual(result, 'discarded')
                    self.assertEqual(app.history.snapshot(active_url), {})
                    self.assertIsNone(app.session.work.next_scope())
                    self.assertEqual(app.snapshots, {1: saved_snapshot})
                    save_dialog(False, 'Nowy filtr', added)
                    self.assertEqual([item['name'] for item in app.filters], ['B', 'Nowy filtr'])
                    app.filter_buttons[2].invoke()
                    app.filter_buttons[2].invoke()
                    self.assertEqual(app.session.filter_parts, ())
                    self.assertTrue(app.cycle_active)
                    self.assertFalse(app.session.cycle.stop.is_set())
            finally:
                root.destroy()

    @unittest.skipUnless(sys.platform == 'win32', 'Native Chromium visibility is Windows-specific')
    def test_password_save_prompt_gates_start_and_reauthentication(self):
        import ctypes
        from ctypes import wintypes
        from urllib.parse import urlsplit
        from neto_incident_monitor.browser_session import open_context
        from neto_incident_monitor.login_diagnostics import _logger
        from neto_incident_monitor.widgets import RoundedButton
        from neto_incident_monitor.window_style import _frame_handle

        login = 'https://idpb2e.adeo.com/login'
        authenticated = False
        reads = []

        def launch(playwright, profile, diagnostics, **options):
            self.assertTrue(options['offer_password_save'])
            context = open_context(playwright, profile, diagnostics, **options)

            def route(request):
                if request.request.url == login:
                    request.fulfill(content_type='text/html', body='<input type="password">')
                elif urlsplit(request.request.url).path == '/now/sow/home':
                    if authenticated:
                        request.fulfill(content_type='text/html', body='<script>window.g_user={userID:"fixture"}</script>')
                    else:
                        request.fulfill(content_type='text/html', body=f'<script>location.replace("{login}")</script>')
                else:
                    request.fulfill(status=404)

            context.route('**/*', route)
            return context

        def enter_fixture_password(_, page):
            nonlocal authenticated
            page.locator('[type=password]').press('x', timeout=3000)
            authenticated = True
            page.goto('https://adeo.service-now.com/now/sow/home', timeout=3000)

        def read(page, part, stop, source):
            nonlocal authenticated
            reads.append(part.scope)
            if len(reads) == 1:
                authenticated = False
                page.goto(login)
            return True

        with TemporaryDirectory() as directory:
            folder = Path(directory)
            root = tk.Tk()
            root.withdraw()
            try:
                with self.assertLogs(_logger, level='INFO') as captured, \
                        patch('neto_incident_monitor.app.DATA', folder), \
                        patch('neto_incident_monitor.app.read_json', return_value={'filters': [], 'auto_login': True}), \
                        patch('neto_incident_monitor.app.save_json') as save, \
                        patch('neto_incident_monitor.dashboard_cache.load_snapshot', return_value=None), \
                        patch('neto_incident_monitor.shared_session.open_context', side_effect=launch), \
                        patch('neto_incident_monitor.automatic_login.AutomaticLogin.step', new=enter_fixture_password):
                    app = App(root, history_path=folder / 'history.json', enable_tray=False,
                              apply_startup=False, shared_session=True)
                    app.execute_session_part = read

                    def until(predicate):
                        deadline = time.monotonic() + 15
                        while not predicate() and time.monotonic() < deadline:
                            root.update()
                            time.sleep(.01)
                        self.assertTrue(predicate())

                    def press(text):
                        panel = app.password_save_dialog.winfo_children()[0]
                        button = next(widget for container in panel.winfo_children()
                                      for widget in container.winfo_children()
                                      if isinstance(widget, RoundedButton) and widget.text == text)
                        button.invoke()

                    def verify_prompt_window():
                        dialog = app.password_save_dialog
                        user32 = ctypes.WinDLL('user32')
                        user32.GetForegroundWindow.restype = wintypes.HWND
                        user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
                        hwnd = _frame_handle(user32, dialog)
                        until(lambda: user32.GetForegroundWindow() == hwnd and dialog.focus_displayof() is dialog)
                        bounds = wintypes.RECT()
                        self.assertTrue(user32.GetWindowRect(hwnd, ctypes.byref(bounds)))
                        # The requested Tk size excludes the native title bar and borders.
                        self.assertAlmostEqual((bounds.left + bounds.right) / 2,
                                               dialog.winfo_screenwidth() / 2, delta=24)
                        self.assertAlmostEqual((bounds.top + bounds.bottom) / 2,
                                               dialog.winfo_screenheight() / 2, delta=24)
                        self.assertIsNone(dialog.grab_current())

                    def verify_main_focus(reason):
                        def confirmed():
                            for record in captured.records:
                                entry = json.loads(record.getMessage())
                                if entry.get('visibility_reason') == reason and entry.get('keyboard_focus_confirmed'):
                                    return True
                            return False

                        until(confirmed)
                        user32 = ctypes.WinDLL('user32')
                        user32.GetForegroundWindow.restype = wintypes.HWND
                        self.assertEqual(user32.GetForegroundWindow(), _frame_handle(user32, root))
                        self.assertIs(root.focus_displayof().winfo_toplevel(), root)

                    app.session.thread.start()
                    try:
                        until(lambda: app.password_save_dialog is not None)
                        self.assertEqual(root.state(), 'withdrawn')
                        self.assertTrue(app.password_save_dialog.winfo_viewable())
                        self.assertTrue(app.browser_window.is_visible())
                        self.assertFalse(app.session.connected)
                        verify_prompt_window()
                        press('Zapisano')
                        until(lambda: app.session_state == 'ready')
                        self.assertTrue(app.browser_window.is_hidden())
                        verify_main_focus('initial_main_window')
                        self.assertTrue(app.auto_login.get())
                        self.assertTrue(app.request_refresh('dashboard'))
                        until(lambda: len(reads) == 1 and app.session.work.next_scope() is None
                              and app.session.active_job is None)
                        self.assertTrue(app.request_refresh('dashboard'))
                        until(lambda: app.password_save_dialog is not None)
                        self.assertTrue(app.browser_window.is_visible())
                        self.assertEqual(reads, ['dashboard'])
                        verify_prompt_window()
                        save.side_effect = OSError('SYNTHETIC_PRIVATE_DATA')
                        press('Wyłącz autologowanie')
                        self.assertIsNotNone(app.password_save_dialog)
                        self.assertTrue(app.auto_login.get())
                        self.assertEqual(reads, ['dashboard'])
                        save.side_effect = None
                        press('Wyłącz autologowanie')
                        until(lambda: len(reads) == 2 and app.session_state == 'ready')
                        self.assertTrue(app.browser_window.is_hidden())
                        verify_main_focus('recovered_main_window')
                        self.assertFalse(app.auto_login.get())
                        self.assertFalse(app.browser_options.snapshot()['auto_login'])
                        self.assertFalse(save.call_args.args[1]['auto_login'])
                    finally:
                        app.session.shutdown()
                        app.session.thread.join(6)
                entries = [json.loads(record.getMessage()) for record in captured.records]
                prompts = [entry for entry in entries if entry['event'] == 'password_save_prompt']
                self.assertEqual([entry['password_save_choice'] for entry in prompts],
                                 ['waiting', 'saved', 'waiting', 'save_error', 'disabled'])
                self.assertEqual(prompts[0]['session'], prompts[1]['session'])
                self.assertEqual(len({entry['session'] for entry in prompts[2:]}), 1)
                self.assertTrue(all(entry['window_visible'] for entry in prompts if 'window_visible' in entry))
                self.assertTrue(prompts[1]['foreground_confirmed'])
                self.assertTrue(prompts[4]['foreground_confirmed'])
                self.assertNotIn('SYNTHETIC_PRIVATE_DATA', '\n'.join(captured.output))
            finally:
                root.destroy()

    def test_refresh_buttons_follow_queued_and_finished_scopes(self):
        settings = {'filters': [
            {'name': 'Cykliczny', 'url': 'https://adeo.service-now.com/incident_list.do'},
            {'name': 'Ręczny', 'url': 'https://adeo.service-now.com/sc_task_list.do', 'enabled': False},
        ]}
        with TemporaryDirectory() as directory:
            root = tk.Tk()
            root.withdraw()
            try:
                with patch('neto_incident_monitor.app.read_json', return_value=settings), \
                        patch('neto_incident_monitor.dashboard_cache.load_snapshot', return_value=None):
                    app = App(root, history_path=Path(directory) / 'history.json', enable_tray=False,
                              apply_startup=False, shared_session=True)
                session = app.session
                session.log = Mock()
                session.ready_once = True
                app.handle_session_event('session_ready', None)
                filter_button = app.refresh_filter_button
                dashboard = app.dashboard_view.refresh_button
                threats = app.threatened_view.refresh_button
                full = app.check_button

                filter_button.invoke()
                self.assertFalse(filter_button.enabled)
                self.assertTrue(dashboard.enabled and threats.enabled and full.enabled)
                dashboard.invoke()
                threats.invoke()
                self.assertFalse(dashboard.enabled or threats.enabled)
                self.assertTrue(full.enabled)
                full.invoke()
                self.assertFalse(full.enabled or dashboard.enabled or threats.enabled or filter_button.enabled)

                app.filter_table.selection_set('1')
                app.filter_selected()
                self.assertTrue(filter_button.enabled)
                app.filter_table.selection_set('0')
                app.filter_selected()
                self.assertFalse(filter_button.enabled)

                for scope, button in [('dashboard', dashboard), ('threatened', threats), ('filter', filter_button)]:
                    part, source = session.next_part(None)
                    self.assertEqual((part.scope, source), (scope, 'manual'))
                    self.assertFalse(button.enabled)
                    session.work.complete_part(part, manual=True, success=scope != 'threatened')
                    session.emit('refresh_state')
                    app.drain()
                    self.assertTrue(button.enabled)
                    self.assertFalse(full.enabled)
                    self.assertTrue(app.request_refresh('all'))
                    self.assertIsNone(session.work.next_scope())

                self.assertIsNone(session.next_part(None))
                app.drain()
                self.assertTrue(full.enabled)
            finally:
                root.destroy()

    def test_refresh_button_reads_disabled_filter_outside_the_cycle(self):
        from neto_incident_monitor.login_diagnostics import _logger

        url = 'https://adeo.service-now.com/incident_list.do?sysparm_query=active%3Dtrue'
        enabled_url = 'https://adeo.service-now.com/sc_task_list.do'
        settings = {'filters': [{'name': 'Poza harmonogramem', 'url': url, 'enabled': False},
                                {'name': 'Cykliczny', 'url': enabled_url}]}
        with TemporaryDirectory() as directory:
            root = tk.Tk()
            root.withdraw()
            try:
                with patch('neto_incident_monitor.app.read_json', return_value=settings), \
                        patch('neto_incident_monitor.dashboard_cache.load_snapshot', return_value=None):
                    app = App(root, history_path=Path(directory) / 'history.json', enable_tray=False,
                              apply_startup=False, shared_session=True)
                app.session.log = Mock()
                app.session.ready_once = True
                app.handle_session_event('session_ready', None)
                app.filter_table.selection_set('0')
                app.filter_selected()
                self.assertTrue(app.refresh_filter_button.enabled)
                app.refresh_filter_button.invoke()
                self.assertTrue(app.request_refresh('all'))
                self.assertEqual([part.target[0] for part in app.session.filter_parts], [enabled_url])
                pending_full = next(job for job in app.session.work.pending if job.scope == 'all')
                self.assertEqual([part.target[0] for part in pending_full.parts if part.scope == 'filter'],
                                 [enabled_url])

                part, source = app.session.next_part(None)
                page = Mock()
                page.is_closed.return_value = False
                incident = {'number': 'INC0000001', 'url': url}
                with patch('neto_incident_monitor.app.read_all', return_value=({incident['number']: incident}, 1)), \
                        patch('neto_incident_monitor.app.STATE', Path(directory) / 'seen.json'), \
                        self.assertLogs(_logger, level='INFO') as captured:
                    self.assertTrue(app.execute_session_part(page, part, app.session.closed, source))
                app.drain()
                self.assertIn(incident['number'], app.snapshots[1])
                self.assertIn(incident['number'], app.history.snapshot(url))
                self.assertFalse(app.filters[0]['enabled'])
                end = next(row for row in map(lambda record: json.loads(record.getMessage()), captured.records)
                           if row['event'] == 'filter_read_end')
                self.assertEqual((end['outside_schedule'], end['filter_outcome']), (True, 'success'))
            finally:
                root.destroy()

    def test_autostart_waits_for_ready_session_and_requires_enabled_filter(self):
        url = 'https://adeo.service-now.com/incident_list.do'
        for automatic, enabled in ((True, True), (True, False), (False, True)):
            with self.subTest(automatic=automatic, enabled=enabled), TemporaryDirectory() as directory:
                root = tk.Tk()
                root.withdraw()
                try:
                    settings = {'start_monitoring': automatic, 'filters': [{'name': 'Test', 'url': url, 'enabled': enabled}]}
                    with patch('neto_incident_monitor.app.read_json', return_value=settings), \
                            patch('neto_incident_monitor.dashboard_cache.load_snapshot', return_value=None):
                        app = App(root, history_path=Path(directory) / 'history.json', enable_tray=False,
                                  shared_session=True)
                    app.start_session_cycle = Mock()
                    root.update()
                    app.start_session_cycle.assert_not_called()
                    app.session.ready_once = True
                    app.handle_session_event('session_ready', None)
                    self.assertEqual(app.start_session_cycle.call_count, int(automatic and enabled))
                finally:
                    root.destroy()

    def test_minimized_start_and_background_recovery_do_not_activate_main_window(self):
        with TemporaryDirectory() as directory:
            root = tk.Tk()
            root.withdraw()
            try:
                with patch('neto_incident_monitor.app.read_json',
                           return_value={'start_minimized': True, 'filters': []}), \
                        patch('neto_incident_monitor.dashboard_cache.load_snapshot', return_value=None):
                    app = App(root, history_path=Path(directory) / 'history.json', enable_tray=False,
                              shared_session=True)
                app.session.ready_once = True
                with patch.object(root, 'iconify') as minimize, \
                        patch('neto_incident_monitor.window_style.activate_window') as activate:
                    app.handle_session_event('session_ready', None)
                    root.update_idletasks()
                    minimize.assert_called_once()
                    app.handle_session_event('session_waiting', None)
                    app.handle_session_event('session_ready', True)
                    root.update_idletasks()
                    root.deiconify()
                    root.update_idletasks()
                    app.handle_session_event('session_waiting', None)
                    app.handle_session_event('session_ready', False)
                    root.update_idletasks()
                    activate.assert_not_called()
            finally:
                root.destroy()

    @unittest.skipUnless(sys.platform == 'win32', 'requires the Windows window manager')
    def test_main_window_is_uncovered_after_login_and_native_reactivation(self):
        import ctypes
        import subprocess
        from ctypes import wintypes
        from uuid import uuid4

        from neto_incident_monitor.login_diagnostics import _logger
        from neto_incident_monitor.window_style import _frame_handle

        user32 = ctypes.WinDLL('user32')
        user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        user32.FindWindowW.restype = wintypes.HWND
        user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.AllowSetForegroundWindow.argtypes = [wintypes.DWORD]
        title = f'Neto focus fixture {uuid4().hex}'
        fixture = '''
import ctypes, sys, threading, tkinter as tk
from ctypes import wintypes
api = ctypes.WinDLL('user32')
api.ShowWindowAsync.argtypes = [wintypes.HWND, ctypes.c_int]
api.SetForegroundWindow.argtypes = [wintypes.HWND]
api.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
api.GetAncestor.restype = wintypes.HWND
root = tk.Tk()
root.title(sys.argv[1])
root.geometry('1050x850+25+25')
root.attributes('-topmost', True)
root.update_idletasks()
own_hwnd = api.GetAncestor(root.winfo_id(), 2)
def reactivate():
    for line in sys.stdin:
        hwnd = int(line)
        if hwnd:
            api.ShowWindowAsync(hwnd, 9)
        api.SetForegroundWindow(hwnd or own_hwnd)
threading.Thread(target=reactivate, daemon=True).start()
root.mainloop()
'''

        def until(check, message):
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                root.update()
                if check():
                    return
                time.sleep(.01)
            self.fail(message() if callable(message) else message)

        with TemporaryDirectory() as directory, subprocess.Popen([sys.executable, '-B', '-c', fixture, title],
                stdin=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NO_WINDOW) as cover:
            root = tk.Tk()
            root.withdraw()
            try:
                with patch('neto_incident_monitor.app.read_json', return_value={'filters': [],
                        'window_layout': {'geometry': '930x700+60+60'}}), \
                        patch('neto_incident_monitor.dashboard_cache.load_snapshot', return_value=None), \
                        self.assertLogs(_logger, level='INFO') as logs:
                    app = App(root, history_path=Path(directory) / 'history.json', enable_tray=False,
                              apply_startup=False, shared_session=True)
                    until(lambda: user32.FindWindowW(None, title), 'The covering window did not map')
                    covering = user32.FindWindowW(None, title)
                    app.handle_session_event('session_ready', None)
                    hwnd = _frame_handle(user32, root)
                    topmost = lambda: bool(user32.GetWindowLongW(hwnd, -20) & 8)
                    exposed = lambda: (app.main_window.inspect().exposure == 'exposed'
                                       and user32.GetForegroundWindow() == hwnd)
                    until(lambda: exposed() and topmost(), 'The initial active frame remained covered')

                    # Let Windows restore/activate the main frame from another process.
                    # No call to the app's show/focus methods on the return path.
                    def switch_to_cover():
                        user32.AllowSetForegroundWindow(cover.pid)
                        cover.stdin.write('0\n')
                        cover.stdin.flush()

                    switch_to_cover()
                    until(lambda: not app.main_window.inspect().foreground and not topmost(),
                          lambda: ('The monitor did not release the topmost state: '
                                   f'cover_active={user32.GetForegroundWindow() == covering}, '
                                   f'monitor={app.main_window.inspect()}, topmost={topmost()}'))
                    root.iconify()
                    until(lambda: app.main_window.inspect().exposure == 'minimized',
                          'The monitor did not minimize')
                    cover.stdin.write(f'{hwnd}\n')
                    cover.stdin.flush()
                    until(lambda: exposed() and topmost(), 'Native restore did not expose the active monitor')

                    switch_to_cover()
                    until(lambda: not topmost() and not app.main_window.inspect().foreground,
                          'The temporary raise was not released after native reactivation')
                    rows = [json.loads(record.getMessage()) for record in logs.records]
                    self.assertTrue(any(row.get('previous_window_exposure') == 'covered_topmost'
                                        and row.get('window_exposure') == 'exposed'
                                        and row.get('temporarily_raised') for row in rows))
                    self.assertTrue(any(row.get('temporary_raise_released') for row in rows))
            finally:
                cover.terminate()
                root.destroy()

    def test_one_browser_worker_serves_readers_and_import_without_monitoring(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        url = 'https://adeo.service-now.com/incident_list.do'
        settings = {'filters': [{'name': 'Test', 'url': url, 'enabled': True}], 'auto_login': True}
        page = Mock(url='https://adeo.service-now.com/now/sow/home')
        page.is_closed.return_value = False
        page.wait_for_timeout.side_effect = lambda ms: time.sleep(ms / 1000)
        context = Mock(pages=[page])
        runtime = Mock()
        runtime.window.is_hidden.return_value = True
        calls = []

        def reader(kind):
            def invoke(tab, *_args, **_kwargs):
                calls.append((kind, tab, threading.get_ident()))
                if kind == 'threatened':
                    app.threatened_next_read = time.monotonic() + 60
                return 'success' if kind == 'filter' else True
            return invoke

        with patch('neto_incident_monitor.app.read_json', return_value=settings), \
                patch('neto_incident_monitor.dashboard_cache.load_snapshot', return_value=None), \
                patch('neto_incident_monitor.shared_session.open_context', return_value=context) as launch, \
                patch('neto_incident_monitor.shared_session.create_runtime', return_value=runtime), \
                patch('neto_incident_monitor.shared_session.sync_playwright'), \
                patch('neto_incident_monitor.shared_session.authentication_required', return_value=False), \
                patch('neto_incident_monitor.app.open_login_target', return_value=True), \
                patch('neto_incident_monitor.app.wait_for_login', return_value=True), \
                patch('neto_incident_monitor.favorites_worker.collect_with_recovery', return_value=[]) as favorites:
            app = App(root, history_path=Path(directory.name) / 'history.json', enable_tray=False,
                      apply_startup=False, shared_session=True)
            app.read_dashboard_request = reader('dashboard')
            app.read_threatened_request = reader('threatened')
            app.read_filter = reader('filter')
            self.assertEqual(root.state(), 'withdrawn')
            app.session.thread.start()
            self.addCleanup(app.session.thread.join, 2)
            self.addCleanup(app.session.shutdown)

            def wait_for(predicate):
                deadline = time.monotonic() + 4
                while not predicate() and time.monotonic() < deadline:
                    root.update()
                    time.sleep(.01)
                self.assertTrue(predicate())

            wait_for(lambda: app.session_state == 'ready')
            self.assertNotEqual(root.state(), 'withdrawn')
            self.assertTrue(app.request_refresh('all'))
            app.import_favorites()
            wait_for(lambda: app.favorites_import.result is not None)
            self.assertEqual([item[0] for item in calls], ['dashboard', 'threatened', 'filter'])
            self.assertTrue(all(item[1] is page and item[2] == app.session.thread.ident for item in calls))
            self.assertIs(favorites.call_args.args[0], page)
            self.assertFalse(app.cycle_active)
            launch.assert_called_once()
            self.assertTrue(launch.call_args.kwargs['visible'])
            context.new_page.assert_not_called()
            app.favorites_import.cancel()
            app.submit_alert_delivery = Mock()
            app.dashboard_auto_refresh.set(True)
            calls.clear()
            app.start()
            self.assertEqual(app.session.cycle.intervals['task'], 60)
            wait_for(lambda: len(calls) >= 3)
            self.assertEqual([item[0] for item in calls[:3]], ['dashboard', 'threatened', 'filter'])
            self.assertTrue(app.import_button.enabled)
            app.import_favorites()
            self.assertFalse(app.import_button.enabled)
            wait_for(lambda: app.favorites_import.result is not None)
            self.assertTrue(app.cycle_active)
            app.favorites_import.cancel()
            app.stop_monitoring()
            self.assertFalse(app.cycle_active)
            context.close.assert_not_called()
            self.assertTrue(app.request_refresh('dashboard'))
            wait_for(lambda: len(calls) == 4)
            self.assertEqual(calls[-1][0], 'dashboard')
            self.assertTrue(all(item[1] is page for item in calls))
            launch.assert_called_once()
            app.session.shutdown()
            app.session.thread.join(2)
            self.assertFalse(app.session.thread.is_alive())
            context.close.assert_called_once()

    @unittest.skipUnless(sys.platform == 'win32', 'Native Chromium visibility is Windows-specific')
    def test_native_start_hides_chromium_before_revealing_tk(self):
        import ctypes
        from ctypes import wintypes

        from neto_incident_monitor.browser_session import open_context

        user32 = ctypes.WinDLL('user32')
        user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        user32.GetAncestor.restype = wintypes.HWND
        user32.GetForegroundWindow.restype = wintypes.HWND
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        folder = Path(directory.name)
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)

        def fixture_browser(playwright, profile, diagnostics, **options):
            context = open_context(playwright, profile, diagnostics, **options)
            context.route('**/*', lambda route: route.fulfill(
                content_type='text/html', body='<script>window.g_user={userID:"fixture"}</script>'))
            return context

        with patch('neto_incident_monitor.app.read_json', return_value={'filters': []}), \
                patch('neto_incident_monitor.app.DATA', folder), \
                patch('neto_incident_monitor.dashboard_cache.load_snapshot', return_value=None), \
                patch('neto_incident_monitor.shared_session.open_context', side_effect=fixture_browser):
            app = App(root, history_path=folder / 'history.json', enable_tray=False, apply_startup=False,
                      shared_session=True)
            revealed = []
            show_window = app.show_window

            def check_visibility(**options):
                revealed.append(app.browser_window.is_hidden())
                show_window(**options)

            app.show_window = check_visibility
            self.assertEqual(root.state(), 'withdrawn')
            app.session.thread.start()
            try:
                deadline = time.monotonic() + 15
                while app.session_state not in ('ready', 'failed') and time.monotonic() < deadline:
                    root.update()
                    time.sleep(.01)
                self.assertEqual(app.session_state, 'ready')
                self.assertEqual(revealed, [True])
                self.assertEqual(root.state(), 'normal')
                self.assertTrue(app.browser_window.is_hidden())
                hwnd = user32.GetAncestor(root.winfo_id(), 2)
                deadline = time.monotonic() + 1
                while user32.GetForegroundWindow() != hwnd and time.monotonic() < deadline:
                    root.update()
                    time.sleep(.01)
                self.assertEqual(user32.GetForegroundWindow(), hwnd, 'Tk did not receive the Windows foreground')
                focused = root.focus_displayof()
                self.assertIsNotNone(focused)
                self.assertIs(focused.winfo_toplevel(), root)
            finally:
                app.session.shutdown()
                app.session.thread.join(6)
            self.assertFalse(app.session.thread.is_alive())
