import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from neto_incident_monitor.dashboard_drilldown import resolve_drilldown, valid_drilldown


class DrilldownTests(unittest.TestCase):
    def page(self, table):
        page = Mock(url=f"https://adeo.service-now.com/now/nav/ui/classic/params/target/{table}_list.do%3Fsysparm_tiny%3Dsynthetic")
        page.locator.return_value.count.return_value = 1
        page.locator.return_value.is_visible.return_value = True
        frame = Mock(url=f"https://adeo.service-now.com/{table}_list.do")
        frame.name = "gsft_main"
        page.frames = [frame]
        rows = frame.locator.return_value.filter.return_value
        rows.count.return_value = 1
        rows.get_attribute.return_value = "active=true^short_descriptionLIKESynthetic"
        return page, rows

    def test_confirmed_l1_tables_use_full_query(self):
        for section, table in (("requests", "sc_task"), ("held", "incident_metric")):
            with self.subTest(section=section):
                page, rows = self.page(table)
                direct = urlsplit(resolve_drilldown(page, section))
                self.assertEqual(direct.path, f"/{table}_list.do")
                self.assertEqual(parse_qs(direct.query), {"sysparm_query": [rows.get_attribute.return_value]})

    def test_rejects_wrong_origin_wrong_table_and_ambiguous_list(self):
        page, rows = self.page("sc_task")
        self.assertIsNone(resolve_drilldown(page, "held"))
        rows.count.return_value = 2
        self.assertIsNone(resolve_drilldown(page, "requests"))
        page.url = page.url.replace("adeo.service-now.com", "example.test")
        self.assertIsNone(resolve_drilldown(page, "requests"))


    def test_sla_query_requires_exact_snapshot_period(self):
        from urllib.parse import urlencode

        for month, last in ((9, 30), (11, 30)):
            period = (2026, month)
            query = (
                f"task.opened_atBETWEENjavascript:gs.dateGenerate('2026-{month:02d}-01','start')"
                f"@javascript:gs.dateGenerate('2026-{month:02d}-{last}','end')^active=true"
            )
            page, rows = self.page("task_sla")
            rows.get_attribute.return_value = query
            direct = resolve_drilldown(page, "sla", period)
            self.assertTrue(valid_drilldown(direct, "sla", period))
            self.assertFalse(valid_drilldown(direct, "sla", (2026, 10)))
            relative = "https://adeo.service-now.com/task_sla_list.do?" + urlencode({
                "sysparm_query": "task.opened_atBETWEENjavascript:gs.beginningOfLastMonth()@javascript:gs.endOfLastMonth()"
            })
            self.assertFalse(valid_drilldown(relative, "sla", period))

    def test_collects_links_from_synthetic_browser_and_closes_scratch_tab(self):
        import html
        import json
        from threading import Event
        from playwright.sync_api import sync_playwright
        from neto_incident_monitor.dashboard import DASHBOARD_URL, TITLES
        from neto_incident_monitor.dashboard_drilldown import collect_drilldown
        from tests.dashboard_fixture import workspace

        query = ("task.opened_atBETWEENjavascript:gs.dateGenerate('2026-11-01','start')"
                 "@javascript:gs.dateGenerate('2026-11-30','end')^active=true")
        wrapper = '/now/nav/ui/classic/params/target/task_sla_list.do%3Fsysparm_tiny%3Dsynthetic'
        title = TITLES[0]
        dashboard = workspace() + f"""<script>
            const card = document.querySelector('.score-card');
            const button = document.createElement('button');
            button.textContent = {json.dumps(title + ', 0,')};
            button.onclick = () => location.href = {json.dumps(wrapper)};
            card.appendChild(button);
        </script>"""

        def route_handler(route):
            path = urlsplit(route.request.url).path
            if path.startswith('/now/nav/ui/classic/'):
                body = '<iframe id="gsft_main" name="gsft_main" src="/task_sla_list.do"></iframe>'
            elif path == '/task_sla_list.do':
                body = f'<table glide_table="task_sla" query="{html.escape(query, quote=True)}"><tr><td>Test</td></tr></table>'
            else:
                body = dashboard
            route.fulfill(content_type='text/html; charset=utf-8', body=body)

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                context = browser.new_context()
                context.route('**/*', route_handler)
                page = context.new_page()
                page.goto(DASHBOARD_URL)
                from neto_incident_monitor.dashboard import open_section
                from neto_incident_monitor.pagination import AuthenticationRequired

                first_attempt = True
                def open_after_transient_auth(*args):
                    nonlocal first_attempt
                    if first_attempt:
                        first_attempt = False
                        raise AuthenticationRequired()
                    return open_section(*args)

                diagnostics = Mock()
                with patch('neto_incident_monitor.dashboard.open_section', side_effect=open_after_transient_auth):
                    link = collect_drilldown(page, 'sla', title, Event(), diagnostics, (2026, 11))
                diagnostics.record.assert_any_call('dashboard_drilldown_tile', tile_index=0,
                                                   attempt=1, drilldown_result='authentication_retry')
                self.assertTrue(valid_drilldown(link, 'sla', (2026, 11)))
                self.assertEqual(context.pages, [page])
                self.assertEqual(page.url, DASHBOARD_URL)
            finally:
                browser.close()
