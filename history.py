"""Durable, thread-safe history shared by the monitor and the interface."""
import copy
import json
import threading
import time
from pathlib import Path


class History:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.RLock()
        self.records = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}

    def _commit(self, records):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)
        self.records = records

    def add(self, incident, filter_name, filter_url):
        with self.lock:
            records = copy.deepcopy(self.records)
            number = incident["number"]
            fresh = number not in records
            if fresh:
                records[number] = {"incident": incident, "detected": time.time(),
                                   "read": False, "filters": {}}
            records[number]["incident"] = dict(incident)
            records[number]["filters"][filter_url] = filter_name
            self._commit(records)
            return fresh

    def mark_read(self, numbers):
        with self.lock:
            records = copy.deepcopy(self.records)
            for number in numbers:
                if number in records:
                    records[number]["read"] = True
            self._commit(records)

    def clear(self):
        with self.lock:
            self._commit({})

    def snapshot(self):
        with self.lock:
            return copy.deepcopy(self.records)

    def unread(self):
        with self.lock:
            return sum(not record["read"] for record in self.records.values())
