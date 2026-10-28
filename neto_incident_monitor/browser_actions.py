"""Short, cancellable waits executed by the Playwright owner thread."""
from contextvars import ContextVar
from time import monotonic
from playwright.sync_api import TimeoutError
from neto_incident_monitor.pagination import Cancelled

ACTION_TICK = ContextVar('browser_action_tick', default=None)


def checkpoint(stop):
    if stop is not None and stop.is_set():
        raise Cancelled()
    tick = ACTION_TICK.get()
    if tick:
        tick()
    if stop is not None and stop.is_set():
        raise Cancelled()


def navigate_page(page, url, stop, timeout=60000):
    checkpoint(stop)
    deadline = monotonic() + timeout / 1000
    committed = False
    def navigated(frame):
        nonlocal committed
        if frame == page.main_frame:
            committed = True
    page.on('framenavigated', navigated)
    try:
        try:
            page.goto(url, wait_until='commit', timeout=1000)
            committed = True
        except TimeoutError:
            pass  # Keep the pending navigation; do not issue another request.
        except Exception as error:
            if 'interrupted by another navigation' not in str(error):
                raise
        while monotonic() < deadline:
            checkpoint(stop)
            if committed:
                try:
                    page.wait_for_load_state('domcontentloaded', timeout=500)
                    checkpoint(stop)
                    return
                except TimeoutError:
                    pass
            else:
                page.wait_for_timeout(100)
        raise TimeoutError('Navigation deadline exceeded')
    finally:
        try:
            page.remove_listener('framenavigated', navigated)
        except Exception:
            pass


def wait_control(control, stop, timeout=30000, state='visible', check=None):
    deadline = monotonic() + timeout / 1000
    while monotonic() < deadline:
        checkpoint(stop)
        if check:
            check()
        try:
            control.wait_for(state=state, timeout=500)
            checkpoint(stop)
            return
        except TimeoutError:
            pass
    raise TimeoutError('Control deadline exceeded')


def ready_control(control, stop, timeout=30000, check=None, editable=False):
    """Wait for actionability in short trials, without sending a real click."""
    deadline = monotonic() + timeout / 1000
    while monotonic() < deadline:
        checkpoint(stop)
        if check:
            check()
        try:
            control.click(trial=True, timeout=500)
            if not editable or control.is_editable(timeout=500):
                checkpoint(stop)
                return
        except TimeoutError:
            pass
        control.page.wait_for_timeout(100)
    raise TimeoutError('Control readiness deadline exceeded')


def read_control(control, stop, read, timeout=15000, check=None, assertion=False):
    """Retry only observations; never repeat a possibly delivered action."""
    deadline = monotonic() + timeout / 1000
    while monotonic() < deadline:
        checkpoint(stop)
        if check:
            check()
        try:
            return read()
        except TimeoutError:
            pass
        except AssertionError:
            if not assertion:
                raise
        control.page.wait_for_timeout(100)
    raise TimeoutError('Control observation deadline exceeded')
