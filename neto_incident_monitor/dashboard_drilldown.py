"""Resolve observed classic drill-down lists without retaining short URLs."""
from calendar import monthrange
from contextlib import nullcontext
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit

from neto_incident_monitor.service_now_urls import TENANT_HOST, trusted_url

DRILLDOWN_TABLES = {"requests": "sc_task", "held": "incident_metric", "sla": "task_sla"}
_WRAPPER = "/now/nav/ui/classic/params/target/"


def resolve_drilldown(page, section, period=None):
    """Return a direct list URL from the visible drill-down, or None while unverified."""
    table = DRILLDOWN_TABLES.get(section)
    if table is None or not trusted_url(page.url):
        return None
    path = urlsplit(page.url).path
    if not path.startswith(_WRAPPER):
        return None
    destination = urlsplit(unquote(path[len(_WRAPPER):]))
    if destination.path != f"{table}_list.do" or destination.netloc or destination.scheme:
        return None
    frame = page.locator("iframe#gsft_main")
    if frame.count() != 1 or not frame.is_visible():
        return None
    frames = [candidate for candidate in page.frames if candidate.name == "gsft_main"]
    if len(frames) != 1 or not trusted_url(frames[0].url):
        return None
    if urlsplit(frames[0].url).path != f"/{table}_list.do":
        return None
    rows = frames[0].locator(f'table[glide_table="{table}"][query]').filter(visible=True)
    if rows.count() != 1:
        return None
    query = rows.get_attribute("query", timeout=300)
    if not query or any(ord(char) < 32 or ord(char) == 127 for char in query):
        return None
    direct = f"https://{TENANT_HOST}/{table}_list.do?" + urlencode({"sysparm_query": query})
    return direct if valid_drilldown(direct, section, period) else None

def valid_drilldown(url, section, period=None):
    if section not in DRILLDOWN_TABLES or not trusted_url(url):
        return False
    parsed = urlsplit(url)
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    if not (parsed.path == f"/{DRILLDOWN_TABLES[section]}_list.do"
            and len(pairs) == 1 and pairs[0][0] == "sysparm_query" and bool(pairs[0][1])):
        return False
    if section != "sla":
        return True
    if period is None:
        return False
    year, month = period
    last_day = monthrange(year, month)[1]
    start, end = f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last_day:02d}"
    clause = f"task.opened_atBETWEENjavascript:gs.dateGenerate('{start}','start')@javascript:gs.dateGenerate('{end}','end')"
    return [part for part in pairs[0][1].split("^") if part.startswith("task.opened_atBETWEEN")] == [clause]


def collect_drilldown(page, section, title, stop, diagnostics, period=None, *, runtime=None):
    """Resolve only the requested metric in a disposable browser tab."""
    from time import monotonic
    from playwright.sync_api import Error
    from neto_incident_monitor.browser_actions import checkpoint
    from neto_incident_monitor.dashboard import (
        DASHBOARD_URL, check_session, click_control, ensure_all_categories,
        open_section, read_tile, score_pattern, set_period, verify_context,
    )
    from neto_incident_monitor.dashboard_cache import SECTIONS
    from neto_incident_monitor.dashboard_context import DashboardReadError, TAB_IDS
    from neto_incident_monitor.pagination import AuthenticationRequired
    from neto_incident_monitor.read_budget import Budget, budget_scope, remaining_ms
    from neto_incident_monitor.login_diagnostics import error_facts

    if (title not in SECTIONS.get(section, ()) or not trusted_url(page.url)
            or (section == "sla" and period is None)):
        return None
    source_url = DASHBOARD_URL.replace(TAB_IDS["sla"], TAB_IDS[section])
    budget = Budget(18)
    scratch = None
    url = None
    index = SECTIONS[section].index(title)
    started = monotonic()
    diagnostics.record('dashboard_drilldown_start', expected_count=1, tile_index=index)
    try:
        scratch = page.context.new_page()
        visibility = runtime.dashboard_read(scratch, diagnostics) if runtime else nullcontext()
        with visibility, budget_scope(budget):
            for attempt in (1, 2):
                reason = "unavailable"
                try:
                    checkpoint(stop)
                    scratch.goto(source_url, wait_until="commit", timeout=remaining_ms(3000))
                    open_section(scratch, section, stop)
                    expected_period = period or (None, None)
                    try:
                        verify_context(scratch, section, *expected_period)
                    except DashboardReadError as error:
                        if error.reason not in ("wrong_period", "wrong_filter"):
                            raise
                        if section == "sla":
                            if error.reason == "wrong_period":
                                set_period(scratch, *period, stop)
                            ensure_all_categories(scratch, stop)
                        else:
                            ensure_all_categories(scratch, stop, ("Agent L1",))
                        verify_context(scratch, section, *expected_period)

                    ready_until = min(budget.end, monotonic() + 2)
                    facts = read_tile(scratch, title)
                    while facts["state"] != "ready" and monotonic() < ready_until:
                        checkpoint(stop)
                        scratch.wait_for_timeout(100)
                        facts = read_tile(scratch, title)
                    if facts["state"] != "ready":
                        reason = "not_ready"
                        break
                    button = scratch.get_by_role("button", name=score_pattern(title)).filter(visible=True)
                    if button.count() != 1:
                        reason = "button_unavailable"
                        break
                    click_control(button, scratch, stop, timeout=2000)
                    reason = "list_unconfirmed"
                    until = min(budget.end, monotonic() + 3)
                    while monotonic() < until:
                        checkpoint(stop)
                        url = resolve_drilldown(scratch, section, period)
                        if url:
                            reason = "ready"
                            break
                        scratch.wait_for_timeout(100)
                    break
                except AuthenticationRequired:
                    reason = "authentication"
                    if attempt == 2:
                        break
                    try:
                        check_session(page)
                    except AuthenticationRequired:
                        break
                    reason = "authentication_retry"
                except (Error, DashboardReadError) as error:
                    diagnostics.record('section_read_error',
                                       read_reason=getattr(error, 'reason', 'unexpected'),
                                       **error_facts(error))
                    break
                finally:
                    diagnostics.record("dashboard_drilldown_tile", tile_index=index,
                                       attempt=attempt, drilldown_result=reason)
    except Error as error:
        diagnostics.record('section_read_error', **error_facts(error))
    finally:
        if runtime is not None:
            runtime.page = page
        if scratch is not None:
            try:
                scratch.close()
            except Error:
                pass
        diagnostics.record('dashboard_drilldown_finish', ready_count=int(url is not None),
                           duration_ms=round((monotonic() - started) * 1000))
    return url
