import unittest
from neto_incident_monitor.filter_definition import read_list_headers
from neto_incident_monitor.list_context import ListTarget


class ColumnTests(unittest.TestCase):
    def test_browser_detects_empty_columns_and_separates_descriptions(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.route('https://adeo.service-now.com/**', lambda route: route.fulfill(body=''))
                url = 'https://adeo.service-now.com/incident_list.do'
                page.goto(url)
                headers = '<tr><th name="incident.cmdb_ci">Objęty element konfiguracji</th><th name="incident.assignment_group">Grupa przypisania</th><th name="incident.description">Opis</th><th name="incident.number">Numer</th><th name="incident.short_description">Krótki opis</th><th name="incident.sys_updated_on">Zaktualizowano</th><th name="incident.state">Stan</th><th name="incident.caller_id">Zgłaszający</th><th name="incident.assigned_to">Przypisane do</th><th name="incident.parent_incident">Incydent nadrzędny</th><th name="incident.location" style="display:none">Lokalizacja</th></tr>'
                page.set_content('<table>' + headers + '</table>')
                columns = read_list_headers(ListTarget.find(page, url))['schema']
                mapping = {column['key']: column['field'] for column in columns}
                self.assertEqual(mapping, {'configuration_item': 'cmdb_ci', 'assignment_group': 'assignment_group',
                    'description': 'description', 'short_description': 'short_description', 'number': 'number',
                    'updated': 'sys_updated_on', 'state': 'state', 'caller': 'caller_id', 'assigned_to': 'assigned_to',
                    'parent_incident': 'parent_incident'})
            finally:
                browser.close()
