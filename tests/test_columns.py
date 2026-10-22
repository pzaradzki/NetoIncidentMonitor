import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch
from neto_incident_monitor.app import App, collect
from neto_incident_monitor.columns import DEFAULT


class ColumnTests(unittest.TestCase):
    def test_browser_detects_empty_columns_and_separates_descriptions(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.route('https://adeo.service-now.com/**', lambda route: route.fulfill(body=''))
                page.goto('https://adeo.service-now.com/incident_list.do')
                headers = '<tr><th name="incident.cmdb_ci">Objęty element konfiguracji</th><th name="incident.assignment_group">Grupa przypisania</th><th name="incident.description">Opis</th><th name="incident.number">Numer</th><th name="incident.short_description">Krótki opis</th><th name="incident.sys_updated_on">Zaktualizowano</th><th name="incident.state">Stan</th><th name="incident.caller_id">Zgłaszający</th><th name="incident.assigned_to">Przypisane do</th><th name="incident.parent_incident">Incydent nadrzędny</th><th name="incident.location" style="display:none">Lokalizacja</th></tr>'
                page.set_content('<table>' + headers + '</table>')
                available = set()
                self.assertEqual(collect(page, available), {})
                self.assertIn('description', available)
                self.assertNotIn('location', available)
                page.set_content('<table>' + headers + '<tr><td>Drukarka</td><td>LMPL-L1-Support</td><td>Pełny opis</td><td><a href="https://adeo.service-now.com/incident.do">INC1234567</a></td><td>Krótki opis testowy</td><td>2026-10-08 12:00:00</td><td>Nowy</td><td>Anna</td><td></td><td><a href="https://adeo.service-now.com/incident.do">INC7654321</a></td><td style="display:none">Sklep</td></tr></table>')
                rows = collect(page)
                self.assertEqual(set(rows), {'INC1234567'})
                row = rows['INC1234567']
                for key, value in {'configuration_item': 'Drukarka', 'assignment_group': 'LMPL-L1-Support', 'description': 'Pełny opis', 'short_description': 'Krótki opis testowy', 'updated': '2026-10-08 12:00:00', 'state': 'Nowy', 'caller': 'Anna', 'assigned_to': '', 'parent_incident': 'INC7654321'}.items():
                    self.assertEqual(row[key], value)
            finally:
                browser.close()
