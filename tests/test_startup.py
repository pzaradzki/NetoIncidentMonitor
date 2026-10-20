import sys
import unittest
import tempfile
import tkinter as tk
from pathlib import Path
from unittest.mock import Mock, patch

from neto_incident_monitor.startup import set_windows_startup, startup_command


class StartupTests(unittest.TestCase):
    def test_start_minimized_respects_tray_readiness_and_user_preferences(self):
        from neto_incident_monitor.app import App
        cases = [
            (True, True, False, True, 'withdrawn'),
            (True, True, True, True, 'withdrawn'),
            (True, False, False, True, 'iconic'),
            (False, True, False, True, 'normal'),
            (True, True, False, False, 'normal'),
        ]
        for minimized, to_tray, ready_early, apply_startup, expected in cases:
            with self.subTest(minimized=minimized, to_tray=to_tray, ready_early=ready_early, apply_startup=apply_startup):
                root = tk.Tk()
                try:
                    settings = {'start_minimized': minimized, 'minimize_to_tray': to_tray}
                    with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder, \
                         patch('neto_incident_monitor.app.read_json', return_value=settings), \
                         patch('neto_incident_monitor.tray.Tray'):
                        app = App(root, history_path=Path(folder) / 'history.json', apply_startup=apply_startup)
                        if ready_early:
                            app.tray_ready = True
                        root.update()
                        if ready_early:
                            self.assertEqual(root.state(), 'withdrawn')
                        app.events.put(('tray_ready', None))
                        app.drain()
                        self.assertEqual(root.state(), expected)
                        if expected == 'withdrawn':
                            app.events.put(('phase', 'Uruchamianie przeglądarki'))
                            app.events.put(('phase', 'Oczekiwanie na logowanie'))
                            app.drain()
                            root.update()
                            self.assertEqual(root.state(), 'withdrawn')
                            app.events.put(('tray_failed', None))
                            app.drain()
                            self.assertEqual(root.state(), 'normal')
                finally:
                    for timer in root.tk.call('after', 'info'):
                        root.after_cancel(timer)
                    root.destroy()

    def test_frozen_command_quotes_executable_with_spaces(self):
        with patch.object(sys, "frozen", True, create=True), patch.object(sys, "executable", r"C:\Program Files\Neto\Neto Incident Monitor.exe"):
            self.assertEqual(startup_command(), '"C:\\Program Files\\Neto\\Neto Incident Monitor.exe"')

    def test_source_command_uses_absolute_launcher(self):
        command = startup_command()
        self.assertIn("launcher.pyw", command)
        self.assertIn("Robot ServiceNow", command)

    def test_registration_enable_disable_without_changing_real_registry(self):
        import winreg
        with patch.object(winreg, "CreateKeyEx") as create, patch.object(winreg, "SetValueEx") as write, patch.object(winreg, "DeleteValue") as delete:
            key = create.return_value.__enter__.return_value
            set_windows_startup(True)
            self.assertEqual(write.call_args.args[1], "NetoIncidentMonitorSource")
            self.assertEqual(write.call_args.args[-1], startup_command())
            set_windows_startup(False)
            delete.assert_called_once_with(key, "NetoIncidentMonitorSource")
            delete.side_effect = FileNotFoundError
            set_windows_startup(False)
