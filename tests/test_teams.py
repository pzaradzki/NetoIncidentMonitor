import json
import queue
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from neto_incident_monitor.teams_notifications import validate_webhook, payload, send, Sender

URL = 'https://example.environment.api.powerplatform.com/powerautomate/workflows/test/triggers/manual/paths/invoke?sig=test-secret'


class TeamsTests(unittest.TestCase):
    def test_expired_session_alert_respects_teams_setting(self):
        from neto_incident_monitor.app import App
        from neto_incident_monitor.monitoring import Health
        app = Mock()
        app.teams_webhook = URL
        app.teams_enabled.get.return_value = True
        health = Health()
        for _ in range(3):
            if health.authentication():
                App.session_expired(app, 'Sesja wygasła. Zaloguj się ponownie.')
        app.teams_sender.submit.assert_called_once_with(URL, 'ServiceNow — sesja wygasła',
                                                       'Sesja wygasła. Zaloguj się ponownie.')
        health.resumed()
        if health.authentication():
            App.session_expired(app, 'Kolejna przerwa')
        self.assertEqual(app.teams_sender.submit.call_count, 2)
        app.teams_enabled.get.return_value = False
        App.session_expired(app, 'Teams wyłączony')
        self.assertEqual(app.teams_sender.submit.call_count, 2)

    def test_locations_in_single_and_batch_alerts(self):
        from neto_incident_monitor.teams_notifications import incident_text
        first = {'number': 'INC1234567', 'location': 'STORE 003 GDAŃSK', 'short_description': 'Problem z kasą'}
        title, message = incident_text([first])
        self.assertIn('STORE 003 GDAŃSK', message)
        self.assertIn('Problem z kasą', message)
        title, message = incident_text([first, first, {'number': 'INC1234568', 'location': '—'}])
        self.assertEqual(title, 'Nowe incydenty: 2')
        self.assertEqual(message.count('INC1234567'), 1)
        self.assertIn('INC1234568 - Brak lokalizacji - Brak opisu', message)
        self.assertIn('INC1234567 - STORE 003 GDAŃSK - Problem z kasą', message)
        self.assertEqual(len(message.splitlines()), 2)

    def test_description_and_location_stay_on_one_line(self):
        from neto_incident_monitor.teams_notifications import incident_text
        _, message = incident_text([{'number': 'INC1234567', 'location': 'STORE\n003',
                                    'short_description': 'Problem\nz kasą'}])
        self.assertEqual(message, 'INC1234567 - STORE 003 - Problem z kasą')

    def test_teams_is_independent_of_windows_toggle(self):
        from neto_incident_monitor.app import App
        app = Mock()
        app.history.snapshot.return_value = {'INC1234567': {'read': False}}
        app.teams_enabled.get.return_value = True
        app.notify.get.return_value = False
        app.teams_webhook = URL
        with patch('plyer.notification.notify') as windows:
            App.notify_batch(app, [{'number': 'INC1234567'}])
            app.teams_sender.submit.assert_called_once()
            windows.assert_not_called()
            app.teams_enabled.get.return_value = False
            App.notify_batch(app, [{'number': 'INC1234567'}])
            app.teams_sender.submit.assert_called_once()

    def test_rejects_foreign_hosts_and_insecure_urls(self):
        self.assertEqual(validate_webhook(URL), URL)
        for url in (URL.replace('https:', 'http:'), URL.replace('.api.powerplatform.com', '.api.powerplatform.com.evil.com'), URL.split('?')[0]):
            with self.assertRaises(ValueError):
                validate_webhook(url)

    def test_payload_is_safe_html_and_valid_card(self):
        value = payload('Nowe: 2', '<script>\nINC1234567')
        self.assertIn('&lt;script&gt;<br>', value['text'])
        self.assertEqual(value['attachments'][0]['content']['type'], 'AdaptiveCard')

    def test_incident_numbers_keep_original_plain_text(self):
        original = 'INC7164358 - STORE 014 - Telefon 123456789\nINC7164363 - <Opis>'
        value = payload('Nowe incydenty: 2', original)
        self.assertEqual(value['attachments'][0]['content']['body'][1]['text'], original)
        self.assertIn('INC7164358 - STORE 014', value['text'])
        self.assertIn('<br>INC7164363 - &lt;Opis&gt;', value['text'])
        self.assertNotIn('<code>', value['text'])
        self.assertNotIn('\u200b', value['text'])

    def test_transport_posts_and_redacts_http_errors(self):
        response = Mock(status=202)
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch('neto_incident_monitor.teams_notifications.build_opener') as opener:
            opener.return_value.open.return_value = response
            send(URL, 'Test', 'Message')
            request = opener.return_value.open.call_args.args[0]
            self.assertEqual(request.get_method(), 'POST')
            self.assertIn('text', json.loads(request.data))
            opener.return_value.open.side_effect = HTTPError(URL, 403, 'secret', {}, None)
            with self.assertRaises(RuntimeError) as error:
                send(URL, 'Test', 'Message')
            self.assertNotIn('test-secret', str(error.exception))
            self.assertIn('403', str(error.exception))

    def test_background_result_and_failure(self):
        events = queue.Queue()
        with patch('neto_incident_monitor.teams_notifications.send') as transport:
            sender = Sender(events)
            sender.submit(URL, 'Test', 'Message', True)
            kind, result = events.get(timeout=2)
            self.assertEqual(kind, 'teams_result')
            self.assertEqual(result[:2], (True, True))
            transport.side_effect = RuntimeError('Offline')
            sender.submit(URL, 'Test', 'Message')
            self.assertEqual(events.get(timeout=2)[1], (False, False, 'Offline'))
