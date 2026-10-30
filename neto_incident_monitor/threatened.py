"""Read only the six SLA-risk counters, without traversing incident lists."""
import re
import time
from playwright.sync_api import TimeoutError
from neto_incident_monitor.browser_actions import navigate_page, checkpoint
from neto_incident_monitor.dashboard import (
    authenticated_read, check_session, activate_dashboard_widgets, _request_tile, operation, _diagnostics,
)
from neto_incident_monitor.login_diagnostics import error_facts
from neto_incident_monitor.pagination import Cancelled

THREATENED_URL = (
    'https://adeo.service-now.com/now/platform-analytics-workspace/dashboards/params/edit/false/'
    'tab-sys-id/54154e7fadc41fd030fd4a7e9f322595/sys-id/22361ad72b6a8b504b98f4c2c891bfab/'
    '__state__/b64-tiny~MwXI59oDkaQ8SM4vFHJzNp3mnHkKbaoo'
)
KEYS = ('P1', 'P2', 'P3', 'P4', 'P5', 'Podjęcie')
READ_TIMEOUT = 45


@authenticated_read
def read_threatened_dashboard(page, stop):
    checkpoint(stop)
    operation('navigate')
    # A fresh navigation makes manual Update a real read, not a cached tab switch.
    navigate_page(page, THREATENED_URL, stop)
    check_session(page)
    deadline = time.monotonic() + READ_TIMEOUT
    previous, stable_since = None, None
    next_activation = 0
    diagnostics = _diagnostics.get()
    last_states = {}
    while time.monotonic() < deadline:
        checkpoint(stop)
        check_session(page)
        if stop.is_set():
            raise Cancelled()
        operation('read_scores')
        current = {}
        for key in KEYS:
            checkpoint(stop)
            # Anchor by category, never by layout order or the extra table below.
            heading = page.get_by_role('heading', name=re.compile(
                r'^\s*' + re.escape(key) + r'\s*[-–—:]\s*<')).filter(visible=True)
            count = heading.count()
            state = {'state': 'missing' if not count else 'ambiguous'}
            if count == 1:
                try:
                    title = heading.inner_text(timeout=500).strip()
                    state = _request_tile(page, title)
                except TimeoutError:
                    state = {'state': 'unavailable'}
            facts = (state['state'], state.get('score_source', 'none'), state.get('loading', False))
            if diagnostics and last_states.get(key) != facts:
                diagnostics.record('dashboard_tile_state', risk_tile=key, tile_state=facts[0],
                                   score_source=facts[1], loading=facts[2])
                last_states[key] = facts
            if state['state'] == 'ready':
                current[key] = state['value']
        if len(current) == len(KEYS):
            if current == previous and time.monotonic() - stable_since >= 1:
                return current
            if current != previous:
                previous, stable_since = current, time.monotonic()
        else:
            previous = stable_since = None
            # Observe complete scores first. Do not scroll an unrelated table
            # when all six counters are already rendered. SPA refreshes can
            # replace cards during enumeration/scrolling; retry with fresh
            # locators, within the same overall deadline, without reloading.
            if time.monotonic() >= next_activation and page.locator('.grid-stack-item-content').filter(visible=True).count():
                try:
                    activate_dashboard_widgets(page, stop)
                except TimeoutError as exc:
                    checkpoint(stop)
                    check_session(page)
                    if diagnostics:
                        diagnostics.record('dashboard_widgets_retry', **error_facts(exc))
                next_activation = time.monotonic() + 1
        page.wait_for_timeout(200)
    raise ValueError('Nie odczytano kompletu sześciu liczników zagrożeń SLA.')
