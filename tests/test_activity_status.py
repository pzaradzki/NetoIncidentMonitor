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
        request = app.dashboard_view.request_id
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
        request = app.dashboard_view.request_id
        self.emit(('dashboard_section_status', (request, 'Wnioski L1', 'Błąd odczytu')), ('dashboard_updating', False))
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
