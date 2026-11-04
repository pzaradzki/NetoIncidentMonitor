import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from neto_incident_monitor.history import History


class AuditStartupTests(unittest.TestCase):
    def test_bad_json_and_structures_are_reported_without_rewrite(self):
        from neto_incident_monitor.data_validation import preflight, StartupDataError
        samples = ['{PRIVATE_SECRET', '[]', '{"filters":null}', '{"filters":[{}]}',
                   '{"filters":[null]}', '{"window_layout":[]}', '{"notification_library":{"x":null}}']
        with tempfile.TemporaryDirectory() as d:
            config, history = Path(d)/'config.json', Path(d)/'history.json'
            for sample in samples:
                config.write_text(sample)
                before = config.read_bytes()
                with self.assertRaises(StartupDataError) as error:
                    preflight(config, history)
                self.assertEqual(error.exception.category, 'invalid')
                self.assertEqual(config.read_bytes(), before)
                self.assertNotIn('PRIVATE', str(error.exception))

    def test_corrupt_history_prevents_plaintext_migration(self):
        from neto_incident_monitor.data_validation import preflight, StartupDataError
        with tempfile.TemporaryDirectory() as d:
            config, history = Path(d)/'config.json', Path(d)/'history.json'
            config.write_text(json.dumps({'teams_webhook': 'PRIVATE_SECRET', 'filters': []}))
            history.write_text(json.dumps({'x': {'incident': {}, 'filters': {'A': 'Name'}, 'detected': 1}}))
            before = {p: p.read_bytes() for p in (config, history)}
            with patch('neto_incident_monitor.secret_config.protect') as protect:
                with self.assertRaises(StartupDataError):
                    preflight(config, history)
                protect.assert_not_called()
            self.assertEqual({p: p.read_bytes() for p in before}, before)

    def test_io_and_dpapi_are_distinct_and_ciphertext_is_preserved(self):
        from neto_incident_monitor.data_validation import preflight, StartupDataError
        from neto_incident_monitor.secret_config import SecretStorageError
        with tempfile.TemporaryDirectory() as d:
            config, history = Path(d)/'config.json', Path(d)/'history.json'
            config.write_text(json.dumps({'teams_webhook': {'protection':'dpapi-user-v1','blob':'synthetic'}, 'filters': []}))
            before = config.read_bytes()
            with patch('neto_incident_monitor.secret_config.unprotect', side_effect=SecretStorageError()):
                preflight(config, history)
            self.assertEqual(config.read_bytes(), before)
            with patch.object(Path, 'read_text', side_effect=PermissionError('PRIVATE_SECRET')):
                with self.assertRaises(StartupDataError) as error:
                    preflight(config, history)
            self.assertEqual(error.exception.category, 'unavailable')

    def test_invalid_history_records_raise_safe_value_error(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'history.json'
            for value in (None, {}, {'incident': {}, 'filters': {'A':'Name'}, 'detected':1},
                          {'incident': {'number': 'INC1'}, 'filters': [], 'detected': 1}):
                path.write_text(json.dumps({'key':value}))
                with self.assertRaises(ValueError):
                    History(path)

    def test_preflight_precedes_app_executors_and_autostart(self):
        from neto_incident_monitor import app
        from neto_incident_monitor.data_validation import StartupDataError
        window = Mock()
        with patch('neto_incident_monitor.data_validation.preflight', side_effect=StartupDataError('configuration','invalid')), \
                patch.object(app.tk, 'Tk', return_value=window), \
                patch.object(app, '_show_startup_problem') as screen, \
                patch.object(app, 'App') as constructor, \
                patch('neto_incident_monitor.startup.reconcile_windows_startup') as startup:
            self.assertFalse(app.main(SimpleNamespace(primary=True)))
            constructor.assert_not_called()
            startup.assert_not_called()
            screen.assert_called_once()

    def test_invalid_sqlite_is_read_only_and_not_replaced(self):
        from neto_incident_monitor.data_validation import preflight, StartupDataError
        import sqlite3
        with tempfile.TemporaryDirectory() as d:
            config, history = Path(d)/'config.json', Path(d)/'history.json'
            store = history.with_suffix('.state.sqlite3')
            with sqlite3.connect(store) as db:
                db.execute('PRAGMA user_version=1')
            db.close()
            before = store.read_bytes()
            with self.assertRaises(StartupDataError) as error:
                preflight(config, history)
            self.assertEqual(error.exception.category, 'invalid')
            self.assertEqual(store.read_bytes(), before)
            self.assertFalse(config.exists())
            self.assertFalse(history.exists())

    def test_real_problem_screen_exposes_only_safe_information_and_close(self):
        import tkinter as tk
        from neto_incident_monitor.app import _show_startup_problem
        from neto_incident_monitor.data_validation import StartupDataError
        from neto_incident_monitor.widgets import RoundedButton
        root = tk.Tk()
        seen = []
        def inspect():
            panel = root.winfo_children()[0]
            children = panel.winfo_children()
            seen.extend(w.cget('text') for w in children if not isinstance(w, RoundedButton))
            next(w for w in children if isinstance(w, RoundedButton)).invoke()
        root.after(0, inspect)
        _show_startup_problem(root, StartupDataError('history', 'invalid'))
        self.assertIn('historia pozostały bez zmian', ' '.join(seen))


if __name__ == '__main__':
    unittest.main()
