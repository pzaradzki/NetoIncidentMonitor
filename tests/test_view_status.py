import json
import tempfile
import threading
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from neto_incident_monitor.analytics_api import data_duration, get, measure_data_requests
from neto_incident_monitor.app import App
from neto_incident_monitor.dashboard_cache import SECTIONS, load_snapshot
from neto_incident_monitor.login_diagnostics import safe_facts
from neto_incident_monitor.monitoring import ReadPart
from neto_incident_monitor.threatened import KEYS


class RequestTimingTests(unittest.TestCase):
    def test_reused_requests_are_counted_once_and_logging_failure_does_not_change_results(self):
        stop = threading.Event()
        log = Mock()
        log.record.side_effect = OSError('SYNTHETIC_SECRET')
        page = Mock()
        reply = {'status': 200, 'next': False, 'result': {}}
        page.evaluate.side_effect = [dict(reply, elapsedMs=16.5), dict(reply, elapsedMs=28.5),
                                     dict(reply, elapsedMs=100.5)]
        with measure_data_requests() as times:
            for ordinal in (1, 1, 2):
                get(page, stop, log, 'held', '/api/now/stats/incident_metric', {}, ordinal=ordinal)
        self.assertEqual(data_duration(times), 129)
        completion = log.record.call_args.kwargs
        self.assertEqual(safe_facts(completion)['api_data_ms'], 100)
        self.assertNotIn('SYNTHETIC_SECRET', str(log.record.call_args_list))


class ViewStatusTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name)
        self.root = tk.Tk()
        self.addCleanup(self.close_root)
        self.root.report_callback_exception = Mock()
        self.settings = {'filters': [dict(name='Długi tytuł filtra ' * 14,
                                         url='https://adeo.service-now.com/incident_list.do?sysparm_query=active%3Dtrue'),
                                     dict(name='Wnioski', url='https://adeo.service-now.com/sc_task_list.do?sysparm_query=active%3Dtrue')]}
        self.app = self.build_app()

    def build_app(self):
        with patch('neto_incident_monitor.app.read_json', return_value=self.settings), \
                patch('neto_incident_monitor.runtime_paths.DATA', self.path), \
                patch('neto_incident_monitor.app.CONFIG', self.path / 'config.json'):
            app = App(self.root, history_path=self.path / 'history.json', apply_startup=False,
                      enable_tray=False, shared_session=True)
        self.addCleanup(app.teams_sender.stop)
        self.addCleanup(app.google_chat_sender.stop)
        self.addCleanup(app.alert_writer.shutdown)
        self.addCleanup(app.history_writer.shutdown)
        return app

    def close_root(self):
        for timer in self.root.tk.splitlist(self.root.tk.call('after', 'info')):
            self.root.tk.call('after', 'cancel', timer)
        self.root.destroy()

    def emit(self, *events):
        for event in events:
            self.app.events.put(event)
        self.app.drain()

    def test_all_three_read_bars_hide_missing_metadata_and_share_the_pill_style(self):
        from neto_incident_monitor.read_status import ReadStatus
        from neto_incident_monitor.theme import SURFACE

        app = self.app
        bars = (app.filter_read_bar, app.dashboard_view.read_bar, app.threatened_view.read_bar)
        for bar in bars:
            with self.subTest(label=bar.date_label):
                self.assertEqual(bar.cget('background'), SURFACE)
                self.assertEqual(bar.pill.status_text, 'Brak odczytu')
                self.assertTrue(bar.pill.winfo_manager())
                self.assertTrue(all(not label.winfo_manager() for label in bar.labels[1:]))
                accepted = ReadStatus().accepted(100.0, None)
                bar.show(accepted)
                self.assertEqual(bar.pill.tone, 'success')
                self.assertTrue(bar.labels[1].winfo_manager())
                self.assertFalse(bar.labels[2].winfo_manager())
                bar.show(accepted.failed('Spróbuj ponownie.'))
                self.assertTrue(bar.message.winfo_manager())
                self.assertFalse(bar.pill.winfo_manager())
                self.assertTrue(bar.labels[1].winfo_manager())
                bar.show(ReadStatus().failed('Spróbuj ponownie.'))
                self.assertFalse(bar.meta.winfo_manager())

    def test_settings_layout_preview_shows_field_identifiers_and_clears_on_relogin(self):
        from tkinter import ttk
        from neto_incident_monitor.filter_layouts import LayoutAccount, LayoutStore
        from neto_incident_monitor.widgets import RoundedButton

        app = self.app
        app.session.layouts = LayoutStore(self.path / 'filter-layouts.json')
        app.session.layout_account = LayoutAccount('test-account', 'pl')
        app.session.connected = True
        app.session_state = 'ready'
        app.session.layouts.save(app.session.layout_account, 'incident', 'default',
                                 [{'label': 'Krótki opis', 'field': 'short_description', 'key': 'short_description'}])
        settings = app.settings_window
        settings.deiconify()

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        next(widget for widget in descendants(settings) if isinstance(widget, RoundedButton) and widget.text == 'Pokaż').invoke()
        dialog = next(widget for widget in settings.winfo_children() if isinstance(widget, tk.Toplevel))
        tables = [widget for widget in descendants(dialog) if isinstance(widget, ttk.Treeview)]
        self.assertEqual(len(tables), 4)
        self.assertEqual(tables[0].item(tables[0].get_children()[0], 'values'), ('Krótki opis', 'short_description'))
        self.assertTrue(all(not table.get_children() for table in tables[1:]))
        self.emit(('session_waiting', None))
        self.assertTrue(all(not table.get_children() for table in tables))
        dialog.destroy()
        self.assertIsNone(app.refresh_saved_layout_preview)

    def test_layout_refresh_queues_during_monitoring_and_preserves_failed_table(self):
        from tkinter import ttk
        from neto_incident_monitor.dashboard_context import DashboardReadError
        from neto_incident_monitor.filter_layout_ui import show_saved_layouts
        from neto_incident_monitor.filter_layouts import LayoutAccount, LayoutStore
        from neto_incident_monitor.widgets import RoundedButton

        app = self.app
        session = app.session
        session.layouts = LayoutStore(self.path / 'filter-layouts.json')
        session.log = Mock()
        session.layout_account = LayoutAccount('test-account', 'pl')
        session.ready_once = session.connected = app.cycle_active = True
        app.session_state = 'ready'
        old = [{'label': 'Numer', 'field': 'number', 'key': 'number'}]
        new = [{'label': 'Krótki opis', 'field': 'short_description', 'key': 'short_description'}]
        session.layouts.save(session.layout_account, 'sc_request', 'default', old)
        earlier = ReadPart('dashboard', app.dashboard_view.selected_period())
        session.submit('dashboard', [earlier])
        self.assertEqual(session.next_part(None), (earlier, 'manual'))
        app.settings_window.deiconify()
        dialog = show_saved_layouts(app, app.settings_window)
        panel = dialog.winfo_children()[0]
        footer = panel.winfo_children()[-1]
        update = next(button for button in footer.winfo_children()
                      if isinstance(button, RoundedButton) and button.text == 'Aktualizuj')
        status = next(widget for widget in footer.winfo_children() if isinstance(widget, ttk.Label))
        update.invoke()
        request_id = app.default_layout_refresh[0]
        self.assertEqual(footer.getvar(status['textvariable']), 'W kolejce')
        self.assertFalse(update.enabled)
        self.assertFalse(app.request_default_layout_refresh())
        self.assertIs(session.active_job.parts[0], earlier)
        session.work.complete_part(earlier, manual=True, success=True)
        part, source = session.next_part(None)
        self.assertEqual(part.scope, 'default_layouts')
        self.emit(('session_default_layout_started', request_id))
        self.assertEqual(footer.getvar(status['textvariable']), 'Aktualizowanie układów…')
        with patch.object(session, 'update_layout_account'), patch(
                'neto_incident_monitor.shared_session.fetch_layout',
                side_effect=[new, DashboardReadError('api_access'), new, new]) as read:
            self.assertFalse(app.execute_session_part(Mock(), part, session.closed, source))
        self.assertEqual([call.args[3] for call in read.call_args_list], ['incident', 'sc_request', 'sc_req_item', 'sc_task'])
        session.active_job_success = False
        session.work.complete_part(part, manual=True, success=False)
        session.finish_manual_job(None)
        self.emit()
        self.assertTrue(update.enabled)
        self.assertIn('REQ.', footer.getvar(status['textvariable']))
        self.assertEqual(session.saved_default_layouts()['REQ'], (('Numer', 'number'),))
        self.assertEqual(session.saved_default_layouts()['INC'], (('Krótki opis', 'short_description'),))
        queue_log = session.log.record.call_args.kwargs
        self.assertEqual((queue_log['request_id'], queue_log['outcome'], queue_log['ready_count']), (request_id, 'partial', 3))
        dialog.destroy()

    def test_dashboard_scope_preview_queues_one_refresh_and_shows_saved_ids(self):
        from tkinter import ttk
        from neto_incident_monitor.analytics_config import save_dashboard_scope
        from neto_incident_monitor.filter_layouts import LayoutAccount
        from neto_incident_monitor.widgets import RoundedButton

        app = self.app
        session = app.session
        session.log = Mock()
        session.layout_account = LayoutAccount('test-account', 'pl')
        session.connected = True
        app.session_state = 'ready'
        app.cycle_active = True
        settings = app.settings_window
        settings.deiconify()

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        path = self.path / 'dashboard-api.json'
        original = {'assignees': ['a' * 32], 'locations': ['b' * 32]}
        updated = {'assignees': ['c' * 32], 'locations': ['d' * 32]}
        path.write_text(json.dumps({'version': 1, **original}), encoding='utf-8')
        with patch('neto_incident_monitor.analytics_config.CONFIG_PATH', path):
            buttons = [widget for widget in descendants(settings)
                       if isinstance(widget, RoundedButton) and widget.text == 'Pokaż']
            buttons[-1].invoke()
            dialog = next(widget for widget in settings.winfo_children() if isinstance(widget, tk.Toplevel))
            self.assertEqual(dialog.title(), 'Agenci i lokalizacje Dashboardu SLA')
            tables = [widget for widget in descendants(dialog) if isinstance(widget, ttk.Treeview)]
            update = next(widget for widget in descendants(dialog)
                          if isinstance(widget, RoundedButton) and widget.text == 'Aktualizuj')

            def rows():
                return [table.item(table.get_children()[0], 'values') for table in tables]

            self.assertEqual(rows(), [('a' * 32,), ('b' * 32,)])
            update.invoke()
            request_id, phase = app.dashboard_scope_refresh
            self.assertEqual(phase, 'queued')
            self.assertFalse(update.enabled)
            self.assertFalse(app.request_dashboard_scope_refresh())
            part, source = session.next_part(None)
            self.assertEqual((part.scope, source), ('dashboard_scope', 'manual'))
            self.emit(('session_dashboard_scope_started', request_id))
            save_dashboard_scope(updated)
            session.work.complete_part(part, manual=True, success=True)
            session.finish_manual_job(None)
            self.emit()
            self.assertTrue(update.enabled)
            self.assertEqual(rows(), [('c' * 32,), ('d' * 32,)])
            app.cycle_active = False
            update.invoke()
            self.assertEqual(app.dashboard_scope_refresh[1], 'queued')
            dialog.destroy()
            self.assertIsNone(app.refresh_dashboard_scope_preview)
        self.root.report_callback_exception.assert_not_called()

    def test_queue_work_login_and_notice_have_independent_lifetimes(self):
        app = self.app
        app.session.ready_once = True
        app.session_state = 'ready'
        dashboard = ReadPart('dashboard', app.dashboard_view.selected_period())
        threatened = ReadPart('threatened')
        app.session.submit('dashboard', [dashboard])
        app.session.submit('all', [dashboard, threatened])
        app.update_refresh_controls()
        self.assertTrue(app.dashboard_button.queued)
        self.assertTrue(app.threatened_incidents_button.queued)
        self.assertFalse(app.dashboard_view.refresh_button.enabled)
        app.session.work.take()
        token = object()
        app.status.set('Nie zapisano konfiguracji.')
        self.emit(('session_part_started', (token, dashboard)), ('session_waiting', None))
        self.assertTrue(app.dashboard_button.updating)
        self.assertIn('Oczekuje na logowanie', app.work_status.get())
        self.assertEqual(app.activity_pill.status_text, 'Monitoring zatrzymany')
        app.session.work.complete_part(dashboard, manual=True, success=True)
        next_token = object()
        self.emit(('session_part_started', (next_token, threatened)), ('session_part_finished', token))
        self.assertIn('Incydenty zagrożone', app.work_status.get())
        app.session.work.complete_part(threatened, manual=True, success=True)
        self.emit(('session_part_finished', next_token), ('session_job_finished', ('all', True, 0)))
        self.assertEqual(app.work_status.get(), '')
        self.assertEqual(app.status.get(), 'Nie zapisano konfiguracji.')

    def test_shared_footer_spans_gap_and_follows_sidebar_resize(self):
        app = self.app
        app.show_incident_view()
        self.root.geometry('1500x780')
        self.root.update()
        surface, line = app.footer_surface, app.footer_line

        def verify_alignment():
            self.assertEqual(surface.winfo_rootx(), app.sidebar_canvas.winfo_rootx())
            self.assertEqual(app.work_bar.winfo_rootx(), app.filter_read_bar.winfo_rootx())
            self.assertEqual(line.winfo_width(), surface.winfo_width())
            self.assertTrue(surface.winfo_ismapped())
            self.assertEqual(surface.winfo_rooty(), app.session_bar.winfo_rooty())
            self.assertEqual(surface.winfo_rooty(), app.work_bar.winfo_rooty())
            self.assertGreater(surface.winfo_rootx() + surface.winfo_width(), app.work_bar.winfo_rootx())

        verify_alignment()
        start = app.splitter.winfo_rootx()
        before = app.work_bar.winfo_rootx()
        with patch.object(app, 'save_sidebar_width'):
            app.splitter.event_generate('<ButtonPress-1>', rootx=start)
            app.splitter.event_generate('<B1-Motion>', rootx=start + 35)
            app.splitter.event_generate('<ButtonRelease-1>', rootx=start + 35)
        self.root.update()
        self.assertGreater(app.work_bar.winfo_rootx(), before)
        verify_alignment()
        state_label = next(child for child in app.session_bar.winfo_children() if isinstance(child, tk.Label))
        work_label = next(child for child in app.work_bar.winfo_children() if isinstance(child, tk.Label))
        icon = next(child for child in app.work_bar.winfo_children() if isinstance(child, tk.Canvas))
        pulse, = icon.find_all()
        self.assertEqual(icon.type(pulse), 'line')
        self.assertLess(icon.winfo_rootx(), work_label.winfo_rootx())
        idle_color = icon.itemcget(pulse, 'fill')
        app.session_state = 'ready'
        app.work_status.set('Aktualizuje filtr')
        self.assertNotEqual(icon.itemcget(pulse, 'fill'), idle_color)
        app.work_status.set('')
        self.assertEqual(state_label.cget('font'), work_label.cget('font'))
        self.assertEqual(state_label.winfo_height(), work_label.winfo_height())
        self.assertEqual(work_label.getvar(work_label.cget('textvariable')), 'Aktywność · Brak zleceń')
        self.emit(('session_waiting', None), ('session_activity', ('Wymagane logowanie', 'waiting', True)))
        self.root.update()
        self.assertTrue(app.login_window_button.winfo_ismapped())
        self.assertIs(app.login_window_button.master, app.footer_actions)
        self.assertEqual(app.session_status.get(), 'Wymagane logowanie')
        self.assertEqual(state_label.getvar(state_label.cget('textvariable')), 'ServiceNow · Wymagane logowanie')
        self.root.report_callback_exception.assert_not_called()

    def test_filter_read_follows_selected_filter_and_ignores_old_revision(self):
        app = self.app
        url = app.selected_filter_url()
        revision, generation = app.filter_revisions.get(url), app.monitor_generation
        self.emit(('snapshot', (url, {}, revision, generation, True, False, None, (100.0, 250))))
        fields = app.filter_read_bar.fields
        self.assertEqual(fields[0].get(), 'Odczyt udany')
        self.assertEqual(fields[2].get(), 'Zapytanie 0,25 s')
        self.assertFalse(app.filter_read_bar.message.winfo_manager())
        self.emit(('filter_activity', (url, ('filter_error', ('ServiceNow nie odpowiedział.', 'api_timeout')),
                                      revision, generation)))
        self.assertEqual(app.filter_read_bar.title.cget('text'), 'Nie udało się połączyć z ServiceNow')
        self.assertIn('Zachowano wynik', app.filter_read_bar.detail.cget('text'))
        self.assertFalse(app.filter_read_bar.labels[0].winfo_manager())
        self.assertEqual(fields[0].get(), 'Błąd odczytu')
        self.assertEqual(fields[2].get(), 'Zapytanie 0,25 s')
        self.emit(('snapshot', (url, {}, object(), generation, True, False, None, (200.0, 999))))
        self.assertEqual(fields[2].get(), 'Zapytanie 0,25 s')
        app.filter_table.selection_set('1')
        self.assertEqual(fields[0].get(), 'Brak odczytu')
        app.filter_table.selection_set('0')
        app.tabs.select(1)
        self.root.update()
        self.assertEqual(fields[0].get(), 'Błąd odczytu')
        self.root.report_callback_exception.assert_not_called()

    def test_notice_actions_share_the_header_controls_and_follow_filter_selection(self):
        app = self.app
        app.session.ready_once = True
        app.session_state = 'ready'
        app.update_refresh_controls()
        url = app.selected_filter_url()
        bar = app.filter_read_bar
        app.update_filter_read_result(url, error='Lista jest za duża.', title='Za dużo zgłoszeń w filtrze',
                                      action='edit', warning=True)
        with patch.object(app, 'edit_filter') as edit:
            bar.invoke_action()
            edit.assert_called_once_with(True)
        app.update_filter_read_result(url, error='Brak odpowiedzi.')
        bar.invoke_action()
        self.assertIn(ReadPart('filter', (url, app.filter_revisions.get(url))), app.session.work.pending_refreshes()[1])
        self.assertFalse(bar.button.enabled)
        app.filter_table.selection_set('1')
        self.assertFalse(bar.message.winfo_manager())

    def test_dashboard_period_partial_result_and_restored_timing(self):
        app = self.app
        app.worker = Mock()
        panel = app.dashboard_view
        request = panel.request_refresh(coordinated=True, enqueue=False)
        for section, titles in SECTIONS.items():
            panel.apply_result((*request, {}, None, '', dict(section=section, values=dict.fromkeys(titles, 0),
                read_at='2026-10-01T12:00:00+02:00', diagnostics=Mock(), duration_ms=400)))
        panel.apply_result((*request, {}, None, ''))
        panel.finish_pending()
        panel.set_updating(*request, 'finished')
        self.assertEqual(panel.read_bar.fields[2].get(), 'Zapytanie 1,20 s')
        cache = load_snapshot(self.path / 'dashboard-cache.json')
        self.assertEqual(cache['last_complete_period'], list(request[1:]))
        self.assertEqual(cache['last_complete_duration_ms'], 1200)
        request = panel.request_refresh(coordinated=True, enqueue=False)
        panel.apply_result((*request, {}, None, '', dict(section='sla', values=dict.fromkeys(SECTIONS['sla'], 1),
            read_at='2026-10-01T12:00:01+02:00', diagnostics=Mock(), duration_ms=975)))
        panel.apply_result((*request, {}, None, 'Brak danych Wniosków L1.'))
        panel.set_updating(*request, 'finished')
        self.assertEqual(panel.read_bar.fields[0].get(), 'Odczyt częściowy')
        self.assertEqual(panel.read_bar.fields[2].get(), 'Zapytanie 1,20 s')
        month = panel.month.get()
        self.root.update_idletasks()
        panel.month.set('Styczeń' if month != 'Styczeń' else 'Luty')
        panel.period_controls[0].event_generate('<<ComboboxSelected>>')
        self.assertEqual(panel.read_bar.fields[2].get(), 'Zapytanie —')

    def test_threatened_complete_empty_read_restores_and_late_results_are_ignored(self):
        app = self.app
        values = dict.fromkeys(KEYS, 0)
        app.history.commit_threatened({}, 100, lambda: None, lambda _: (), counters=values, duration_ms=78)
        from neto_incident_monitor.threatened_ui import build_threatened_view
        panel = build_threatened_view(self.root, app)
        self.assertEqual(panel.values, values)
        self.assertEqual(panel.read_bar.fields[0].get(), 'Odczyt udany')
        self.assertEqual(panel.read_bar.fields[2].get(), 'Zapytanie 0,08 s')
        panel.apply_result(panel.request_id, None, None)
        panel.finish_request(panel.request_id)
        panel.apply_result(panel.request_id, values, 200)
        panel.apply_details(panel.request_id, {}, 999)
        self.assertEqual(panel.read_bar.fields[0].get(), 'Błąd odczytu')
        self.assertEqual(panel.read_bar.fields[2].get(), 'Zapytanie 0,08 s')

    def test_filter_actions_share_heading_and_bars_fit_minimum_window(self):
        app = self.app
        app.show_incident_view()
        self.root.update_idletasks()
        for dpi_scale in (96, 120):
            with self.subTest(dpi_scale=dpi_scale):
                self.root.tk.call('tk', 'scaling', dpi_scale / 72)
                self.root.geometry(f'{self.root.minsize()[0]}x680')
                self.root.update()
                actions = app.configure_filter_button.master
                last = app.open_filter_button
                self.assertEqual(actions, last.master)
                self.assertLess(last.winfo_rooty(), app.tabs.winfo_rooty())
                self.assertLessEqual(last.winfo_rootx() + last.winfo_width(), self.root.winfo_rootx() + self.root.winfo_width())
                self.assertEqual(app.session_bar.winfo_rootx(), app.sidebar_canvas.winfo_rootx())
                self.assertGreater(app.filter_read_bar.winfo_rooty(), app.tabs.winfo_rooty())
                self.assertGreater(app.session_bar.winfo_rooty(), app.filter_read_bar.winfo_rooty())
                bar = app.filter_read_bar
                self.assertFalse(bar.message.winfo_manager())
                url = app.selected_filter_url()
                app.update_filter_read_result(url, error='Zawęź warunki w ServiceNow, aby zmniejszyć liczbę zgłoszeń. ' * 5,
                                              title='Filtr wyłączony z harmonogramu', action='edit', warning=True)
                self.root.update()
                self.assertTrue(bar.message.winfo_ismapped())
                self.assertLessEqual(bar.detail.winfo_rootx() + bar.detail.winfo_width(), bar.button.winfo_rootx())
                self.assertGreater(app.session_bar.winfo_rooty(), bar.winfo_rooty() + bar.winfo_height() - 1)
                app.update_filter_read_result(url, accepted=(100, 200))
        self.root.report_callback_exception.assert_not_called()
