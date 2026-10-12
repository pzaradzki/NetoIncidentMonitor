import sys
import unittest
from unittest.mock import Mock, patch

from neto_incident_monitor.startup import set_windows_startup, startup_command


class StartupTests(unittest.TestCase):
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
