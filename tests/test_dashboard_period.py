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

    def start_clocked_cycle(self):
        self.clock = 100
        self.enterContext(patch('neto_incident_monitor.shared_session.monotonic', side_effect=lambda: self.clock))
        self.app.start()
        cycle = self.session.cycle
        cycle.deadlines.update(inc=10_000, task=10_000)
        return cycle

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
                self.app.drain()
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
        self.wait_for_cache()
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
                    self.assertNotIn('threatened', self.session.cycle.last_finished)
                    self.assertIsNone(self.app.history.membership)

    def test_periodic_dashboard_uses_current_period_and_reschedules_partial_attempt(self):
        cycle = self.start_clocked_cycle()
        with self.assertLogs(_logger, level='INFO') as output:
            def first(*_args):
                self.clock += 10
                return dict.fromkeys(TITLES, 10)

            self.assertEqual(self.execute(first)[1:], (2026, 10))
            self.assertEqual(cycle.deadlines['dashboard'], 170)
            self.assert_controls('readonly')
            self.panel.month.set('Listopad')
            self.clock = 169
            unexpected = Mock()
            self.assertIsNone(self.execute(unexpected))
            unexpected.assert_not_called()
            self.assertEqual(self.panel.last_complete_period, (2026, 10))

            self.clock = 200
            def partial(*_args):
                self.clock += 180
                self.session.update_intervals({'inc': 60, 'task': 60, 'dashboard': 90, 'threatened': 60})
                raise ValueError('synthetic partial result')

            self.assertEqual(self.execute(partial)[1:], (2026, 11))
            self.assertEqual(cycle.deadlines['dashboard'], 470)
            self.assertEqual(self.panel.last_complete_period, (2026, 10))
            self.assert_controls('readonly')

        events = [json.loads(record.getMessage()) for record in output.records]
        schedule = [event for event in events if event['event'] == 'dashboard_schedule']
        self.assertEqual([event['outcome'] for event in schedule], ['started', 'returned', 'started', 'partial'])
        self.assertEqual(schedule[-1]['lateness_ms'], 30_000)
        self.assertEqual(schedule[-1]['delay_reason'], 'threatened')
        self.assertTrue(all(event['schedule_trigger'] == 'periodic' and event['run_id'] for event in schedule))
        self.assertEqual(schedule[-2]['read_id'], schedule[-1]['read_id'])
        sections = [event for event in events if event.get('section') == 'sla']
        self.assertTrue(any(event['read_id'] == schedule[-1]['read_id'] for event in sections))

    def test_manual_and_full_dashboard_set_deadline_from_dashboard_completion(self):
        cycle = self.start_clocked_cycle()
        self.execute()
        self.clock = 120
        self.request()
        self.execute(Mock(side_effect=ValueError('synthetic refusal')))
        self.assertEqual(cycle.deadlines['dashboard'], 180)

        self.clock = 150
        self.request('all')

        def read_filter(*_args, **_kwargs):
            self.clock += 15
            return 'success'

        with patch.object(self.session, 'update_layout_account'), patch.object(self.app, 'read_filter', read_filter):
            self.execute()
        self.assertEqual(self.clock, 165)
        self.assertEqual(cycle.deadlines['dashboard'], 210)
        self.assert_controls('readonly')

    def test_periodic_success_satisfies_only_matching_queued_dashboard(self):
        cycle = self.start_clocked_cycle()
        periods = []

        def sla(_page, _stop, _diagnostics, _config, year, month, _completed):
            periods.append((year, month))
            if len(periods) == 1:
                self.request('all')
                self.session.submit('dashboard', [ReadPart('dashboard', (2026, 11))])
            return dict.fromkeys(TITLES, 10)

        with patch.object(self.session, 'update_layout_account'), patch.object(self.app, 'read_filter', return_value='success'):
            self.execute(sla)
        self.assertEqual(periods, [(2026, 10), (2026, 11)])
        self.assertFalse(self.session.work.pending_refreshes()[1])
        self.assertEqual(cycle.deadlines['dashboard'], 160)

    def test_stop_during_periodic_attempt_preserves_matching_manual_request(self):
        cycle = self.start_clocked_cycle()
        attempts = []

        def sla(_page, stop, *_args):
            attempts.append(stop)
            if len(attempts) == 1:
                self.request()
                self.app.stop_monitoring()
                self.assertTrue(stop.is_set())
            return dict.fromkeys(TITLES, 10)

        self.execute(sla)
        self.assertEqual(len(attempts), 2)
        self.assertFalse(attempts[1].is_set())
        self.assertNotIn('dashboard', cycle.last_finished)
        self.assertEqual(self.panel.last_complete_period, (2026, 10))
        self.assert_controls('readonly')

    def test_periodic_reconnect_preserves_request_before_later_work(self):
        cycle = self.start_clocked_cycle()
        with self.assertRaises(BrowserClosedError):
            self.execute(Mock(side_effect=BrowserClosedError('synthetic close')))
        self.app.drain()
        request = self.panel.active_request
        self.assertIsNotNone(request)
        self.assert_controls('disabled')
        self.clock = 131
        self.assertEqual(self.execute(), request)
        self.assertEqual(cycle.deadlines['dashboard'], 191)
        self.assertIsNone(cycle.dashboard_part)
        self.assert_controls('readonly')

    def test_start_during_manual_dashboard_uses_its_completion_for_first_deadline(self):
        self.clock = 100
        with patch('neto_incident_monitor.shared_session.monotonic', side_effect=lambda: self.clock):
            self.request()

            def sla(*_args):
                self.app.start()
                self.session.cycle.deadlines.update(inc=10_000, task=10_000)
                self.clock = 110
                return dict.fromkeys(TITLES, 10)

            read = Mock(side_effect=sla)
            self.execute(read)
        read.assert_called_once()
        self.assertEqual(self.session.cycle.deadlines['dashboard'], 170)

    def test_stopped_dashboard_completion_does_not_set_deadline_of_restarted_cycle(self):
        cancelled_cycle = self.start_clocked_cycle()
        attempts = []

        def sla(_page, _stop, diagnostics, *_args):
            attempts.append(diagnostics.context['request_id'])
            if len(attempts) == 1:
                self.app.stop_monitoring()
                self.clock = 115
                self.app.start()
                self.session.cycle.deadlines.update(inc=10_000, task=10_000)
                return dict.fromkeys(TITLES, 99)
            return dict.fromkeys(TITLES, 10)

        self.execute(sla)
        self.assertEqual(len(set(attempts)), 2)
        self.assertNotIn('dashboard', cancelled_cycle.last_finished)
        self.assertEqual(self.session.cycle.deadlines['dashboard'], 175)
        self.assertEqual(self.panel.values[TITLES[0]].get(), '10')

    def test_stop_after_browser_close_releases_interrupted_automatic_dashboard(self):
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
