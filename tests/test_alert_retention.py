from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import json
from pathlib import Path
import queue
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from neto_incident_monitor import alert_retention as retention, login_diagnostics
from neto_incident_monitor.app import App
from neto_incident_monitor.data_validation import preflight
from neto_incident_monitor.filter_state import FilterState
from neto_incident_monitor.history import History
from neto_incident_monitor.read_errors import Cancelled
from neto_incident_monitor.safe_logging import DiagnosticFileHandler
from neto_incident_monitor.threatened import KEYS


NOW = 1_800_000_000
PAYLOAD = {'url': 'https://example.test/SYNTHETIC_SECRET', 'channel': 'teams',
           'target': 'revision', 'title': 'Alert', 'message': 'SYNTHETIC_SECRET', 'links': {}}
SCHEMA = 'CREATE TABLE alert_outbox (id TEXT PRIMARY KEY, state TEXT NOT NULL, payload TEXT NOT NULL)'


class AlertRetentionTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.path = self.folder / 'history.json'
        self.history = History(self.path)
        self.stop = threading.Event()

    def seed(self, *rows):
        with closing(sqlite3.connect(self.history.store)) as db, db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name = 'alert_outbox'").fetchone():
                db.execute(SCHEMA)
            db.executemany('INSERT INTO alert_outbox VALUES (?, ?, ?)', (
                (key, state, payload if isinstance(payload, str) else json.dumps(payload))
                for key, state, payload in rows))

    def rows(self):
        with closing(sqlite3.connect(self.history.store)) as db:
            return {key: (state, payload) for key, state, payload in db.execute(
                'SELECT id, state, payload FROM alert_outbox ORDER BY rowid')}

    def batch(self, after=0, now=NOW):
        return retention.clean_batch(self.history.store, self.stop, after_rowid=after, now=now)

    @staticmethod
    def aged(seconds):
        return {**PAYLOAD, '_retention': {'since': NOW - seconds, 'source': 'finished'}}

    def test_terminal_transitions_stamp_time_and_recovery_leaves_pending_untouched(self):
        self.seed(('pending', 'pending', PAYLOAD), ('accepted', 'pending', PAYLOAD),
                  ('cancelled', 'pending', PAYLOAD), ('uncertain', 'sending', PAYLOAD),
                  ('recovered', 'sending', PAYLOAD))
        before = self.rows()
        with patch('neto_incident_monitor.history.time.time', return_value=NOW):
            self.assertTrue(self.history.transition_alert('accepted', 'pending', 'sending'))
            self.assertEqual(json.loads(self.rows()['accepted'][1]), PAYLOAD)
            self.assertTrue(self.history.transition_alert('accepted', 'sending', 'accepted'))
            self.assertTrue(self.history.transition_alert('cancelled', 'pending', 'cancelled'))
            self.assertTrue(self.history.transition_alert('uncertain', 'sending', 'uncertain'))
            self.assertEqual(self.history.pending_alerts(recover=True), [('pending', PAYLOAD)])
        rows = self.rows()
        for key in ('accepted', 'cancelled', 'uncertain', 'recovered'):
            state, raw = rows[key]
            self.assertEqual(state, key if key != 'recovered' else 'uncertain')
            origin = 'recovered' if key == 'recovered' else 'finished'
            self.assertEqual(json.loads(raw)['_retention'], {'since': NOW, 'source': origin})
        self.assertEqual(rows['pending'], before['pending'])

    def test_exact_thresholds_protect_active_rows_and_minimize_uncertain(self):
        a, b = retention.PAYLOAD_AGE, retention.UNCERTAIN_AGE
        self.seed(('pending', 'pending', self.aged(b)), ('sending', 'sending', self.aged(b)),
                  ('young-accepted', 'accepted', self.aged(a - 1)), ('accepted', 'accepted', self.aged(a)),
                  ('young-cancelled', 'cancelled', self.aged(a - 1)), ('cancelled', 'cancelled', self.aged(a)),
                  ('young-uncertain', 'uncertain', self.aged(a - 1)), ('minimize', 'uncertain', self.aged(a)),
                  ('before-delete', 'uncertain', self.aged(b - 1)), ('expired', 'uncertain', self.aged(b)),
                  ('unknown-channel', 'uncertain', {**self.aged(a), 'channel': 'SYNTHETIC_SECRET'}))
        before = self.rows()
        result = self.batch()
        self.assertEqual((result.dated, result.minimized, result.deleted), (0, 3, 3))
        rows = self.rows()
        self.assertEqual(set(before) - set(rows), {'accepted', 'cancelled', 'expired'})
        for key in ('pending', 'sending', 'young-accepted', 'young-cancelled', 'young-uncertain'):
            self.assertEqual(rows[key], before[key])
        self.assertEqual(json.loads(rows['minimize'][1]),
                         {'_retention': {'since': NOW - a, 'source': 'finished', 'minimized': True}, 'channel': 'teams'})
        self.assertEqual(set(json.loads(rows['unknown-channel'][1])), {'_retention'})
        self.assertEqual([key for key, _ in self.history.pending_alerts()], ['pending'])
        same = self.batch()
        self.assertEqual((same.dated, same.minimized, same.deleted), (0, 0, 0))
        self.assertEqual(self.batch(now=NOW + 1).deleted, 3)
        self.assertEqual(set(rows) - set(self.rows()), {'before-delete', 'young-accepted', 'young-cancelled'})

    def test_legacy_rows_get_one_observed_time_and_no_immediate_removal(self):
        self.seed(('accepted', 'accepted', PAYLOAD), ('damaged', 'cancelled', 'INVALID JSON'),
                  ('uncertain', 'uncertain', {'_retention': {'since': False}, **PAYLOAD}))
        self.assertEqual(self.batch().dated, 3)
        rows = self.rows()
        for _, raw in rows.values():
            self.assertEqual(json.loads(raw)['_retention'], {'since': NOW, 'source': 'observed'})
        self.assertEqual(json.loads(rows['damaged'][1])['legacy_payload'], 'INVALID JSON')
        self.history = History(self.path)
        self.assertEqual(self.batch(now=NOW + 1).dated, 0)
        self.assertEqual(self.rows(), rows)
        self.assertEqual(self.batch(now=NOW + retention.PAYLOAD_AGE - 1).deleted, 0)
        self.assertEqual(self.batch(now=NOW + retention.PAYLOAD_AGE).deleted, 2)

    def test_preserves_versions_history_and_preflight_with_or_without_outbox(self):
        self.assertEqual(self.batch(), retention.Batch())
        self.assertFalse(self.history.store.exists())
        incident = {'number': 'INC1', 'url': 'https://example.test/i', 'deadline': '2026-11-23 10:00:00',
                    'remaining': '00:10:00', 'categories': ['P1'], 'percent': 90}
        counters = dict.fromkeys(KEYS, 0)
        counters['P1'] = 1
        for version in (0, 1):
            with self.subTest(version=version):
                self.path = self.folder / f'history-{version}.json'
                self.history = History(self.path)
                self.history.commit_threatened({'INC1': incident}, NOW, lambda: None, lambda _: (), counters=counters)
                if version == 1:
                    self.history.commit_filter(FilterState(self.folder / 'seen.json'), 'A', 'A',
                                               {'INC2': {'number': 'INC2'}}, lambda: None)
                protected = self.history.snapshot('A'), self.history.membership
                threatened = self.history.threatened_snapshot(with_summary=True)
                before = self.history.store.read_bytes()
                self.assertEqual(self.batch(), retention.Batch())
                self.assertEqual(self.history.store.read_bytes(), before)
                self.seed(('legacy', 'cancelled', PAYLOAD), ('active', 'pending', PAYLOAD))
                self.assertEqual(self.batch().dated, 1)
                self.assertEqual(self.batch(now=NOW + retention.PAYLOAD_AGE).deleted, 1)
                # Exercise the three-value insert used by earlier versions.
                self.seed(('older-writer', 'pending', PAYLOAD))
                before = self.history.store.read_bytes()
                preflight(self.folder / 'config.json', self.path)
                self.history = History(self.path)
                self.assertEqual(self.history.store.read_bytes(), before)
                self.assertEqual(self.history.threatened_snapshot(with_summary=True), threatened)
                self.assertEqual((self.history.snapshot('A'), self.history.membership), protected)
                self.assertEqual(self.history.pending_alerts(), [('active', PAYLOAD), ('older-writer', PAYLOAD)])
                with closing(sqlite3.connect(self.history.store)) as db:
                    self.assertEqual(db.execute('PRAGMA user_version').fetchone(), (version,))
                if version == 0:
                    self.history.commit_filter(FilterState(self.folder / 'seen.json'), 'A', 'A',
                                               {'INC2': {'number': 'INC2'}}, lambda: None)
                    self.assertEqual(self.history.threatened_snapshot(with_summary=True), threatened)

    def test_bounded_continuation_and_restart_between_batches(self):
        self.seed(*(('old-' + str(index), 'accepted', self.aged(retention.PAYLOAD_AGE)) for index in range(5)))
        with patch.object(retention, 'BATCH_SIZE', 2):
            first = self.batch()
            self.assertEqual((first.scanned, first.deleted), (2, 2))
            self.stop.set()
            with self.assertRaises(Cancelled):
                self.batch(after=first.next_rowid)
            self.assertEqual(len(self.rows()), 3)
            self.history = History(self.path)
            self.stop.clear()
            second = self.batch()
            final = self.batch(after=second.next_rowid)
        self.assertEqual((second.deleted, final.deleted, final.next_rowid), (2, 1, None))
        self.assertEqual(self.rows(), {})

    def test_cancel_before_commit_rolls_back_batch(self):
        self.seed(('expired', 'accepted', self.aged(retention.PAYLOAD_AGE)), ('legacy', 'cancelled', PAYLOAD))
        before = self.rows()
        stop = Mock()
        stop.is_set.side_effect = [False, True]
        with self.assertRaises(Cancelled):
            retention.clean_batch(self.history.store, stop, after_rowid=0, now=NOW)
        self.assertEqual(self.rows(), before)

    def test_failed_delete_rolls_back_and_delivery_remains_available(self):
        self.seed(('first', 'accepted', self.aged(retention.PAYLOAD_AGE)),
                  ('blocked', 'cancelled', self.aged(retention.PAYLOAD_AGE)),
                  ('active', 'pending', PAYLOAD), ('interrupted', 'sending', PAYLOAD))
        before = self.rows()
        with closing(sqlite3.connect(self.history.store)) as db, db:
            db.execute("""CREATE TRIGGER test_failed_delete BEFORE DELETE ON alert_outbox
                          WHEN old.id = 'blocked' BEGIN SELECT RAISE(ABORT, 'SYNTHETIC_SECRET'); END""")
        with self.assertRaises(sqlite3.IntegrityError):
            self.batch()
        self.assertEqual(self.rows(), before)
        app = App.__new__(App)
        app.history, app.stop, app.events = History(self.path), self.stop, queue.Queue()
        app.alert_routes = Mock(return_value={'teams': ('revision', 'fixture')})
        with patch('neto_incident_monitor.teams_notifications.send') as send:
            app.deliver_alerts(recover=True)
            send.assert_called_once()
        rows = self.rows()
        self.assertEqual((rows['active'][0], rows['interrupted'][0]), ('accepted', 'uncertain'))

    def test_concurrent_writer_leaves_cursor_for_retry_and_keeps_new_alert(self):
        self.seed(('old', 'accepted', self.aged(retention.PAYLOAD_AGE)))
        with ThreadPoolExecutor(max_workers=1) as writer:
            job = retention.AlertRetention(self.history.store, writer, self.stop)
            with closing(sqlite3.connect(self.history.store)) as db, db:
                db.execute('BEGIN IMMEDIATE')
                db.execute("INSERT INTO alert_outbox VALUES ('new', 'pending', ?)", (json.dumps(PAYLOAD),))
                with self.assertLogs('neto.login_diagnostics', level='INFO') as log:
                    result = writer.submit(job._run, 0).result(timeout=5)
                self.assertEqual(result, (0, retention.CONTINUE_AFTER))
                self.assertTrue(any(json.loads(line.getMessage()).get('retention_outcome') == 'busy'
                                    for line in log.records))
            self.assertEqual(self.batch().deleted, 1)
            self.assertEqual(self.history.pending_alerts(), [('new', PAYLOAD)])

    def test_tk_tick_reuses_writer_and_reschedules_without_new_alerts(self):
        self.seed(('old', 'accepted', self.aged(retention.PAYLOAD_AGE)))
        with ThreadPoolExecutor(max_workers=1) as writer, patch.object(retention.time, 'time', return_value=NOW), \
                patch.object(retention.time, 'monotonic', return_value=100) as clock:
            job = retention.AlertRetention(self.history.store, writer, self.stop)
            job.tick()
            self.assertIsNone(job.future)
            clock.return_value = 105
            job.tick()
            self.assertEqual(job.future.result(timeout=5), (0, retention.DAY))
            job.tick()
            self.assertEqual(job.next_at, 105 + retention.DAY)
            self.assertEqual(self.rows(), {})
            self.seed(('legacy', 'cancelled', PAYLOAD))
            clock.return_value += retention.DAY
            job.tick()
            job.future.result(timeout=5)
            self.assertEqual(json.loads(self.rows()['legacy'][1])['_retention']['source'], 'observed')
            self.stop.set()
            job.tick()

    def test_jsonl_records_safe_outcomes_and_correlates_each_run(self):
        self.seed(('old', 'accepted', self.aged(retention.PAYLOAD_AGE)))
        job = retention.AlertRetention(self.history.store, None, self.stop)
        log_dir = self.folder / 'logs'
        with patch.object(login_diagnostics, 'DATA', log_dir), \
                patch.object(login_diagnostics._logger, 'handlers', []), patch.object(retention.time, 'time', return_value=NOW):
            try:
                job._run(0)
                job._run(0)
                self.stop.set()
                job._run(0)
                self.stop.clear()
                with patch.object(retention, 'clean_batch', side_effect=sqlite3.OperationalError(PAYLOAD['url'])):
                    self.assertEqual(job._run(0), (0, retention.RETRY_AFTER_ERROR))
            finally:
                login_diagnostics.close_diagnostics()
        content = (log_dir / 'login-diagnostics.jsonl').read_text(encoding='utf-8')
        self.assertNotIn('SYNTHETIC_SECRET', content)
        self.assertNotIn('https://example.test', content)
        events = [json.loads(line) for line in content.splitlines()]
        events = [event for event in events if event['event'] == 'alert_retention']
        self.assertEqual([e['retention_outcome'] for e in events[1::2]], ['complete', 'no_changes', 'cancelled', 'error'])
        self.assertEqual({e['run_id'] for e in events}, {login_diagnostics.RUN_ID})
        self.assertEqual(len({e['read_id'] for e in events}), 4)
        for started, ended in zip(events[::2], events[1::2], strict=True):
            self.assertEqual(started['read_id'], ended['read_id'])
            self.assertEqual(started['retention_outcome'], 'started')
            self.assertEqual(started['retention_limit'], retention.BATCHES_PER_RUN * retention.BATCH_SIZE)
            self.assertIn('duration_ms', ended)
        self.assertEqual(events[1]['retention_deleted'], 1)
        self.assertEqual(events[-1]['retention_next_s'], retention.RETRY_AFTER_ERROR)

    def test_failed_diagnostics_preserve_cleanup_and_delivery_outcomes(self):
        self.seed(('old', 'accepted', self.aged(retention.PAYLOAD_AGE)), ('active', 'pending', PAYLOAD))
        job = retention.AlertRetention(self.history.store, None, self.stop)
        with patch.object(login_diagnostics, 'DATA', self.folder), \
                patch.object(login_diagnostics._logger, 'handlers', []), \
                patch.object(DiagnosticFileHandler, '_open', side_effect=PermissionError('SYNTHETIC_SECRET')), \
                patch.object(retention.time, 'time', return_value=NOW):
            try:
                self.assertEqual(job._run(0), (0, retention.DAY))
            finally:
                login_diagnostics.close_diagnostics()
        self.assertNotIn('old', self.rows())
        self.assertEqual(self.history.pending_alerts(), [('active', PAYLOAD)])
