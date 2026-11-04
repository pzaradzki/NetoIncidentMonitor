import json
import threading
import unittest
from urllib.parse import urlencode
from unittest.mock import Mock

from playwright.sync_api import sync_playwright
from neto_incident_monitor.app import collect, empty_list, authentication_page, navigate
from neto_incident_monitor.list_context import list_conditions, compare_list_conditions, ListStateError
from neto_incident_monitor.pagination import read_all
from neto_incident_monitor.login_diagnostics import LoginDiagnostics, _logger
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


class DateAliasBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def read(self, requested, first, later, diagnostics):
        page = self.browser.new_page()
        self.addCleanup(page.close)
        body = classic_list(total=23, size=10).replace('function render(){',
            'function render(){table.setAttribute("query",s.first===1?'
            + json.dumps(first) + ':' + json.dumps(later) + ');')
        page.route('**/*', lambda route: route.fulfill(body=body, content_type='text/html; charset=utf-8'))
        return read_all(page, 'https://adeo.service-now.com/incident_list.do?' + urlencode({'sysparm_query': requested}),
                        threading.Event(), collect, empty_list, authentication_page, navigate,
                        diagnostics=diagnostics)

    def test_three_pages_accept_alias_changes_and_log_bounded_safe_results(self):
        canonical = QUERY.replace(LEGACY, CANONICAL)
        for requested, first, later in ((QUERY, canonical, QUERY), (canonical, QUERY, canonical)):
            with self.assertLogs(_logger, level='INFO') as captured:
                result, pages = self.read(requested, first, later, LoginDiagnostics(source='pagination', filter_index=1))
            self.assertEqual((len(result), pages), (23, 3))
            records = [json.loads(r.getMessage()) for r in captured.records]
            comparisons = [r for r in records if r['event'] == 'pagination_query_comparison']
            self.assertEqual([r['query_comparison'] for r in comparisons], ['known_alias', 'exact'])
            self.assertEqual(comparisons[0]['query_alias'], 'last_7_days')
            output = '\n'.join(captured.output)
            for secret in ('SYNTHETIC_PRIVATE_ID', 'SYNTHETIC_GROUP', 'sysparm_query', 'INC000'):
                self.assertNotIn(secret, output)
            self.assertEqual(len({r['session'] for r in records}), 1)

    def test_real_change_after_first_page_never_returns_partial_result(self):
        diagnostics = Mock()
        with self.assertRaises(ListStateError) as raised:
            self.read(QUERY, QUERY.replace(LEGACY, CANONICAL), QUERY.replace('(7)', '(8)'), diagnostics)
        self.assertEqual(raised.exception.reason, 'list_changed')
        self.assertEqual(sum(call.args[0] == 'pagination_attempt' for call in diagnostics.record.call_args_list), 2)
