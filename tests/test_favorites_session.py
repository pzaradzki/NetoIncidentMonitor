import threading
import unittest
from unittest.mock import Mock, patch

from neto_incident_monitor.app import App


class FavoritesSessionTests(unittest.TestCase):
    def test_start_during_import_does_not_start_monitor(self):
        app = App.__new__(App)
        app.quitting = False
        app.worker = None
        app.favorites_import = Mock()
        app.start_button = Mock()
        with patch('neto_incident_monitor.app.load_filters') as load:
            app.start()
        load.assert_not_called()

    def test_import_during_monitor_does_not_open_dialog(self):
        app = App.__new__(App)
        app.quitting = False
        app.worker = Mock()
        app.worker.is_alive.return_value = True
        app.favorites_import = None
        with patch('neto_incident_monitor.favorites_ui.FavoritesImport') as dialog:
            app.import_favorites()
        dialog.assert_not_called()

    def test_context_cleanup_does_not_mask_primary_error(self):
        from neto_incident_monitor.browser_session import close_session
        context, runtime, log = Mock(), Mock(), Mock()
        runtime.close.side_effect = OSError('SYNTHETIC_SECRET')
        context.close.side_effect = OSError('SYNTHETIC_SECRET')
        close_session(context, runtime, log)
        context.close.assert_called_once()
        self.assertNotIn('SYNTHETIC_SECRET', str(log.mock_calls))

    def test_guard_failure_releases_profile(self):
        from neto_incident_monitor.browser_session import open_context
        playwright, log = Mock(), Mock()
        context = playwright.chromium.launch_persistent_context.return_value
        with patch('neto_incident_monitor.authentication.install_input_guard', side_effect=RuntimeError()):
            with self.assertRaises(RuntimeError):
                open_context(playwright, 'synthetic-profile', log)
        context.close.assert_called_once()
