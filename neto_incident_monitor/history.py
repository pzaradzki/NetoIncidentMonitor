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
        migrated = {}
        for record in self.records.values():
            for url, name in record.get("filters", {}).items():
                item = copy.deepcopy(record)
                item["filters"] = {url: name}
                migrated[url + "\n" + item["incident"]["number"]] = item
        self.records = migrated

    def _commit(self, records):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)
        self.records = records

    def add(self, incident, filter_name, filter_url, reappeared=False):
        with self.lock:
            records = copy.deepcopy(self.records)
            number = incident["number"]
            key = filter_url + "\n" + number
            fresh = key not in records
            if fresh:
                records[key] = {"incident": incident, "detected": time.time(),
                                   "read": False, "filters": {}}
            records[key]["incident"] = dict(incident)
            records[key]["filters"][filter_url] = filter_name
            if reappeared:
                records[key]["read"] = False
                records[key]["detected"] = time.time()
            self._commit(records)
            return fresh

    def mark_read(self, numbers, filter_url=None):
        with self.lock:
            records = copy.deepcopy(self.records)
            for record in records.values():
                if record["incident"]["number"] in numbers and (filter_url is None or filter_url in record["filters"]):
                    record["read"] = True
            self._commit(records)

    def clear(self, filter_url=None):
        with self.lock:
            self._commit({key: record for key, record in self.records.items()
                          if filter_url is not None and filter_url not in record["filters"]})

    def snapshot(self, filter_url=None):
        with self.lock:
            return {record["incident"]["number"]: copy.deepcopy(record)
                    for record in self.records.values()
                    if filter_url is None or filter_url in record["filters"]}

    def unread(self):
        with self.lock:
            return sum(not record["read"] for record in self.records.values())
