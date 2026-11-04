import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from neto_incident_monitor.app import App
from neto_incident_monitor.data_reset import DataReset


class DataResetTests(unittest.TestCase):
    def setUp(self):
        self.startup = self.enterContext(patch("neto_incident_monitor.startup.set_windows_startup"))
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.data = self.root / "data"
        self.data.mkdir()
        for name in ("config.json", "seen.json", "history.state.sqlite3", "monitor.log.3",
                     "dashboard-cache.json.synthetic.tmp", "login-diagnostics.jsonl.1"):
            (self.data / name).write_text("synthetic")
        profile = self.data / "browser-profile"
        profile.mkdir()
        (profile / "test-session").write_text("synthetic")
        (self.data / "release-test.log").write_text("project artifact")

    def test_source_reset_preserves_project_artifacts(self):
        reset = DataReset(self.data, packaged=False)
        reset.request()
        reset.finish()
        self.assertEqual([path.name for path in self.data.iterdir()], ["release-test.log"])
        self.assertFalse(reset.pending())
        self.assertFalse(reset.staging.exists())
        self.startup.assert_called_once_with(False, packaged=False)

    def test_packaged_reset_resumes_after_staging(self):
        reset = DataReset(self.data, packaged=True)
        reset.request()
        self.data.rename(reset.staging)
        DataReset(self.data, packaged=True).finish()
        self.assertFalse(self.data.exists())
        self.assertFalse(reset.pending())
        self.assertFalse(reset.staging.exists())

    def test_failure_preserves_marker_for_retry(self):
        reset = DataReset(self.data, packaged=True)
        reset.request()
        with patch("neto_incident_monitor.data_reset.shutil.rmtree", side_effect=PermissionError):
            with self.assertRaises(PermissionError):
                reset.finish()
        self.assertTrue(reset.pending())
        self.assertTrue(reset.staging.exists())
        reset.finish()
        self.assertFalse(reset.pending())

    @unittest.skipUnless(os.name == "nt", "Windows file sharing")
    def test_open_file_in_source_reset_leaves_request_pending(self):
        reset = DataReset(self.data, packaged=False)
        reset.request()
        with (self.data / "config.json").open("rb"):
            with self.assertRaises(OSError):
                reset.finish()
            self.assertTrue(reset.pending())
        reset.finish()
        self.assertEqual([path.name for path in self.data.iterdir()], ["release-test.log"])

    def test_redirect_in_profile_is_rejected(self):
        reset = DataReset(self.data, packaged=True)
        outside = self.root / "outside"
        outside.write_text("keep")
        link = self.data / "browser-profile" / "link"
        try:
            os.symlink(outside, link)
        except OSError as error:
            self.skipTest(f"Creating a symbolic link is unavailable: {type(error).__name__}")
        reset.request()
        with self.assertRaises(OSError):
            reset.finish()
        self.assertEqual(outside.read_text(), "keep")
        self.assertTrue(self.data.exists())

    def test_cancel_keeps_application_running(self):
        app = SimpleNamespace(quitting=False, root=Mock(), quit_app=Mock())
        with patch("neto_incident_monitor.widgets.confirm_dialog", return_value=False),                 patch("neto_incident_monitor.data_reset.DataReset") as reset:
            App.request_data_reset(app)
        reset.assert_not_called()
        app.quit_app.assert_not_called()

    def test_shutdown_waits_for_worker_and_writers(self):
        worker = Mock()
        worker.is_alive.side_effect = [True, False, False, False]
        future = Mock()
        future.done.side_effect = [False, True, True, True, True]
        history_writer, alert_writer = Mock(), Mock()
        history_writer.submit.return_value = future
        alert_writer.submit.return_value = future
        sender = Mock()
        sender.thread.is_alive.side_effect = [True, False, False]
        app = SimpleNamespace(worker=worker, status=Mock(), root=Mock(), finish_quit=Mock(),
                              history_writer=history_writer, alert_writer=alert_writer, tray=None,
                              reset_data_on_exit=True, reset_started=time.monotonic(), teams_sender=sender, google_chat_sender=sender)
        for _ in range(3):
            App.finish_quit(app)
            app.root.destroy.assert_not_called()
        App.finish_quit(app)
        self.assertTrue(app.reset_data_ready)
        app.root.destroy.assert_called_once()

    def test_second_instance_cannot_own_data_during_reset(self):
        from neto_incident_monitor.single_instance import SingleInstance

        first = SingleInstance(self.data)
        self.addCleanup(first.close)
        self.assertTrue(first.primary)
        reset = DataReset(self.data, packaged=True)
        reset.request()
        second = SingleInstance(self.data)
        self.addCleanup(second.close)
        self.assertFalse(second.primary)
        reset.finish()

    def test_escape_and_window_close_cancel_real_confirmation(self):
        import tkinter as tk
        from neto_incident_monitor.widgets import confirm_dialog

        root = tk.Tk()
        self.addCleanup(root.destroy)
        for via_escape in (True, False):
            def dismiss():
                dialog = next(child for child in root.winfo_children() if isinstance(child, tk.Toplevel))
                if via_escape:
                    dialog.focus_force()
                    dialog.event_generate("<Escape>")
                else:
                    dialog.tk.call(dialog.protocol("WM_DELETE_WINDOW"))
            root.after(100, dismiss)
            self.assertFalse(confirm_dialog(root, "Reset", "Test syntetyczny"))

    def test_launcher_recovers_before_opening_log_and_finishes_after_closing_it(self):
        import logging
        import runpy
        from neto_incident_monitor import login_diagnostics
        from neto_incident_monitor.single_instance import SingleInstance

        reset = DataReset(self.data, packaged=True)
        reset.request()
        launcher = runpy.run_path(str(Path(__file__).resolve().parents[1] / "launcher.pyw"))
        main = launcher["main"]

        def run_app(instance):
            self.assertTrue(instance.primary)
            self.assertFalse((self.data / "config.json").exists())
            self.assertTrue((self.data / "monitor.log").exists())
            other = SingleInstance(self.data)
            try:
                self.assertFalse(other.primary)
            finally:
                other.close()
            login_diagnostics.LoginDiagnostics(source="monitor")
            reset.request()
            return True

        logger = logging.getLogger()
        previous_level = logger.level
        self.addCleanup(logger.setLevel, previous_level)
        with patch.dict(main.__globals__, DATA=self.data), \
                patch("neto_incident_monitor.data_reset.DataReset", return_value=reset), \
                patch("neto_incident_monitor.app.main", side_effect=run_app) as app_main, \
                patch.object(login_diagnostics, "DATA", self.data):
            main()
        app_main.assert_called_once()
        self.assertFalse(self.data.exists())
        self.assertFalse(reset.pending())

    def test_registry_failure_keeps_reset_pending(self):
        reset = DataReset(self.data, packaged=True)
        reset.request()
        self.startup.side_effect = PermissionError
        with self.assertRaises(PermissionError):
            reset.finish()
        self.assertTrue(reset.pending())
        self.startup.side_effect = None
        reset.finish()
        self.assertFalse(reset.pending())
        self.startup.assert_called_with(False, packaged=True)
