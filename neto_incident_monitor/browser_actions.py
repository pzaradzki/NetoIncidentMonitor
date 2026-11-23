"""Short, cancellable waits executed by the Playwright owner thread."""
import logging
from contextvars import ContextVar
from time import monotonic
from playwright.sync_api import TimeoutError
from neto_incident_monitor.read_errors import BrowserClosedError, Cancelled

from neto_incident_monitor.read_budget import CURRENT, remaining_ms

ACTION_TICK = ContextVar('browser_action_tick', default=None)
LOG = logging.getLogger("servicenow")


def checkpoint(stop):
    if stop is not None and stop.is_set():
        raise Cancelled()
    budget = CURRENT.get()
    if budget:
        budget.check()
    tick = ACTION_TICK.get()
    if tick:
        tick()
    if stop is not None and stop.is_set():
        raise Cancelled()


def navigate_page(page, url, stop, timeout=60000):
    checkpoint(stop)
    deadline = monotonic() + remaining_ms(timeout) / 1000
    committed = False
    def navigated(frame):
        nonlocal committed
        if frame == page.main_frame:
            committed = True
    page.on('framenavigated', navigated)
    try:
        try:
            page.goto(url, wait_until='commit', timeout=remaining_ms(1000))
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
                    page.wait_for_load_state('domcontentloaded', timeout=remaining_ms(500))
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
    deadline = monotonic() + remaining_ms(timeout) / 1000
    while monotonic() < deadline:
        checkpoint(stop)
        if check:
            check()
        try:
            control.wait_for(state=state, timeout=remaining_ms(500))
            checkpoint(stop)
            return
        except TimeoutError:
            pass
    raise TimeoutError('Control deadline exceeded')


def ready_control(control, stop, timeout=30000, check=None, editable=False):
    """Wait for actionability in short trials, without sending a real click."""
    deadline = monotonic() + remaining_ms(timeout) / 1000
    while monotonic() < deadline:
        checkpoint(stop)
        if check:
            check()
        try:
            control.click(trial=True, timeout=remaining_ms(500))
            if not editable or control.is_editable(timeout=remaining_ms(500)):
                checkpoint(stop)
                return
        except TimeoutError:
            pass
        control.page.wait_for_timeout(100)
    raise TimeoutError('Control readiness deadline exceeded')


def read_control(control, stop, read, timeout=15000, check=None, assertion=False):
    """Retry only observations; never repeat a possibly delivered action."""
    deadline = monotonic() + remaining_ms(timeout) / 1000
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


def wait_for_browser_cycle(page, schedule, seconds, stop):
    """Keep Playwright events flowing while waiting for the next read."""
    deadline = monotonic() + seconds
    while not stop.is_set():
        checkpoint(stop)
        if page.is_closed():
            raise BrowserClosedError("Karta monitoringu została zamknięta.")
        if schedule.wait(0, stop):
            return True
        if schedule.woken_by_request:
            return False
        remaining = deadline - monotonic()
        if remaining <= 0:
            return False
        page.wait_for_timeout(min(250, remaining * 1000))
    return True


def minimize_chromium(page):
    set_chromium_window_state(page, "minimized")


def set_chromium_window_state(page, state):
    """Change only the Chromium window containing this tab."""
    session = None
    try:
        session = page.context.new_cdp_session(page)
        window = session.send("Browser.getWindowForTarget")
        session.send("Browser.setWindowBounds", {
            "windowId": window["windowId"], "bounds": {"windowState": state}})
        bounds = session.send("Browser.getWindowBounds", {"windowId": window["windowId"]})
        return bounds.get("bounds", {}).get("windowState") == state
    except Exception:
        LOG.warning("Nie udało się zmienić stanu okna przeglądarki na %s.", state)
    finally:
        if session:
            try:
                session.detach()
            except Exception:
                pass
