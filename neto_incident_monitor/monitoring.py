"""Cycle scheduling and interruption alert policy."""
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from itertools import count


DEFAULT_TASK_INTERVAL = 60


@dataclass(frozen=True)
class ReadPart:
    scope: str
    target: object = None
    data: object = field(default=None, compare=False)


@dataclass
class ReadJob:
    id: int
    scope: str
    parts: deque
    requested: tuple
    submitted_at: float = field(default_factory=time.monotonic)
    skipped_filters: int = 0


class ReadQueue:
    """Manual work shared by the UI and the single browser worker."""

    def __init__(self):
        self.lock = threading.Lock()
        self.pending = deque()
        self.active = None
        self.ids = count(1)

    def submit(self, scope, parts):
        with self.lock:
            jobs = ([self.active] if self.active is not None else []) + list(self.pending)
            parts = deque(parts)
            requested = set(parts)
            if scope == 'all':
                existing = next((job for job in jobs if job.scope == 'all' and set(job.requested) == requested), None)
            else:
                existing = next((job for job in jobs if requested.issubset(job.parts)), None)
            if existing is not None:
                return existing.id, True
            merged = False
            if scope == 'all':
                for job in self.pending:
                    if job.scope == 'all':
                        continue
                    remaining = deque(part for part in job.parts if part not in parts)
                    merged |= len(remaining) != len(job.parts)
                    job.parts = remaining
                self.pending = deque(job for job in self.pending if job.parts)
            job = ReadJob(next(self.ids), scope, parts, tuple(parts))
            self.pending.append(job)
            return job.id, merged

    def pending_refreshes(self):
        with self.lock:
            jobs = ([self.active] if self.active is not None else []) + list(self.pending)
            return any(job.scope == 'all' for job in jobs), {part for job in jobs for part in job.parts}

    def has_full_read(self, parts):
        requested = set(parts)
        with self.lock:
            jobs = ([self.active] if self.active is not None else []) + list(self.pending)
            return any(job.scope == 'all' and set(job.requested) == requested for job in jobs)

    def discard_pending_filters(self, parts):
        with self.lock:
            affected = []
            for job in self.pending:
                remaining = deque(part for part in job.parts if part not in parts)
                skipped = len(job.parts) - len(remaining)
                if skipped:
                    job.parts = remaining
                    job.skipped_filters += skipped
                    affected.append((job, skipped))
            self.pending = deque(job for job in self.pending if job.parts)
            return affected

    def cancel_pending(self, part):
        with self.lock:
            for job in self.pending:
                if part in job.parts:
                    job.parts.remove(part)
                    if not job.parts:
                        self.pending.remove(job)
                    return job.id
            return None

    def next_scope(self):
        with self.lock:
            return self.pending[0].scope if self.pending else None

    def take(self):
        with self.lock:
            if self.active is None and self.pending:
                self.active = self.pending.popleft()
            return self.active

    def complete_part(self, part, *, manual, success):
        with self.lock:
            if manual:
                self.active.parts.popleft()
            if success:
                for job in self.pending:
                    job.parts = deque(queued for queued in job.parts if queued != part)
                self.pending = deque(job for job in self.pending if job.parts)

    def finish(self):
        with self.lock:
            self.active = None

    def abort_all(self):
        with self.lock:
            jobs = ([self.active] if self.active is not None else []) + list(self.pending)
            self.active = None
            self.pending.clear()
            return jobs


class RefreshControl:
    """One reserved refresh at a time, shared by Tk and the browser worker."""
    def __init__(self):
        self.lock = threading.Lock()
        self.task = None

    @property
    def busy(self):
        with self.lock:
            return self.task is not None

    def current(self):
        with self.lock:
            return self.task

    def reserve(self, scope, url=None):
        with self.lock:
            if self.task is not None:
                return False
            self.task = (scope, url)
            return True

    def scheduled(self):
        with self.lock:
            if self.task is None:
                self.task = ('scheduled', None)
            return self.task

    def finish(self):
        with self.lock:
            self.task = None


class Schedule:
    def __init__(self):
        self.condition = threading.Condition()
        self.requested = False
        self.woken_by_request = False

    def request(self):
        with self.condition:
            self.requested = True
            self.condition.notify_all()

    def consume(self):
        with self.condition:
            self.requested = False

    def wait(self, seconds, stop):
        deadline = time.monotonic() + seconds
        with self.condition:
            while not self.requested and not stop.is_set():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self.condition.wait(min(remaining, 0.25))
            self.woken_by_request = self.requested
            self.requested = False
        return stop.is_set()


class Health:
    def __init__(self, threshold=3):
        self.threshold = threshold
        self.failures = {}
        self.alerted = set()
        self.authentication_alerted = False

    def failure(self, key):
        self.failures[key] = self.failures.get(key, 0) + 1
        if self.failures[key] >= self.threshold and key not in self.alerted:
            self.alerted.add(key)
            return True
        return False

    def success(self, key):
        self.failures.pop(key, None)
        self.alerted.discard(key)

    def authentication(self):
        if self.authentication_alerted:
            return False
        self.authentication_alerted = True
        return True

    def resumed(self):
        self.authentication_alerted = False
