import json
import queue
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from neto_incident_monitor import google_chat_notifications as chat
from neto_incident_monitor.app import App
from neto_incident_monitor.teams_notifications import incident_text

URL = 'https://chat.googleapis.com/v1/spaces/AAAA_test/messages?key=test-key&token=test-secret'


class GoogleChatTests(unittest.TestCase):
    def test_only_complete_google_chat_https_webhooks_are_accepted(self):
        self.assertEqual(chat.validate_webhook(' ' + URL + ' '), URL)
        for value in (URL.replace('https:', 'http:'), URL.replace('googleapis.com', 'googleapis.com.evil.test'),
                      URL.replace('/messages', '/other'), URL.split('?')[0], URL + '&token=second',
                      URL.replace('token=test-secret', 'token='), URL.replace('chat.googleapis.com', 'user@chat.googleapis.com'),
                      URL.replace('chat.googleapis.com', 'chat.googleapis.com:bad'), URL + '#fragment'):
            with self.subTest(value=value), self.assertRaises(ValueError) as error:
                chat.validate_webhook(value)
            self.assertNotIn('test-secret', str(error.exception))

    def test_incident_and_task_links_and_formats(self):
        records = [{'number': 'INC123', 'location': 'Store', 'short_description': 'Printer'},
                   {'number': 'SCTASK456', 'short_description': 'Laptop', 'requested_for': 'Anna'}]
        _, message = incident_text(records)
        link = 'https://adeo.service-now.com/incident.do?sys_id=123&view=default'
        task_link = link.replace('/incident.do', '/sc_task.do')
        result = chat.payloads('Filter', message, {'INC123': link, 'SCTASK456': task_link})[0]['text']
        self.assertIn(f'<{link}|INC123> - Store - Printer', result)
        self.assertIn(f'<{task_link}|SCTASK456> - Laptop - Anna', result)
        unsafe = chat.payloads('<users/all>', 'INC123 - <users/all>', {'INC123': 'javascript:alert(1)'})[0]['text']
        self.assertNotIn('<users/all>', unsafe)
        self.assertNotIn('javascript', unsafe)

    def test_large_unicode_batches_are_split_without_losing_record_numbers(self):
        records = [{'number': f'INC{i:07}', 'short_description': 'Zażółć 😀 ' * 30} for i in range(200)]
        _, message = incident_text(records)
        contents = chat.payloads('Filtr', message)
        self.assertGreater(len(contents), 1)
        self.assertTrue(all(len(item['text'].encode('utf-8')) < 28000 for item in contents))
        combined = '\n'.join(item['text'] for item in contents)
        for record in records:
            self.assertEqual(combined.count(record['number']), 1)
        long_line = chat.payloads('X' * 1000, 'SCTASK123 - ' + '😀' * 30000,
                                  {'SCTASK123': 'https://adeo.service-now.com/' + '😀' * 3900})
        self.assertTrue(all(len(item['text'].encode('utf-8')) < 28000 for item in long_line))
        quoted = chat.payloads('Title', '\n'.join('INC123 - ' + '"' * 5990 for _ in range(20)))
        self.assertTrue(all(len(json.dumps(item, ensure_ascii=False).encode('utf-8')) < 32000 for item in quoted))

    def test_post_and_failures_never_expose_webhook_or_response_body(self):
        response = Mock(status=200)
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch.object(chat, 'build_opener') as opener:
            opener.return_value.open.return_value = response
            chat.send(URL, {'text': 'Hello'})
            request = opener.return_value.open.call_args.args[0]
            self.assertEqual(request.get_method(), 'POST')
            self.assertEqual(json.loads(request.data), {'text': 'Hello'})
            opener.return_value.open.side_effect = HTTPError(URL, 403, 'test-secret', {}, None)
            with self.assertRaises(RuntimeError) as error:
                chat.send(URL, {'text': 'Hello'})
            self.assertIn('403', str(error.exception))
            self.assertNotIn('test-secret', str(error.exception))
            opener.return_value.open.side_effect = OSError(URL)
            with self.assertRaises(RuntimeError) as error:
                chat.send(URL, {'text': 'Hello'})
            self.assertNotIn('test-secret', str(error.exception))
        self.assertIsNone(chat.NoRedirect().redirect_request(None, None, None, None, None, None))

    def test_sender_rate_limits_chunks_and_reports_test_result(self):
        sender = chat.Sender.__new__(chat.Sender)
        sender.events = queue.Queue()
        sender.next_send = 0
        with patch.object(chat, 'payloads', return_value=[{'text': 'one'}, {'text': 'two'}]), \
             patch.object(chat, 'send') as send, patch.object(chat.time, 'monotonic', return_value=0), \
             patch.object(chat.time, 'sleep') as sleep:
            sender.deliver((URL, 'title', 'message', True, {}))
            self.assertEqual(send.call_count, 2)
            sleep.assert_called_once_with(1.1)
        kind, result = sender.events.get_nowait()
        self.assertEqual(kind, 'google_chat_result')
        self.assertEqual(result[:2], (True, True))
        with patch.object(chat, 'send', side_effect=RuntimeError(URL)), patch.object(chat.time, 'sleep'):
            sender.deliver((URL, 'title', 'message', False, None))
        self.assertNotIn('test-secret', sender.events.get_nowait()[1][2])

    def test_background_queue_is_bounded(self):
        sender = chat.Sender.__new__(chat.Sender)
        sender.events, sender.jobs = queue.Queue(), queue.Queue(maxsize=1)
        sender.submit(URL, 'Title', 'First')
        sender.submit(URL, 'Title', 'Second', test=True)
        self.assertEqual(sender.events.get_nowait()[1][:2], (False, True))

    def make_app(self):
        app = App.__new__(App)
        app.notify, app.teams_enabled, app.google_chat_enabled = Mock(), Mock(), Mock()
        app.notify.get.return_value = False
        app.teams_enabled.get.return_value = False
        app.google_chat_enabled.get.return_value = True
        app.google_chat_webhook, app.google_chat_sender = URL, Mock()
        app.root, app.history = Mock(), Mock()
        app.filters = [{'name': 'Tasks', 'url': 'filter'}]
        return app

    def test_global_and_per_filter_preferences_are_independent(self):
        app = self.make_app()
        record = {'number': 'SCTASK123', 'short_description': 'Laptop', 'requested_for': 'Anna', 'url': 'https://adeo.service-now.com/task'}
        with patch('plyer.notification.notify') as windows:
            app.notify_filter('filter', [record])
            windows.assert_not_called()
        args = app.google_chat_sender.submit.call_args
        self.assertIn('SCTASK123 - Laptop - Anna', args.args[2])
        self.assertEqual(args.kwargs['links'], {'SCTASK123': record['url']})
        app.filters[0]['notify_google_chat'] = False
        app.notify_filter('filter', [record])
        self.assertEqual(app.google_chat_sender.submit.call_count, 1)
        app.filters[0]['notify_google_chat'] = True
        app.google_chat_enabled.get.return_value = False
        app.notify_filter('filter', [record])
        self.assertEqual(app.google_chat_sender.submit.call_count, 1)

    def test_context_test_works_with_only_google_chat_on_disabled_filter(self):
        app = self.make_app()
        app.filters[0]['enabled'] = False
        app.current_table = Mock()
        app.selected_filter_url = Mock(return_value='filter')
        app.selected_filter_index = Mock(return_value=1)
        app.snapshots = {1: {'INC123': {'short_description': 'Printer'}}}
        app.test_record_notification(app.current_table, 'INC123', 'https://adeo.service-now.com/inc')
        app.google_chat_sender.submit.assert_called_once()
        app.history.mark_read.assert_not_called()

    def test_session_expiry_respects_google_chat_setting(self):
        app = self.make_app()
        app.interruption = Mock()
        app.session_expired('Please log in')
        app.google_chat_sender.submit.assert_called_once_with(URL, 'ServiceNow — sesja wygasła', 'Please log in')
        app.google_chat_enabled.get.return_value = False
        app.session_expired('Please log in')
        self.assertEqual(app.google_chat_sender.submit.call_count, 1)

    def test_preferences_are_saved_and_failed_write_restores_previous_state(self):
        from neto_incident_monitor.google_chat_ui import persist
        app = self.make_app()
        app.saved_google_chat = False, ''
        app.saving_google_chat = False
        app.status = Mock()
        with patch('neto_incident_monitor.app.read_json', return_value={'other': 123}), \
             patch('neto_incident_monitor.app.save_json') as save:
            self.assertTrue(persist(app))
            self.assertEqual(save.call_args.args[1], {'other': 123, 'google_chat_enabled': True, 'google_chat_webhook': URL})
        app.google_chat_webhook = 'new'
        app.google_chat_enabled.get.return_value = False
        with patch('neto_incident_monitor.app.read_json', return_value={}), \
             patch('neto_incident_monitor.app.save_json', side_effect=OSError()):
            self.assertFalse(persist(app))
        self.assertEqual(app.google_chat_webhook, URL)
        app.google_chat_enabled.set.assert_called_once_with(True)
