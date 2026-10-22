import unittest
from urllib.parse import quote

from neto_incident_monitor.service_now_urls import normalize_list_url, safe_record_url
from neto_incident_monitor.notification_templates import linked_parts, standard
from neto_incident_monitor.teams_notifications import payload
from neto_incident_monitor.google_chat_notifications import payloads

BASE = 'https://adeo.service-now.com'


class RequestListTests(unittest.TestCase):
    def test_lists_and_safe_matching_record_links(self):
        for prefix, table in [('REQ', 'sc_request'), ('RITM', 'sc_req_item')]:
            direct = f'{BASE}/{table}_list.do?sysparm_query=active%3Dtrue'
            self.assertEqual(normalize_list_url(direct), direct)
            wrapped = BASE + '/now/nav/ui/classic/params/target/' + quote(direct[len(BASE)+1:], safe='')
            self.assertEqual(normalize_list_url(wrapped), direct)
            number = prefix + '0012345'
            record = f'{BASE}/{table}.do?sys_id=abc'
            self.assertEqual(safe_record_url(record, number, direct), record)
            self.assertEqual(safe_record_url(BASE + '/incident.do?sys_id=abc', number), '')
            self.assertEqual(safe_record_url(record.replace('adeo.service-now.com', 'evil.test'), number), '')
            title, text = standard('Filtr', [{'number': number, 'short_description': 'Opis'}])
            self.assertEqual(title, 'Filtr · 1')
            self.assertIn(f'>{number}</a>', payload(title, text, {number: record})['text'])
            self.assertIn(f'|{number}>', payloads(title, text, {number: record})[0]['text'])

    def test_reader_and_pagination_for_catalog_lists(self):
        from playwright.sync_api import sync_playwright
        from neto_incident_monitor.app import collect
        from neto_incident_monitor.columns import ColumnDiscovery
        from neto_incident_monitor.app import empty_list
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, channel='chromium')
            try:
                page = browser.new_page()
                for prefix, table in [('REQ', 'sc_request'), ('RITM', 'sc_req_item')]:
                    page.route(BASE + '/**', lambda route: route.fulfill(body='<html></html>', content_type='text/html'))
                    page.goto(f'{BASE}/{table}_list.do')
                    number = prefix + '0012345'
                    page.set_content(f'<table><tr><th name="{table}.number">Numer</th><th name="{table}.short_description">Krótki opis</th><th name="{table}.u_custom">Własna</th></tr><tr><td><a href="/{table}.do?sys_id=abc">{number}</a></td><td>Opis</td><td>Wartość</td></tr></table>')
                    found = {}; columns = ColumnDiscovery()
                    found = collect(page, columns)
                    self.assertIn(number, found)
                    self.assertEqual(found[number]['_values']['sn:u_custom'], 'Wartość')
                    self.assertEqual(found[number]['url'], f'{BASE}/{table}.do?sys_id=abc')
                    page.set_content('<div>No records to display</div>')
                    self.assertTrue(empty_list(page, page.url))
            finally:
                browser.close()



