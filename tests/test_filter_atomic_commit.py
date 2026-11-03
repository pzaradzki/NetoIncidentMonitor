import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from neto_incident_monitor.filter_state import FilterState
from neto_incident_monitor.history import History


class FilterAtomicCommitTests(unittest.TestCase):
    def test_migration_survives_separate_process_and_preserves_legacy_files(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'history.json'
            legacy_path = path.with_name('seen.json')
            legacy = FilterState(legacy_path)
            legacy.commit('A', {'INC1'})
            history = History(path)
            history.add({'number': 'INC1'}, 'Filter', 'A')
            history.mark_read({'INC1'}, 'A')
            old_history, old_membership = path.read_bytes(), legacy_path.read_bytes()
            notifications = history.commit_filter(legacy, 'A', 'Filter', {'INC1': {'number': 'INC1'}}, False, lambda: None)
            self.assertEqual(notifications, set())
            script = ("from neto_incident_monitor.history import History; import sys, json;"
                      "h=History(sys.argv[1]); print(json.dumps([h.membership,h.snapshot('A')]))")
            output = subprocess.check_output([sys.executable, '-c', script, str(path)], text=True)
            membership, records = json.loads(output)
            self.assertEqual(membership['A']['present'], ['INC1'])
            self.assertTrue(records['INC1']['read'])
            self.assertEqual(path.read_bytes(), old_history)
            self.assertEqual(legacy_path.read_bytes(), old_membership)

    def test_stop_detected_inside_transaction_rolls_back_everything(self):
        from neto_incident_monitor.pagination import Cancelled

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'history.json'
            history = History(path)
            legacy = FilterState(path.with_name('seen.json'))
            history.commit_filter(legacy, 'A', 'Filter', {'INC1': {'number': 'INC1'}}, False, lambda: None)
            calls = 0

            def checkpoint():
                nonlocal calls
                calls += 1
                if calls == 3:
                    raise Cancelled()

            with self.assertRaises(Cancelled):
                history.commit_filter(None, 'A', 'Filter', {'INC2': {'number': 'INC2'}}, False, checkpoint)
            self.assertEqual(set(History(path).snapshot('A')), {'INC1'})
            self.assertEqual(History(path).membership['A']['present'], ['INC1'])

    def test_failed_transaction_keeps_both_history_and_presence_in_previous_generation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'history.json'
            legacy_path = path.with_name('seen.json')
            legacy = FilterState(legacy_path)
            history = History(path)
            history.commit_filter(legacy, 'A', 'Filter', {'INC1': {'number': 'INC1'}}, False, lambda: None)
            before = history.store.read_bytes()
            write_changes = history._write_changes

            def fail_after_history(db, table, previous, current):
                if table == 'membership':
                    raise OSError('synthetic failure')
                write_changes(db, table, previous, current)

            with patch.object(history, '_write_changes', side_effect=fail_after_history):
                with self.assertRaises(OSError):
                    history.commit_filter(legacy, 'A', 'Filter', {'INC2': {'number': 'INC2'}}, False, lambda: None)
            reopened = History(path)
            self.assertEqual(history.store.read_bytes(), before)
            self.assertEqual(set(reopened.snapshot('A')), {'INC1'})
            self.assertEqual(reopened.membership['A']['present'], ['INC1'])
            reopened.clear('A')
            self.assertEqual(History(path).membership['A']['present'], ['INC1'])

class FilterEventGenerationTests(unittest.TestCase):
    def test_stale_result_after_toggle_or_restart_is_discarded(self):
        import queue
        from types import SimpleNamespace
        from unittest.mock import Mock
        from neto_incident_monitor.app import App

        generation, revision = object(), object()
        app = SimpleNamespace(instance=None, events=queue.Queue(),
                              monitor_generation=generation, filter_revisions={'A': revision},
                              event_filter_index=Mock(), quit_app=Mock())
        app.events.put(('snapshot', ('A', {}, object(), generation)))
        app.events.put(('snapshot', ('A', {}, revision, object())))
        app.events.put(('quit', None))
        App.drain(app)
        app.event_filter_index.assert_not_called()
        app.quit_app.assert_called_once()

class NotificationRouteGuardTests(unittest.TestCase):
    def test_queued_job_cannot_send_after_target_change_disable_or_restart(self):
        import threading
        from types import SimpleNamespace
        from neto_incident_monitor.app import App
        from neto_incident_monitor.template_library import resolve

        app = SimpleNamespace(stop=threading.Event(), monitor_generation=object(), filter_revisions={})
        target = 'synthetic-previous-destination'
        settings = {'teams_enabled': True, 'teams_webhook': target, 'filters': [{'url': 'A'}]}
        allow = App.notification_guard(app, 'A', 'teams', target, resolve({}, {}))
        with patch('neto_incident_monitor.secret_config.load_config', return_value=settings):
            self.assertTrue(allow())
            settings['teams_webhook'] = 'synthetic-new-destination'
            self.assertFalse(allow())
            settings['teams_webhook'] = target
            settings['filters'][0]['enabled'] = False
            self.assertFalse(allow())
            settings['filters'][0]['enabled'] = True
            app.stop.set()
            self.assertFalse(allow())
            app.stop.clear()
            app.monitor_generation = object()
            self.assertFalse(allow())

class DurableAlertTests(unittest.TestCase):
    def test_restart_preserves_pending_and_does_not_retry_sending(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.json"
            history = History(path)
            legacy = FilterState(path.with_name("seen.json"))
            history.commit_filter(legacy, "A", "Filter", {}, False, lambda: None)
            history.commit_filter(None, "A", "Filter", {"INC1": {"number": "INC1"}},
                                  False, lambda: None,
                                  prepare_alerts=lambda _: [{"channel": "teams"}, {"channel": "windows"}])
            first, second = history.pending_alerts()
            self.assertTrue(history.transition_alert(first[0], "pending", "sending"))
            reopened = History(path)
            self.assertEqual(reopened.pending_alerts(recover=True), [second])
            self.assertFalse(reopened.transition_alert(first[0], "pending", "sending"))

    def test_changed_route_and_partial_failure_are_not_retried(self):
        import queue
        import threading
        from types import SimpleNamespace
        from neto_incident_monitor.app import App

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.json"
            history = History(path)
            history.commit_filter(FilterState(path.with_name("seen.json")), "A", "Filter",
                                  {}, False, lambda: None)
            job = dict(url="A", channel="teams", title="Alert", message="Test", links={})
            history.commit_filter(None, "A", "Filter", {"INC1": {"number": "INC1"}},
                                  False, lambda: None,
                                  prepare_alerts=lambda _: [dict(job, target="old"), dict(job, target="current")])
            app = SimpleNamespace(history=history, stop=threading.Event(), events=queue.Queue(),
                                  alert_routes=lambda _: {"teams": ("current", "synthetic")})
            with patch("neto_incident_monitor.teams_notifications.message_chunks", return_value=["one", "two"]), \
                 patch("neto_incident_monitor.teams_notifications.send", side_effect=[None, OSError()]) as send:
                App.deliver_alerts(app)
                app.history = History(path)
                App.deliver_alerts(app, recover=True)
                self.assertEqual(send.call_count, 2)
                self.assertEqual(send.call_args_list[0].args[2], "one")
            self.assertEqual(app.history.pending_alerts(), [])
            self.assertIn("1", app.events.get_nowait()[1])

class NotificationRevisionTests(unittest.TestCase):
    def test_revision_changes_when_settings_return_to_previous_values(self):
        from neto_incident_monitor.secret_config import load_config, save_config

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            save_config(path, {"notify": True})
            first = load_config(path, {})["notification_revision"]
            save_config(path, {"notify": True, "window_geometry": "800x600"})
            self.assertEqual(load_config(path, {})["notification_revision"], first)
            save_config(path, {"notify": False})
            save_config(path, {"notify": True})
            self.assertNotEqual(load_config(path, {})["notification_revision"], first)

class ShutdownWriteTests(unittest.TestCase):
    def test_window_stays_open_until_queued_writes_finish(self):
        from concurrent.futures import Future
        from unittest.mock import Mock
        from neto_incident_monitor.app import App

        app = App.__new__(App)
        app.worker = None
        app.tray = None
        app.root = Mock()
        app.status = Mock()
        app.history_writer = Mock()
        app.alert_writer = Mock()
        history_done = Future()
        alerts_done = Future()
        app.history_writer.submit.return_value = history_done
        app.alert_writer.submit.return_value = alerts_done

        app.finish_quit()
        app.root.destroy.assert_not_called()
        history_done.set_result(None)
        app.finish_quit()
        app.root.destroy.assert_not_called()
        alerts_done.set_result(None)
        app.finish_quit()
        app.root.destroy.assert_called_once()
        app.history_writer.submit.assert_called_once()
        app.alert_writer.submit.assert_called_once()
