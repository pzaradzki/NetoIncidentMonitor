import unittest
from unittest.mock import Mock, patch

from neto_incident_monitor.app import App


class FavoritesSessionTests(unittest.TestCase):
    def test_start_while_waiting_for_login_does_not_start_cycle(self):
        app = App.__new__(App)
        app.quitting = False
        app.cycle_active = False
        app.session_state = 'waiting'
        app.session = Mock()
        app.start()
        app.session.start_cycle.assert_not_called()

    def test_import_without_confirmed_shared_session_does_not_open_dialog(self):
        app = App.__new__(App)
        app.quitting = False
        app.status = Mock()
        app.favorites_import = None
        app.session = Mock(ready_once=False)
        with patch('neto_incident_monitor.favorites_ui.FavoritesImport') as dialog:
            app.import_favorites()
        dialog.assert_not_called()
        app.status.set.assert_called_once()

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
