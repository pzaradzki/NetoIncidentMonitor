import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from playwright.sync_api import sync_playwright
from neto_incident_monitor.dashboard import DASHBOARD_URL, TITLES, HELD_TITLES, REQUEST_TITLES, read_dashboard, read_held_dashboard, read_requests_dashboard, read_scores, verify_context
from neto_incident_monitor.dashboard_context import DashboardReadError
from neto_incident_monitor.threatened import read_threatened_dashboard, KEYS
from neto_incident_monitor.section_runner import run_section
from neto_incident_monitor.login_diagnostics import LoginDiagnostics
from neto_incident_monitor.dashboard_cache import load_snapshot, save_sections
from tests.dashboard_fixture import workspace


class StabilizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = sync_playwright().start()
        cls.browser = cls.p.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.p.stop()

    def setUp(self):
        self.page = self.browser.new_page()
        self.addCleanup(self.page.close)
        self.page.route('**/*', lambda r: r.fulfill(body=workspace(), content_type='text/html; charset=utf-8'))
        self.stop = threading.Event()

    def test_all_sections_share_local_reader_and_ignore_forever_loading_chart(self):
        sla = read_dashboard(self.page, 2026, 9, self.stop)
        self.assertEqual(sla, dict(zip(TITLES, range(11))))
        self.assertEqual(read_held_dashboard(self.page, self.stop), dict(zip(HELD_TITLES, range(2))))
        self.assertEqual(read_requests_dashboard(self.page, self.stop), dict(zip(REQUEST_TITLES, range(len(REQUEST_TITLES)))))
        self.assertEqual(read_threatened_dashboard(self.page, self.stop), dict(zip(KEYS, range(6))))

    def test_wrong_tab_period_and_pending_filter_are_rejected(self):
        read_dashboard(self.page, 2026, 10, self.stop)
        with self.assertRaises(DashboardReadError):
            verify_context(self.page, 'sla', 2026, 9)
        self.page.locator('input[type=checkbox]').first.uncheck()
        with self.assertRaises(DashboardReadError):
            verify_context(self.page, 'sla', 2026, 10)

        self.page.get_by_role('tab', name='Wnioski L1').click()
        with self.assertRaises(DashboardReadError):
            verify_context(self.page, 'sla', 2026, 10)

    def test_delayed_date_popover_is_waited_for(self):
        self.page.unroute_all()
        html = workspace().replace('document.body.appendChild(panel);}',
                                   'setTimeout(()=>document.body.appendChild(panel),350);}')
        self.page.route('**/*', lambda r: r.fulfill(body=html, content_type='text/html; charset=utf-8'))
        self.assertEqual(read_dashboard(self.page, 2026, 9, self.stop), dict(zip(TITLES, range(11))))

    def test_delayed_loader_does_not_accept_old_stable_numbers(self):
        self.page.unroute_all()
        html = workspace(delay=200).replace('+i+', '+999+')
        html = html.replace('function refresh(){', 'function refresh(){setTimeout(()=>{')
        html = html.replace('},200);}}', '},200);}},1200);}')
        self.page.route('**/*', lambda r: r.fulfill(body=html, content_type='text/html; charset=utf-8'))
        self.assertEqual(read_dashboard(self.page, 2026, 9, self.stop), dict(zip(TITLES, range(11))))

    def test_duplicate_target_is_fatal_not_a_partial_success(self):
        self.page.goto(DASHBOARD_URL)
        self.page.locator('.score-card').first.evaluate('(e)=>e.parentElement.appendChild(e.cloneNode(true))')
        with self.assertRaises(DashboardReadError) as error:
            read_scores(self.page, TITLES, self.stop)
        self.assertFalse(error.exception.retryable)

    def test_risk_heading_before_score_is_loading_not_definition_change(self):
        from tests.dashboard_fixture import RISK_TITLES
        from neto_incident_monitor.dashboard_context import TAB_IDS
        self.page.goto(DASHBOARD_URL.replace(TAB_IDS['sla'], TAB_IDS['threatened']))
        self.page.evaluate("""() => {for(const card of document.querySelectorAll('.score-card')) {
            card.querySelector('now-score-basic').innerHTML='';
            setTimeout(()=>card.querySelector('now-score-basic').innerHTML='<span class="now-score-value">0</span>',600);
        }}""")
        self.assertEqual(read_scores(self.page, RISK_TITLES, self.stop), dict.fromkeys(RISK_TITLES, 0))

    def test_changed_risk_threshold_is_rejected(self):
        from tests.dashboard_fixture import RISK_TITLES
        from neto_incident_monitor.dashboard_context import TAB_IDS
        self.page.goto(DASHBOARD_URL.replace(TAB_IDS['sla'], TAB_IDS['threatened']))
        self.page.get_by_role('heading', name=RISK_TITLES[1], exact=True).evaluate('(e)=>e.textContent=e.textContent.replace("2 h","3 h")')
        with self.assertRaises(DashboardReadError) as error:
            read_scores(self.page, RISK_TITLES, self.stop)
        self.assertEqual(error.exception.reason, 'definition_changed')
        self.assertFalse(error.exception.retryable)

    def test_missing_category_triggers_lazy_activation(self):
        from neto_incident_monitor.dashboard import ensure_all_categories
        self.page.goto(DASHBOARD_URL)
        self.page.locator('sn-component-filter').first.evaluate('(e)=>{window.lazyCategory=e.cloneNode(true);e.remove()}')
        def reveal(*args, **kwargs):
            self.page.evaluate('() => document.querySelector("main").appendChild(window.lazyCategory)')
        with patch('neto_incident_monitor.dashboard.activate_dashboard_widgets', side_effect=reveal) as activate:
            ensure_all_categories(self.page, self.stop, ('Status zgłoszenia',))
        self.assertTrue(activate.called)

    def test_context_survives_replacement_of_equivalent_dom_controls(self):
        read_dashboard(self.page, 2026, 10, self.stop)
        self.page.evaluate("""() => {window.churn=setInterval(()=>{
            for(const e of document.querySelectorAll('[role=tab], sn-component-filter'))
                e.replaceWith(e.cloneNode(true));
        },25)}""")
        try:
            for _ in range(15):
                verify_context(self.page, 'sla', 2026, 10)
        finally:
            self.page.evaluate('() => clearInterval(window.churn)')

    def test_single_retry_discards_partial_and_preserves_status(self):
        reader = Mock(side_effect=[DashboardReadError('incomplete_widgets'), {'good': 0}])
        states = []
        value = run_section(self.page, self.stop, reader, LoginDiagnostics(section='held'),
                            Mock(), states.append, lambda v: v == {'good': 0})
        self.assertEqual(value, {'good': 0})
        self.assertEqual(reader.call_count, 2)
        self.assertIn('Ponawianie odczytu', states)

    def test_legacy_cache_has_no_invented_section_dates(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'cache.json'
            path.write_text(json.dumps({'schema': 1, 'year': 2026, 'month': 10, 'read_at': '2026-10-01T12:00:00',
                'values': dict.fromkeys(TITLES + HELD_TITLES, 0)}))
            loaded = load_snapshot(path)
            self.assertEqual(set(loaded['sections']), {'sla', 'held'})
            self.assertIsNone(loaded['sections']['held']['read_at'])
            save_sections(path, loaded['sections'])
            self.assertEqual(load_snapshot(path), loaded)
