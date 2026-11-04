import io
import logging
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from neto_incident_monitor.safe_logging import DiagnosticFileHandler


class AuditLoggingTests(unittest.TestCase):
    def test_launcher_continues_when_log_directory_is_unavailable(self):
        launcher = runpy.run_path('launcher.pyw', run_name='audit_test')
        from neto_incident_monitor.single_instance import SingleInstance
        root = logging.getLogger()
        with patch.dict(launcher['main'].__globals__, DATA=Path('synthetic-unavailable')), \
                patch('neto_incident_monitor.single_instance.SingleInstance') as instance, \
                patch('neto_incident_monitor.data_reset.finish_with_retry', return_value=True), \
                patch('neto_incident_monitor.app.main', return_value=False) as app_main, \
                patch.object(DiagnosticFileHandler, '_open', side_effect=PermissionError('PRIVATE_SECRET')), \
                patch.object(sys, '__stderr__', io.StringIO()) as emergency, \
                patch.object(root, 'handlers', []), patch.object(root, 'level', logging.INFO):
            launcher['main']()
            app_main.assert_called_once()
            instance.return_value.close.assert_called_once()
            self.assertNotIn('PRIVATE', emergency.getvalue())

    def test_failures_do_not_recurse_or_dump_secrets_and_recover(self):
        launcher = runpy.run_path('launcher.pyw', run_name='audit_test')
        with tempfile.TemporaryDirectory() as folder:
            handler = DiagnosticFileHandler(Path(folder) / 'log', maxBytes=100, backupCount=1, delay=True)
            root = logging.getLogger()
            with patch.object(root, 'handlers', [handler]), patch.object(root, 'level', logging.INFO), \
                    patch.object(sys, 'stderr', launcher['LogStream'](logging.ERROR)), \
                    patch.object(sys, '__stderr__', io.StringIO()) as emergency, \
                    patch('neto_incident_monitor.safe_logging.monotonic', return_value=10):
                with patch.object(handler, 'shouldRollover', side_effect=OSError('PRIVATE_SECRET')) as fail:
                    root.error('PRIVATE_RECORD')
                    root.error('PRIVATE_RECORD')
                    self.assertEqual(fail.call_count, 1)
                self.assertNotIn('PRIVATE', emergency.getvalue())
                self.assertEqual(handler.retry_at, 40)
            with patch('neto_incident_monitor.safe_logging.monotonic', return_value=41):
                handler.emit(logging.makeLogRecord({'msg': 'recovered'}))
            self.assertEqual(handler.retry_at, 0)
            handler.close()

    def test_flush_and_close_failure_are_contained(self):
        with tempfile.TemporaryDirectory() as folder:
            handler = DiagnosticFileHandler(Path(folder) / 'log', delay=True)
            handler.stream = unittest.mock.Mock()
            handler.stream.flush.side_effect = OSError('PRIVATE_SECRET')
            handler.stream.close.side_effect = OSError('PRIVATE_SECRET')
            handler.flush()
            handler.close()


if __name__ == '__main__':
    unittest.main()
