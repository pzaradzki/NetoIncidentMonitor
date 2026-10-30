import threading
import unittest
from unittest.mock import Mock

from playwright.sync_api import TimeoutError, sync_playwright
from neto_incident_monitor.app import collect, empty_list, authentication_page, navigate
from neto_incident_monitor.pagination import read_all, activate_pager, Cancelled

URL = 'https://adeo.service-now.com/incident_list.do?sysparm_first_row=1'


class PaginationControlsTests(unittest.TestCase):
    def test_modern_pager_moves_without_actionability_and_resets_restored_page(self):
        html = '''<style>@keyframes moving {from {transform:translateX(0)} to {transform:translateX(60px)}}
          button {animation:moving .15s linear infinite alternate}</style>
          <table><tr><th glide_field="incident.number">Numer</th></tr>
          <tr><td><a id="inc" href="/incident.do"></a></td></tr></table>
          <div style="height:5000px"></div>
          <button title="Pierwsza strona" onclick="n=1;render()">First</button>
          <input class="list_row_number_input" onkeydown="if(event.key==='Enter'){n=Number(this.value);render()}">
          <button title="Następna strona" onclick="n++;render()">Next</button>
          <script>let n=3;function render(){document.querySelector('#inc').textContent='INC000000'+n;
          document.querySelector('input').value=n;
          document.querySelector('[title="Pierwsza strona"]').disabled=n===1;
          document.querySelector('[title="Następna strona"]').disabled=n===3;}render();</script>'''
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.route('https://adeo.service-now.com/**', lambda route: route.fulfill(
                    content_type='text/html; charset=utf-8', body=html))
                page.goto(URL)
                # Physical clicks time out on this pager while its DOM handler remains usable.
                with self.assertRaises(TimeoutError):
                    page.get_by_title('Pierwsza strona', exact=True).click(trial=True, timeout=500)
                stages = []
                rows, pages = read_all(page, URL, threading.Event(), collect, empty_list,
                    authentication_page, navigate, on_stage=lambda name, index: stages.append((name, index)))
                self.assertEqual(pages, 3)
                self.assertEqual(set(rows), {'INC0000001', 'INC0000002', 'INC0000003'})
                self.assertIn(('first_page', 1), stages)
                self.assertIn(('next_page', 2), stages)
                self.assertEqual(page.locator('input').input_value(), '3')
                # Without a First button, the modern row input must still reset the list.
                page.unroute('https://adeo.service-now.com/**')
                field_only = html.replace('<button title="Pierwsza strona" onclick="n=1;render()">First</button>', '')
                field_only = field_only.replace("document.querySelector('[title=\"Pierwsza strona\"]').disabled=n===1;", '')
                page.route('https://adeo.service-now.com/**', lambda route: route.fulfill(
                    content_type='text/html; charset=utf-8', body=field_only))
                rows, pages = read_all(page, URL, threading.Event(), collect, empty_list,
                    authentication_page, navigate)
                self.assertEqual(pages, 3)
                self.assertEqual(len(rows), 3)
            finally:
                browser.close()

    def test_disabled_control_and_stop_do_not_deliver_pagination(self):
        button = Mock()
        button.evaluate.return_value = True
        with self.assertRaisesRegex(RuntimeError, 'nie jest gotowy'):
            activate_pager(button, threading.Event())
        stop = threading.Event()
        stop.set()
        button.reset_mock()
        with self.assertRaises(Cancelled):
            activate_pager(button, stop)
        button.evaluate.assert_not_called()
