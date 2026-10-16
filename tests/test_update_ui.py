import queue
import json
from pathlib import Path
import tempfile
import sys
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

from neto_incident_monitor.update_ui import UpdateController


class UpdateUITests(unittest.TestCase):
    def test_update_restart_resumes_monitoring_without_changing_startup_preference(self):
        from neto_incident_monitor.app import App
        root = tk.Tk()
        try:
            with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory, \
                 patch('neto_incident_monitor.app.read_json', return_value={
                     'start_monitoring': False, 'check_updates': False,
                     'filters': [{'name': 'Test', 'url': 'https://example.test/incident_list.do'}]}), \
                 patch.object(sys, 'argv', ['app', '--resume-monitoring']), \
                 patch.object(App, 'start') as start, patch.object(root, 'after', wraps=root.after) as after:
                app = App(root, history_path=Path(directory) / 'history.json', enable_tray=False)
                root.update_idletasks()
                self.assertFalse(app.start_monitoring.get())
                self.assertTrue(any(len(call.args) > 1 and call.args[1] is start for call in after.call_args_list))
        finally:
            for timer in root.tk.call('after', 'info'):
                root.after_cancel(timer)
            root.destroy()

    def controller(self):
        app = Mock()
        app.quitting = False
        app.check_updates.get.return_value = True
        app.events = queue.Queue()
        controller = UpdateController(app, {}, apply_startup=False)
        controller.background = Mock()
        return app, controller

    def test_disabling_startup_check_is_respected_and_manual_check_still_works(self):
        app, controller = self.controller()
        app.check_updates.get.return_value = False
        controller.check(manual=False)
        controller.background.assert_not_called()
        controller.check(manual=True)
        controller.background.assert_called_once()
        controller.check(manual=True)
        self.assertEqual(controller.background.call_count, 1)

    def test_download_and_install_require_separate_confirmations(self):
        app, controller = self.controller()
        with patch('neto_incident_monitor.update_ui.FROZEN', True), \
             patch('neto_incident_monitor.update_ui.messagebox.askyesno', return_value=False):
            controller.handle('update_checked', ({'version': '2.0.0'}, True))
            controller.background.assert_not_called()
            controller.handle('update_prepared', ('job.json', True))
            controller.background.assert_not_called()
            app.quit_app.assert_not_called()
        with patch('neto_incident_monitor.update_ui.FROZEN', True), \
             patch('neto_incident_monitor.update_ui.messagebox.askyesno', return_value=True):
            controller.handle('update_checked', ({'version': '2.0.0'}, True))
            self.assertEqual(controller.background.call_args.args[1], 'update_prepared')
            app.quit_app.assert_not_called()
            controller.handle('update_prepared', ('job.json', True))
            self.assertEqual(controller.background.call_args.args[1], 'update_helper_ready')
            app.quit_app.assert_not_called()
            controller.handle('update_helper_ready', ('job.json', True))
            app.quit_app.assert_called_once()

    def test_background_failure_never_closes_application(self):
        app, controller = self.controller()
        with patch('neto_incident_monitor.update_ui.messagebox.showerror') as error:
            controller.handle('update_error', ('network unavailable', False))
            error.assert_not_called()
            controller.handle('update_error', ('network unavailable', True))
            error.assert_called_once()
        self.assertFalse(controller.busy)
        app.quit_app.assert_not_called()

    def test_postponed_verified_package_is_reused_without_downloading_again(self):
        app, controller = self.controller()
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            payload = Path(directory) / 'payload'
            payload.mkdir()
            job = Path(directory) / 'job.json'
            job.write_text(json.dumps({'version': '2.0.0', 'payload': str(payload)}))
            controller.prepared = str(job)
            with patch('neto_incident_monitor.update_ui.FROZEN', True), \
                 patch('neto_incident_monitor.update_ui.messagebox.askyesno', return_value=False) as ask:
                controller.handle('update_checked', ({'version': '2.0.0'}, True))
                self.assertIn('Zainstalować', ask.call_args.args[1])
            controller.background.assert_not_called()
            app.quit_app.assert_not_called()

    def test_preference_is_persisted_and_failed_save_restores_previous_value(self):
        app, controller = self.controller()
        app.check_updates.get.return_value = False
        with patch('neto_incident_monitor.app.read_json', return_value={'other': 123}), \
             patch('neto_incident_monitor.app.save_json') as save:
            controller.save_preference()
            self.assertEqual(save.call_args.args[1], {'other': 123, 'check_updates': False})
        app.check_updates.get.return_value = True
        with patch('neto_incident_monitor.app.read_json', return_value={}), \
             patch('neto_incident_monitor.app.save_json', side_effect=OSError()), \
             patch('neto_incident_monitor.update_ui.messagebox.showerror'):
            controller.save_preference()
        app.check_updates.set.assert_called_once_with(False)
