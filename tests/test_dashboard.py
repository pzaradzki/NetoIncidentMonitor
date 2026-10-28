import threading
import queue
import unittest
from unittest.mock import MagicMock, patch

from neto_incident_monitor.dashboard import TITLES, month_range, parse_score, read_dashboard, score_pattern, ensure_all_categories
from neto_incident_monitor.dashboard import calculate_wjruw
from neto_incident_monitor.dashboard import read_held_dashboard, HELD_TITLES
from neto_incident_monitor.dashboard import DASHBOARD_URL
from neto_incident_monitor.pagination import Cancelled


class DashboardTests(unittest.TestCase):
    def test_requests_reads_four_tiles_in_source_order(self):
        from neto_incident_monitor.dashboard import read_requests_dashboard, REQUEST_TITLES
        page = MagicMock(url=DASHBOARD_URL)
        page.get_by_text.return_value.count.return_value = 0
        page.get_by_text.return_value.filter.return_value.count.return_value = 0
        expected = dict(zip(REQUEST_TITLES, (202, 118, 99, 17)))
        page.locator.return_value.filter.return_value.filter.return_value.count.return_value = 0
        def role(role, name=None, **kwargs):
            locator = MagicMock()
            locator.filter.return_value = locator
            locator.count.return_value = 1
            if hasattr(name, 'pattern'):
                for title, value in expected.items():
                    if name.match(title + ','):
                        locator.inner_text.return_value = str(value)
            return locator
        page.get_by_role.side_effect = role
        # A complete snapshot arriving after the former 20-second limit is valid.
        with patch('neto_incident_monitor.dashboard.time.monotonic', side_effect=[0, 0, 0, 25, 25]), \
                patch('neto_incident_monitor.dashboard.navigate_page') as navigate, \
                patch('neto_incident_monitor.dashboard.ensure_all_categories') as ensure:
            self.assertEqual(read_requests_dashboard(page, threading.Event()), expected)
        self.assertEqual(ensure.call_args.args[2], ('Agent L1',))
        navigate.assert_not_called()
        page.go_back.assert_not_called()

    def test_refresh_reads_only_values_and_preserves_sla_on_held_error(self):
        from neto_incident_monitor.app import App
        for fail in (False, True):
            app = App.__new__(App)
            app.stop = threading.Event()
            app.events = queue.Queue()
            app.dashboard_requests = queue.Queue()
            app.dashboard_requests.put((1, 2026, 10))
            page = MagicMock()
            with patch('neto_incident_monitor.dashboard.read_dashboard', return_value={t: 0 for t in TITLES}) as sla, patch(
                    'neto_incident_monitor.dashboard.read_held_dashboard',
                    side_effect=ValueError('missing') if fail else None,
                    return_value=dict(zip(HELD_TITLES, (19, 43)))) as held, patch(
                    'neto_incident_monitor.dashboard.read_requests_dashboard', return_value={}):
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

    def test_held_reads_both_tiles_with_all_agents(self):
        page = MagicMock(url=DASHBOARD_URL)
        page.get_by_text.return_value.count.return_value = 0
        page.get_by_text.return_value.filter.return_value.count.return_value = 0
        def role(role, name=None, **kwargs):
            locator = MagicMock()
            if hasattr(name, 'pattern'):
                locator.inner_text.return_value = '19' if name.match('Wstrzymane L1 >14 dni, 19,') else '43'
            return locator
        page.get_by_role.side_effect = role
        with patch('neto_incident_monitor.dashboard.ensure_all_categories') as ensure, patch(
                'neto_incident_monitor.dashboard.time.monotonic', side_effect=[0, 0, 0, 2, 2]), \
                patch('neto_incident_monitor.dashboard.navigate_page') as navigate:
            values = read_held_dashboard(page, threading.Event())
        navigate.assert_not_called()
        self.assertEqual(values, dict(zip(HELD_TITLES, (19, 43))))
        self.assertEqual(ensure.call_args.args[2], ('Agent L1',))

    def test_wjruw_matches_original_script(self):
        values = {f'Zgłoszenia P{p}': n for p, n in enumerate((0, 44, 209, 387, 295), 1)}
        values.update({f'Przekroczone P{p}': n for p, n in enumerate((0, 0, 7, 4, 0), 1)})
        self.assertEqual(f'{calculate_wjruw(values):.2f}', '98.32')
        self.assertIsNone(calculate_wjruw({}))
        self.assertIsNone(calculate_wjruw({title: 0 for title in TITLES}))
        values['Przekroczone P3'] = values['Przekroczone P4'] = 0
        self.assertEqual(calculate_wjruw(values), 100)

    def test_categories_apply_only_incomplete_selection(self):
        page = MagicMock()
        containers = [MagicMock() for _ in range(3)]
        page.locator.return_value.filter.side_effect = containers
        # The middle category is already selected and must not be applied again.
        for index, container in enumerate(containers):
            container.filter.return_value = container
            checkbox = container.get_by_role.return_value
            checkbox.evaluate.side_effect = [index == 1, False] if index != 1 else [True]
        with patch('neto_incident_monitor.dashboard.expect'):
            ensure_all_categories(page, threading.Event())
        containers[0].get_by_role.return_value.check.assert_called_once()
        self.assertEqual(sum(not call.kwargs.get('trial', False)
                             for call in containers[0].get_by_role.return_value.click.call_args_list), 1)
        containers[1].get_by_role.return_value.check.assert_not_called()
        containers[1].get_by_role.return_value.click.assert_not_called()
        containers[2].get_by_role.return_value.check.assert_called_once()
        self.assertEqual(sum(not call.kwargs.get('trial', False)
                             for call in containers[2].get_by_role.return_value.click.call_args_list), 1)

    def test_servicenow_widget_title_whitespace(self):
        pattern = score_pattern('Przekroczone P1')
        self.assertIsNotNone(pattern.match('Przekroczone P1 , 0, '))
        self.assertIsNotNone(pattern.match('Przekroczone\u00a0P1  , 0, '))
        self.assertIsNone(pattern.match('Przekroczone P2, 0, '))

    def test_calendar_boundaries(self):
        self.assertEqual(month_range(2024, 2), ('2024-02-01', '2024-02-29'))
        self.assertEqual(month_range(2026, 2), ('2026-02-01', '2026-02-28'))
        self.assertEqual(month_range(2026, 12), ('2026-12-01', '2026-12-31'))
        with self.assertRaises(ValueError):
            month_range(2026, 13)

    def test_exact_scores_only(self):
        self.assertEqual(parse_score('1\u00a0234\u202f567 '), 1234567)
        for value in ('Brak danych', '1,2 tys.', '—', ''):
            with self.assertRaises(ValueError):
                parse_score(value)

    def test_reads_by_title_not_widget_position(self):
        page = MagicMock()
        values = {title: str(i) for i, title in enumerate(TITLES)}
        def role(role, name=None, **kwargs):
            locator = MagicMock()
            if hasattr(name, 'pattern'):
                for title, value in values.items():
                    if name.match(title + (' ' if title == 'Przekroczone P1' else '') + ', wartość'):
                        locator.inner_text.return_value = value
            return locator
        page.get_by_role.side_effect = role
        page.get_by_text.return_value.count.return_value = 0
        page.get_by_text.return_value.filter.return_value.count.return_value = 0
        with patch('neto_incident_monitor.dashboard.time.monotonic', side_effect=[0, 0, 0, 2, 2]):
            result = read_dashboard(page, 2026, 9, threading.Event())
        self.assertEqual(result['Zgłoszenia P1'], 1)
        self.assertEqual(result['Przekroczone P1'], 6)
        page.get_by_role.assert_any_call('textbox', name='Data rozpoczęcia', exact=True)

    def test_stop_does_not_return_zeros(self):
        page = MagicMock()
        stop = threading.Event()
        stop.set()
        with self.assertRaises(Cancelled):
            read_dashboard(page, 2026, 9, stop)
