"""Durable, thread-safe history shared by the monitor and the interface."""
import copy
import json
import sqlite3
from contextlib import closing
import threading
import time
from pathlib import Path
from uuid import uuid4


class History:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.RLock()
        self.store = self.path.with_suffix(".state.sqlite3")
        self.membership = None
        raw = {}
        if self.store.exists():
            with closing(sqlite3.connect(self.store.resolve().as_uri() + '?mode=ro', uri=True)) as db:
                version, = db.execute("PRAGMA user_version").fetchone()
                if version == 1:
                    tables = {name for name, in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                    if not {'history', 'membership'} <= tables:
                        raise ValueError('Niekompletny magazyn filtrów.')
                    raw = dict((key, json.loads(value)) for key, value in db.execute(
                        "SELECT key, value FROM history"))
                    from neto_incident_monitor.filter_state import validate_membership
                    self.membership = validate_membership(dict(
                        (key, json.loads(value)) for key, value in db.execute("SELECT key, value FROM membership")))
                elif version != 0 or db.execute(
                        "SELECT 1 FROM sqlite_master WHERE type = 'table' "
                        "AND name NOT IN ('threatened_history', 'alert_outbox')"
                ).fetchone():
                    raise ValueError("Nieprawidłowa wersja magazynu filtrów.")
        if self.membership is None and self.path.exists():
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        from neto_incident_monitor.data_validation import validate_history
        validate_history(raw)
        self.records = raw
        migrated = {}
        for record in self.records.values():
            for url, name in record.get("filters", {}).items():
                item = copy.deepcopy(record)
                item.pop("read", None)
                item["filters"] = {url: name}
                migrated[url + "\n" + item["incident"]["number"]] = item
        self.records = migrated

    def _commit(self, records, membership=None, before_commit=None, alerts=()):
        membership = self.membership if membership is None else membership
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if membership is None:
            temporary = self.path.with_suffix(".tmp")
            try:
                temporary.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
                temporary.replace(self.path)
            finally:
                temporary.unlink(missing_ok=True)
        else:
            try:
                self._commit_store(records, membership, before_commit, alerts)
            except sqlite3.Error:
                raise OSError("Nie udało się zapisać transakcji historii i stanu filtrów.") from None
        self.records, self.membership = records, membership

    def _commit_store(self, records, membership, before_commit, alerts):
        with closing(sqlite3.connect(self.store)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            version, = db.execute("PRAGMA user_version").fetchone()
            if version == 0 and self.membership is None:
                db.execute("CREATE TABLE history (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
                db.execute("CREATE TABLE membership (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
                db.execute("PRAGMA user_version = 1")
                previous_records, previous_membership = {}, {}
            elif version == 1 and self.membership is not None:
                previous_records, previous_membership = self.records, self.membership
            else:
                raise ValueError("Magazyn filtrów zmienił się podczas zapisu.")
            self._write_changes(db, "history", previous_records, records)
            self._write_changes(db, "membership", previous_membership, membership)
            self._enqueue_alerts(db, alerts)
            if before_commit is not None:
                before_commit()

    @staticmethod
    def _enqueue_alerts(db, alerts):
        if alerts:
            db.execute("CREATE TABLE IF NOT EXISTS alert_outbox (id TEXT PRIMARY KEY, "
                       "state TEXT NOT NULL, payload TEXT NOT NULL)")
            db.executemany("INSERT INTO alert_outbox VALUES (?, 'pending', ?)",
                           ((uuid4().hex, json.dumps(alert, ensure_ascii=False)) for alert in alerts))

    def threatened_snapshot(self):
        if not self.store.exists():
            return {}
        with closing(sqlite3.connect(self.store.resolve().as_uri() + '?mode=ro', uri=True)) as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name = 'threatened_history'").fetchone():
                return {}
            return {key: json.loads(value) for key, value in db.execute(
                "SELECT key, value FROM threatened_history")}

    def commit_threatened(self, incidents, timestamp, checkpoint, prepare_alerts):
        with self.lock:
            checkpoint()
            self.store.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(self.store)) as db, db:
                db.execute("BEGIN IMMEDIATE")
                db.execute("CREATE TABLE IF NOT EXISTS threatened_history (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
                previous = {key: json.loads(value) for key, value in db.execute(
                    "SELECT key, value FROM threatened_history")}
                updated = {key: dict(value, present=False) for key, value in previous.items()}
                arrivals = []
                for key, incident in incidents.items():
                    old = previous.get(key, {})
                    arrived = not old.get("present", False)
                    if arrived:
                        arrivals.append(incident)
                    updated[key] = dict(incident, present=True, last_seen=timestamp,
                                        first_seen=old.get("first_seen", timestamp),
                                        appearances=old.get("appearances", 0) + int(arrived))
                self._write_changes(db, "threatened_history", previous, updated)
                self._enqueue_alerts(db, tuple(prepare_alerts(arrivals)) if arrivals else ())
                checkpoint()
            return updated, len(arrivals)

    def pending_alerts(self, *, recover=False):
        if not self.store.exists():
            return []
        with closing(sqlite3.connect(self.store)) as db, db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name = 'alert_outbox'").fetchone():
                return []
            if recover:
                db.execute("UPDATE alert_outbox SET state = 'uncertain' WHERE state = 'sending'")
            return [(key, json.loads(payload)) for key, payload in db.execute(
                "SELECT id, payload FROM alert_outbox WHERE state = 'pending' ORDER BY rowid")]

    def transition_alert(self, key, expected, state):
        allowed = {("pending", "sending"), ("pending", "cancelled"),
                   ("sending", "accepted"), ("sending", "uncertain")}
        if (expected, state) not in allowed:
            raise ValueError("Niedozwolona zmiana stanu alertu.")
        with closing(sqlite3.connect(self.store)) as db, db:
            updated = db.execute(
                "UPDATE alert_outbox SET state = ? WHERE id = ? AND state = ?",
                (state, key, expected),
            )
            return updated.rowcount == 1

    @staticmethod
    def _write_changes(db, table, previous, current):
        db.executemany(f"DELETE FROM {table} WHERE key = ?",
                       ((key,) for key in previous.keys() - current.keys()))
        db.executemany(f"INSERT OR REPLACE INTO {table} VALUES (?, ?)",
                       ((key, json.dumps(value, ensure_ascii=False)) for key, value in current.items()
                        if value is not previous.get(key) and value != previous.get(key)))

    def commit_filter(self, legacy, url, name, incidents, first_only, checkpoint, prepare_alerts=None):
        with self.lock:
            checkpoint()
            membership = self.membership if self.membership is not None else legacy.filters
            previous = membership.get(url, {})
            arrivals = set(incidents) - set(previous.get("present", []))
            new = set(incidents) - set(previous.get("ever" if first_only else "present", []))
            records = self.records.copy()
            detected = time.time()
            for number in arrivals:
                records[url + '\n' + number] = {
                    "incident": copy.deepcopy(incidents[number]), "detected": detected,
                    "filters": {url: name},
                }
            updated = membership.copy()
            updated[url] = {"present": sorted(incidents),
                            "ever": sorted(set(previous.get("ever", [])) | set(incidents))}
            checkpoint()
            if self.membership is None or updated != membership:
                alerts = prepare_alerts(new) if prepare_alerts and new and url in membership else ()
                self._commit(records, updated, checkpoint, tuple(alerts))
            return new if url in membership else set()

    def add(self, incident, filter_name, filter_url, reappeared=False):
        return incident['number'] in self.add_many([incident], filter_name, filter_url, reappeared)

    def add_many(self, incidents, filter_name, filter_url, reappeared=False):
        incidents = list(incidents)
        if not incidents:
            return set()
        with self.lock:
            records = copy.deepcopy(self.records)
            fresh = set()
            for incident in incidents:
                number = incident['number']
                key = filter_url + '\n' + number
                if key not in records:
                    fresh.add(number)
                    records[key] = {'incident': incident, 'detected': time.time(),
                                    'filters': {}}
                records[key]['incident'] = copy.deepcopy(incident)
                records[key]['filters'][filter_url] = filter_name
                if reappeared:
                    records[key]['detected'] = time.time()
            self._commit(records)
            return fresh

    def clear(self, filter_url=None):
        with self.lock:
            self._commit({key: record for key, record in self.records.items()
                          if filter_url is not None and filter_url not in record["filters"]})

    def snapshot(self, filter_url=None):
        # Writers publish a replacement dict after the complete disk commit.
        # The UI can safely read the previous snapshot without waiting for I/O.
        records = self.records
        return {record["incident"]["number"]: copy.deepcopy(record)
                for record in records.values()
                if filter_url is None or filter_url in record["filters"]}

    def record(self, number, filter_url):
        value = self.records.get(filter_url + '\n' + number)
        return copy.deepcopy(value) if value is not None else None
