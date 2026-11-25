import json
import queue
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from neto_incident_monitor.app import App
from neto_incident_monitor.dashboard_context import DashboardReadError
from neto_incident_monitor.filter_layouts import read_account
from neto_incident_monitor.filter_metadata import metadata_from_address
from neto_incident_monitor.filter_state import FilterState
from neto_incident_monitor.history import History
from neto_incident_monitor.monitoring import Schedule
from neto_incident_monitor.read_errors import AuthenticationRequired, Cancelled
from neto_incident_monitor.shared_session import SharedSession


class ScheduledFilterStateTests(unittest.TestCase):
    def configure_filters(self, urls):
        folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.clock = 100
        app = self.app = App.__new__(App)
        app.events = queue.Queue()
        app.schedule = Schedule()
        app.browser_runtime = None
        app.filter_revisions = {url: object() for url in urls}
        app.monitor_generation = object()
        app.disabled_filter_urls = frozenset()
        app.history = History(folder / 'history.json')
        session = self.session = app.session = SharedSession(app, folder / 'profile')
        session.connected = True
        session.log = Mock()
        self.page = Mock()
        self.page.is_closed.return_value = False
        self.page.evaluate.return_value = ['f' * 32, 'pl']
        session.layout_account = read_account(self.page, session.closed)
        app.filters = [{'name': str(index), 'url': url, 'list_definition': dict(
            metadata_from_address(url), version=2, source_url=url, account=session.layout_account.key,
        )} for index, url in enumerate(urls, 1)]
        app.update_session_filters()
        columns = [{'key': 'number', 'field': 'number', 'label': 'Numer'}]
        self.enterContext(patch.object(session, 'filter_layout', return_value=columns))
        self.enterContext(patch('neto_incident_monitor.app.STATE', folder / 'seen.json'))
        self.enterContext(patch('neto_incident_monitor.shared_session.authentication_required', return_value=False))
        self.enterContext(patch('neto_incident_monitor.shared_session.monotonic', side_effect=lambda: self.clock))
        app_time = self.enterContext(patch('neto_incident_monitor.app.time', wraps=time))
        app_time.monotonic.side_effect = lambda: self.clock

    def run_cycle(self, batches=1):
        waits = []

        def wait(_page, _schedule, seconds, _stop):
            waits.append(seconds)
            if len(waits) == batches:
                raise Cancelled()
            self.clock += seconds

        self.session.start_cycle([], {'inc': 60, 'task': 120})
        with patch('neto_incident_monitor.browser_actions.wait_for_browser_cycle', side_effect=wait), self.assertRaises(Cancelled):
            self.session.serve(self.page)
        return waits

    def test_session_expiry_after_successful_filter_read_reauthenticates(self):
        url = 'https://adeo.service-now.com/incident_list.do?sysparm_query=active=true'
        self.configure_filters([url])
        with patch.object(self.session, 'authenticate', return_value=True) as login, \
                patch('neto_incident_monitor.filter_api.read_filter_records',
                      side_effect=[{}, AuthenticationRequired(), {}]) as read:
            self.assertEqual(self.run_cycle(batches=2), [60, 60])
        self.assertEqual(read.call_count, 3)
        self.assertTrue(all(call.args[0] is self.page for call in read.call_args_list))
        login.assert_called_once()
        events = list(self.app.events.queue)
        self.assertTrue(any(kind == 'session_expired' for kind, _ in events))
        self.assertEqual(sum(kind == 'snapshot' for kind, _ in events), 2)

    def test_separate_incident_and_task_intervals(self):
        urls = ['https://adeo.service-now.com/incident_list.do?sysparm_query=active=true',
                'https://adeo.service-now.com/sc_task_list.do?sysparm_query=active=true']
        self.configure_filters(urls)
        with patch('neto_incident_monitor.filter_api.read_filter_records', return_value={}) as read:
            self.assertEqual(self.run_cycle(batches=3), [60, 60, 60])
        self.assertEqual([call.args[3]['source_url'] for call in read.call_args_list],
                         [urls[index] for index in (0, 1, 0, 0, 1)])

    def test_monitor_pipeline_scopes_notifications_and_ignores_failed_reads(self):
        url_a, url_b = [f'https://adeo.service-now.com/incident_list.do?sysparm_query=priority={value}'
                        for value in (1, 2)]
        self.configure_filters([url_a, url_b])
        history = self.app.history
        self.app.alert_writer = Mock()
        self.app.submit_alert_delivery = Mock()
        self.app.prepare_filter_alerts = Mock(side_effect=lambda url, _name, _incidents: [{'filter_url': url}])
        present = {'INC1': {'number': 'INC1', 'url': 'https://example.test/incident'}}

        def cycle(a, b):
            before = {key for key, _ in history.pending_alerts()}
            with patch('neto_incident_monitor.filter_api.read_filter_records', side_effect=[a, b]):
                self.run_cycle()
            return [job['filter_url'] for key, job in history.pending_alerts() if key not in before]

        self.assertEqual(cycle(RuntimeError('synthetic first read failure'), {}), [])
        self.assertEqual(cycle(present, {}), [])
        self.assertEqual(cycle(present, present), [url_b])
        before = history.snapshot(url_a)
        self.assertEqual(cycle(DashboardReadError('api_filter_mismatch', retryable=False), present), [])
        self.assertEqual(history.snapshot(url_a), before)
        self.assertEqual(cycle(present, present), [])
        self.assertEqual(cycle({}, present), [])
        self.assertEqual(cycle(present, present), [url_a])
        self.app.filters[0]['first_only'] = True
        self.assertEqual(cycle({}, {}), [])
        self.assertEqual(cycle(present, {}), [url_a])


