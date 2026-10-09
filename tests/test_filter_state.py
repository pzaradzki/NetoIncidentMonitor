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
    def test_monitor_pipeline_scopes_notifications_and_ignores_failed_reads(self):
        from neto_incident_monitor.app import App
        with tempfile.TemporaryDirectory() as folder:
            app = App.__new__(App)
            app.events = queue.Queue()
            app.stop = threading.Event()
            app.schedule = Mock()
            app.schedule.wait.return_value = True
            app.filters = [{"name": "A", "url": "https://example.test/a"},
                           {"name": "B", "url": "https://example.test/b"}]
            app.disabled_filter_urls = frozenset()
            app.history = History(Path(folder)/"history.json")
            settings = {"urls": [entry["url"] for entry in app.filters], "filters": app.filters, "interval": 60}
            page = Mock()
            page.is_closed.return_value = False
            context = Mock()
            context.pages = [page]
            playwright = MagicMock()
            playwright.__enter__.return_value.chromium.launch_persistent_context.return_value = context
            incident = {"number": "INC1", "url": "https://example.test/incident"}

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
            incident = {"number": "INC1", "url": "https://example.test/incident"}
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
