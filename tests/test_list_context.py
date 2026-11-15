import unittest
from playwright.sync_api import sync_playwright
from neto_incident_monitor.list_context import ListTarget, ListStateError
from neto_incident_monitor.filter_definition import read_list_headers
from tests.list_fixture import URL, classic_list


class ListContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.page = self.browser.new_page()
        self.addCleanup(self.page.close)
        self.page.route('**/*', lambda route: route.fulfill(body=classic_list(), content_type='text/html; charset=utf-8'))
        self.page.goto(URL)

    def test_metadata_is_independent_of_classic_page_size(self):
        for size in (20, 100):
            self.page.set_content(classic_list(size=size))
            target = ListTarget.find(self.page, URL)
            self.assertEqual([c['key'] for c in read_list_headers(target)['schema']],
                             ['number', 'short_description'])

    def test_other_list_does_not_contaminate_selected_metadata(self):
        foreign = classic_list().replace('incident', 'sc_task').replace('short_description', 'assignment_group')
        self.page.set_content(foreign + classic_list())
        target = ListTarget.find(self.page, URL)
        self.assertEqual(target.table.get_attribute('id'), 'incident_table')
        self.assertEqual([c['key'] for c in read_list_headers(target)['schema']],
                         ['number', 'short_description'])

    def test_two_matching_lists_are_rejected(self):
        self.page.locator('body').evaluate("body => body.appendChild(document.querySelector('.list-container').cloneNode(true))")
        with self.assertRaises(ListStateError):
            ListTarget.find(self.page, URL)

    def test_related_list_of_same_type_does_not_override_primary_list(self):
        self.page.locator('body').evaluate("""body => {const related=document.querySelector('.list-container').cloneNode(true);
            related.id='related_expanded';const t=related.querySelector('table');t.id='related_table';
            t.setAttribute('data-list_id','related');body.prepend(related)}""")
        target = ListTarget.find(self.page, URL)
        self.assertEqual(target.table.get_attribute('id'), 'incident_table')

class EncodedConditionsTests(unittest.TestCase):
    def test_end_and_sort_directives_do_not_change_ordered_conditions(self):
        from neto_incident_monitor.list_context import list_conditions
        query = 'active=true^ORstate=1^NQstate=2'
        self.assertEqual(list_conditions(query + '^EQ^ORDERBYDESCnumber'), query)
        self.assertEqual(list_conditions(query + '^ORDERBYnumber^EQ'), query)
        self.assertNotEqual(list_conditions('active=false^ORstate=1^NQstate=2'), query)
        self.assertEqual(list_conditions('short_descriptionLIKEORDERBYnumber'), 'short_descriptionLIKEORDERBYnumber')