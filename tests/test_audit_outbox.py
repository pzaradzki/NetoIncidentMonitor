from concurrent.futures import ThreadPoolExecutor
import json
import queue
import sqlite3
import threading
import unittest
from unittest.mock import Mock, patch

from neto_incident_monitor.app import App


class AuditOutboxTests(unittest.TestCase):
    def app(self):
        app = App.__new__(App)
        app.stop = Mock(wraps=threading.Event())
        app.stop.wait = Mock(return_value=False)
        app.events = queue.Queue()
        app.history = Mock()
        app.alert_routes = Mock(return_value={'teams': ('revision', 'synthetic')})
        app.history.pending_alerts.return_value = [('a'*32, dict(url='A', channel='teams',
            target='revision', title='Title', message='Message', links={}))]
        app.history.transition_alert.return_value = True
        return app

    def test_read_retries_are_bounded_cancelable_and_safe(self):
        app = self.app()
        app.history.pending_alerts.side_effect = sqlite3.OperationalError('PRIVATE_SECRET')
        with self.assertLogs('neto.login_diagnostics', level='INFO') as logs:
            app.deliver_alerts()
        self.assertEqual(app.history.pending_alerts.call_count, 3)
        self.assertEqual([c.args[0] for c in app.stop.wait.call_args_list], [1, 5])
        self.assertFalse(app.events.empty())
        self.assertNotIn('PRIVATE_SECRET', '\n'.join(logs.output))
        records = [json.loads(record.getMessage()) for record in logs.records]
        attempts = [r['attempt'] for r in records if 'attempt' in r]
        self.assertEqual(attempts, [1, 2, 3])
        self.assertEqual(len({r['run_id'] for r in records}), 1)
        self.assertEqual(len({r['read_id'] for r in records}), 1)
        self.assertTrue(any(r.get('delivery_stage') == 'worker' and r.get('delivery_outcome') == 'error' for r in records))
        app.history.transition_alert.assert_not_called()

    def test_success_after_read_retry_sends_once(self):
        app = self.app()
        jobs = app.history.pending_alerts.return_value
        app.history.pending_alerts.side_effect = [sqlite3.OperationalError(), jobs]
        with patch('neto_incident_monitor.teams_notifications.send') as send, \
                self.assertLogs('neto.login_diagnostics', level='INFO') as logs:
            app.deliver_alerts()
        send.assert_called_once()
        app.history.transition_alert.assert_any_call('a'*32, 'sending', 'accepted')
        records = [json.loads(record.getMessage()) for record in logs.records]
        finished = next(r for r in records if r.get('delivery_stage') == 'finish')
        self.assertEqual((finished['action_id'], finished['channel'], finished['accepted_parts']), ('a'*32, 'teams', 1))

    def test_state_failures_never_retry_post(self):
        for failure_at in ('start', 'finish'):
            app = self.app()
            app.history.transition_alert.side_effect = ([sqlite3.OperationalError('PRIVATE_SECRET')]
                if failure_at == 'start' else [True, sqlite3.OperationalError('PRIVATE_SECRET')])
            with patch('neto_incident_monitor.teams_notifications.send') as send:
                app.deliver_alerts()
            self.assertEqual(send.call_count, int(failure_at == 'finish'))
            self.assertFalse(app.events.empty())

    def test_stop_during_backoff_prevents_retry(self):
        app = self.app()
        app.history.pending_alerts.side_effect = sqlite3.OperationalError()
        app.stop.wait.return_value = True
        app.deliver_alerts()
        self.assertEqual(app.history.pending_alerts.call_count, 1)

    def test_every_submitted_future_is_observed(self):
        app = self.app()
        app.deliver_alerts = Mock(side_effect=RuntimeError('PRIVATE_SECRET'))
        with ThreadPoolExecutor(max_workers=1) as executor:
            app.alert_writer = executor
            future = app.submit_alert_delivery()
            self.assertIsNotNone(future.exception(timeout=2))
        self.assertFalse(app.events.empty())


if __name__ == '__main__':
    unittest.main()
