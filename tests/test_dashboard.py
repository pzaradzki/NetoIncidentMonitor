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
        from playwright.sync_api import sync_playwright
        from tests.dashboard_fixture import workspace
        from neto_incident_monitor.dashboard import read_requests_dashboard, REQUEST_TITLES
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.route('**/*', lambda r: r.fulfill(body=workspace(delay=1200), content_type='text/html; charset=utf-8'))
                self.assertEqual(read_requests_dashboard(page, threading.Event()), dict(zip(REQUEST_TITLES, range(len(REQUEST_TITLES)))))
            finally:
                browser.close()

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
        from playwright.sync_api import sync_playwright
        from tests.dashboard_fixture import workspace
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                html = workspace().replace('type="checkbox" checked', 'type="checkbox"')
                page.route('**/*', lambda r: r.fulfill(body=html, content_type='text/html; charset=utf-8'))
                self.assertEqual(read_held_dashboard(page, threading.Event()), dict(zip(HELD_TITLES, range(2))))
                self.assertEqual(page.evaluate('window.applied'), 1)
            finally:
                browser.close()

    def test_wjruw_matches_original_script(self):
        values = {f'Zgłoszenia P{p}': n for p, n in enumerate((0, 44, 209, 387, 295), 1)}
        values.update({f'Przekroczone P{p}': n for p, n in enumerate((0, 0, 7, 4, 0), 1)})
        self.assertEqual(f'{calculate_wjruw(values):.2f}', '98.32')
        self.assertIsNone(calculate_wjruw({}))
        self.assertIsNone(calculate_wjruw({title: 0 for title in TITLES}))
        values['Przekroczone P3'] = values['Przekroczone P4'] = 0
        self.assertEqual(calculate_wjruw(values), 100)

    def test_categories_commit_each_selection_but_check_only_incomplete(self):
        page = MagicMock()
        containers = [MagicMock() for _ in range(3)]
        page.locator.return_value.filter.side_effect = containers
        # The middle category is already selected, so do not check it again.
        for index, container in enumerate(containers):
            container.filter.return_value = container
            checkbox = container.get_by_role.return_value
            # Both observations now require checked AND not indeterminate.
            checkbox.evaluate.side_effect = [index == 1, True]
        # This unit test covers category actions, not a browser document/session.
        with patch('neto_incident_monitor.dashboard.expect'), \
                patch('neto_incident_monitor.dashboard.authentication_required', return_value=False):
            ensure_all_categories(page, threading.Event())
        containers[0].get_by_role.return_value.check.assert_called_once()
        self.assertEqual(sum(not call.kwargs.get('trial', False)
                             for call in containers[0].get_by_role.return_value.click.call_args_list), 1)
        containers[1].get_by_role.return_value.check.assert_not_called()
        self.assertEqual(sum(not call.kwargs.get('trial', False) for call in containers[1].get_by_role.return_value.click.call_args_list), 1)
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
        from playwright.sync_api import sync_playwright
        from tests.dashboard_fixture import workspace
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                html = workspace().replace('main.appendChild(c);});', 'main.insertBefore(c,main.firstChild);});')
                page.route('**/*', lambda r: r.fulfill(body=html, content_type='text/html; charset=utf-8'))
                self.assertEqual(read_dashboard(page, 2026, 9, threading.Event()), dict(zip(TITLES, range(11))))
            finally:
                browser.close()

    def test_stop_does_not_return_zeros(self):
        page = MagicMock()
        stop = threading.Event()
        stop.set()
        with self.assertRaises(Cancelled):
            read_dashboard(page, 2026, 9, stop)
