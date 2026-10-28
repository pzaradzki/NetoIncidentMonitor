import threading
import unittest
from unittest.mock import Mock, patch
from playwright.sync_api import sync_playwright, TimeoutError

from neto_incident_monitor.dashboard import DASHBOARD_URL, TAB_IDS, same_dashboard, open_dashboard_tab
from neto_incident_monitor.browser_actions import navigate_page
from neto_incident_monitor.pagination import AuthenticationRequired, Cancelled


class DashboardNavigationTests(unittest.TestCase):
    def page(self, url=DASHBOARD_URL):
        page = Mock(url=url, frames=[])
        page.get_by_role.return_value.get_attribute.return_value = None
        return page

    def test_reuses_same_dashboard_without_reloading(self):
        page = self.page()
        with patch('neto_incident_monitor.dashboard.navigate_page') as navigate, \
                patch('neto_incident_monitor.dashboard.click_control') as click:
            open_dashboard_tab(page, 'Wstrzymane L1', threading.Event())
        navigate.assert_not_called()
        click.assert_called_once()

    def test_already_selected_tab_does_not_click_again(self):
        page = self.page()
        page.get_by_role.return_value.get_attribute.return_value = 'true'
        with patch('neto_incident_monitor.dashboard.navigate_page') as navigate, \
                patch('neto_incident_monitor.dashboard.click_control') as click:
            open_dashboard_tab(page, 'Wnioski L1', threading.Event())
        navigate.assert_not_called()
        click.assert_not_called()

    def test_other_dashboard_or_list_requires_one_full_navigation(self):
        for url in (DASHBOARD_URL.replace('22361ad72b6a8b504b98f4c2c891bfab', 'different'),
                    'https://adeo.service-now.com/incident_list.do'):
            with self.subTest(url_kind='other'):
                page = self.page(url)
                with patch('neto_incident_monitor.dashboard.navigate_page') as navigate, \
                        patch('neto_incident_monitor.dashboard.click_control'):
                    open_dashboard_tab(page, 'Wnioski L1', threading.Event())
                navigate.assert_called_once()
                self.assertIn(TAB_IDS['Wnioski L1'], navigate.call_args.args[1])

    def test_reuse_timeout_falls_back_once_to_full_navigation(self):
        page = self.page()
        with patch('neto_incident_monitor.dashboard.navigate_page') as navigate, \
                patch('neto_incident_monitor.dashboard.click_control', side_effect=[TimeoutError('not ready'), None]) as click:
            open_dashboard_tab(page, 'Wstrzymane L1', threading.Event())
        navigate.assert_called_once()
        self.assertEqual(click.call_count, 2)

    def test_repeated_timeout_does_not_reload_forever(self):
        page = self.page()
        with patch('neto_incident_monitor.dashboard.navigate_page') as navigate, \
                patch('neto_incident_monitor.dashboard.click_control', side_effect=TimeoutError('not ready')):
            with self.assertRaises(TimeoutError):
                open_dashboard_tab(page, 'Wstrzymane L1', threading.Event())
        navigate.assert_called_once()

    def test_expired_session_is_not_overwritten_by_navigation(self):
        page = self.page('https://idpb2e.adeo.com/login')
        with patch('neto_incident_monitor.dashboard.navigate_page') as navigate:
            with self.assertRaises(AuthenticationRequired):
                open_dashboard_tab(page, 'Wnioski L1', threading.Event())
        navigate.assert_not_called()

    def test_cancellation_does_not_trigger_reload(self):
        page = self.page()
        with patch('neto_incident_monitor.dashboard.navigate_page') as navigate, \
                patch('neto_incident_monitor.dashboard.click_control', side_effect=Cancelled()):
            with self.assertRaises(Cancelled):
                open_dashboard_tab(page, 'Wnioski L1', threading.Event())
        navigate.assert_not_called()

    def test_wrong_host_is_not_treated_as_loaded_dashboard(self):
        page = self.page(DASHBOARD_URL.replace('adeo.service-now.com', 'other.example'))
        self.assertFalse(same_dashboard(page))

    def test_native_tabs_use_one_document_navigation_for_three_sections(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                documents = []
                html = '''<button role="tab" aria-selected="true">Dashboard SLA</button>
                    <button role="tab" aria-selected="false">Wstrzymane L1</button>
                    <button role="tab" aria-selected="false">Wnioski L1</button>
                    <p id="content">Dashboard SLA</p>
                    <script>
                    window.clicks=0;
                    for (const tab of document.querySelectorAll('[role=tab]')) {
                        tab.onclick = () => {
                            window.clicks++;
                            for (const item of document.querySelectorAll('[role=tab]'))
                                item.setAttribute('aria-selected', String(item === tab));
                            document.querySelector('#content').innerText = tab.innerText;
                        };
                    }
                    </script>'''
                def serve(route):
                    if route.request.resource_type == 'document':
                        documents.append(True)
                    route.fulfill(body=html, content_type='text/html; charset=utf-8')
                page.route('**/*', serve)
                stop = threading.Event()
                navigate_page(page, DASHBOARD_URL, stop)
                open_dashboard_tab(page, 'Wstrzymane L1', stop)
                self.assertEqual(page.locator('#content').inner_text(), 'Wstrzymane L1')
                open_dashboard_tab(page, 'Wnioski L1', stop)
                self.assertEqual(page.locator('#content').inner_text(), 'Wnioski L1')
                open_dashboard_tab(page, 'Wnioski L1', stop)
                self.assertEqual(len(documents), 1)
                self.assertEqual(page.evaluate('window.clicks'), 2)
            finally:
                browser.close()

    def test_hidden_loader_in_another_tab_does_not_block_current_scores(self):
        from neto_incident_monitor.dashboard import read_requests_dashboard, REQUEST_TITLES
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                expected = dict(zip(REQUEST_TITLES, (202, 118, 99, 17)))
                html = '<button role="tab" aria-selected="true">Wnioski L1</button>'
                html += '<sn-component-filter><h3>Agent L1</h3><label><input type="checkbox" checked>Wybierz wszystko</label></sn-component-filter>'
                html += '<div hidden>Trwa ładowanie danych wizualizacji</div>'
                html += ''.join(f'<button aria-label="{title}, {value}">{value}</button>'
                                for title, value in expected.items())
                documents = []
                def serve(route):
                    documents.append(True)
                    route.fulfill(body=html, content_type='text/html; charset=utf-8')
                page.route('**/*', serve)
                page.goto(DASHBOARD_URL)
                self.assertEqual(read_requests_dashboard(page, threading.Event()), expected)
                self.assertEqual(len(documents), 1)
            finally:
                browser.close()
