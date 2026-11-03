"""One cooperative active-time budget, shared by nested browser operations."""
from contextvars import ContextVar
from contextlib import contextmanager
from time import monotonic
from playwright.sync_api import TimeoutError

CURRENT = ContextVar('read_budget', default=None)
RECOVERY = ContextVar('section_recovery', default=False)


class BudgetExpired(TimeoutError):
    pass


class Budget:
    def __init__(self, seconds):
        self.end = monotonic() + seconds

    def check(self):
        if monotonic() >= self.end:
            raise BudgetExpired('Active read budget exhausted')

    def milliseconds(self, maximum):
        self.check()
        return max(1, min(maximum, int((self.end - monotonic()) * 1000)))


def remaining_ms(maximum):
    budget = CURRENT.get()
    return budget.milliseconds(maximum) if budget else maximum


@contextmanager
def budget_scope(budget, recovery=False):
    token = CURRENT.set(budget)
    recovery_token = RECOVERY.set(recovery)
    try:
        yield budget
    finally:
        RECOVERY.reset(recovery_token)
        CURRENT.reset(token)
