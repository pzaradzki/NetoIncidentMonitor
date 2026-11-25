import json
import tempfile
import threading
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from neto_incident_monitor.app import App
from neto_incident_monitor.shared_session import StopSignal


class ActivityStatusTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.addCleanup(self.root.destroy)
        folder = Path(self.folder.name)
        config = folder / 'config.json'
        config.write_text(json.dumps({'filters': [
            {'name': 'Testowy filtr', 'url': 'https://adeo.service-now.com/incident_list.do'}
        ]}), encoding='utf-8')
        self.enterContext(patch('neto_incident_monitor.config_io.CONFIG', config))
        self.enterContext(patch('neto_incident_monitor.runtime_paths.DATA', folder))
        self.app = App(self.root, history_path=folder / 'history.json', apply_startup=False, enable_tray=False)
        self.addCleanup(self.app.teams_sender.stop)
        self.addCleanup(self.app.google_chat_sender.stop)
        self.addCleanup(self.app.alert_writer.shutdown)
        self.addCleanup(self.app.history_writer.shutdown)
        self.app.window_restoring = False
        self.app.session.ready_once = True
        self.app.session.log = Mock()
        self.app.handle_session_event('session_ready', None)
        self.root.update_idletasks()

    def begin_dashboard(self, *, automatic=False):
        app = self.app
        if automatic:
            app.start()
        else:
            self.assertTrue(app.request_refresh('dashboard'))
        cycle = app.session.cycle if automatic else None
        self.part, source = app.session.next_part(cycle)
        self.assertEqual(source, 'dashboard' if automatic else 'manual')
        self.token = object()
        stop = StopSignal(app.session.closed, cycle.stop) if cycle else app.session.closed
        preparation = {'part': self.part, 'stop': stop, 'done': threading.Event(), 'value': None}
        self.emit(('session_part_started', (self.token, self.part)), ('session_prepare_read', preparation))
        return preparation['value']

    def emit(self, *events):
        for event in events:
            self.app.events.put(event)
        self.app.drain()

    def finish(self, request):
        session = self.app.session
        session.work.complete_part(self.part, manual=True, success=True)
        session.finish_manual_job(None)
        self.emit(('dashboard_updating', (*request, 'finished')), ('session_part_finished', self.token))

    def test_stop_leaves_session_and_manual_work_available(self):
        app = self.app
        self.begin_dashboard(automatic=True)
        self.assertEqual(app.activity_pill.status_text, 'Monitoring aktywny')
        self.emit(('session_waiting', None), ('session_activity', ('Wymagane logowanie', 'waiting', True)))
        self.assertEqual(app.session_status.get(), 'Wymagane logowanie')
        self.assertIn('Oczekuje na logowanie', app.work_status.get())
        app.stop_monitoring()
        self.emit(('session_part_finished', self.token))
        self.assertEqual(app.activity_pill.status_text, 'Monitoring zatrzymany')
        self.assertEqual(app.session_status.get(), 'Wymagane logowanie')
        self.assertFalse(app.session.closed.is_set())
        self.assertTrue(app.request_refresh('dashboard'))

    def test_long_activity_fits_small_header_and_retains_full_tooltip(self):
        app = self.app
        self.root.geometry('1120x680')
        text = 'Aktualizowanie filtra: ' + 'Długi opis filtra ' * 12
        app.activity_pill.set_status(text, 'working')
        self.root.update()
        pill = app.activity_pill
        self.assertEqual(pill.status_text, text)
        self.assertEqual(pill.status_tooltip.text, text)
        self.assertLess(len(pill.display_text), len(text))
        self.assertLessEqual(pill.winfo_width(), pill.master.winfo_width())
        self.assertLessEqual(app.controls.winfo_x() + app.controls.winfo_width(), self.root.winfo_width())

    def test_retry_after_login_updates_both_pills_and_footer(self):
        app = self.app
        request = self.begin_dashboard()
        self.emit(('dashboard_section_status', (request[0], 'Dashboard SLA', 'W trakcie aktualizacji')),
                  ('session_waiting', None),
                  ('dashboard_section_status', (request[0], 'Dashboard SLA', 'Oczekuje')))
        self.assertIn('Oczekuje na logowanie', app.work_status.get())
        self.emit(('session_ready', None),
                  ('dashboard_section_status', (request[0], 'Dashboard SLA', 'Ponawianie odczytu')))
        self.assertEqual(app.work_status.get(), 'Ponawianie odczytu: Dashboard SLA')
        self.assertEqual(app.activity_pill.status_text, 'Monitoring zatrzymany')
        self.assertEqual(app.dashboard_view.section_pills['Dashboard SLA'].status_text, 'Ponawianie odczytu')
        self.assertIn('Ponawianie odczytu: Dashboard SLA', app.dashboard_view.message.get())
        self.assertEqual(app.dashboard_view.active_request, request)
        self.assertIsNone(app.dashboard_view.last_complete_read_at)

    def test_all_sections_share_status_mapping_without_changing_period_or_values(self):
        app = self.app
        request = self.begin_dashboard()
        panel = app.dashboard_view
        prefix = panel.message.get().split(' • ')[0]
        values = {key: value.get() for key, value in panel.values.items()}
        mapping = [('W trakcie aktualizacji', 'Pobieranie danych', 'working'),
                   ('Ponawianie odczytu', 'Ponawianie odczytu', 'waiting'),
                   ('Oczekuje', 'Oczekiwanie na logowanie', 'waiting'),
                   ('Błąd odczytu', 'Błąd odczytu', 'error')]
        for section in panel.section_pills:
            for state, description, tone in mapping:
                with self.subTest(section=section, state=state):
                    self.emit(('dashboard_section_status', (request[0], section, state)))
                    expected = 'Aktualizuje Dashboard SLA' if tone == 'error' else description + ': ' + section
                    self.assertEqual(app.work_status.get(), expected)
                    self.assertEqual(panel.section_states[section], state)
                    self.assertIn(description + ': ' + section, panel.message.get())
                    self.assertTrue(panel.message.get().startswith(prefix))
                    self.assertEqual(panel.last_read_text, '—')
                    self.assertEqual(panel.active_request, request)
                    self.assertEqual({key: value.get() for key, value in panel.values.items()}, values)
                    self.assertTrue(all(str(combo['state']) == 'disabled' for combo in panel.period_controls))

    def test_stale_and_finished_request_statuses_do_not_change_ui(self):
        app = self.app
        request = self.begin_dashboard()
        self.emit(('dashboard_section_status', (request[0], 'Dashboard SLA', 'Ponawianie odczytu')))
        before = (app.work_status.get(), app.dashboard_view.message.get(), dict(app.dashboard_view.section_states))
        self.emit(('dashboard_section_status', (request[0]-1, 'Dashboard SLA', 'Błąd odczytu')))
        self.assertEqual(before, (app.work_status.get(), app.dashboard_view.message.get(), app.dashboard_view.section_states))
        self.finish(request)
        self.assertNotIn('Ponawianie', app.work_status.get())
        self.assertNotIn('Ponawianie', app.dashboard_view.message.get())
        before = (app.work_status.get(), app.dashboard_view.message.get(), dict(app.dashboard_view.section_states))
        self.emit(('dashboard_section_status', (request[0], 'Dashboard SLA', 'Ponawianie odczytu')))
        self.assertEqual(before, (app.work_status.get(), app.dashboard_view.message.get(), app.dashboard_view.section_states))

    def test_final_error_message_wins_over_late_retry_and_finish(self):
        app = self.app
        request = self.begin_dashboard()
        self.emit(('dashboard_section_status', (request[0], 'Dashboard SLA', 'Błąd odczytu')),
                  ('dashboard_result', (*request, None, True)))
        message = app.dashboard_view.message.get()
        self.emit(('dashboard_section_status', (request[0], 'Dashboard SLA', 'Ponawianie odczytu')))
        self.finish(request)
        self.assertEqual(app.dashboard_view.section_states['Dashboard SLA'], 'Błąd odczytu')
        self.assertEqual(app.dashboard_view.message.get(), message)

    def test_partial_failure_remains_error_after_later_section_activity(self):
        app = self.app
        request = self.begin_dashboard()
        self.emit(('dashboard_section_status', (request[0], 'Dashboard SLA', 'Błąd odczytu')),
                  ('dashboard_section_status', (request[0], 'Wnioski L1', 'W trakcie aktualizacji')),
                  ('dashboard_result', (*request, {}, None, 'Nie udało się odczytać: Dashboard SLA')))
        self.finish(request)
        self.assertEqual(app.dashboard_view.section_states['Dashboard SLA'], 'Błąd odczytu')
        self.assertIn('Nie udało się odczytać', app.dashboard_view.message.get())

    def test_stop_clears_automatic_retry_and_ignores_late_events(self):
        app = self.app
        request = self.begin_dashboard(automatic=True)
        self.emit(('dashboard_section_status', (request[0], 'Dashboard SLA', 'Ponawianie odczytu')))
        app.stop_monitoring()
        self.emit(('session_part_finished', self.token),
                  ('dashboard_section_status', (request[0], 'Dashboard SLA', 'Ponawianie odczytu')))
        self.assertEqual(app.activity_pill.status_text, 'Monitoring zatrzymany')
        self.assertIn('Aktualizacja przerwana', app.dashboard_view.message.get())
        self.assertNotEqual(app.dashboard_view.section_states['Dashboard SLA'], 'Ponawianie odczytu')

    def test_ui_state_diagnostics_are_correlated_deduplicated_and_safe(self):
        app = self.app
        request = self.begin_dashboard()
        with self.assertLogs('neto.login_diagnostics', level='INFO') as logs:
            self.emit(('dashboard_section_status', (request[0], 'Dashboard SLA', 'Ponawianie odczytu')),
                      ('dashboard_section_status', (request[0], 'Dashboard SLA', 'Ponawianie odczytu')),
                      ('dashboard_section_status', (request[0], 'PRIVATE_SECRET', 'Błąd odczytu')))
        records = [json.loads(record.getMessage()) for record in logs.records]
        states = [r for r in records if r['event'] == 'dashboard_ui_state']
        self.assertEqual(len(states), 1)
        self.assertEqual(states[0]['request_id'], request[0])
        self.assertEqual(states[0]['section'], 'sla')
        self.assertEqual(states[0]['ui_state'], 'retrying')
        self.assertNotIn('PRIVATE_SECRET', json.dumps(records))

    def test_success_preserves_final_footer_timestamp_and_values(self):
        from neto_incident_monitor.dashboard import TITLES, HELD_TITLES, REQUEST_TITLES
        app = self.app
        request = self.begin_dashboard()
        self.emit(('dashboard_section_status', (request[0], 'Dashboard SLA', 'Ponawianie odczytu')))
        with patch('neto_incident_monitor.analytics_config.load_config', return_value={'assignees': ['a' * 32], 'locations': ['b' * 32]}), \
                patch('neto_incident_monitor.dashboard_api.read_month', return_value=dict.fromkeys(TITLES, 0)), \
                patch('neto_incident_monitor.dashboard_api.read_held', return_value=dict.fromkeys(HELD_TITLES, 0)), \
                patch('neto_incident_monitor.dashboard_api.read_requests', return_value=dict.fromkeys(REQUEST_TITLES, 0)):
            app.read_dashboard_request(Mock(), request=request, stop=app.session.closed)
        self.finish(request)
        panel = app.dashboard_view
        self.assertEqual(app.work_status.get(), '')
        self.assertEqual(panel.read_bar.fields[0].get(), 'Odczyt udany')
        self.assertIsNotNone(panel.last_complete_read_at)
        self.assertEqual(panel.message.get(),
                         f'Dane SLA za okres {panel.month.get().lower()} {request[1]} • '
                         f'Ostatnia aktualizacja: {panel.last_read_text} • Dane aktualne')
        self.assertEqual(panel.values[TITLES[0]].get(), '0')
        before = (panel.message.get(), panel.last_complete_read_at)
        self.emit(('dashboard_section_status', (request[0], 'Wnioski L1', 'Ponawianie odczytu')))
        self.assertEqual(before, (panel.message.get(), panel.last_complete_read_at))
        self.assertTrue(all(str(combo['state']) == 'readonly' for combo in panel.period_controls))

    def test_browser_restart_retains_request_and_resumed_status(self):
        app = self.app
        request = self.begin_dashboard()
        self.emit(('dashboard_section_status', (request[0], 'Dashboard SLA', 'Ponawianie odczytu')),
                  ('dashboard_updating', (*request, 'retrying')),
                  ('session_part_finished', self.token), ('session_problem', None))
        self.assertEqual(app.dashboard_view.active_request, request)
        self.assertEqual(app.session_status.get(), 'Brak połączenia')
        self.emit(('session_ready', None), ('session_part_started', (self.token, self.part)),
                  ('dashboard_section_status', (request[0], 'Dashboard SLA', 'Ponawianie odczytu')))
        self.assertEqual(app.work_status.get(), 'Ponawianie odczytu: Dashboard SLA')
        self.assertIn('Ponawianie odczytu: Dashboard SLA', app.dashboard_view.message.get())
        self.assertEqual(app.dashboard_view.active_request, request)
        self.assertTrue(all(str(combo['state']) == 'disabled' for combo in app.dashboard_view.period_controls))
