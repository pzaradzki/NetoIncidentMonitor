"""Local period/transaction races; no ServiceNow session or user data required."""
import json
import queue
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from neto_incident_monitor.app import App, BrowserClosedError
from neto_incident_monitor.dashboard import TITLES, HELD_TITLES, REQUEST_TITLES
from neto_incident_monitor.dashboard_cache import load_snapshot
from neto_incident_monitor.login_diagnostics import _logger, safe_facts
from neto_incident_monitor.pagination import Cancelled, AuthenticationRequired


class DashboardPeriodTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = tk.Tk()
        self.root.withdraw()
        def destroy():
            for timer in self.root.tk.call('after', 'info'):
                self.root.tk.call('after', 'cancel', timer)
            self.root.destroy()
        self.addCleanup(destroy)
        with patch('neto_incident_monitor.runtime_paths.DATA', Path(self.temp.name)), \
                patch('neto_incident_monitor.app.read_json', return_value={}):
            self.app = App(self.root, history_path=Path(self.temp.name)/'history.json',
                           enable_tray=False, apply_startup=False)
        self.app.worker = Mock()
        self.app.worker.is_alive.return_value = True
        self.panel = self.app.dashboard_view
        self.panel.year.set('2026')
        self.panel.month.set('Październik')
        self.root.update_idletasks()

    def request(self, scope='dashboard'):
        self.assertTrue(self.app.request_refresh(scope))
        return self.panel.active_request

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
        self.app.observe_main_window()
        self.app.main_window.uncover.assert_called_once()

    def execute(self, during=None, failure=None, drain=True):
        def sla(*args):
            if during:
                during()
            if failure:
                raise failure
            return dict.fromkeys(TITLES, 10)
        with patch('neto_incident_monitor.analytics_config.load_config', return_value={}), \
                patch('neto_incident_monitor.dashboard_api.read_month', side_effect=sla), \
                patch('neto_incident_monitor.dashboard_api.read_held', return_value=dict.fromkeys(HELD_TITLES, 20)), \
                patch('neto_incident_monitor.dashboard_api.read_requests', return_value=dict.fromkeys(REQUEST_TITLES, 30)):
            self.app.read_dashboard_request(Mock())
        if drain:
            self.app.drain()

    def test_final_result_waiting_in_ui_queue_keeps_period_frozen(self):
        request = self.request()
        self.execute(drain=False)
        self.assert_controls('disabled')
        self.panel.year.set('2028')
        self.assertEqual(self.panel.active_request, request)
        self.assertEqual(self.panel.year.get(), '2026')
        self.app.drain()
        self.assertEqual(self.panel.values[TITLES[0]].get(), '10')
        self.assert_controls('readonly')

    def test_reauthentication_and_retry_keep_controls_locked(self):
        request = self.request()
        self.app.monitor_settings = {'urls':['https://adeo.service-now.com/incident_list.do']}
        def restore(*_):
            self.assert_controls('disabled')
            self.panel.month.set('Listopad')
            self.assertEqual(self.panel.active_request, request)
            return True
        self.app.restore_login = Mock(side_effect=restore)
        with patch('neto_incident_monitor.analytics_config.load_config', return_value={}), \
                patch('neto_incident_monitor.dashboard_api.read_month', side_effect=[AuthenticationRequired(),dict.fromkeys(TITLES,10)]), \
                patch('neto_incident_monitor.dashboard_api.read_held', return_value=dict.fromkeys(HELD_TITLES,20)), \
                patch('neto_incident_monitor.dashboard_api.read_requests', return_value=dict.fromkeys(REQUEST_TITLES,30)):
            self.app.read_dashboard_request(Mock())
        self.app.restore_login.assert_called_once()
        self.app.drain()
        self.assert_controls('readonly')
        self.assertEqual(self.panel.values[TITLES[0]].get(), '10')

    def test_queued_request_freezes_both_controls_and_rejects_all_selection_paths(self):
        request = self.request()
        self.assert_controls('disabled')
        for control in self.panel.period_controls:
            control.current(1)  # Tcl/programmatic changes bypass disabled widgets.
            for event in ('<Button-1>', '<Key-Down>', '<MouseWheel>', '<<ComboboxSelected>>'):
                control.event_generate(event)
        self.panel.month.set('Grudzień')
        self.panel.year.set('2027')
        self.assertEqual(self.panel.active_request, request)
        self.assertEqual((self.panel.year.get(), self.panel.month.get()), ('2026', 'Październik'))
        self.assertEqual(self.panel.request_id, request[0])
        self.assertEqual(self.app.dashboard_requests.qsize(), 1)

    def test_actual_worker_results_and_cache_survive_selection_attempt(self):
        request = self.request()
        self.execute(lambda: self.panel.month.set('Listopad'))
        self.assertEqual(self.panel.values[TITLES[0]].get(), '10')
        self.assertEqual(self.panel.values[HELD_TITLES[0]].get(), '20')
        self.assertEqual(self.panel.values[REQUEST_TITLES[0]].get(), '30')
        self.assertEqual(self.panel.section_states['Dashboard SLA'], 'Zaktualizowany')
        self.assertEqual(load_snapshot(Path(self.temp.name)/'dashboard-cache.json')['sections']['sla']['month'], 10)
        self.assertIsNone(self.panel.active_request)
        self.assert_controls('readonly')
        self.assertEqual(self.panel.request_id, request[0])

    def test_controls_unlock_on_partial_failure_and_cancel(self):
        for failure in (ValueError('synthetic'), Cancelled()):
            with self.subTest(failure=type(failure).__name__):
                self.app.refresh_coordinator().finish()
                self.request()
                self.execute(failure=failure)
                self.assertIsNone(self.panel.active_request)
                self.assert_controls('readonly')

    def test_browser_restart_keeps_same_request_locked_until_real_completion(self):
        request = self.request()
        with self.assertRaises(BrowserClosedError):
            self.execute(failure=BrowserClosedError('closed'))
        self.app.drain()
        self.assertEqual(self.panel.active_request, request)
        self.assert_controls('disabled')
        self.assertEqual(self.app.dashboard_requests.qsize(), 1)
        self.execute()
        self.assert_controls('readonly')

    def test_old_finish_and_wrong_period_do_not_release_new_transaction(self):
        old = self.request()
        self.finish(old)
        self.app.refresh_coordinator().finish()
        current = self.request()
        for event in ((*old, 'finished'), (current[0], 2027, 10, 'finished')):
            self.finish(event[:3], event[3])
            self.assertEqual(self.panel.active_request, current)
            self.assert_controls('disabled')
        self.finish(current)
        self.assert_controls('readonly')

    def test_wrong_period_with_current_id_cannot_write_values_or_cache(self):
        request = self.request()
        metadata = {'section': 'sla', 'values': dict.fromkeys(TITLES, 9),
                    'read_at': '2026-10-01T12:00:00+02:00', 'diagnostics': Mock()}
        self.panel.apply_result((request[0], 2027, 10, {}, None, '', metadata))
        self.assertEqual(self.panel.section_snapshots, {})
        self.assertFalse((Path(self.temp.name)/'dashboard-cache.json').exists())
        self.finish(request)

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
        self.app.refresh_coordinator().finish()
        request = self.request()
        self.assertEqual(request[1:], (2026, 11))

    def test_stop_invalidates_old_events_and_new_request_remains_locked(self):
        old = self.request()
        self.app.stop.set()
        self.app.events.put(('finished', None))
        self.app.drain()
        self.assert_controls('readonly')
        self.app.stop.clear()
        self.app.refresh_coordinator().finish()
        current = self.request()
        self.finish(old)
        self.assertEqual(self.panel.active_request, current)
        self.assert_controls('disabled')

    def test_all_request_locks_before_threatened_read_and_other_scope_does_not(self):
        self.request('threatened')
        self.assert_controls('readonly')
        self.app.refresh_coordinator().finish()
        self.request('all')
        self.assert_controls('disabled')
        self.app.show_threatened_view()
        self.app.show_dashboard_view()
        self.assert_controls('disabled')

    def test_queue_failure_restores_controls_and_releases_coordinator(self):
        with patch.object(self.app.dashboard_requests, 'put', side_effect=RuntimeError('SYNTHETIC_SECRET')):
            self.assertFalse(self.app.request_refresh('all'))
        self.assertIsNone(self.panel.active_request)
        self.assertFalse(self.app.refresh_coordinator().busy)
        self.assert_controls('readonly')
        self.assertNotIn('SYNTHETIC_SECRET', self.panel.message.get())

    def test_startup_request_locks_before_worker_and_failed_thread_releases_it(self):
        self.app.dashboard_auto_refresh.set(True)
        self.app.worker = None
        self.app.filters = [{'name':'Synthetic','url':'https://adeo.service-now.com/incident_list.do','enabled':True}]
        self.app.interval.set('60')
        self.app.task_interval.set('60')
        with patch('neto_incident_monitor.app.save_json'), \
                patch('neto_incident_monitor.app.read_json', return_value={}), \
                patch('neto_incident_monitor.app.messagebox.showerror') as error, \
                patch.object(self.app.alert_writer, 'submit'), \
                patch('neto_incident_monitor.app.threading.Thread') as thread:
            def fail_start():
                self.assertIsNotNone(self.panel.active_request)
                self.assert_controls('disabled')
                raise RuntimeError('SYNTHETIC_SECRET')
            thread.return_value.start.side_effect = fail_start
            self.app.start()
            thread.return_value.start.assert_called_once()
            error.assert_not_called()
        self.assertTrue(self.app.stop.is_set())
        self.assertIsNone(self.panel.active_request)
        self.assert_controls('readonly')
        self.assertFalse(self.app.refresh_coordinator().busy)

    def test_duplicate_result_after_finish_cannot_overwrite_accepted_snapshot(self):
        request = self.request()
        self.execute()
        old = dict(self.panel.section_snapshots['sla'])
        self.panel.apply_result((*request, {}, None, '',
            {'section':'sla','values':dict.fromkeys(TITLES,99),'read_at':'2026-10-02T12:00:00+02:00','diagnostics':Mock()}))
        self.assertEqual(self.panel.section_snapshots['sla'], old)

    def test_diagnostic_failure_cannot_keep_period_locked_or_discard_good_result(self):
        with patch('neto_incident_monitor.login_diagnostics.LoginDiagnostics', side_effect=OSError('SYNTHETIC_SECRET')):
            request = self.request()
            self.panel.month.set('Listopad')
            self.finish(request)
        self.assert_controls('readonly')

    def test_lifecycle_diagnostics_are_allowlisted_correlated_and_safe(self):
        with self.assertLogs(_logger, level='INFO') as captured:
            request = self.request()
            self.panel.year.set('2027')
            self.finish((request[0]-1, 2026, 10))
            self.panel.apply_result((request[0], 2027, 10, {}, None))
            self.finish(request)
        rows = [json.loads(record.getMessage()) for record in captured.records]
        relevant = [r for r in rows if r['event'] in {'dashboard_period_state', 'dashboard_request_state', 'dashboard_result_rejected'}]
        self.assertTrue(all('run_id' in r and 'request_id' in r and 'request_state' in r for r in relevant))
        self.assertTrue({'locked','blocked','queued','unlocked','period_mismatch','stale_id'} <= {r['request_state'] for r in relevant})
        self.assertEqual(safe_facts({'request_state':'SYNTHETIC_SECRET','year':2026,'url':'SYNTHETIC_SECRET'}), {'year':2026})
