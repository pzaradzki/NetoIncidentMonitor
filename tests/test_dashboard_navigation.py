import threading
import unittest
from unittest.mock import Mock, patch
from playwright.sync_api import sync_playwright, TimeoutError
from neto_incident_monitor.dashboard import DASHBOARD_URL, TAB_IDS, same_dashboard, open_dashboard_tab, read_requests_dashboard, REQUEST_TITLES
from neto_incident_monitor.section_runner import run_section
from neto_incident_monitor.login_diagnostics import LoginDiagnostics
from neto_incident_monitor.pagination import AuthenticationRequired, Cancelled
from tests.dashboard_fixture import workspace


class DashboardNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = sync_playwright().start()
        cls.browser = cls.p.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.p.stop()

    def setUp(self):
        self.page = self.browser.new_page()
        self.addCleanup(self.page.close)
        self.documents = []
        def serve(route):
            if route.request.resource_type == 'document':
                self.documents.append(True)
            route.fulfill(body=workspace(), content_type='text/html; charset=utf-8')
        self.page.route('**/*', serve)
        self.stop = threading.Event()

    def test_reuses_same_dashboard_without_reloading(self):
        self.page.goto(DASHBOARD_URL)
        open_dashboard_tab(self.page, 'Wstrzymane L1', self.stop)
        self.assertEqual(len(self.documents), 1)
        self.assertEqual(self.page.get_by_role('tab', name='Wstrzymane L1').get_attribute('aria-selected'), 'true')

    def test_already_selected_tab_does_not_click_again(self):
        self.page.goto(DASHBOARD_URL.replace('ba36dad72b6a8b504b98f4c2c891bf73', TAB_IDS['Wnioski L1']))
        with patch('neto_incident_monitor.dashboard.click_control') as click:
            open_dashboard_tab(self.page, 'Wnioski L1', self.stop)
        click.assert_not_called()
        self.assertEqual(len(self.documents), 1)

    def test_other_dashboard_requires_one_full_navigation(self):
        self.page.goto(DASHBOARD_URL.replace('22361ad72b6a8b504b98f4c2c891bfab', 'different'))
        open_dashboard_tab(self.page, 'Wnioski L1', self.stop)
        self.assertEqual(len(self.documents), 2)
        self.assertIn(TAB_IDS['Wnioski L1'], self.page.url)

    def test_single_retry_owner_resets_document_after_uncertain_click(self):
        self.page.goto(DASHBOARD_URL)
        with patch('neto_incident_monitor.dashboard.click_control', side_effect=TimeoutError('uncertain')) as click:
            # The retry navigates directly to the requested tab and does not
            # repeat the uncertain tab click against the original document.
            run_section(self.page, self.stop, lambda: open_dashboard_tab(self.page, 'Wstrzymane L1', self.stop),
                        LoginDiagnostics(), Mock(), Mock(), lambda value: True)
        self.assertEqual(click.call_count, 1)
        self.assertEqual(len(self.documents), 2)

    def test_repeated_navigation_failure_has_only_two_attempts(self):
        reader = Mock(side_effect=TimeoutError('navigation'))
        with self.assertRaises(TimeoutError):
            run_section(self.page, self.stop, reader, LoginDiagnostics(), Mock(), Mock(), lambda v: True)
        self.assertEqual(reader.call_count, 2)

    def test_expired_session_is_not_overwritten_by_navigation(self):
        self.page.goto('https://idpb2e.adeo.com/login')
        with self.assertRaises(AuthenticationRequired):
            open_dashboard_tab(self.page, 'Wnioski L1', self.stop)
        self.assertEqual(len(self.documents), 1)

    def test_cancellation_does_not_trigger_navigation(self):
        self.stop.set()
        with self.assertRaises(Cancelled):
            open_dashboard_tab(self.page, 'Wnioski L1', self.stop)
        self.assertEqual(self.documents, [])

    def test_wrong_host_is_not_treated_as_loaded_dashboard(self):
        self.page.goto(DASHBOARD_URL.replace('adeo.service-now.com', 'other.example'))
        self.assertFalse(same_dashboard(self.page))

    def test_tabs_and_explicit_refresh_do_not_require_document_reloads(self):
        self.page.goto(DASHBOARD_URL)
        open_dashboard_tab(self.page, 'Wstrzymane L1', self.stop)
        open_dashboard_tab(self.page, 'Wnioski L1', self.stop)
        self.assertEqual(read_requests_dashboard(self.page, self.stop), dict(zip(REQUEST_TITLES, range(4))))
        self.assertEqual(len(self.documents), 1)

    def test_unrelated_loader_does_not_block_current_scores(self):
        self.page.goto(DASHBOARD_URL)
        self.assertEqual(read_requests_dashboard(self.page, self.stop), dict(zip(REQUEST_TITLES, range(4))))
        self.assertEqual(len(self.documents), 1)
