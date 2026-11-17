import tempfile
import unittest
from pathlib import Path

from neto_incident_monitor.data_validation import preflight
from neto_incident_monitor.filter_state import FilterState
from neto_incident_monitor.history import History
from neto_incident_monitor.threatened import KEYS


class ThreatenedDetailsTests(unittest.TestCase):
    def test_first_threatened_read_survives_startup_and_filter_migration(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path = Path(folder) / 'history.json'
            config = path.with_name('config.json')
            number = 'INC0001'
            incident = {'number': number, 'url': 'https://example.test/incident',
                        'deadline': '2026-11-17 12:00:00', 'remaining': '00:10:00',
                        'categories': ['P1'], 'percent': 90}
            counters = dict.fromkeys(KEYS, 0)
            counters['P1'] = 1
            alert = {'channel': 'windows', 'count': 1}
            history = History(path)
            rows, arrivals = history.commit_threatened(
                {number: incident}, 1, lambda: None, lambda _: [alert], counters=counters, duration_ms=42)
            expected_snapshot = (rows, {'counters': counters, 'read_at': 1, 'duration_ms': 42})
            self.assertEqual(arrivals, 1)
            before = history.store.read_bytes()

            preflight(config, path)
            reopened = History(path)
            self.assertIsNone(reopened.membership)
            self.assertEqual(reopened.store.read_bytes(), before)
            self.assertEqual(reopened.threatened_snapshot(with_summary=True), expected_snapshot)
            pending = reopened.pending_alerts()
            self.assertEqual([payload for _, payload in pending], [alert])

            legacy = FilterState(path.with_name('seen.json'))
            reopened.commit_filter(legacy, 'test-filter', 'Test', {number: {'number': number}}, lambda: None)
            preflight(config, path)
            migrated = History(path)
            self.assertEqual(migrated.membership['test-filter']['present'], [number])
            self.assertIn(number, migrated.snapshot('test-filter'))
            self.assertEqual(migrated.threatened_snapshot(with_summary=True), expected_snapshot)
            self.assertEqual(migrated.pending_alerts(), pending)

    def test_history_and_outbox_survive_restart_and_rollback(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path = Path(folder) / 'history.json'
            snapshot = {'INC0001': {'number': 'INC0001'}}
            def prepare(rows):
                return [{'channel': 'windows', 'count': len(rows)}]
            def checkpoint():
                pass
            history = History(path)
            self.assertEqual(history.commit_threatened(snapshot, 1, checkpoint, prepare)[1], 1)
            history = History(path)
            self.assertEqual(history.commit_threatened(snapshot, 2, checkpoint, prepare)[1], 0)
            self.assertEqual(len(history.pending_alerts()), 1)
            history.commit_threatened({}, 3, checkpoint, prepare)
            self.assertFalse(history.threatened_snapshot()['INC0001']['present'])
            calls = iter((None, RuntimeError('cancelled')))
            def interrupted():
                if error := next(calls):
                    raise error
            with self.assertRaises(RuntimeError):
                history.commit_threatened(snapshot, 4, interrupted, prepare)
            self.assertFalse(history.threatened_snapshot()['INC0001']['present'])
            self.assertEqual(len(history.pending_alerts()), 1)
            self.assertEqual(history.commit_threatened(snapshot, 5, checkpoint, prepare)[0]
                             ['INC0001']['appearances'], 2)
            self.assertEqual(len(history.pending_alerts()), 2)