class FilterStateTests(unittest.TestCase):
    def test_notification_baseline_survives_restart_and_is_independent_per_filter(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'seen.json'
            state = FilterState(path)
            initial = {f'INC{i}' for i in range(500)}
            self.assertEqual(state.arrivals('A', initial), initial)  # History is populated.
            self.assertEqual(state.notification_arrivals('A', initial), set())
            with patch.object(Path, 'write_text', side_effect=OSError('fixture')):
                with self.assertRaises(OSError):
                    state.commit('A', initial)
            self.assertEqual(state.notification_arrivals('A', initial), set())
            state.commit('A', initial)
            state = FilterState(path)
            self.assertEqual(state.notification_arrivals('A', initial | {'INC_NEW'}), {'INC_NEW'})
            self.assertEqual(state.notification_arrivals('B', initial | {'INC_NEW'}), set())
            state.commit('B', set())
            state = FilterState(path)
            self.assertEqual(state.notification_arrivals('B', {'INC_NEW'}), {'INC_NEW'})
            state.commit('A', set())
            self.assertEqual(state.notification_arrivals('A', {'INC1'}), {'INC1'})

    def test_independent_arrivals_and_return_after_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "seen.json"
            state = FilterState(path)
            self.assertEqual(state.arrivals("A", {"INC1"}), {"INC1"})
            state.commit("A", {"INC1"})
            self.assertEqual(state.arrivals("B", {"INC1"}), {"INC1"})
            state = FilterState(path)
            self.assertEqual(state.arrivals("A", {"INC1"}), set())
            state.commit("A", set())
            state = FilterState(path)
            self.assertEqual(state.arrivals("A", {"INC1"}), {"INC1"})
            state.commit("A", {"INC1"})
            self.assertEqual(state.arrivals("A", {"INC1"}), set())

    def test_legacy_state_does_not_notify_again_on_upgrade(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "seen.json"
            path.write_text(json.dumps({"A": ["INC1"]}))
            state = FilterState(path)
            self.assertEqual(state.arrivals("A", {"INC1"}), set())
            state.commit("A", set())
            self.assertEqual(FilterState(path).arrivals("A", {"INC1"}), {"INC1"})

    def test_history_is_scoped_and_survive_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "history.json"
            history = History(path)
            incident = {"number": "INC1", "url": "https://adeo.service-now.com/incident"}
            history.add(incident, "Filter A", "A")
            history.add(incident, "Filter B", "B")
            history = History(path)
            history.add(incident, "Filter A", "A", reappeared=True)
            history.clear("A")
            self.assertEqual(history.snapshot("A"), {})
            self.assertIn("INC1", History(path).snapshot("B"))

    def test_legacy_history_is_split_without_losing_records(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "history.json"
            path.write_text(json.dumps({"INC1": {"incident": {"number": "INC1"},
                "read": True, "detected": 123, "filters": {"A": "A", "B": "B"}}}))
            history = History(path)
            self.assertIn("INC1", History(path).snapshot("A"))
            history.clear("A")
