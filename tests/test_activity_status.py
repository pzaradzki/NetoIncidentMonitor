import json
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from neto_incident_monitor.app import App


class ActivityStatusTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.addCleanup(self.root.destroy)
        settings = {'filters': [{'name': 'Testowy filtr', 'url': 'https://example.com/incident_list.do'}]}
        with patch('neto_incident_monitor.app.read_json', return_value=settings), \
                patch('neto_incident_monitor.dashboard_cache.load_snapshot', return_value=None):
            self.app = App(self.root, history_path=Path(self.folder.name) / 'history.json',
                           apply_startup=False, enable_tray=False)
        self.app.worker = Mock()
        self.app.worker.is_alive.return_value = True
        self.root.update_idletasks()

    def begin_dashboard(self):
        self.assertTrue(self.app.dashboard_view.request_refresh(automatic=True, coordinated=True))
        return self.app.dashboard_view.active_request

    def emit(self, *events):
        for event in events:
            self.app.events.put(event)
        self.app.drain()

    def test_real_events_switch_between_login_dashboard_filter_idle_and_stop(self):
        app = self.app
        app.set_phase('Uruchamianie przeglądarki')
        self.assertEqual(app.activity_pill.status_text, 'Uruchamianie przeglądarki')
        self.emit(('activity', ('Wymagane ręczne logowanie', 'waiting', 'login')))
        self.assertEqual(app.activity_pill.tone, 'waiting')
        request = self.begin_dashboard()[0]
        self.emit(('dashboard_section_status', (request, 'Wnioski L1', 'W trakcie aktualizacji')))
        self.assertEqual(app.activity_pill.status_text, 'Pobieranie danych: Wnioski L1')
        self.emit(('dashboard_section_status', (request - 1, 'Dashboard SLA', 'W trakcie aktualizacji')))
        self.assertEqual(app.activity_pill.status_text, 'Pobieranie danych: Wnioski L1')
        self.emit(('filter_updating', app.filters[0]['url']))
        self.assertEqual(app.activity_pill.status_text, 'Aktualizowanie filtra: Testowy filtr')
        self.emit(('activity', ('Wymagane ręczne logowanie', 'waiting', 'login')), ('filter_updating', None))
        self.assertEqual(app.activity_pill.status_text, 'Wymagane ręczne logowanie')
        self.emit(('waiting', (0, False)))
        self.assertEqual(app.activity_pill.status_text, 'Oczekiwanie na kolejne sprawdzenie')
        app.stop.set()
        self.emit(('finished', None))
        self.assertEqual(app.activity_pill.status_text, 'Monitoring zatrzymany')

    def test_error_is_not_overwritten_when_filter_or_dashboard_finishes(self):
        app = self.app
        self.emit(('filter_updating', app.filters[0]['url']), ('phase', 'Błąd odczytu'), ('filter_updating', None))
        self.assertEqual(app.activity_pill.tone, 'error')
        request = self.begin_dashboard()[0]
        self.emit(('dashboard_section_status', (request, 'Wnioski L1', 'Błąd odczytu')),
                  ('dashboard_updating', (request, 2026, 10, 'finished')))
        self.assertEqual(app.activity_pill.status_text, 'Błąd odczytu: Wnioski L1')

    def test_long_activity_fits_small_header_and_retains_full_tooltip(self):
        app = self.app
        self.root.geometry('1120x680')
        text = 'Aktualizowanie filtra: ' + 'Długi opis filtra ' * 12
        app.set_activity(text, 'working', 'filter')
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
                  ('dashboard_section_status', (request[0], 'Dashboard SLA', 'Oczekuje')),
                  ('activity', ('Wymagane ręczne logowanie', 'waiting', 'login')),
                  ('phase', 'Oczekiwanie'))
        before = (app.monitoring_phase, app.auth_waiting, str(app.check_button['state']))
        self.emit(('dashboard_section_status', (request[0], 'Dashboard SLA', 'Ponawianie odczytu')))
        self.assertEqual(app.activity_pill.status_text, 'Ponawianie odczytu: Dashboard SLA')
        self.assertEqual(app.activity_pill.tone, 'waiting')
        self.assertEqual(app.activity_pill.status_tooltip.text, app.activity_pill.status_text)
        self.assertEqual(app.dashboard_view.section_pills['Dashboard SLA'].status_text, 'Ponawianie odczytu')
        self.assertIn('Ponawianie odczytu: Dashboard SLA', app.dashboard_view.message.get())
        self.assertEqual(before, (app.monitoring_phase, app.auth_waiting, str(app.check_button['state'])))
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
                    self.assertEqual(app.activity_pill.status_text, description + ': ' + section)
                    self.assertEqual(app.activity_pill.tone, tone)
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
        before = (app.activity_pill.status_text, app.dashboard_view.message.get(), dict(app.dashboard_view.section_states))
        self.emit(('dashboard_section_status', (request[0]-1, 'Dashboard SLA', 'Błąd odczytu')))
        self.assertEqual(before, (app.activity_pill.status_text, app.dashboard_view.message.get(), app.dashboard_view.section_states))
        self.emit(('dashboard_updating', (*request, 'finished')))
        self.assertNotIn('Ponawianie', app.activity_pill.status_text)
        self.assertNotIn('Ponawianie', app.dashboard_view.message.get())
        before = (app.activity_pill.status_text, app.dashboard_view.message.get(), dict(app.dashboard_view.section_states))
        self.emit(('dashboard_section_status', (request[0], 'Dashboard SLA', 'Ponawianie odczytu')))
        self.assertEqual(before, (app.activity_pill.status_text, app.dashboard_view.message.get(), app.dashboard_view.section_states))

    def test_final_error_message_wins_over_late_retry_and_finish(self):
        app = self.app
        request = self.begin_dashboard()
        self.emit(('dashboard_section_status', (request[0], 'Dashboard SLA', 'Błąd odczytu')),
                  ('dashboard_result', (*request, None, True)))
        message = app.dashboard_view.message.get()
        self.emit(('dashboard_section_status', (request[0], 'Dashboard SLA', 'Ponawianie odczytu')),
                  ('dashboard_updating', (*request, 'finished')))
        self.assertEqual(app.activity_pill.status_text, 'Błąd odczytu: Dashboard SLA')
        self.assertEqual(app.dashboard_view.section_states['Dashboard SLA'], 'Błąd odczytu')
        self.assertEqual(app.dashboard_view.message.get(), message)

    def test_partial_failure_remains_error_after_later_section_activity(self):
        app = self.app
        request = self.begin_dashboard()
        self.emit(('dashboard_section_status', (request[0], 'Dashboard SLA', 'Błąd odczytu')),
                  ('dashboard_section_status', (request[0], 'Wnioski L1', 'W trakcie aktualizacji')),
                  ('dashboard_result', (*request, {}, None, 'Nie udało się odczytać: Dashboard SLA')),
                  ('dashboard_updating', (*request, 'finished')))
        self.assertEqual(app.activity_pill.tone, 'error')
        self.assertIn('Dashboard SLA', app.activity_pill.status_text)
        self.assertIn('Nie udało się odczytać', app.dashboard_view.message.get())

    def test_stop_clears_retry_and_ignores_late_events(self):
        app = self.app
        request = self.begin_dashboard()
        self.emit(('dashboard_section_status', (request[0], 'Dashboard SLA', 'Ponawianie odczytu')))
        app.stop.set()
        self.emit(('finished', None),
                  ('dashboard_section_status', (request[0], 'Dashboard SLA', 'Ponawianie odczytu')))
        self.assertEqual(app.activity_pill.status_text, 'Monitoring zatrzymany')
        self.assertIn('Monitoring zatrzymany', app.dashboard_view.message.get())
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
        with patch('neto_incident_monitor.analytics_config.load_config', return_value={}), \
                patch('neto_incident_monitor.dashboard_api.read_month', return_value=dict.fromkeys(TITLES, 0)), \
                patch('neto_incident_monitor.dashboard_api.read_held', return_value=dict.fromkeys(HELD_TITLES, 0)), \
                patch('neto_incident_monitor.dashboard_api.read_requests', return_value=dict.fromkeys(REQUEST_TITLES, 0)):
            app.read_dashboard_request(Mock())
        app.drain()
        panel = app.dashboard_view
        self.assertEqual(app.activity_pill.status_text, 'Aktualizacja dashboardu zakończona')
        self.assertEqual(app.activity_pill.tone, 'success')
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
                  ('phase', 'Ponowne uruchamianie przeglądarki'))
        self.assertEqual(app.dashboard_view.active_request, request)
        self.assertEqual(app.activity_pill.status_text, 'Ponowne uruchamianie przeglądarki')
        self.emit(('dashboard_section_status', (request[0], 'Dashboard SLA', 'Ponawianie odczytu')))
        self.assertEqual(app.activity_pill.status_text, 'Ponawianie odczytu: Dashboard SLA')
        self.assertIn('Ponawianie odczytu: Dashboard SLA', app.dashboard_view.message.get())
        self.assertEqual(app.dashboard_view.active_request, request)
        self.assertTrue(all(str(combo['state']) == 'disabled' for combo in app.dashboard_view.period_controls))
