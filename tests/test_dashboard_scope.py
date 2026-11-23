import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from urllib.parse import quote, urlsplit
from unittest.mock import Mock, patch

from playwright.sync_api import sync_playwright

from neto_incident_monitor.analytics_config import dashboard_scope, load_config, save_dashboard_scope, scope_from_p1_query
from neto_incident_monitor.dashboard_context import DashboardReadError
from neto_incident_monitor.dashboard_scope import CLASSIC_PREFIX, DASHBOARD_URL, refresh_scope
from neto_incident_monitor.favorites import HOME
from neto_incident_monitor.monitoring import ReadPart


AGENT = 'a' * 32
LOCATION = 'b' * 32
QUERY = f'task.locationIN{LOCATION}^task.assigned_toIN{AGENT}^task.priority=1'


class DashboardScopeTests(unittest.TestCase):
    def test_extracts_only_identifier_lists_from_p1(self):
        self.assertEqual(scope_from_p1_query(QUERY + '^ORDERBYsys_id'),
                         {'assignees': [AGENT], 'locations': [LOCATION]})
        for query in (QUERY.replace('priority=1', 'priority=2'), QUERY.replace(AGENT, 'SYNTHETIC_NAME'),
                      QUERY.replace(LOCATION, ''), QUERY + '^NQtask.priority=1', QUERY + '^ORactive=true',
                      QUERY + f'^task.locationIN{LOCATION}', QUERY.replace(AGENT, f'{AGENT},{AGENT.upper()}')):
            with self.subTest(query=query), self.assertRaises(DashboardReadError):
                scope_from_p1_query(query)

    def test_saves_both_lists_and_preserves_existing_config_on_failed_replace(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'dashboard-api.json'
            original = {'version': 1, 'assignees': ['1' * 32], 'locations': ['2' * 32], 'monthly_group': '3' * 32}
            path.write_text(json.dumps(original), encoding='utf-8')
            scope = scope_from_p1_query(QUERY)
            with patch('neto_incident_monitor.config_io.save_json', side_effect=OSError('SYNTHETIC_SECRET')):
                with self.assertRaises(DashboardReadError) as error:
                    save_dashboard_scope(scope, path)
            self.assertEqual(error.exception.reason, 'dashboard_scope_save')
            self.assertEqual(load_config(path), original)
            save_dashboard_scope(scope, path)
            self.assertEqual(dashboard_scope(load_config(path)), scope)
            self.assertEqual(load_config(path)['monthly_group'], original['monthly_group'])

    def test_packaged_defaults_work_before_the_first_local_save(self):
        with TemporaryDirectory() as folder:
            seed = Path(folder) / 'default.json'
            local = Path(folder) / 'profile' / 'dashboard-api.json'
            defaults = {'version': 1, 'lost_excluded_group': '3' * 32}
            previous_bundle = {**defaults, 'assignees': [AGENT], 'locations': [LOCATION]}
            seed.write_text(json.dumps(previous_bundle), encoding='utf-8')
            scope = {'assignees': ['1' * 32], 'locations': ['2' * 32]}

            with (patch('neto_incident_monitor.analytics_config.PACKAGED_CONFIG', seed),
                  patch('neto_incident_monitor.analytics_config.CONFIG_PATH', local),
                  patch('neto_incident_monitor.analytics_config.FROZEN', True)):
                self.assertEqual(load_config(), defaults)
                self.assertFalse(local.exists())
                save_dashboard_scope(scope)
                self.assertEqual(load_config(local), {'version': 1, **scope})
                self.assertEqual(load_config(), {**defaults, **scope})
                local.write_text(json.dumps({'version': 1, **scope, 'monthly_group': '4' * 32}), encoding='utf-8')
                self.assertEqual(load_config(), {**defaults, **scope, 'monthly_group': '4' * 32})
                local.write_text('{invalid', encoding='utf-8')
                with self.assertRaises(DashboardReadError):
                    load_config()
                self.assertEqual(local.read_text(encoding='utf-8'), '{invalid')
            self.assertEqual(json.loads(seed.read_text(encoding='utf-8')), previous_bundle)

    def test_p1_with_no_records_refreshes_both_lists_on_the_shared_card(self):
        classic = '/task_sla_list.do?sysparm_tiny=fixture'
        drilldown = CLASSIC_PREFIX + quote(classic.lstrip('/'), safe='')
        category = '''<sn-component-filter><span>{name}</span>
        <label><input type="checkbox">Wybierz wszystko</label>
        <button>Zastosuj</button></sn-component-filter>'''
        dashboard = category.format(name='Lokalizacja') + category.format(name='Przypisany do') + '''
        <button aria-label="Zgłoszenia P1, 0, Wykres">0</button>
        <script>
        const categories = [...document.querySelectorAll('sn-component-filter')];
        const clicks = [0, 0];
        const applied = [false, false];
        categories.forEach((section, index) => {
            const checkbox = section.querySelector('input');
            checkbox.indeterminate = index === 0;
            checkbox.addEventListener('change', () => {
                clicks[index]++;
                checkbox.checked = index === 0 ? clicks[index] === 2 : clicks[index] === 1;
            });
            section.querySelector('button').addEventListener('click', () => {
                applied[index] = checkbox.checked;
            });
        });
        document.querySelector('[aria-label]').addEventListener('click', () => {
            if (clicks.join(',') === '2,1' && applied.every(Boolean)) location.href = ''' + json.dumps(drilldown) + ''';
        });
        </script>'''
        with TemporaryDirectory() as folder, sync_playwright() as playwright:
            path = Path(folder) / 'dashboard-api.json'
            path.write_text('{"version": 1}', encoding='utf-8')
            browser = playwright.chromium.launch()
            page = browser.new_page()

            def route(response):
                url = response.request.url
                if url == DASHBOARD_URL:
                    body = dashboard
                elif urlsplit(url).path == drilldown:
                    body = f'<iframe id="gsft_main" name="gsft_main" src="{classic}"></iframe>'
                elif urlsplit(url).path == '/task_sla_list.do':
                    body = f'<table glide_table="task_sla" query="{QUERY}"><tbody></tbody></table>'
                else:
                    body = '<title>Shared session</title>'
                response.fulfill(content_type='text/html; charset=utf-8', body=body)

            page.context.route('**/*', route)
            page.goto(HOME)
            runtime = Mock(debug_show_browser=False)
            runtime.window.is_hidden.return_value = True
            account = object()
            session = Mock(runtime=runtime, layout_account=account, active_job=Mock(id=17))
            part = ReadPart('dashboard_scope', account, {})
            with (patch('neto_incident_monitor.analytics_config.CONFIG_PATH', path),
                  patch('neto_incident_monitor.dashboard_scope.LoginDiagnostics') as diagnostics):
                self.assertTrue(refresh_scope(session, page, part, Event()))
            self.assertEqual(dashboard_scope(load_config(path)), {'assignees': [AGENT], 'locations': [LOCATION]})
            self.assertEqual(page.context.pages, [page])
            self.assertEqual(page.url, HOME)
            log = str(diagnostics.return_value.record.call_args_list)
            self.assertIn('rendering_start', log)
            self.assertIn('rendering_stop', log)
            self.assertNotIn(AGENT, log)
            self.assertNotIn(LOCATION, log)
            browser.close()
