import json
from pathlib import Path
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

from playwright.sync_api import TimeoutError

from tests.test_filter_api import filter_definition

from neto_incident_monitor.app import App
from neto_incident_monitor.dashboard import TITLES, HELD_TITLES, REQUEST_TITLES
from neto_incident_monitor.filter_layouts import read_account
from neto_incident_monitor.filter_metadata import metadata_from_address
from neto_incident_monitor.read_errors import AuthenticationRequired
from neto_incident_monitor.threatened import KEYS


class UpdateOrderTests(unittest.TestCase):
    def run_shared_cycle(self, *, manual=False, dashboard=True, dashboard_error=False, recover_login=False):
        filters = [
            {'name': 'INC', 'url': 'https://adeo.service-now.com/incident_list.do?sysparm_query=active%3Dtrue'},
            {'name': 'SCTASK', 'url': 'https://adeo.service-now.com/sc_task_list.do?sysparm_query=active%3Dtrue'},
            {'name': 'REQ', 'url': 'https://adeo.service-now.com/sc_request_list.do?sysparm_query=active%3Dtrue',
             'enabled': False},
        ]
        order = []
        page = Mock()
        page.is_closed.return_value = False
        page.evaluate.return_value = ['f' * 32, 'pl']
        page.wait_for_timeout.side_effect = lambda milliseconds: time.sleep(milliseconds / 1000)

        def reader(name, result):
            def read(*_args):
                order.append(name)
                return result
            return read

        def read_filter(_page, _stop, _diagnostics, definition):
            order.append(definition['table'])
            return {}

        month = ValueError('Synthetic dashboard failure') if dashboard_error else dict.fromkeys(TITLES, 0)
        monthly_reads = iter([TimeoutError('Synthetic timeout'), AuthenticationRequired(), month]
                             if recover_login else [month])

        def read_month(*_args):
            order.append('sla')
            result = next(monthly_reads)
            if isinstance(result, Exception):
                raise result
            return result

        def authenticate(*_args):
            order.append('login')
            return True

        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            config = folder / 'config.json'
            config.write_text(json.dumps({'filters': filters, 'dashboard_auto_refresh': dashboard}), encoding='utf-8')
            root = tk.Tk()
            root.withdraw()
            app = None
            try:
                with patch('neto_incident_monitor.app.CONFIG', config), \
                        patch('neto_incident_monitor.app.STATE', folder / 'seen.json'), \
                        patch('neto_incident_monitor.app.DATA', folder), \
                        patch('neto_incident_monitor.runtime_paths.DATA', folder), \
                        patch('neto_incident_monitor.shared_session.sync_playwright'), \
                        patch('neto_incident_monitor.shared_session.authentication_required', return_value=False), \
                        patch('neto_incident_monitor.analytics_config.load_config', return_value={
                            'assignees': ['a' * 32], 'locations': ['b' * 32]}), \
                        patch('neto_incident_monitor.dashboard_api.read_month', side_effect=read_month), \
                        patch('neto_incident_monitor.dashboard_api.read_held', side_effect=reader('held', dict.fromkeys(HELD_TITLES, 0))), \
                        patch('neto_incident_monitor.dashboard_api.read_requests', side_effect=reader('requests', dict.fromkeys(REQUEST_TITLES, 0))), \
                        patch('neto_incident_monitor.threatened_api.read_threats', side_effect=reader('threatened', (dict.fromkeys(KEYS, 0), {}))), \
                        patch('neto_incident_monitor.filter_api.read_filter_records', side_effect=read_filter):
                    app = App(root, history_path=folder / 'history.json', enable_tray=False,
                              apply_startup=False)
                    session = app.session
                    account = session.layout_account = read_account(page, session.closed)
                    for entry in app.filters:
                        url = entry['url']
                        entry['list_definition'] = dict(metadata_from_address(url), version=2, source_url=url,
                                                        instance=entry.get('filter_instance'), account=account.key)
                    session.open_and_serve = lambda _playwright: session.serve(page)
                    app.window_restoring = False
                    session.connected = session.ready_once = True
                    app.handle_session_event('session_ready', None)
                    with patch.object(session, 'filter_layout', return_value=filter_definition(filters[0]['url'])['columns']), \
                            patch.object(session, 'authenticate', side_effect=authenticate):
                        if manual:
                            self.assertTrue(app.request_refresh('all'))
                        else:
                            app.start()
                        self.assertEqual(app.dashboard_button.queued, manual or dashboard)
                        self.assertTrue(app.threatened_incidents_button.queued)
                        self.assertEqual(app.work_status.get(), 'Oczekuje w kolejce')
                        session.thread.start()
                        try:
                            deadline = time.monotonic() + 6
                            while session.last_idle is None and time.monotonic() < deadline:
                                root.update()
                                time.sleep(.01)
                            self.assertIsNotNone(session.last_idle, order)
                            app.drain()
                            self.assertEqual(app.cycle_active, not manual)
                            self.assertEqual(set(app.history.membership or ()), {entry['url'] for entry in filters[:2]})
                            self.assertIsNotNone(app.threatened_view.last_full_read)
                            expected_sections = {'sla', 'held', 'requests'} if manual or dashboard else set()
                            if dashboard_error:
                                expected_sections.remove('sla')
                            self.assertEqual(set(app.dashboard_view.section_snapshots), expected_sections)
                            self.assertEqual(app.dashboard_view.last_complete_read_at is not None,
                                             expected_sections == {'sla', 'held', 'requests'})
                        finally:
                            session.shutdown()
                            session.thread.join(3)
                        self.assertFalse(session.thread.is_alive())
            finally:
                if app is not None:
                    app.teams_sender.stop()
                    app.google_chat_sender.stop()
                    app.history_writer.shutdown(wait=True)
                    app.alert_writer.shutdown(wait=True)
                root.destroy()
        return order

    def test_startup_and_all_use_dashboard_then_threats_then_filters(self):
        for manual in (False, True):
            with self.subTest(manual=manual):
                order = self.run_shared_cycle(manual=manual, dashboard=not manual)
                self.assertEqual(order, ['sla', 'held', 'requests', 'threatened', 'incident', 'sc_task'])

    def test_no_startup_dashboard_request_skips_dashboard(self):
        order = self.run_shared_cycle(dashboard=False)
        self.assertEqual(order, ['threatened', 'incident', 'sc_task'])

    def test_dashboard_section_error_does_not_block_other_work(self):
        for manual in (False, True):
            with self.subTest(manual=manual):
                order = self.run_shared_cycle(manual=manual, dashboard_error=True)
                self.assertEqual(order, ['sla', 'held', 'requests', 'threatened', 'incident', 'sc_task'])

    def test_dashboard_login_recovery_finishes_before_threats_and_filters(self):
        order = self.run_shared_cycle(recover_login=True)
        self.assertEqual(order, ['sla', 'sla', 'login', 'sla', 'held', 'requests', 'threatened', 'incident', 'sc_task'])


if __name__ == '__main__':
    unittest.main()
