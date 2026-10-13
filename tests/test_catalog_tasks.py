import unittest
from urllib.parse import quote

from neto_incident_monitor.app import collect, normalize_url
from neto_incident_monitor.pagination import first_page, next_button


class CatalogTaskTests(unittest.TestCase):
    def test_navigation_url_preserves_query_encoding(self):
        target = "sc_task_list.do?sysparm_query=request.requested_for.companyDYNAMIC123%5Eopened_by%3D456&sysparm_first_row=1&sysparm_view="
        direct = "https://example.test/" + target
        wrapped = "https://example.test/now/nav/ui/classic/params/target/" + quote(target, safe="")
        self.assertEqual(normalize_url(wrapped), direct)
        self.assertEqual(normalize_url(direct), direct)
        self.assertIn("/sc_task_list.do?", first_page(direct))

    def test_task_fields_primary_state_and_pagination(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.route("https://example.test/**", lambda route: route.fulfill(content_type="text/html; charset=utf-8", body='''
                    <table><tr>
                    <th name="sc_task.number">Numer</th>
                    <th name="sc_task.request.state">Stan</th>
                    <th name="sc_task.state">Stan</th>
                    <th name="sc_task.request.requested_for">Wnioskowane dla</th>
                    <th name="sc_task.opened_by">Otwarte przez</th>
                    <th name="sc_task.request_item">Pozycja wniosku</th>
                    <th name="sc_task.short_description">Krótki opis</th></tr>
                    <tr><td><a href="/sc_task.do?sys_id=1">SCTASK1954200</a></td>
                    <td>Otwarty</td><td>Oczekujący</td><td>Anna</td><td>Piotr</td>
                    <td>RITM1234567</td><td>Przygotowanie sprzętu</td></tr></table>
                    <button data-type="list_nav_next" disabled>Next page</button>
                '''))
                page.goto("https://example.test/sc_task_list.do")
                available = set()
                rows = collect(page, available)
                self.assertEqual(set(rows), {"SCTASK1954200"})
                task = rows["SCTASK1954200"]
                self.assertEqual(task["state"], "Oczekujący")
                self.assertEqual(task["requested_for"], "Anna")
                self.assertEqual(task["opened_by"], "Piotr")
                self.assertEqual(task["request_item"], "RITM1234567")
                self.assertIn("requested_for", available)
                self.assertTrue(next_button(page)[1])
            finally:
                browser.close()
