import queue
import threading
import unittest
from unittest.mock import MagicMock, patch

from neto_incident_monitor.dashboard import HELD_TITLES, TITLES, calculate_wjruw, month_range


class DashboardTests(unittest.TestCase):
    def test_refresh_reads_only_values_and_preserves_sla_on_held_error(self):
        from neto_incident_monitor.app import App
        for fail in (False, True):
            app = App.__new__(App)
            app.stop = threading.Event()
            app.events = queue.Queue()
            app.dashboard_requests = queue.Queue()
            app.dashboard_requests.put((1, 2026, 10))
            page = MagicMock()
            with patch('neto_incident_monitor.analytics_config.load_config', return_value={}), \
                    patch('neto_incident_monitor.dashboard_api.read_month', return_value={t: 0 for t in TITLES}) as sla, patch(
                    'neto_incident_monitor.dashboard_api.read_held',
                    side_effect=ValueError('missing') if fail else None,
                    return_value=dict(zip(HELD_TITLES, (19, 43)))) as held, patch(
                    'neto_incident_monitor.dashboard_api.read_requests', return_value={}):
                app.read_dashboard_request(page)
            sla.assert_called_once()
            held.assert_called_once()
            page.get_by_role.assert_not_called()
            page.go_back.assert_not_called()
            results = [value for kind, value in app.events.queue if kind == 'dashboard_result']
            self.assertIn('Liczba zgłoszeń', results[-1][3])
            self.assertIsNone(results[-1][4])
            if fail:
                self.assertIn('Wstrzymane L1', results[-1][-1])
            else:
                self.assertEqual(results[-1][3][HELD_TITLES[0]], 19)

    def test_wjruw_matches_original_script(self):
        values = {f'Zgłoszenia P{p}': n for p, n in enumerate((0, 44, 209, 387, 295), 1)}
        values.update({f'Przekroczone P{p}': n for p, n in enumerate((0, 0, 7, 4, 0), 1)})
        self.assertEqual(f'{calculate_wjruw(values):.2f}', '98.32')
        self.assertIsNone(calculate_wjruw({}))
        self.assertIsNone(calculate_wjruw({title: 0 for title in TITLES}))
        values['Przekroczone P3'] = values['Przekroczone P4'] = 0
        self.assertEqual(calculate_wjruw(values), 100)

    def test_calendar_boundaries(self):
        self.assertEqual(month_range(2024, 2), ('2024-02-01', '2024-02-29'))
        self.assertEqual(month_range(2026, 2), ('2026-02-01', '2026-02-28'))
        self.assertEqual(month_range(2026, 12), ('2026-12-01', '2026-12-31'))
        with self.assertRaises(ValueError):
            month_range(2026, 13)
