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

    def test_threatened_alerts_send_record_links_without_dashboard_footer(self):
        from neto_incident_monitor.teams_notifications import payload
        from neto_incident_monitor.threatened import THREATENED_URL

        app = self.app()
        app.alert_routes.return_value = dict.fromkeys(('teams', 'google_chat', 'windows'), ('revision', 'synthetic'))
        number = 'INC0000001'
        record_url = 'https://adeo.service-now.com/incident.do?sys_id=0123456789abcdef0123456789abcdef'
        incident = dict(number=number, url=record_url, deadline=0, categories=('P4',), remaining='15 godzin', percent=87.35)
        expected = f'{number} · P4 · Pozostało 15 godzin · 87,35%'

        for legacy in (False, True):
            with self.subTest(legacy=legacy):
                jobs = list(app.prepare_threatened_alerts([incident], request_id=1))
                for job in jobs:
                    self.assertEqual(job['message'], expected)
                    self.assertEqual(job['links'], {number: record_url})
                    if legacy:
                        job['message'] += '\n' + THREATENED_URL
                        job['links'][THREATENED_URL] = THREATENED_URL
                app.history.pending_alerts.return_value = [(str(i) * 32, job) for i, job in enumerate(jobs, 1)]

                with patch('neto_incident_monitor.teams_notifications.send') as teams, \
                        patch('neto_incident_monitor.google_chat_notifications.send') as chat, \
                        patch('plyer.notification.notify') as windows:
                    app.deliver_alerts()
                windows.assert_called_once()
                self.assertEqual(windows.call_args.kwargs['message'], expected)
                teams.assert_called_once()
                teams_text = payload(*teams.call_args.args[1:])['text']
                self.assertEqual(teams_text, f'Incydenty zagrożone SLA · 1<br><a href="{record_url}">{number}</a>{expected[len(number):]}')
                chat.assert_called_once()
                chat_text = chat.call_args.args[1]['text']
                self.assertEqual(chat_text, f'Incydenty zagrożone SLA · 1\n<{record_url}|{number}>{expected[len(number):]}')

    def test_long_queued_windows_alert_fits_utf16_buffers_and_logs_lengths_only(self):
        app = self.app()
        app.alert_routes.return_value = {'windows': ('revision', '')}
        app.history.pending_alerts.return_value = [('a'*32, dict(url='A', channel='windows',
            target='revision', title='ą' * 61 + '😀x', message='ż' * 253 + '😀PRIVATE_SECRET', links={}))]
        with patch('plyer.notification.notify') as notify, \
                self.assertLogs('neto.login_diagnostics', level='INFO') as logs:
            app.deliver_alerts()

        notify.assert_called_once_with(title='ą' * 61 + '…', message='ż' * 253 + '…',
                                       app_name='Neto Incident Monitor', timeout=10)
        app.history.transition_alert.assert_any_call('a'*32, 'sending', 'accepted')
        events = [json.loads(record.getMessage()) for record in logs.records]
        clipped = next(event for event in events if event['event'] == 'windows_notification_truncated')
        self.assertEqual(clipped['action_id'], 'a'*32)
        self.assertEqual(clipped['title_units'], 64)
        self.assertEqual(clipped['message_units'], 269)
        self.assertEqual((clipped['title_limit'], clipped['message_limit']), (63, 255))
        self.assertNotIn('PRIVATE_SECRET', '\n'.join(logs.output))

    def test_windows_text_at_exact_limits_is_kept(self):
        from neto_incident_monitor.windows_notifications import notify

        title = 'ą' * 61 + '😀'
        message = 'ż' * 253 + '😀'
        diagnostics = Mock()
        with patch('plyer.notification.notify') as sender:
            notify(title, message, timeout=15, diagnostics=diagnostics)
        sender.assert_called_once_with(title=title, message=message, app_name='Neto Incident Monitor', timeout=15)
        diagnostics.record.assert_not_called()

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
