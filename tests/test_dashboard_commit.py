"""Commit races observed on ServiceNow, using synthetic DOM only."""
import json
import threading
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright, TimeoutError
from neto_incident_monitor import dashboard
from neto_incident_monitor.dashboard_context import DashboardReadError
from neto_incident_monitor.read_budget import Budget, budget_scope
from neto_incident_monitor.browser_actions import ACTION_TICK
from neto_incident_monitor.pagination import Cancelled
from neto_incident_monitor.login_diagnostics import LoginDiagnostics, _logger
from tests.dashboard_fixture import workspace


class DashboardCommitTests(unittest.TestCase):
    def setUp(self):
        self.playwright = sync_playwright().start()
        self.addCleanup(self.playwright.stop)
        self.browser = self.playwright.chromium.launch(headless=True)
        self.addCleanup(self.browser.close)
        self.page = self.browser.new_page()
        self.page.route('**/*', lambda route: route.fulfill(body=workspace(), content_type='text/html; charset=utf-8'))
        self.page.goto('https://adeo.service-now.com/test-dashboard')
        self.stop = threading.Event()

    def delay_apply(self):
        self.page.evaluate('''() => {
            const open = dates;
            dates = () => {open(); const panel=document.querySelector('now-popover-panel');
                const apply=panel.querySelector('button'); apply.disabled=true;
                panel.querySelectorAll('input')[1].onblur=()=>setTimeout(()=>apply.disabled=false,700);
            };
            document.querySelector('#period').onclick=dates;
        }''')

    def test_changed_period_waits_for_apply_instead_of_cancelling(self):
        self.delay_apply()
        with budget_scope(Budget(4)):
            dashboard.set_period(self.page, 2026, 11, self.stop)
        self.assertIn('2026-11-01 - 2026-11-30', self.page.locator('#period').get_attribute('aria-label'))
        self.assertEqual(self.page.locator('now-popover-panel').count(), 0)

    def test_unchanged_period_can_cancel_disabled_apply(self):
        self.delay_apply()
        dashboard.set_period(self.page, 2026, 10, self.stop)
        self.assertEqual(self.page.locator('now-popover-panel').count(), 0)

    def test_category_confirmation_retries_transient_observation(self):
        original = type(self.page.locator('input')).evaluate
        def evaluate(locator, expression, *args, **kwargs):
            if self.page.evaluate('window.applied') and not getattr(self, 'failed', False):
                self.failed = True
                raise TimeoutError('SYNTHETIC_SECRET')
            return original(locator, expression, *args, **kwargs)
        with patch.object(type(self.page.locator('input')), 'evaluate', evaluate):
            dashboard.ensure_all_categories(self.page, self.stop, ('Status zgłoszenia',))
        self.assertTrue(self.failed)
        self.assertEqual(self.page.evaluate('window.applied'), 1)

    def test_partial_category_never_accepted(self):
        self.page.evaluate('''() => {document.querySelector('sn-component-filter button').onclick=()=>{
            window.applied++;document.querySelector('input[type=checkbox]').indeterminate=true;
        }}''')
        with budget_scope(Budget(1)), self.assertRaises((TimeoutError, DashboardReadError)):
            dashboard.ensure_all_categories(self.page, self.stop, ('Status zgłoszenia',))
        self.assertEqual(self.page.evaluate('window.applied'), 1)

    def test_partial_category_confirms_clear_before_selecting_all(self):
        self.page.evaluate('''() => {
            const checkbox = document.querySelector('input[type=checkbox]');
            checkbox.checked = false;
            checkbox.setAttribute('aria-checked', 'mixed');
            checkbox.onclick = event => {
                event.preventDefault();
                window.clearClicks = (window.clearClicks || 0) + 1;
                setTimeout(() => {
                    const empty = checkbox.cloneNode();
                    empty.removeAttribute('aria-checked');
                    empty.checked = false;
                    empty.onclick = () => window.selectClicks = (window.selectClicks || 0) + 1;
                    checkbox.replaceWith(empty);
                }, 250);
            };
        }''')
        log = LoginDiagnostics(source='dashboard', section='sla', request_id=73)
        with self.assertLogs(_logger, level='INFO') as captured, dashboard.diagnostic_steps(log):
            dashboard.ensure_all_categories(self.page, self.stop, ('Status zgłoszenia',))
        self.assertEqual(self.page.evaluate('[clearClicks, selectClicks, applied]'), [1, 1, 1])
        records = [json.loads(record.getMessage()) for record in captured.records]
        resolved = next(row for row in records if row['event'] == 'category_partial_resolved')
        self.assertEqual((resolved['request_id'], resolved['category'], resolved['category_state']),
                         (73, 'status', 'none'))

    def test_unconfirmed_partial_category_is_not_clicked_again_or_applied(self):
        self.page.evaluate('''() => {
            const checkbox = document.querySelector('input[type=checkbox]');
            checkbox.setAttribute('aria-checked', 'mixed');
            checkbox.onclick = event => {
                event.preventDefault();
                window.clearClicks = (window.clearClicks || 0) + 1;
            };
        }''')
        with self.assertRaises(DashboardReadError) as error:
            dashboard.ensure_all_categories(self.page, self.stop, ('Status zgłoszenia',))
        self.assertEqual(error.exception.reason, 'wrong_filter')
        self.assertEqual(self.page.evaluate('[clearClicks, applied]'), [1, 0])

    def test_stop_during_apply_readiness_never_commits(self):
        self.delay_apply()
        def tick():
            if self.page.locator('now-popover-panel').count():
                self.stop.set()
        token = ACTION_TICK.set(tick)
        try:
            with self.assertRaises(Cancelled):
                dashboard.set_period(self.page, 2026, 11, self.stop)
        finally:
            ACTION_TICK.reset(token)
        self.assertIn('2026-10-01', self.page.locator('#period').get_attribute('aria-label'))

    def test_uncertain_period_click_is_not_repeated(self):
        original = type(self.page.locator('button')).click
        def click(locator, *args, **kwargs):
            if not kwargs.get('trial') and locator.get_attribute('data-commit') == 'yes':
                original(locator, *args, **kwargs)
                self.delivered = getattr(self, 'delivered', 0) + 1
                raise TimeoutError('SYNTHETIC_SECRET')
            return original(locator, *args, **kwargs)
        self.page.evaluate('''() => {const open=dates;dates=()=>{open();
            document.querySelector('now-popover-panel button').dataset.commit='yes';};
            document.querySelector('#period').onclick=dates;}''')
        with patch.object(type(self.page.locator('button')), 'click', click), self.assertRaises(TimeoutError):
            dashboard.set_period(self.page, 2026, 11, self.stop)
        self.assertEqual(self.delivered, 1)

    def test_invalid_field_cannot_commit(self):
        self.page.evaluate('''() => {const open=dates;dates=()=>{open();
            document.querySelector('now-popover-panel input').setAttribute('aria-invalid','true');};
            document.querySelector('#period').onclick=dates;}''')
        with self.assertRaises(DashboardReadError):
            dashboard.set_period(self.page, 2026, 11, self.stop)
        self.assertIn('2026-10-01', self.page.locator('#period').get_attribute('aria-label'))

    def test_delayed_panel_and_confirmation(self):
        self.page.evaluate('''() => {const open=dates;dates=()=>setTimeout(()=>{open();
            const apply=document.querySelector('now-popover-panel button'),commit=apply.onclick;
            apply.onclick=()=>{window.commits=(window.commits||0)+1;setTimeout(commit,500);};
        },400);document.querySelector('#period').onclick=dates;}''')
        dashboard.set_period(self.page, 2026, 11, self.stop)
        self.assertEqual(self.page.evaluate('window.commits'), 1)
        self.assertEqual(self.page.locator('now-popover-panel').count(), 0)

    def test_commit_stages_really_reach_diagnostics(self):
        log = LoginDiagnostics(source='dashboard', section='sla', request_id=73)
        with self.assertLogs(_logger, level='INFO') as captured:
            with dashboard.diagnostic_steps(log):
                dashboard.set_period(self.page, 2026, 11, self.stop)
                dashboard.ensure_all_categories(self.page, self.stop, ('Status zgłoszenia',))
        records = [json.loads(r.getMessage()) for r in captured.records]
        stages = [r for r in records if r['event']=='dashboard_stage_end']
        for code in ('period_ready', 'commit_period', 'period_confirm', 'category_apply', 'category_confirm'):
            row = next(r for r in stages if r.get('operation')==code)
            self.assertEqual(row['request_id'], 73)
            self.assertGreaterEqual(row['duration_ms'], 0)
        self.assertNotIn('2026-11-01', str(captured.output))
        self.assertNotIn('SYNTHETIC_SECRET', str(captured.output))
