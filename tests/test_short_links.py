import threading
import unittest
from unittest.mock import Mock

from neto_incident_monitor.app import navigate, collect, empty_list, authentication_page, wait_for_login, load_filters
from neto_incident_monitor.pagination import read_all, first_page
from neto_incident_monitor.service_now_urls import normalize_list_url, resolved_list_url, effective_list_url

BASE = 'https://adeo.service-now.com'
SHORT = BASE + '/now/nav/ui/classic/__tinyId__/' + 'Abc123xyz456' * 3


class ShortLinkTests(unittest.TestCase):
    def test_only_exact_trusted_short_links_are_accepted(self):
        self.assertEqual(normalize_list_url(SHORT), SHORT)
        self.assertEqual(first_page(SHORT), SHORT)
        self.assertNotIn('url_invalid', load_filters({'urls': [SHORT]}, tolerate_invalid=True)[0])
        for bad in [SHORT.replace('adeo.service-now.com', 'evil.test'), SHORT + '/other',
                    SHORT + '?url=https://evil.test', SHORT + '#fragment',
                    SHORT.replace('.com/', '.com:8443/'), SHORT.replace('https://', 'https://:secret@'),
                    SHORT.rsplit('/', 1)[0] + '/short']:
            with self.subTest(url=bad), self.assertRaises(ValueError):
                normalize_list_url(bad)

    def test_only_visible_trusted_list_frames_resolve(self):
        foreign = Mock(url='https://evil.test/sc_task_list.do')
        admin = Mock(url=BASE + '/admin')
        hidden = Mock(url=BASE + '/incident_list.do')
        hidden.locator.return_value.is_visible.return_value = False
        trusted = Mock(url=BASE + '/sc_task_list.do?sysparm_query=active%3Dtrue')
        trusted.locator.return_value.is_visible.return_value = True
        self.assertIsNone(resolved_list_url(Mock(frames=[foreign, admin, hidden]), SHORT))
        target = resolved_list_url(Mock(frames=[foreign, trusted]), SHORT)
        self.assertEqual(target, trusted.url)
        self.assertEqual(effective_list_url(SHORT, [{'url': SHORT, 'resolved_list_url': target}]), target)
        self.assertEqual(effective_list_url(SHORT, [{'url': SHORT, 'resolved_list_url': foreign.url}]), SHORT)

    def test_browser_short_link_to_task_list_and_empty_list(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                for empty in (False, True):
                    page.unroute_all()
                    def route(request):
                        if '__tinyId__' in request.request.url:
                            body = '<iframe style="width:800px;height:500px" src="/sc_task_list.do?sysparm_query=active%3Dtrue"></iframe>'
                        else:
                            body = ('<p>Brak rekordów do wyświetlenia</p>' if empty else
                                    '<table><tr><th>Numer</th></tr><tr><td><a href="/sc_task.do?sys_id=1">SCTASK1954200</a></td></tr></table>')
                            body += '<button data-type="list_nav_next" disabled>Next</button>'
                        request.fulfill(content_type='text/html; charset=utf-8', body=body)
                    page.route('**/*', route)
                    navigate(page, SHORT)
                    self.assertTrue(wait_for_login(page, SHORT, threading.Event()))
                    rows, pages = read_all(page, SHORT, threading.Event(), collect, empty_list, authentication_page, navigate)
                    self.assertEqual(set(rows), set() if empty else {'SCTASK1954200'})
                    self.assertEqual(pages, 1)
                    self.assertIn('/sc_task_list.do?', page.url)
                    self.assertIn('sysparm_first_row=1', page.url)
            finally:
                browser.close()
