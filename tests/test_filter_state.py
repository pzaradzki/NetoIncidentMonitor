import json
import tempfile
import unittest
import queue
import threading
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path

from neto_incident_monitor.filter_state import FilterState
from neto_incident_monitor.history import History


class FilterStateTests(unittest.TestCase):
    def setUp(self):
        window = patch('neto_incident_monitor.browser_window.BrowserWindow')
        window.start()
        self.addCleanup(window.stop)

    def test_session_expiry_after_successful_filter_read_reauthenticates(self):
        from neto_incident_monitor.app import App
        from neto_incident_monitor.pagination import AuthenticationRequired
        with tempfile.TemporaryDirectory() as folder:
            app = App.__new__(App)
            app.stop = threading.Event()
            app.events = queue.Queue()
            app.schedule = Mock()
            app.schedule.woken_by_request = False
            url = 'https://adeo.service-now.com/incident_list.do'
            app.filters = [{'name': 'A', 'url': url}]
            app.disabled_filter_urls = frozenset()
            app.history = History(Path(folder) / 'history.json')
            page = Mock()
            page.is_closed.return_value = False
            context = Mock(pages=[page])
            playwright = MagicMock()
            playwright.__enter__.return_value.chromium.launch_persistent_context.return_value = context
            settings = {'urls': [url], 'filters': app.filters, 'interval': 60, 'task_interval': 60}
            with patch('playwright.sync_api.sync_playwright', return_value=playwright), \
                    patch('neto_incident_monitor.app.STATE', Path(folder) / 'seen.json'), \
                    patch('neto_incident_monitor.app.navigate'), \
                    patch.object(app, 'restore_login', return_value=True) as login, \
                    patch('neto_incident_monitor.app.read_all', side_effect=[({}, 1), AuthenticationRequired(), ({}, 1)]) as read, \
                    patch('neto_incident_monitor.app.wait_for_browser_cycle', side_effect=[False, False, True]):
                app.monitor(settings)
            self.assertEqual(read.call_count, 3)
            self.assertEqual(login.call_count, 2)  # Startup and session recovery.
            app.schedule.request.assert_called()
            phases = [value for kind, value in app.events.queue if kind == 'phase']
            self.assertIn('Oczekiwanie na logowanie', phases)
            self.assertNotIn('Błąd uruchomienia', phases)
            self.assertEqual(sum(kind == 'snapshot' for kind, _ in app.events.queue), 2)

    def test_separate_incident_and_task_intervals(self):
        from neto_incident_monitor.app import App
        with tempfile.TemporaryDirectory() as folder:
            app = App.__new__(App)
            app.events = queue.Queue()
            app.stop = threading.Event()
            app.schedule = Mock()
            app.schedule.woken_by_request = False
            clock = [100]
            waits = []
            def wait(seconds, stop):
                waits.append(seconds)
                clock[0] += seconds
                return len(waits) == 3
            app.schedule.wait.side_effect = wait
            app.filters = [{"name": "INC", "url": "https://adeo.service-now.com/incident_list.do"},
                           {"name": "TASK", "url": "https://adeo.service-now.com/sc_task_list.do"}]
            app.disabled_filter_urls = frozenset()
            app.history = History(Path(folder)/"history.json")
            settings = {"urls": [f["url"] for f in app.filters], "filters": app.filters,
                        "interval": 60, "task_interval": 120}
            page = Mock()
            page.is_closed.return_value = False
            context = Mock(pages=[page])
            playwright = MagicMock()
            playwright.__enter__.return_value.chromium.launch_persistent_context.return_value = context
            with patch("playwright.sync_api.sync_playwright", return_value=playwright), \
                 patch("neto_incident_monitor.app.STATE", Path(folder)/"seen.json"), \
                 patch("neto_incident_monitor.app.navigate"), \
                 patch("neto_incident_monitor.app.wait_for_login", return_value=True), \
                 patch("neto_incident_monitor.app.wait_for_browser_cycle", side_effect=lambda page, schedule, seconds, stop: schedule.wait(seconds, stop)), \
                 patch("neto_incident_monitor.app.time.monotonic", side_effect=lambda: clock[0]), \
                 patch("neto_incident_monitor.app.read_all", return_value=({}, 1)) as read:
                app.monitor(settings)
            self.assertEqual([call.args[1] for call in read.call_args_list],
                             [settings["urls"][i] for i in (0, 1, 0, 0, 1)])
            self.assertEqual(waits, [60, 60, 60])

    def test_monitor_pipeline_scopes_notifications_and_ignores_failed_reads(self):
        from neto_incident_monitor.app import App
        with tempfile.TemporaryDirectory() as folder:
            app = App.__new__(App)
            app.events = queue.Queue()
            app.stop = threading.Event()
            app.schedule = Mock()
            app.schedule.wait.return_value = True
            app.filters = [{"name": "A", "url": "https://adeo.service-now.com/incident_list.do?fixture=a"},
                           {"name": "B", "url": "https://adeo.service-now.com/incident_list.do?fixture=b"}]
            app.disabled_filter_urls = frozenset()
            app.history = History(Path(folder)/"history.json")
            settings = {"urls": [entry["url"] for entry in app.filters], "filters": app.filters, "interval": 60}
            page = Mock()
            page.is_closed.return_value = False
            context = Mock()
            context.pages = [page]
            playwright = MagicMock()
            playwright.__enter__.return_value.chromium.launch_persistent_context.return_value = context
            incident = {"number": "INC1", "url": "https://adeo.service-now.com/incident"}

            def cycle(a, b):
                reads = [a if isinstance(a, Exception) else (a, 1), (b, 1)]
                with patch("playwright.sync_api.sync_playwright", return_value=playwright), \
                     patch("neto_incident_monitor.app.STATE", Path(folder)/"seen.json"), \
                     patch("neto_incident_monitor.app.navigate"), \
                     patch("neto_incident_monitor.app.wait_for_login", return_value=True), \
                     patch("neto_incident_monitor.app.read_all", side_effect=reads):
                    app.monitor(settings)
                events = []
                while not app.events.empty():
                    kind, value = app.events.get()
                    if kind == "filter_notification":
                        events.append(value[0])
                return events

            self.assertEqual(cycle({"INC1": dict(incident)}, {}), [settings["urls"][0]])
            self.assertEqual(cycle({"INC1": dict(incident)}, {"INC1": dict(incident)}), [settings["urls"][1]])
            self.assertEqual(cycle(RuntimeError("read failed"), {"INC1": dict(incident)}), [])
            self.assertEqual(cycle({"INC1": dict(incident)}, {"INC1": dict(incident)}), [])
            self.assertEqual(cycle({}, {"INC1": dict(incident)}), [])
            self.assertEqual(cycle({"INC1": dict(incident)}, {"INC1": dict(incident)}), [settings["urls"][0]])
            app.filters[0]["first_only"] = True
            cycle({}, {})
            self.assertEqual(cycle({"INC1": dict(incident)}, {}), [])

    def test_independent_arrivals_restart_return_and_first_only(self):
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
            self.assertEqual(state.arrivals("A", {"INC1"}, True), set())
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

    def test_history_and_read_status_are_scoped_and_survive_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "history.json"
            history = History(path)
            incident = {"number": "INC1", "url": "https://adeo.service-now.com/incident"}
            history.add(incident, "Filter A", "A")
            history.add(incident, "Filter B", "B")
            history.mark_read(["INC1"], "A")
            history = History(path)
            self.assertTrue(history.snapshot("A")["INC1"]["read"])
            self.assertFalse(history.snapshot("B")["INC1"]["read"])
            history.add(incident, "Filter A", "A", reappeared=True)
            self.assertFalse(history.snapshot("A")["INC1"]["read"])
            history.clear("A")
            self.assertEqual(history.snapshot("A"), {})
            self.assertIn("INC1", History(path).snapshot("B"))

    def test_legacy_history_is_split_without_losing_records(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "history.json"
            path.write_text(json.dumps({"INC1": {"incident": {"number": "INC1"},
                "read": True, "detected": 123, "filters": {"A": "A", "B": "B"}}}))
            history = History(path)
            history.mark_read([], "A")
            self.assertIn("INC1", History(path).snapshot("A"))
            history.clear("A")
            self.assertTrue(history.snapshot("B")["INC1"]["read"])
