"""Local period/transaction races; no ServiceNow session or user data required."""
import json
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from neto_incident_monitor.app import App
from neto_incident_monitor.read_errors import BrowserClosedError
from neto_incident_monitor.dashboard import TITLES, HELD_TITLES, REQUEST_TITLES
from neto_incident_monitor.dashboard_cache import load_snapshot
from neto_incident_monitor.login_diagnostics import _logger, safe_facts
from neto_incident_monitor.monitoring import ReadPart
from neto_incident_monitor.read_errors import Cancelled, AuthenticationRequired
from neto_incident_monitor.threatened import KEYS


class DashboardPeriodTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        folder = Path(self.temp.name)
        config = folder / 'config.json'
        config.write_text(json.dumps({'filters': [
            {'name': 'Synthetic', 'url': 'https://adeo.service-now.com/incident_list.do?sysparm_query=active%3Dtrue'}
        ]}), encoding='utf-8')
        self.enterContext(patch('neto_incident_monitor.config_io.CONFIG', config))
        for name, path in (('STATE', folder / 'seen.json'), ('DATA', folder)):
            self.enterContext(patch(f'neto_incident_monitor.app.{name}', path))
        self.enterContext(patch('neto_incident_monitor.runtime_paths.DATA', folder))
        self.root = tk.Tk()
        self.root.withdraw()
        def destroy():
            for timer in self.root.tk.call('after', 'info'):
                self.root.tk.call('after', 'cancel', timer)
            self.root.destroy()
        self.addCleanup(destroy)
        self.app = App(self.root, history_path=folder / 'history.json',
                       enable_tray=False, apply_startup=False)
        self.addCleanup(self.app.teams_sender.stop)
        self.addCleanup(self.app.google_chat_sender.stop)
        self.addCleanup(self.app.alert_writer.shutdown)
        self.addCleanup(self.app.history_writer.shutdown)
        self.app.worker = Mock()
        self.app.worker.is_alive.return_value = True
        self.session = self.app.session
        self.session.connected = self.session.ready_once = True
        self.session.log = Mock()
        self.app.window_restoring = False
        self.app.handle_session_event('session_ready', None)
        self.panel = self.app.dashboard_view
        self.addCleanup(self.close_cache)
        self.panel.year.set('2026')
        self.panel.month.set('Październik')
        self.root.update_idletasks()

    def request(self, scope='dashboard'):
        self.assertTrue(self.app.request_refresh(scope))

    def wait_for_cache(self):
        deadline = time.monotonic() + 5
        while not self.panel.cache_writer.idle and time.monotonic() < deadline:
            self.root.update()
            time.sleep(.002)
        self.assertTrue(self.panel.cache_writer.idle)

    def close_cache(self):
        self.panel.cache_writer.close()
        self.wait_for_cache()

    def finish(self, request, state='finished'):
        self.app.events.put(('dashboard_updating', (*request, state)))
        self.app.drain()

    def assert_controls(self, state):
        self.assertEqual([str(c.cget('state')) for c in self.panel.period_controls], [state, state])

    def test_native_period_popdown_does_not_break_window_observation_or_error_dialog(self):
        from neto_incident_monitor.themed_dialogs import showerror
        from neto_incident_monitor.window_style import WindowPresentation, current_grab_path

        self.root.deiconify()
        self.root.update()
        self.app.session_state = 'ready'
        self.app.main_window = Mock()
        self.app.main_window.inspect.return_value = WindowPresentation('visible', True)
        for combo in self.panel.period_controls:
            with self.subTest(combo=str(combo)):
                self.root.tk.call('ttk::combobox::Post', str(combo))
                self.root.update()
                popdown = current_grab_path(self.root)
                self.assertEqual(str(popdown), f'{combo}.popdown')
                self.app.main_window.uncover.reset_mock()
                self.app.main_window.activate.reset_mock()
                self.app.observe_main_window()
                self.assertFalse(self.app.activate_main_window())
                self.app.focus_after_login()
                self.app.main_window.uncover.assert_not_called()
                self.app.main_window.activate.assert_not_called()

                def close_error():
                    for child in self.root.children.values():
                        if isinstance(child, tk.Toplevel) and child.title() == 'Błąd testowy':
                            child.destroy()
                            break

                close_timer = self.root.after(50, close_error)
                try:
                    self.assertEqual(showerror('Błąd testowy', 'Komunikat testowy', parent=self.root), 'ok')
                finally:
                    self.root.after_cancel(close_timer)
                if self.root.tk.getboolean(self.root.tk.call('winfo', 'viewable', popdown)):
                    self.assertEqual(current_grab_path(self.root), popdown)
                self.root.tk.call('ttk::combobox::Unpost', str(combo))
                self.root.update_idletasks()
                self.assertFalse(current_grab_path(self.root))
        self.app.main_window.uncover.reset_mock()
        self.app.observe_main_window()
        self.app.main_window.uncover.assert_called_once()

    def execute(self, read_month=None, *, drain=True):
        """Run the actual queue with a synchronous bridge for Tk's prepare event."""
        def sla(_page, _stop, _diagnostics, _config, _year, _month, _completed):
            return dict.fromkeys(TITLES, 10)

        request = None
        enqueue = self.app.events.put

        def prepare_or_queue(event):
            nonlocal request
            kind, value = event
            if kind == 'session_prepare_read':
                self.app.handle_session_event(kind, value)
                if value['part'].scope == 'dashboard':
                    request = value['value']
            else:
                enqueue(event)

        page = Mock()
        page.is_closed.return_value = False
        with patch('neto_incident_monitor.analytics_config.load_config', return_value={'assignees': ['a' * 32], 'locations': ['b' * 32]}), \
                patch('neto_incident_monitor.shared_session.authentication_required', return_value=False), \
                patch('neto_incident_monitor.browser_actions.wait_for_browser_cycle', side_effect=Cancelled) as wait, \
                patch.object(self.app.events, 'put', side_effect=prepare_or_queue), \
                patch('neto_incident_monitor.dashboard_api.read_month', side_effect=read_month or sla), \
                patch('neto_incident_monitor.dashboard_api.read_held', return_value=dict.fromkeys(HELD_TITLES, 20)), \
                patch('neto_incident_monitor.dashboard_api.read_requests', return_value=dict.fromkeys(REQUEST_TITLES, 30)), \
                patch('neto_incident_monitor.threatened_api.read_threats', return_value=(dict.fromkeys(KEYS, 0), {})):
            with self.assertRaises(Cancelled):
                self.session.serve(page)
            wait.assert_called_once()
        if drain:
            self.app.drain()
        return request

    def test_final_result_waiting_in_ui_queue_keeps_period_frozen(self):
        self.request()
        request = self.execute(drain=False)
        self.assert_controls('disabled')
        self.panel.year.set('2028')
        self.assertEqual(self.panel.active_request, request)
        self.assertEqual(self.panel.year.get(), '2026')
        self.app.drain()
        self.assertEqual(self.panel.values[TITLES[0]].get(), '10')
        self.assert_controls('readonly')

    def test_reauthentication_and_retry_keep_controls_locked(self):
        self.request()
        calls = []

        def sla(_page, _stop, _diagnostics, _config, year, month, _completed):
            calls.append((self.panel.active_request, (year, month)))
            if len(calls) == 1:
                raise AuthenticationRequired()
            return dict.fromkeys(TITLES, 10)

        def restore(*_):
            self.assert_controls('disabled')
            self.panel.month.set('Listopad')
            self.panel.year.set('2027')
            self.assertEqual(self.panel.active_request, calls[0][0])
            return True

        with patch.object(self.session, 'authenticate', side_effect=restore) as authenticate:
            request = self.execute(sla)
        authenticate.assert_called_once()
        self.assertEqual(calls, [(request, (2026, 10))] * 2)
        self.assert_controls('readonly')
        self.assertEqual(self.panel.values[TITLES[0]].get(), '10')

    def test_queued_request_freezes_both_controls_and_rejects_all_selection_paths(self):
        self.request()
        idle_id = self.panel.request_id
        self.assert_controls('disabled')
        for control in self.panel.period_controls:
            control.current(1)  # Tcl/programmatic changes bypass disabled widgets.
            for event in ('<Button-1>', '<Key-Down>', '<MouseWheel>', '<<ComboboxSelected>>'):
                control.event_generate(event)
        self.panel.month.set('Grudzień')
        self.panel.year.set('2027')
        self.assertIsNone(self.panel.active_request)
        self.assertEqual((self.panel.year.get(), self.panel.month.get()), ('2026', 'Październik'))
        self.assertEqual(self.panel.request_id, idle_id)
        self.assertEqual(self.session.work.pending_refreshes()[1], {ReadPart('dashboard', (2026, 10))})

    def test_actual_worker_results_and_cache_survive_selection_attempt(self):
        self.request()

        def sla(_page, _stop, _diagnostics, _config, year, month, _completed):
            self.panel.month.set('Listopad')
            self.assertEqual((year, month), (2026, 10))
            return dict.fromkeys(TITLES, 10)

        request = self.execute(sla)
        self.assertEqual(self.panel.values[TITLES[0]].get(), '10')
        self.assertEqual(self.panel.values[HELD_TITLES[0]].get(), '20')
        self.assertEqual(self.panel.values[REQUEST_TITLES[0]].get(), '30')
        self.assertEqual(self.panel.section_states['Dashboard SLA'], 'Zaktualizowany')
        self.wait_for_cache()
        self.assertEqual(load_snapshot(Path(self.temp.name)/'dashboard-cache.json')['sections']['sla']['month'], 10)
        self.assertIsNone(self.panel.active_request)
        self.assert_controls('readonly')
        self.assertEqual(self.panel.request_id, request[0])

    def test_controls_unlock_on_partial_failure_and_cancel(self):
        for failure in (ValueError('synthetic'), Cancelled()):
            with self.subTest(failure=type(failure).__name__):
                self.request()
                self.execute(Mock(side_effect=failure))
                self.assertIsNone(self.panel.active_request)
                self.assert_controls('readonly')

    def test_browser_restart_keeps_same_request_locked_until_real_completion(self):
        self.request()
        with self.assertRaises(BrowserClosedError):
            self.execute(Mock(side_effect=BrowserClosedError('closed')))
        self.app.drain()
        request = self.panel.active_request
        self.assertIsNotNone(request)
        self.assert_controls('disabled')
        self.assertEqual(self.session.work.pending_refreshes()[1], {ReadPart('dashboard', (2026, 10))})
        self.assertEqual(self.execute(), request)
        self.assert_controls('readonly')

    def test_old_finish_and_wrong_period_do_not_release_new_transaction(self):
        self.request()
        old = self.execute()
        self.wait_for_cache()
        self.request()

        def sla(*_args):
            current = self.panel.active_request
            for event in ((*old, 'finished'), (current[0], 2027, 10, 'finished')):
                self.finish(event[:3], event[3])
                self.assertEqual(self.panel.active_request, current)
                self.assert_controls('disabled')
            return dict.fromkeys(TITLES, 11)

        self.execute(sla)
        self.assert_controls('readonly')
        self.assertEqual(self.panel.values[TITLES[0]].get(), '11')

    def test_wrong_period_with_current_id_cannot_write_values_or_cache(self):
        self.request()
        old = self.execute()
        old_snapshot = dict(self.panel.section_snapshots)
        cache = Path(self.temp.name) / 'dashboard-cache.json'
        previous = cache.read_bytes()
        self.request()
        metadata = {'section': 'sla', 'values': dict.fromkeys(TITLES, 9),
                    'read_at': '2026-10-01T12:00:00+02:00', 'diagnostics': Mock()}

        def sla(*_args):
            request = self.panel.active_request
            for stale in (old, (request[0], 2027, 10)):
                self.app.events.put(('dashboard_result', (*stale, {}, None, '', metadata)))
            self.app.drain()
            self.assertEqual(self.panel.section_snapshots, old_snapshot)
            self.assertEqual(cache.read_bytes(), previous)
            return dict.fromkeys(TITLES, 11)

        self.execute(sla)
        self.assertEqual(self.panel.values[TITLES[0]].get(), '11')

    def test_idle_selection_only_stales_sla_and_preserves_displayed_period(self):
        self.request()
        self.execute()
        old = dict(self.panel.section_snapshots)
        self.panel.month.set('Listopad')
        self.panel.period_controls[0].event_generate('<<ComboboxSelected>>')
        self.assertEqual(self.panel.section_states['Dashboard SLA'], 'Dane nieaktualne')
        self.assertEqual(self.panel.section_states['Wstrzymane L1'], 'Zaktualizowany')
        self.assertEqual(self.panel.section_states['Wnioski L1'], 'Zaktualizowany')
        self.assertEqual(self.panel.section_snapshots, old)
        self.assertIn('Dane SLA za okres październik 2026', self.panel.message.get())
        self.assertIn('Wybrano listopad 2026', self.panel.message.get())
        self.request()
        self.assertEqual(self.panel.queued_period, (2026, 11))

    def test_stop_cancels_automatic_dashboard_and_preserves_manual_dashboard(self):
        for automatic in (True, False):
            with self.subTest(automatic=automatic):
                self.app.dashboard_auto_refresh.set(automatic)
                self.app.start()
                self.assertTrue(self.app.cycle_active)
                if not automatic:
                    self.request()

                def sla(_page, stop, *_args):
                    self.assert_controls('disabled')
                    self.app.stop_monitoring()
                    self.assertEqual(stop.is_set(), automatic)
                    if not automatic:
                        self.assert_controls('disabled')
                        self.panel.month.set('Listopad')
                        self.assertEqual(self.panel.selected_period(), (2026, 10))
                    return dict.fromkeys(TITLES, 10)

                self.execute(sla)
                self.assertFalse(self.app.cycle_active)
                self.assertIsNone(self.panel.active_request)
                self.assert_controls('readonly')
                self.assertEqual(self.panel.last_complete_period, None if automatic else (2026, 10))
                if automatic:
                    self.assertIsNone(self.session.threatened_next_read)
                    self.assertIsNone(self.app.history.membership)

    def test_stop_after_browser_close_releases_interrupted_automatic_dashboard(self):
        self.app.dashboard_auto_refresh.set(True)
        self.app.start()
        with self.assertRaises(BrowserClosedError):
            self.execute(Mock(side_effect=BrowserClosedError('closed')))
        self.app.events.put(('session_problem', None))
        self.app.drain()
        old = self.panel.active_request
        self.assertIsNotNone(old)
        self.assert_controls('disabled')

        with self.assertLogs(_logger, level='INFO') as captured:
            self.app.stop_monitoring()
        events = [json.loads(record.getMessage()) for record in captured.records]
        self.assertTrue(any(event.get('request_id') == old[0] and event.get('request_state') == 'cancelled'
                            for event in events))
        self.assertIsNone(self.panel.active_request)
        self.assert_controls('readonly')
        self.panel.month.set('Listopad')
        self.app.handle_session_event('session_ready', None)
        self.request()

        def sla(_page, _stop, _diagnostics, _config, year, month, _completed):
            self.finish(old)
            self.assertEqual((year, month), (2026, 11))
            self.assert_controls('disabled')
            return dict.fromkeys(TITLES, 10)

        current = self.execute(sla)
        self.assertNotEqual(current[0], old[0])
        self.assertEqual(self.panel.last_complete_period, (2026, 11))

    def test_all_request_locks_before_threatened_read_and_other_scope_does_not(self):
        self.request('threatened')
        self.assert_controls('readonly')
        self.request('all')
        self.assert_controls('disabled')
        self.app.show_threatened_view()
        self.app.show_dashboard_view()
        self.assert_controls('disabled')

    def test_unavailable_session_does_not_lock_period(self):
        self.app.session_state = 'failed'
        self.assertFalse(self.app.request_refresh('all'))
        self.assertIsNone(self.panel.active_request)
        self.assertIsNone(self.panel.queued_period)
        self.assert_controls('readonly')

    def test_startup_request_locks_before_prepare_and_stop_releases_it(self):
        self.app.dashboard_auto_refresh.set(True)
        self.app.start()
        self.assertEqual(self.panel.queued_period, (2026, 10))
        self.assert_controls('disabled')
        self.assertIsNone(self.panel.active_request)
        self.app.stop_monitoring()
        self.assertTrue(self.session.cycle.stop.is_set())
        self.assertFalse(self.session.closed.is_set())
        self.assertIsNone(self.panel.active_request)
        self.assert_controls('readonly')

    def test_duplicate_result_after_finish_cannot_overwrite_accepted_snapshot(self):
        self.request()
        request = self.execute()
        old = dict(self.panel.section_snapshots['sla'])
        self.panel.apply_result((*request, {}, None, '',
            {'section':'sla','values':dict.fromkeys(TITLES,99),'read_at':'2026-10-02T12:00:00+02:00','diagnostics':Mock()}))
        self.assertEqual(self.panel.section_snapshots['sla'], old)

    def test_diagnostic_failure_cannot_keep_period_locked_or_discard_good_result(self):
        self.request()

        def sla(*_args):
            self.panel.request_diagnostics = Mock()
            self.panel.request_diagnostics.record.side_effect = OSError('SYNTHETIC_SECRET')
            self.panel.month.set('Listopad')
            return dict.fromkeys(TITLES, 10)

        self.execute(sla)
        self.assert_controls('readonly')
        self.assertEqual(self.panel.values[TITLES[0]].get(), '10')

    def test_lifecycle_diagnostics_are_allowlisted_correlated_and_safe(self):
        with self.assertLogs(_logger, level='INFO') as captured:
            self.request()
            self.panel.year.set('2027')

            def sla(*_args):
                request = self.panel.active_request
                self.finish((request[0] - 1, 2026, 10))
                self.panel.apply_result((request[0], 2027, 10, {}, None))
                return dict.fromkeys(TITLES, 10)

            self.execute(sla)
        rows = [json.loads(record.getMessage()) for record in captured.records]
        relevant = [r for r in rows if r['event'] in {'dashboard_period_state', 'dashboard_request_state', 'dashboard_result_rejected'}]
        self.assertTrue(all('run_id' in r and 'request_id' in r and 'request_state' in r for r in relevant))
        self.assertTrue({'locked','blocked','queued','unlocked','period_mismatch','stale_id'} <= {r['request_state'] for r in relevant})
        self.assertEqual(safe_facts({'request_state':'SYNTHETIC_SECRET','year':2026,'url':'SYNTHETIC_SECRET'}), {'year':2026})
