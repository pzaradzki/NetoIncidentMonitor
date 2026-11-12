import sys
import unittest
import tempfile
import tkinter as tk
from pathlib import Path
from unittest.mock import Mock, patch

from neto_incident_monitor.startup import set_windows_startup, startup_command


class StartupTests(unittest.TestCase):
    def test_settings_window_is_centered_on_first_open_and_reopen(self):
        from neto_incident_monitor.app import App
        from neto_incident_monitor.widgets import RoundedButton

        with tempfile.TemporaryDirectory() as folder:
            root = tk.Tk()
            root.withdraw()
            try:
                with patch('neto_incident_monitor.app.read_json', return_value={'filters': []}):
                    app = App(root, history_path=Path(folder) / 'history.json',
                              enable_tray=False, apply_startup=False, shared_session=True)
                app.session.ready_once = True
                app.handle_session_event('session_ready', None)
                root.update()
                window = app.settings_window
                button = next(child for child in app.controls.winfo_children()
                              if isinstance(child, RoundedButton) and child.text == 'Ustawienia')
                x = max(0, (window.winfo_screenwidth() - 700) // 2)
                y = max(0, (window.winfo_screenheight() - 700) // 2)
                geometry = window.geometry

                def before_first_map(spec=None):
                    return '1x1+0+0' if spec is None else geometry(spec)

                for opening in (1, 2):
                    with self.subTest(opening=opening):
                        self.assertEqual(window.state(), 'withdrawn')
                        if opening == 1:
                            with patch.object(window, 'geometry', side_effect=before_first_map):
                                button.invoke()
                        else:
                            button.invoke()
                        root.update_idletasks()
                        self.assertTrue(window.winfo_ismapped())
                        self.assertEqual(window.geometry(), f'700x700+{x}+{y}')
                    window.withdraw()
            finally:
                root.destroy()

    def test_windows_startup_has_no_ui_control_and_other_start_options_remain(self):
        from neto_incident_monitor.app import App
        from neto_incident_monitor.widgets import Toggle

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        for status in ('disabled', 'current', 'repaired', 'unknown'):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as folder:
                root = tk.Tk()
                try:
                    with patch('neto_incident_monitor.app.read_json', return_value={}), \
                            patch('neto_incident_monitor.startup.set_windows_startup') as write:
                        app = App(root, history_path=Path(folder) / 'history.json',
                                  enable_tray=False, apply_startup=False, windows_startup=status)
                        toggles = [w for w in descendants(app.settings_window) if isinstance(w, Toggle)]
                        self.assertFalse(any(w.variable is app.start_with_windows for w in toggles))
                        self.assertTrue(any(w.variable is app.start_monitoring for w in toggles))
                        self.assertTrue(any(w.variable is app.start_minimized for w in toggles))
                        self.assertEqual(app.start_with_windows.get(), status in ('current', 'repaired'))
                        write.assert_not_called()
                finally:
                    root.destroy()

    def test_fresh_windows_registration_is_disabled_for_both_variants(self):
        import winreg
        from neto_incident_monitor.startup import reconcile_windows_startup
        for packaged in (False, True):
            with self.subTest(packaged=packaged), \
                    patch.object(sys, 'frozen', packaged, create=True), \
                    patch.object(winreg, 'OpenKey', side_effect=FileNotFoundError), \
                    patch.object(winreg, 'CreateKeyEx') as create, \
                    patch.object(winreg, 'SetValueEx') as write:
                self.assertEqual(reconcile_windows_startup(), 'disabled')
                create.assert_not_called()
                write.assert_not_called()

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
                        # Child widgets unregister their own Tcl callbacks when destroyed.
                        root.tk.call('after', 'cancel', timer)
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
        with patch.object(winreg, "OpenKey") as open_key, patch.object(winreg, "CreateKeyEx"), patch.object(winreg, "SetValueEx") as write, patch.object(winreg, "DeleteValue") as delete:
            key = open_key.return_value.__enter__.return_value
            set_windows_startup(True)
            self.assertEqual(write.call_args.args[1], "NetoIncidentMonitorSource")
            self.assertEqual(write.call_args.args[-1], startup_command())
            set_windows_startup(False)
            delete.assert_called_once_with(key, "NetoIncidentMonitorSource")
            delete.side_effect = FileNotFoundError
            set_windows_startup(False)

    def test_reconcile_existing_registration_only(self):
        import winreg
        from neto_incident_monitor.startup import reconcile_windows_startup

        with patch.object(winreg, "OpenKey"), patch.object(winreg, "QueryValueEx") as query, \
                patch.object(winreg, "CreateKeyEx"), patch.object(winreg, "SetValueEx") as write:
            query.side_effect = FileNotFoundError
            self.assertEqual(reconcile_windows_startup(), "disabled")
            write.assert_not_called()
            query.side_effect = None
            query.return_value = (r'"C:\Old Folder\Monitor.exe"', winreg.REG_SZ)
            self.assertEqual(reconcile_windows_startup(), "repaired")
            self.assertEqual(write.call_args.args[1:], ("NetoIncidentMonitorSource", 0, winreg.REG_SZ, startup_command()))
            query.return_value = (startup_command(), winreg.REG_SZ)
            self.assertEqual(reconcile_windows_startup(), "current")
            self.assertEqual(write.call_count, 1)

    def test_reconcile_and_remove_on_isolated_windows_key(self):
        import uuid
        import winreg
        from neto_incident_monitor.startup import reconcile_windows_startup, windows_startup_status

        key_path = r"Software\NetoIncidentMonitorTests-" + uuid.uuid4().hex
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            winreg.SetValueEx(key, "NetoIncidentMonitorSource", 0, winreg.REG_SZ, '"C:\\Old Folder\\Monitor.exe"')
            winreg.SetValueEx(key, "NetoIncidentMonitor", 0, winreg.REG_SZ, "other variant")
        self.addCleanup(winreg.DeleteKey, winreg.HKEY_CURRENT_USER, key_path)
        with patch("neto_incident_monitor.startup.RUN_KEY", key_path):
            self.assertEqual(reconcile_windows_startup(), "repaired")
            self.assertEqual(reconcile_windows_startup(), "current")
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                self.assertEqual(winreg.QueryInfoKey(key)[1], 2)
            set_windows_startup(False, packaged=False)
            self.assertEqual(reconcile_windows_startup(), "disabled")
            self.assertEqual(windows_startup_status(), "disabled")
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                self.assertEqual(winreg.QueryValueEx(key, "NetoIncidentMonitor")[0], "other variant")

    def test_failed_toggle_rereads_registration(self):
        from neto_incident_monitor.app import App

        app = App.__new__(App)
        app.saving_startup = False
        app.start_with_windows = Mock()
        app.start_with_windows.get.return_value = False
        app.startup_status_text = Mock()
        app.settings_window = None
        with patch("neto_incident_monitor.startup.set_windows_startup", side_effect=PermissionError), \
                patch("neto_incident_monitor.startup.windows_startup_status", return_value="current") as read, \
                patch("neto_incident_monitor.app.messagebox.showerror"):
            app.save_startup_preference("start_with_windows")
        read.assert_called_once()
        app.start_with_windows.set.assert_called_once_with(True)
