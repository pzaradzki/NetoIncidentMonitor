import tempfile
import unittest
from pathlib import Path

from neto_incident_monitor.history import History


class ThreatenedDetailsTests(unittest.TestCase):
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
