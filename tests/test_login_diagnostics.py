import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from playwright.sync_api import sync_playwright
from neto_incident_monitor import login_diagnostics as diagnostics
from neto_incident_monitor.automatic_login import AutomaticLogin


class LoginDiagnosticsTests(unittest.TestCase):
    def test_snapshot_records_structure_without_credentials_or_sso_tokens(self):
        with self.assertLogs(diagnostics._logger, level='INFO') as captured, sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.route('**/*', lambda route: route.fulfill(body='<form><input readonly value="PRIVATE_USER">'
                           '<input type="password" value="PRIVATE_PASSWORD"><button>Zaloguj się</button></form>',
                           content_type='text/html; charset=utf-8'))
                page.goto('https://idpb2e.adeo.com/idp/PRIVATE_PATH/SSO.ping?SAMLRequest=PRIVATE_TOKEN')
                log = diagnostics.LoginDiagnostics(auto_login=True)
                log.inspect(page, AutomaticLogin())
                log.inspect(page, AutomaticLogin())
            finally:
                browser.close()
        output = '\n'.join(captured.output)
        for secret in ('PRIVATE_USER', 'PRIVATE_PASSWORD', 'PRIVATE_TOKEN', 'PRIVATE_PATH', 'SAMLRequest'):
            self.assertNotIn(secret, output)
        records = [json.loads(record.getMessage()) for record in captured.records]
        states = [record for record in records if record['event'] == 'page_state']
        self.assertEqual(len(states), 1)
        self.assertEqual(states[0]['password_count'], 1)
        self.assertTrue(states[0]['password_filled'])
        self.assertTrue(states[0]['identity_locked'])
        self.assertEqual(states[0]['login_button_count'], 1)
        self.assertEqual(states[0]['origin'], 'adeo_identity')

    def test_failed_inspection_records_only_exception_type(self):
        with self.assertLogs(diagnostics._logger, level='INFO') as captured:
            log = diagnostics.LoginDiagnostics()
            page = Mock(url='https://adeo.service-now.com/private')
            page.evaluate.side_effect = RuntimeError('PRIVATE_PASSWORD PRIVATE_TOKEN')
            log.inspect(page, None)
        self.assertNotIn('PRIVATE_', '\n'.join(captured.output))
        self.assertIn('RuntimeError', captured.output[-1])

    def test_disk_failure_does_not_stop_login(self):
        with patch.object(diagnostics._logger, 'info', side_effect=OSError('disk full')):
            log = diagnostics.LoginDiagnostics()
            log.record('submit_attempt', attempt=1)

    def test_rotating_log_is_created_in_data_directory(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(diagnostics, 'DATA', Path(folder)), \
             patch.object(diagnostics._logger, 'handlers', []):
            try:
                diagnostics.LoginDiagnostics(auto_login=True)
                handler = diagnostics._logger.handlers[0]
                self.assertEqual(handler.maxBytes, 2_000_000)
                self.assertEqual(handler.backupCount, 3)
                record = json.loads((Path(folder) / 'login-diagnostics.jsonl').read_text(encoding='utf-8'))
                self.assertEqual(record['event'], 'start')
            finally:
                for handler in diagnostics._logger.handlers:
                    handler.close()
