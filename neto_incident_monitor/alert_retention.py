"""Bounded maintenance of completed entries in the durable alert queue."""
from contextlib import closing
from dataclasses import dataclass
import json
import sqlite3
import time

from neto_incident_monitor.login_diagnostics import LoginDiagnostics, error_facts
from neto_incident_monitor.read_errors import Cancelled


DAY = 24 * 60 * 60
PAYLOAD_AGE = 30 * DAY
UNCERTAIN_AGE = 90 * DAY
BATCH_SIZE = 128
BATCHES_PER_RUN = 4
CONTINUE_AFTER = 30
RETRY_AFTER_ERROR = 5 * 60
COMPLETED_STATES = ('accepted', 'cancelled', 'uncertain')
CHANNELS = ('windows', 'teams', 'google_chat')

# Reuse the payload column to keep the three-column schema compatible with
# earlier versions. Preserve even an unreadable legacy payload until expiry.
STAMP_PAYLOAD = """
    json_set(
        CASE WHEN json_valid(payload) THEN
            CASE WHEN json_type(payload) = 'object' THEN payload
                 ELSE json_object('legacy_payload', payload) END
             ELSE json_object('legacy_payload', payload) END,
        '$._retention', json_object('since', ?, 'source', ?))
"""


@dataclass(frozen=True)
class Batch:
    next_rowid: int | None = None
    scanned: int = 0
    dated: int = 0
    minimized: int = 0
    deleted: int = 0


def _read_metadata(payload):
    try:
        body = json.loads(payload)
    except ValueError:
        return {}, {}
    if not isinstance(body, dict):
        return {}, {}
    metadata = body.get('_retention')
    if not isinstance(metadata, dict):
        return body, {}
    since = metadata.get('since')
    if type(since) is not int or since < 0 or metadata.get('source') not in ('finished', 'recovered', 'observed'):
        return body, {}
    return body, metadata


def clean_batch(store, stop, *, after_rowid, now):
    if not store.is_file():
        return Batch()
    with closing(sqlite3.connect(store.resolve().as_uri() + '?mode=rw', uri=True, timeout=.1)) as db, db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'alert_outbox'").fetchone():
            return Batch()
        # Take the write lock before reading. Other writers cannot change the
        # selected rows or reuse their rowids before this batch commits.
        db.execute('BEGIN IMMEDIATE')
        rows = db.execute(
            """SELECT rowid, state,
                      CASE WHEN state IN ('accepted', 'cancelled', 'uncertain') THEN payload END
               FROM alert_outbox WHERE rowid > ? ORDER BY rowid LIMIT ?""",
            (after_rowid, BATCH_SIZE),
        ).fetchall()
        dated, minimized, deleted = [], [], []
        for rowid, state, payload in rows:
            if state not in COMPLETED_STATES:
                continue
            body, metadata = _read_metadata(payload)
            if not metadata:
                dated.append((now, 'observed', rowid))
                continue
            age = now - metadata['since']
            if age >= (UNCERTAIN_AGE if state == 'uncertain' else PAYLOAD_AGE):
                deleted.append((rowid,))
            elif state == 'uncertain' and age >= PAYLOAD_AGE and metadata.get('minimized') is not True:
                summary = {'_retention': {'since': metadata['since'], 'source': metadata['source'], 'minimized': True}}
                if body.get('channel') in CHANNELS:
                    summary['channel'] = body['channel']
                minimized.append((json.dumps(summary), rowid))
        if stop.is_set():
            raise Cancelled()
        db.executemany(f'UPDATE alert_outbox SET payload = {STAMP_PAYLOAD} WHERE rowid = ?', dated)
        db.executemany("UPDATE alert_outbox SET payload = ? WHERE rowid = ? AND state = 'uncertain'", minimized)
        db.executemany('DELETE FROM alert_outbox WHERE rowid = ?', deleted)
        if stop.is_set():
            raise Cancelled()
        next_rowid = rows[-1][0] if len(rows) == BATCH_SIZE else None
        return Batch(next_rowid, len(rows), len(dated), len(minimized), len(deleted))


class AlertRetention:
    def __init__(self, store, writer, stop):
        self.store = store
        self.writer = writer
        self.stop = stop
        self.future = None
        self.after_rowid = 0
        self.next_at = time.monotonic() + 5

    def tick(self):
        """Called by Tk. Database work and diagnostic writes stay on the writer."""
        if self.stop.is_set():
            return
        now = time.monotonic()
        if self.future is not None:
            if not self.future.done():
                return
            self.after_rowid, delay = self.future.result()
            self.future = None
            self.next_at = now + delay
        if now >= self.next_at:
            self.future = self.writer.submit(self._run, self.after_rowid)

    def _run(self, after_rowid):
        log = LoginDiagnostics(source='monitor')
        started = time.monotonic()
        now = int(time.time())
        totals = dict(retention_scanned=0, retention_dated=0, retention_minimized=0, retention_deleted=0)
        log.record('alert_retention', retention_outcome='started', retention_limit=BATCHES_PER_RUN * BATCH_SIZE)
        delay = CONTINUE_AFTER
        outcome = 'progress'
        facts = {}
        try:
            for _ in range(BATCHES_PER_RUN):
                if self.stop.is_set():
                    raise Cancelled()
                batch = clean_batch(self.store, self.stop, after_rowid=after_rowid, now=now)
                totals['retention_scanned'] += batch.scanned
                totals['retention_dated'] += batch.dated
                totals['retention_minimized'] += batch.minimized
                totals['retention_deleted'] += batch.deleted
                if batch.next_rowid is None:
                    after_rowid = 0
                    delay = DAY
                    outcome = 'complete' if any(totals[key] for key in (
                        'retention_dated', 'retention_minimized', 'retention_deleted')) else 'no_changes'
                    break
                after_rowid = batch.next_rowid
        except Cancelled:
            outcome = 'cancelled'
        except Exception as error:
            sqlite_code = getattr(error, 'sqlite_errorcode', 0) & 255
            if sqlite_code in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
                outcome = 'busy'
            else:
                outcome = 'error'
                delay = RETRY_AFTER_ERROR
            facts = error_facts(error)
        log.record('alert_retention', retention_outcome=outcome,
                   retention_next_s=0 if self.stop.is_set() else delay,
                   duration_ms=round((time.monotonic() - started) * 1000), **totals, **facts)
        return after_rowid, delay
