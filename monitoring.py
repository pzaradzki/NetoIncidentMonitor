"""Cycle scheduling and interruption alert policy."""
import threading
import time


class Schedule:
    def __init__(self):
        self.condition = threading.Condition()
        self.requested = False

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
