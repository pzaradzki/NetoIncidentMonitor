import queue
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from neto_incident_monitor.app import collect, empty_list, authentication_page, navigate, normalize_url, validate_urls
from neto_incident_monitor.monitoring import Health, Schedule
from neto_incident_monitor.pagination import read_all, first_page, AuthenticationRequired, Cancelled
from neto_incident_monitor.single_instance import SingleInstance

URL = "https://example.com/incident_list.do?sysparm_query=active%3Dtrue&sysparm_first_row=21"


class ReliabilityTests(unittest.TestCase):
    def test_empty_list_is_success_even_with_incomplete_pager(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, timeout=15000)
            try:
                page = browser.new_page()
                html = '''<div style="display:none">Brak rekordów do wyświetlenia</div>
                    <div>\n Brak rekordów\n do wyświetlenia. \n</div>
                    <input class="list2_page" value="1"><div class="list2_paging"></div>'''
                page.route("https://example.com/**", lambda route: route.fulfill(content_type="text/html; charset=utf-8", body=html))
                result, pages = read_all(page, URL, threading.Event(), collect, empty_list, authentication_page, navigate)
                self.assertEqual(result, {})
                self.assertEqual(pages, 1)
                self.assertTrue(empty_list(page, URL))
                page.set_content('<div>Access denied</div>')
                self.assertFalse(empty_list(page, URL))
            finally:
                browser.close()
    def test_classic_navigation_link_preserves_encoded_filter(self):
        from urllib.parse import quote, parse_qs, urlparse
        target = "incident_list.do?sysparm_query=active%3Dtrue%5Eassigned_toISEMPTY%5Estate!%3D6%5ElocationLIKESTORE%20003%20GDA%C5%83SK%5EORlocationLIKESTORE%20073%20GDYNIA%5Eassignment_groupLIKELMPL-L1-Support&sysparm_first_row=1&sysparm_view=default"
        direct = "https://adeo.service-now.com/" + target
        wrapped = "https://adeo.service-now.com/now/nav/ui/classic/params/target/" + quote(target, safe="!")
        self.assertEqual(normalize_url(wrapped), direct)
        self.assertEqual(normalize_url(direct), direct)
        self.assertEqual(validate_urls(wrapped + "\n" + direct), [direct])
        query = parse_qs(urlparse(normalize_url(wrapped)).query)
        self.assertIn("STORE 003 GDAŃSK", query["sysparm_query"][0])
        self.assertEqual(query["sysparm_view"], ["default"])
        from neto_incident_monitor.app import load_filters
        self.assertEqual(load_filters({"filters": [{"name": "Test", "url": wrapped}]}),
                         [{"name": "Test", "url": direct}])
        from unittest.mock import Mock
        page = Mock(url=wrapped)
        navigate(page, wrapped)
        self.assertEqual(page.goto.call_count, 2)
        for call in page.goto.call_args_list:
            self.assertEqual(call.args[0], direct)
        with self.assertRaises(ValueError):
            normalize_url("https://adeo.service-now.com/now/nav/ui/classic/params/target/" + quote("https://other.example/incident_list.do", safe=""))

    def test_repeated_cycles_reset_session_restored_last_page(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, timeout=15000)
            try:
                page = browser.new_page()
                # Simulate ServiceNow remembering the last row in the session
                # and ignoring first_row=1 on the next full page navigation.
                html = '''<table><tr><th>Number</th></tr><tr><td><a id="inc" href="/incident.do"></a></td></tr></table>
                  <button data-type="list_nav_first" title="First page" onclick="firstPage()">First</button>
                  <button data-type="list_nav_next" title="Next page" onclick="nextPage()">Next</button>
                  <input class="list2_page">
                  <script>let n=Number(sessionStorage.getItem('row')||1);
                  function render(){document.querySelector('#inc').textContent='INC000000'+n;
                    document.querySelector('input').value=n;
                    document.querySelector('[data-type=list_nav_first]').disabled=n===1;
                    document.querySelector('[data-type=list_nav_next]').disabled=n===3;
                    sessionStorage.setItem('row',n);}
                  function firstPage(){setTimeout(()=>{n=1;render();},400);}
                  function nextPage(){n++;render();}render();</script>'''
                page.route("https://example.com/**", lambda route: route.fulfill(content_type="text/html", body=html))
                for cycle in range(3):
                    progress = []
                    result, pages = read_all(page, URL, threading.Event(), collect, empty_list,
                                            authentication_page, navigate, lambda index, total: progress.append((index, total)))
                    self.assertEqual(set(result), {"INC0000001", "INC0000002", "INC0000003"})
                    self.assertEqual(pages, 3)
                    self.assertEqual(page.locator('input').input_value(), '3')
                    if cycle:
                        self.assertEqual(progress[0], (0, 0))
                    self.assertEqual([entry for entry in progress if entry[0]], [(1, 1), (2, 2), (3, 3)])
                # Also support lists where only the row-entry field is exposed.
                field_only = html.replace('<button data-type="list_nav_first" title="First page" onclick="firstPage()">First</button>', '')
                field_only = field_only.replace("document.querySelector('[data-type=list_nav_first]').disabled=n===1;", '')
                field_only = field_only.replace('<input class="list2_page">', '<input class="list2_page" onkeydown="if(event.key===\'Enter\')firstPage()">')
                page.unroute("https://example.com/**")
                page.route("https://example.com/**", lambda route: route.fulfill(content_type="text/html", body=field_only))
                result, pages = read_all(page, URL, threading.Event(), collect, empty_list, authentication_page, navigate)
                self.assertEqual(pages, 3)
                self.assertEqual(len(result), 3)
            finally:
                browser.close()
    def test_schedule_wakes_and_coalesces_requests(self):
        schedule = Schedule()
        stop = threading.Event()
        done = threading.Event()
        thread = threading.Thread(target=lambda: (schedule.wait(60, stop), done.set()))
        thread.start()
        schedule.request()
        self.assertTrue(done.wait(1))
        thread.join()
        schedule.request()
        schedule.request()
        started = time.monotonic()
        self.assertFalse(schedule.wait(60, stop))
        self.assertLess(time.monotonic() - started, 0.1)
        self.assertFalse(schedule.requested)
        stop.set()
        self.assertTrue(schedule.wait(60, stop))

    def test_health_per_filter_recovery_and_authentication(self):
        health = Health()
        self.assertFalse(health.failure("a"))
        self.assertFalse(health.failure("b"))
        self.assertFalse(health.failure("a"))
        self.assertTrue(health.failure("a"))
        self.assertFalse(health.failure("a"))
        health.success("a")
        self.assertFalse(health.failure("a"))
        self.assertTrue(health.authentication())
        self.assertFalse(health.authentication())
        health.resumed()
        self.assertTrue(health.authentication())

    def test_second_process_signals_primary_and_releases_mutex(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            primary = SingleInstance(folder)
            try:
                self.assertTrue(primary.primary)
                script = "from neto_incident_monitor.single_instance import SingleInstance; import sys; x=SingleInstance(sys.argv[1]); assert not x.primary; x.request_show(); x.close()"
                subprocess.run([sys.executable, "-c", script, folder], check=True, timeout=10)
                self.assertTrue(primary.poll())
                self.assertFalse(primary.poll())
            finally:
                primary.close()
            reopened = SingleInstance(folder)
            try:
                self.assertTrue(reopened.primary)
            finally:
                reopened.close()

    def test_all_pages_then_restarts_at_first_page(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, timeout=15000)
            try:
                page = browser.new_page()
                html = '''<table><tr><th>Numer</th><th>Krótki opis</th></tr><tr><td><a id="inc" href="/incident.do">INC0000001</a></td><td>Test</td></tr></table>
                  <button data-type="list_nav_next" title="Następna strona" onclick="step()">Next</button>
                  <script>let n=1;function step(){n++;document.querySelector('#inc').textContent='INC000000'+n;
                  if(n===3)document.querySelector('button').disabled=true;}</script>'''
                page.route("https://example.com/**", lambda route: route.fulfill(content_type="text/html; charset=utf-8", body=html))
                progress = []
                result, count = read_all(page, URL, threading.Event(), collect, empty_list,
                                         authentication_page, navigate, lambda index, total: progress.append((index, total)))
                self.assertEqual(set(result), {"INC0000001", "INC0000002", "INC0000003"})
                self.assertEqual(count, 3)
                self.assertEqual(progress, [(1, 1), (2, 2), (3, 3)])
                self.assertIn("sysparm_first_row=1", page.url)
                result, count = read_all(page, URL, threading.Event(), collect, empty_list, authentication_page, navigate)
                self.assertEqual(count, 3)
                # Unknown pager fails rather than silently saving one page.
                page.unroute("https://example.com/**")
                page.route("https://example.com/**", lambda route: route.fulfill(content_type="text/html", body='<table><tr><th>Number</th></tr><tr><td><a href="/incident.do">INC0000001</a></td></tr></table><input class="list2_page">'))
                with self.assertRaisesRegex(RuntimeError, "Nie rozpoznano"):
                    read_all(page, URL, threading.Event(), collect, empty_list, authentication_page, navigate)
                # A broken second page must not return a partial result.
                page.unroute("https://example.com/**")
                broken = html.replace("n++;", "n++;document.querySelector('table').remove();")
                page.route("https://example.com/**", lambda route: route.fulfill(content_type="text/html", body=broken))
                with self.assertRaisesRegex(RuntimeError, "Nie udało się odczytać"):
                    read_all(page, URL, threading.Event(), collect, empty_list, authentication_page, navigate)
            finally:
                browser.close()

    def test_authentication_and_cancellation_do_not_commit_partial_results(self):
        from unittest.mock import Mock
        page = Mock(url="https://idp.example.com/login")
        with self.assertRaises(AuthenticationRequired):
            read_all(page, URL, threading.Event(), collect, empty_list, authentication_page, lambda *args: None)
        stop = threading.Event()
        stop.set()
        with self.assertRaises(Cancelled):
            read_all(page, URL, stop, collect, empty_list, authentication_page, lambda *args: None)


if __name__ == "__main__":
    unittest.main()
