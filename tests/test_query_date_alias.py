from html import escape
import threading
import unittest
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

from neto_incident_monitor.app import navigate
from neto_incident_monitor.dashboard_context import DashboardReadError
from neto_incident_monitor.filter_definition import discover_definition
from neto_incident_monitor.list_context import list_conditions, compare_list_conditions
from tests.list_fixture import classic_list

LEGACY = 'javascript:gs.daysAgoStart(7)'
CANONICAL = 'javascript:gs.beginningOfLast7Days()'
BASE = 'company=SYNTHETIC_PRIVATE_ID^assignment_group=SYNTHETIC_GROUP'
QUERY = (BASE + '^stateIN1,2^parent_incidentISEMPTY^assigned_toISEMPTY^GOTOlocation.nameLIKE001'
         + ''.join('^ORlocation.nameLIKE' + str(i).zfill(3) for i in range(2, 65))
         + '^NQ' + BASE + '^stateIN1,2^opened_at<javascript:gs.beginningOfLast15Minutes()'
         + '^NQ' + BASE + '^locationNOT LIKESTORE^assigned_toISEMPTY^stateIN1,2'
         + '^NQ' + BASE + '^state=3^sys_updated_on<' + LEGACY)


class DateAliasUnitTests(unittest.TestCase):
    def test_known_alias_preserves_all_other_conditions_in_both_directions(self):
        canonical = QUERY.replace(LEGACY, CANONICAL)
        for a, b in ((QUERY, canonical), (canonical, QUERY)):
            self.assertEqual(list_conditions(a), list_conditions(b))
            self.assertEqual(compare_list_conditions(a, b), 'known_alias')
        self.assertEqual(compare_list_conditions(QUERY, QUERY + '^EQ^ORDERBYDESCnumber'), 'exact')
        self.assertEqual(list_conditions(QUERY).count('^NQ'), 3)
        for prefix in ('', 'OR', 'NQ', 'GOTO', 'ORGOTO', 'NQGOTO'):
            value = prefix + 'sys_updated_on<=' + LEGACY
            self.assertEqual(list_conditions(value), prefix + 'sys_updated_on<=' + CANONICAL)

    def test_unconfirmed_differences_and_similar_text_remain_distinct(self):
        for changed in (QUERY.replace('(7)', '(8)'), QUERY.replace('state=3', 'state=2'),
                        QUERY.replace('sys_updated_on<', 'sys_updated_on>'),
                        QUERY.replace('LIKE001', 'LIKE099'), QUERY.replace('^NQ', '^OR', 1)):
            self.assertEqual(compare_list_conditions(QUERY, changed), 'mismatch')
        for value in ('short_description=' + LEGACY, 'descriptionLIKE' + LEGACY,
                      'sys_updated_on<' + LEGACY + ';', 'sys_updated_on<javascript:gs.daysAgoStart(70)',
                      'sys_updated_on<javascript:gs.daysAgoStart(7)+1'):
            self.assertEqual(list_conditions(value), value)
        self.assertEqual(compare_list_conditions(QUERY, None), 'mismatch')

    def test_discovery_accepts_known_alias_but_rejects_changed_conditions(self):
        url = 'https://adeo.service-now.com/incident_list.do?' + urlencode({'sysparm_query': QUERY})
        canonical = QUERY.replace(LEGACY, CANONICAL)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()

            def discover(observed):
                page.unroute_all()
                html = classic_list(total=0).replace('query="active=true"', f'query="{escape(observed)}"')
                page.route('**/*', lambda route: route.fulfill(content_type='text/html', body=html))
                return discover_definition(page, {'url': url}, threading.Event(), navigate, lambda *_: False)

            definition, _ = discover(canonical)
            self.assertEqual(definition['query'], canonical)
            with self.assertRaisesRegex(DashboardReadError, 'api_filter_mismatch'):
                discover(canonical.replace('state=3', 'state=2'))
            browser.close()
