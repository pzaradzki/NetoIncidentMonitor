import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from neto_incident_monitor import secret_config as secrets

TEAMS = 'https://test.api.powerplatform.com/invoke?sig=dummy-teams-secret'
CHAT = 'https://chat.googleapis.com/v1/spaces/test/messages?key=dummy&token=dummy-chat-secret'


class SecretConfigTests(unittest.TestCase):
    def test_filter_webhooks_are_protected_migrated_and_preserved_on_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'config.json'
            settings = {'filters': [{'name': 'A', 'teams_webhook': TEAMS, 'google_chat_webhook': CHAT}]}
            path.write_text(json.dumps(settings), encoding='utf-8')
            loaded = secrets.load_config(path, {})
            self.assertEqual(loaded, settings)
            self.assertNotIn('dummy-chat-secret', path.read_text())
            self.assertNotIn('dummy-teams-secret', path.read_text())
            encrypted = json.loads(path.read_text())['filters'][0]['teams_webhook']
            with patch.object(secrets, 'unprotect', side_effect=secrets.SecretStorageError()):
                failed = secrets.load_config(path, {})
            self.assertFalse(failed['filters'][0]['notify_teams'])
            self.assertIsInstance(failed['filters'][0]['teams_webhook'], secrets.UnavailableSecret)
            secrets.save_config(path, failed)
            self.assertEqual(json.loads(path.read_text())['filters'][0]['teams_webhook'], encrypted)
            self.assertEqual(secrets.load_config(path, {})['filters'][0]['teams_webhook'], TEAMS)
            before = path.read_bytes()
            with patch.object(secrets, 'protect', side_effect=secrets.SecretStorageError()):
                with self.assertRaises(secrets.SecretStorageError):
                    secrets.save_config(path, settings)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(settings['filters'][0]['teams_webhook'], TEAMS)

    def test_real_dpapi_roundtrip_and_legacy_migration_through_app_io(self):
        from neto_incident_monitor import app
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'config.json'
            original = {'teams_webhook': TEAMS, 'google_chat_webhook': CHAT,
                        'teams_enabled': True, 'google_chat_enabled': True,
                        'filters': [{'name': 'Zażółć', 'url': 'test'}]}
            path.write_text(json.dumps(original), encoding='utf-8')
            with patch.object(app, 'CONFIG', path):
                loaded = app.read_json(path, {})
                self.assertEqual(loaded, original)
                stored = path.read_text(encoding='utf-8')
                self.assertNotIn(TEAMS, stored)
                self.assertNotIn('dummy-chat-secret', stored)
                self.assertEqual(json.loads(stored)['teams_webhook']['protection'], secrets.FORMAT)
                loaded['interval'] = 120
                app.save_json(path, loaded)
                reread = app.read_json(path, {})
                self.assertEqual(reread['teams_webhook'], TEAMS)
                self.assertEqual(reread['google_chat_webhook'], CHAT)
                self.assertEqual(reread['interval'], 120)
                self.assertFalse(reread.protection_errors)
                self.assertFalse(path.with_suffix('.tmp').exists())

    def test_failed_encryption_keeps_existing_file_and_never_writes_plaintext(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'config.json'
            path.write_text('{"interval": 60}', encoding='utf-8')
            with patch.object(secrets, '_crypt', side_effect=RuntimeError('dummy-teams-secret')):
                with self.assertRaises(secrets.SecretStorageError) as error:
                    secrets.save_config(path, {'teams_webhook': TEAMS})
                self.assertNotIn('dummy-teams-secret', str(error.exception))
            self.assertEqual(json.loads(path.read_text()), {'interval': 60})
            self.assertFalse(path.with_suffix('.tmp').exists())

    def test_unreadable_credentials_are_preserved_on_unrelated_save(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'config.json'
            secrets.save_config(path, {'google_chat_webhook': CHAT, 'google_chat_enabled': True})
            encrypted = json.loads(path.read_text())['google_chat_webhook']
            with patch.object(secrets, 'unprotect', side_effect=secrets.SecretStorageError('Cannot decrypt')):
                loaded = secrets.load_config(path, {})
            self.assertEqual(loaded['google_chat_webhook'], '')
            self.assertFalse(loaded['google_chat_enabled'])
            self.assertTrue(loaded.protection_errors)
            loaded['interval'] = 120
            secrets.save_config(path, loaded)
            self.assertEqual(json.loads(path.read_text())['google_chat_webhook'], encrypted)
            self.assertEqual(secrets.load_config(path, {})['google_chat_webhook'], CHAT)

    def test_migration_failure_preserves_legacy_data_and_reports_problem(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'config.json'
            path.write_text(json.dumps({'teams_webhook': TEAMS}), encoding='utf-8')
            with patch.object(secrets, 'save_config', side_effect=OSError('disk full')):
                loaded = secrets.load_config(path, {})
            self.assertEqual(loaded['teams_webhook'], TEAMS)
            self.assertTrue(loaded.protection_errors)
            self.assertEqual(json.loads(path.read_text())['teams_webhook'], TEAMS)

    def test_corrupt_blob_and_clearing_credentials(self):
        for blob in [{'protection': secrets.FORMAT, 'blob': 'invalid!'},
                     {'protection': 'unknown', 'blob': 'AAAA'},
                     {'protection': secrets.FORMAT, 'blob': 'AAAA'}]:
            with self.assertRaises(secrets.SecretStorageError):
                secrets.unprotect(blob)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'config.json'
            secrets.save_config(path, {'teams_webhook': TEAMS})
            secrets.save_config(path, {'teams_webhook': ''})
            self.assertEqual(secrets.load_config(path, {})['teams_webhook'], '')

    def test_teams_save_failure_restores_previous_credentials(self):
        from neto_incident_monitor.app import App
        from unittest.mock import Mock
        app = App.__new__(App)
        app.teams_enabled = Mock()
        app.teams_enabled.get.return_value = True
        app.teams_webhook = 'new address'
        app.saved_teams = False, TEAMS
        app.saving_teams = False
        app.status = Mock()
        with patch('neto_incident_monitor.app.read_json', return_value={}), \
             patch('neto_incident_monitor.app.save_json', side_effect=secrets.SecretStorageError('DPAPI failed')):
            self.assertFalse(app.persist_teams())
        self.assertEqual(app.teams_webhook, TEAMS)
        app.teams_enabled.set.assert_called_once_with(False)
        self.assertFalse(app.saving_teams)
