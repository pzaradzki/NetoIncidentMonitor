"""Local ServiceNow list monitor. Browser access only; no ServiceNow API."""
from neto_incident_monitor.dynamic_columns import DynamicColumns, load_profiles
from neto_incident_monitor.columns import ColumnDiscovery
from neto_incident_monitor.theme import BG, SURFACE, TEXT, MUTED, ACCENT
from neto_incident_monitor.columns import FIELDS, DEFAULT, age_minutes
from neto_incident_monitor.widgets import IncidentMenu, PriorityDots
from neto_incident_monitor.login_diagnostics import diagnostic_read
from contextlib import nullcontext
import json
import logging
import queue
import re
import threading
from concurrent.futures import ThreadPoolExecutor
import time
import tkinter as tk
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import ttk
from neto_incident_monitor import themed_dialogs as messagebox
from urllib.parse import urlparse, unquote
from neto_incident_monitor.service_now_urls import effective_list_url, is_short_url, resolved_list_url
from neto_incident_monitor.history import History
from neto_incident_monitor.monitoring import Schedule, Health
from neto_incident_monitor.pagination import read_all, AuthenticationRequired, Cancelled, LargeListRejected
from playwright._impl._errors import TargetClosedError

from neto_incident_monitor.runtime_paths import ROOT, DATA
CONFIG = DATA / "config.json"
STATE = DATA / "seen.json"
INC = re.compile(r"\b(?:INC|SCTASK|REQ|RITM)\d{7,}\b", re.I)
from neto_incident_monitor.login_diagnostics import error_facts
LOG = logging.getLogger("servicenow")


class LoginTargetUnavailable(RuntimeError):
    """Login finished but the requested list could not be verified."""


class LoginPopupClosed(LoginTargetUnavailable):
    """The user dismissed the authentication popup before session confirmation."""


class BrowserClosedError(RuntimeError):
    """The monitored browser was closed and can be started again."""


def wait_for_browser_cycle(page, schedule, seconds, stop):
    """Keep Playwright events flowing while waiting for the next read."""
    deadline = time.monotonic() + seconds
    while not stop.is_set():
        from neto_incident_monitor.browser_actions import checkpoint
        checkpoint(stop)
        if page.is_closed():
            raise BrowserClosedError("Karta monitoringu została zamknięta.")
        if schedule.wait(0, stop):
            return True
        if schedule.woken_by_request:
            return False
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        page.wait_for_timeout(min(250, remaining * 1000))
    return True


def without_read_settings(settings):
    from copy import copy

    cleaned = copy(settings)
    cleaned.pop("highlight_unread", None)
    for key in ("visible_columns", "column_widths"):
        value = cleaned.get(key)
        if isinstance(value, list):
            cleaned[key] = [column for column in value if column != "read"]
        elif isinstance(value, dict):
            cleaned[key] = {column: width for column, width in value.items() if column != "read"}
    for key in ("filter_visible_columns", "filter_column_profiles"):
        if isinstance(cleaned.get(key), dict):
            cleaned[key] = {
                url: ([column for column in profile if column != "read"] if isinstance(profile, list)
                      else without_read_column(profile))
                for url, profile in cleaned[key].items()
            }
    return cleaned


def without_read_column(profile):
    if not isinstance(profile, dict):
        return profile
    result = dict(profile)
    for key in ("order", "visible"):
        if isinstance(result.get(key), list):
            result[key] = [column for column in result[key] if column != "read"]
    if isinstance(result.get("schema"), list):
        result["schema"] = [column for column in result["schema"]
                            if not isinstance(column, dict) or column.get("key") != "read"]
    if isinstance(result.get("widths"), dict):
        result["widths"] = {column: width for column, width in result["widths"].items() if column != "read"}
    return result


def read_json(path, default):
    if path == CONFIG:
        from neto_incident_monitor.secret_config import load_config
        return without_read_settings(load_config(path, default))
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, value):
    if path == CONFIG:
        from neto_incident_monitor.secret_config import save_config
        return save_config(path, without_read_settings(value))
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def normalize_url(url):
    from neto_incident_monitor.service_now_urls import normalize_list_url
    return normalize_list_url(url)


@diagnostic_read
def validate_urls(text):
    urls = [line.strip() for line in text.splitlines() if line.strip()]
    if not urls:
        raise ValueError("Wklej przynajmniej jeden adres listy z filtrem.")
    from neto_incident_monitor.login_diagnostics import LoginDiagnostics
    try:
        diagnostics = LoginDiagnostics(source='configuration')
    except Exception:
        diagnostics = None
    def record(**facts):
        try:
            if diagnostics is not None:
                diagnostics.record('filter_url_validation', **facts)
        except Exception:
            pass  # Validation must not depend on diagnostic storage.
    result = []
    for url in urls:
        kind = ('short' if is_short_url(url) else 'wrapper' if
                '/now/nav/ui/classic/params/target/' in url else 'direct')
        try:
            normalized = normalize_url(url)
        except ValueError as error:
            record(url_kind=kind, validation_result='rejected',
                   validation_reason=getattr(error, 'reason', 'unsafe'))
            raise
        record(url_kind=kind, validation_result='accepted', validation_reason='none')
        result.append(normalized)
    return list(dict.fromkeys(result))


def load_filters(settings, tolerate_invalid=False):
    """Migrate the previous URL-only configuration without touching seen state."""
    entries = settings["filters"] if "filters" in settings else [
        {"name": f"Filtr {index}", "url": url}
        for index, url in enumerate(settings.get("urls", []), 1)
    ]
    result = []
    for entry in entries:
        try:
            validated = {**entry, "url": normalize_url(entry["url"])}
            validated.pop('url_invalid', None)
            result.append(validated)
        except ValueError:
            if not tolerate_invalid:
                raise
            # Keep the original value editable, but never navigate to it.
            result.append({**entry, "enabled": False, "url_invalid": True})
    return result


def initialize_default_filters(settings, path=CONFIG):
    """Persist defaults once, only when no previous configuration exists."""
    if path.exists() or 'filters' in settings or 'urls' in settings:
        return settings
    from neto_incident_monitor.default_filters import default_filters
    initialized = {**settings, 'filters': default_filters()}
    save_json(path, initialized)
    return initialized


def incident_values(incident):
    values = []
    for key, _, _ in FIELDS:
        if key in ("read", "time"):
            continue
        value = age_minutes(incident.get("created"), incident.get("number")) if key == "age_minutes" else incident.get(key) or "—"
        if key == "priority" and str(value).strip()[:1] in PriorityDots.COLORS:
            value = "\u2003\u2002" + str(value).strip()
        values.append(value)
    return tuple(values)


def collect(page, available=None):
    """Read incident fields by header identity, including empty-list metadata."""
    found = {}
    from neto_incident_monitor.list_context import ListStateError, ListView
    from neto_incident_monitor.read_budget import remaining_ms
    from neto_incident_monitor.service_now_urls import RECORD_TABLES, normalize_list_url, safe_record_url
    prefixes = {f"/{table}_list.do": prefix for prefix, table in RECORD_TABLES.items()}
    for frame in page.frames:
        try:
            frame_url = normalize_list_url(frame.url, allow_short=False)
        except ValueError:
            continue
        expected = prefixes.get(urlparse(frame_url).path)
        read_rows = """tables => tables.flatMap(table => {
          const visible = el => !!(el.getClientRects().length &&
            getComputedStyle(el).visibility !== 'hidden');
          const fieldName = th => (th.getAttribute('glide_field') || th.getAttribute('name') || th.getAttribute('data-name') || (/^(Numer|Number)$/i.test(th.textContent.trim()) ? 'number' : th.textContent.trim())).replace(/^(?:incident|sc_task|sc_request|sc_req_item)\\./, '');
          const fieldLabel = th => (th.getAttribute('glide_label') || th.querySelector('a.column_head')?.textContent || th.textContent).trim();
          const rows = Array.from(table.rows).filter(tr => tr.closest('table') === table && visible(tr)
            && !tr.classList.contains('list_header_search_row'));
          const candidates = rows.map(tr => Array.from(tr.cells).filter(th => th.tagName === 'TH' && visible(th)
            && !th.classList.contains('col-control') && !th.classList.contains('list-decoration-table')
            && !th.querySelector('input, select, textarea, button, .list_header_search_toggle')
            && !!fieldName(th)));
          const marked = candidates.filter(cells => cells.some(th => th.hasAttribute('glide_field')));
          const eligible = (marked.length ? marked : candidates).filter(cells => cells.some(th => fieldName(th) === 'number'));
          if (!eligible.length) return [];
          if (eligible.length !== 1) throw new Error('Ambiguous ServiceNow column headers');
          const headers = eligible[0].filter(th => !marked.length || th.hasAttribute('glide_field'));
          const header = headers.find(th => {
            const name = fieldName(th);
            return /^(?:(?:incident|sc_task|sc_request|sc_req_item)\\.)?number$/.test(name) || /^(Numer|Number)$/i.test(th.innerText.trim());
          });
          if (!header) return [];
          const column = (names, labels) => headers.find(th => {
            const name = fieldName(th);
            return names.includes(name);
          }) || headers.find(th => labels.includes(th.innerText.trim().toLowerCase()));
          const fields = {
            short_description: column(['short_description'], ['krótki opis', 'short description']),
            priority: column(['priority'], ['priorytet', 'priority']),
            location: column(['location'], ['lokalizacja', 'location']),
            created: column(['sys_created_on'], ['utworzono', 'created']),
            updated: column(['sys_updated_on'], ['zaktualizowano', 'updated']),
            state: column(['state', 'incident_state', 'request_state'], ['stan', 'state']),
            caller: column(['caller_id'], ['zgłaszający', 'caller']),
            requested_for: column(['requested_for', 'request.requested_for', 'request_item.request.requested_for'], ['wnioskowane dla', 'requested for']),
            opened_by: column(['opened_by'], ['otwarte przez', 'opened by']),
            assigned_to: column(['assigned_to'], ['przypisane do', 'assigned to']),
            description: column(['description'], ['opis', 'description']),
            parent_incident: column(['parent_incident', 'parent'], ['incydent nadrzędny', 'parent incident']),
            configuration_item: column(['cmdb_ci'], ['objęty element konfiguracji', 'element konfiguracji', 'configuration item']),
            assignment_group: column(['assignment_group'], ['grupa przypisania', 'assignment group'])
          };
          const used = new Map();
          const schema = headers.map(th => {
            const label = fieldLabel(th).replace(/\\s+/g, ' ').trim();
            const raw = fieldName(th);
            const known = th === header ? 'number' : Object.keys(fields).find(key => fields[key] === th);
            const base = raw === 'request_state' ? 'sn:request_state' : known || 'sn:' + raw;
            const occurrence = used.get(base) || 0;
            used.set(base, occurrence + 1);
            return {key: base + (occurrence ? ':' + occurrence : ''), label: label || raw, index: th.cellIndex};
          });
          return [{available: schema.map(c => c.key), schema: schema.map(({key, label}) => ({key, label}))}, ...Array.from(table.rows).filter(tr => tr.closest('table') === table && visible(tr))
            .flatMap(tr => {
              const cell = tr.cells[header.cellIndex];
              if (!cell || cell.tagName !== 'TD') return [];
              return Array.from(cell.querySelectorAll('a')).filter(visible).map(a => ({
                label: a.innerText, href: a.href, row: tr.innerText,
                values: Object.fromEntries(schema.map(c => [c.key, tr.cells[c.index]?.innerText.trim() || ''])),
                fields: Object.fromEntries(Object.entries(fields).map(([key, th]) => {
                  const td = th && tr.cells[th.cellIndex];
                  return [key, td ? td.innerText.trim() : ''];
                }))
              }));
            })];
        })"""
        tables = frame.locator("table:visible")
        if isinstance(page, ListView):
            rows = tables.evaluate(f"table => ({read_rows})([table])", timeout=remaining_ms(1000))
        else:
            rows = tables.evaluate_all(read_rows)
        for row in rows:
            if "available" in row:
                if available is not None:
                    available.update(row["available"])
                    if hasattr(available, 'discover') and row.get('schema'):
                        available.discover(row['schema'])
                continue
            match = INC.fullmatch(row["label"].strip())
            if match:
                number = match.group().upper()
                if expected and not re.fullmatch(expected + r"\d+", number):
                    raise ListStateError("record_type_mismatch")
                found[number] = {"number": number, "url": safe_record_url(row["href"], number, frame_url),
                                 "_values": {key: " ".join(value.split()) for key, value in row.get('values', {}).items()},
                                 **{key: " ".join(value.split()) for key, value in row["fields"].items()},
                                 "summary": " ".join(row["fields"]["short_description"].split())
                                 or number}
    return found


def empty_list(page, url):
    """Accept the empty-list message only on the expected incident-list frame."""
    from neto_incident_monitor.service_now_urls import trusted_url
    expected_host = urlparse(url).hostname
    for frame in page.frames:
        parsed = urlparse(frame.url)
        if not trusted_url(frame.url) or parsed.hostname != expected_host or parsed.path != urlparse(url).path:
            continue
        messages = frame.get_by_text(re.compile(
            r"Brak\s+rekordów\s+do\s+wyświetlenia|No\s+records\s+to\s+display", re.I))
        for index in range(messages.count()):
            if messages.nth(index).is_visible():
                return True
    return False


def navigate(page, url, stop=None):
    # SSO can start a second navigation before goto has finished. Keep that
    # navigation alive so that the user can complete authentication.
    url = normalize_url(url)
    try:
        if stop is None:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
        else:
            from neto_incident_monitor.browser_actions import navigate_page
            navigate_page(page, url, stop)
        actual = page.url
        if (not is_short_url(url) and isinstance(actual, str) and urlparse(actual).hostname == urlparse(url).hostname
                and actual.startswith(f"https://{urlparse(url).netloc}/now/nav/ui/classic/params/target/")):
            # Authentication/session restoration can wrap an otherwise direct
            # URL. Reopen the requested list rather than the navigation shell.
            if stop is None:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
            else:
                navigate_page(page, url, stop)
    except Exception as exc:
        if "interrupted by another navigation" not in str(exc):
            raise


def open_login_target(page, url, stop, on_error=None):
    from neto_incident_monitor.login_diagnostics import LoginDiagnostics
    diagnostics = LoginDiagnostics(source='monitor')
    detach = diagnostics.attach(page)
    try:
        for attempt in range(1, 4):
            if stop.is_set():
                return False
            diagnostics.record('initial_navigation_attempt', attempt=attempt)
            try:
                navigate(page, url, stop)
                return True
            except Cancelled:
                diagnostics.record('login_cancelled')
                return False
            except TargetClosedError:
                raise
            except Exception as exc:
                diagnostics.record('initial_navigation_error', attempt=attempt, **error_facts(exc))
                if on_error:
                    try:
                        on_error(error_facts(exc))
                    except Exception:
                        pass
                actual = urlparse(page.url)
                if actual.scheme == 'https' and actual.hostname:
                    # Continue inspecting the current page after a slow redirect.
                    return True
                if attempt < 3:
                    page.wait_for_timeout(1000)
        raise LoginTargetUnavailable('Nie udało się połączyć z ServiceNow po trzech próbach.')
    finally:
        detach()


def authentication_page(page, url):
    from neto_incident_monitor.authentication import authentication_required
    return authentication_required(page, url)


def wait_for_login(page, url, stop, auto_login=False, minimize_after_login=False, browser_window=None,
                   on_visibility_failure=None, runtime=None, on_activity=None):
    """Observe authentication, retain delivery ownership and recover only safe GETs."""
    from neto_incident_monitor.automatic_login import AutomaticLogin
    from neto_incident_monitor.authentication import (login_surface, login_observation,
        document_generation, manual_handoff, finish_authentication, set_login_activity, clear_login_activity)
    from neto_incident_monitor.login_diagnostics import LoginDiagnostics
    from neto_incident_monitor.login_observation import origin_kind
    diagnostics = LoginDiagnostics(auto_login=bool(auto_login), minimize=bool(minimize_after_login))
    if runtime:
        diagnostics.network_error = {'network_dns': 'dns', 'network_connection': 'connection',
            'network_tls': 'certificate', 'timeout': 'timeout'}.get(getattr(runtime, 'navigation_error', None))
        runtime.navigation_error = None
    enabled = lambda: not stop.is_set() and (runtime.options.snapshot()['auto_login'] if runtime else auto_login)
    automatic = AutomaticLogin(diagnostics=diagnostics, enabled=enabled)
    detach = [diagnostics.attach(page)]
    popup = None
    stale_main_generation = None
    previous_signature = None
    progress_at = time.monotonic()
    recover_at = 0
    recoveries = 0
    manual_visible = False
    manual_attempts = 0
    manual_due = 0
    visibility_warned = False
    last_activity = None

    def activity(text, tone='working'):
        nonlocal last_activity
        if on_activity and last_activity != (text, tone):
            last_activity = (text, tone)
            on_activity(text, tone)

    def visibility(surface, required):
        nonlocal manual_visible, browser_window, auto_login, minimize_after_login
        nonlocal manual_attempts, manual_due, visibility_warned
        if runtime:
            runtime.page = surface
            runtime.manual_required = required
            options = runtime.tick()
            auto_login = options['auto_login']
            minimize_after_login = options['minimize_browser']
            browser_window = runtime.window
            if runtime.visibility_failure and not visibility_warned:
                visibility_warned = True
                diagnostics.record('manual_login_show_failed', attempt=runtime.manual_attempts)
                if on_visibility_failure:
                    on_visibility_failure()
        elif required and not manual_visible:
            now = time.monotonic()
            if manual_attempts and browser_window and browser_window.is_visible() is True:
                manual_visible = True
                return
            if now < manual_due:
                return
            if manual_attempts >= 3:
                if not visibility_warned:
                    visibility_warned = True
                    diagnostics.record('manual_login_show_failed', attempt=manual_attempts)
                    if on_visibility_failure:
                        on_visibility_failure()
                return
            manual_attempts += 1
            manual_due = now + 2
            if browser_window:
                shown = browser_window.show(activate=True)
            else:
                shown = set_chromium_window_state(surface, 'normal')
            surface.bring_to_front()
            manual_visible = shown is not False
            diagnostics.record('manual_login_shown' if manual_visible else 'manual_login_show_retry', attempt=manual_attempts)

    try:
        set_login_activity(page)
        if runtime:
            runtime.login_rendering.close('not_needed')
            runtime.login_rendering.diagnostics = diagnostics
            runtime.page = page
            runtime.set_activity('login')
        while not stop.is_set():
            if page.is_closed():
                diagnostics.record('browser_closed')
                raise BrowserClosedError('Przeglądarka logowania została zamknięta.')
            try:
                auto_login = runtime.options.snapshot()['auto_login'] if runtime else auto_login
                if popup is not None and popup.is_closed():
                    diagnostics.record('authentication_popup_closed')
                    stale_main_generation = document_generation(page)
                    popup = None
                    if runtime:
                        runtime.page = page
                        runtime.manual_required = not auto_login
                    # The original identity may predate the popup. A fresh safe
                    # target GET is permitted; the delivery ledger is retained.
                    if origin_kind(url) == 'servicenow':
                        diagnostics.record('login_recovery', recovery_reason='popup_closed', attempt=recoveries+1)
                        navigate(page, url, stop)
                elif popup is not None and login_observation(popup, url).session_ready:
                    diagnostics.record('session_confirmed')
                    if runtime:
                        runtime.page = page
                        runtime.manual_required = not auto_login
                    navigate(page, url, stop)
                    popup = None
                surface = login_surface(page, url)
                set_login_activity(surface)
                owned_popup = surface != page
                if owned_popup and surface is not popup:
                    popup = surface
                    detach.append(diagnostics.attach(surface))
                    diagnostics.record('authentication_popup')
                observation = login_observation(surface, url, surface='owned_popup' if owned_popup else 'main')
                facts = observation.facts
                diagnostics.inspect(surface, automatic, target=url,
                                    surface_alias='owned_popup' if owned_popup else 'main')
                signature = (surface, observation.state, observation.origin, observation.generation,
                             facts.get('account_count'), facts.get('password_count'),
                             facts.get('password_filled'), facts.get('document_ready'))
                now = time.monotonic()
                if signature != previous_signature:
                    previous_signature, progress_at = signature, now
                owner = manual_handoff(surface) or facts.get('password_manual_edit') is True
                if owner:
                    automatic.block('wykryto ręczną obsługę formularza')
                required = (not auto_login or owner or owned_popup or automatic.blocked or
                            facts.get('intervention') is True)
                if runtime and runtime.rendering_failed:
                    automatic.pause('strona wymaga interwencji użytkownika lub zgłasza błąd')
                    required = True
                if observation.state == 'session' and not owned_popup:
                    fresh = stale_main_generation is None or document_generation(page) != stale_main_generation
                    if fresh:
                        if runtime:
                            runtime.page = page
                            runtime.complete_login()
                        elif browser_window:
                            browser_window.hide()
                        elif minimize_after_login:
                            minimize_chromium(page)
                        finish_authentication(page)
                        diagnostics.record('session_confirmed')
                        diagnostics.record('login_complete')
                        activity('Zalogowano do ServiceNow', 'success')
                        return True
                visibility(surface, required or automatic.needs_user)
                if observation.state == 'authentication':
                    if auto_login and not owned_popup and not (runtime and runtime.rendering_failed):
                        try:
                            automatic.step(surface)
                        except Cancelled:
                            raise
                        except Exception as error:
                            diagnostics.record('automatic_login_step_error', **error_facts(error))
                    required = required or automatic.needs_user or automatic.blocked
                    visibility(surface, required)
                    if required:
                        activity('Wymagane ręczne logowanie', 'waiting')
                    elif automatic.submitted:
                        activity('Oczekiwanie na wynik logowania')
                    elif automatic.prefill_since is not None:
                        activity('Oczekiwanie na autouzupełnienie')
                    else:
                        activity('Logowanie automatyczne')
                else:
                    pending = automatic.submitted or automatic.pending_delivery_token is not None
                    network = diagnostics.network_error
                    certificate = network == 'certificate'
                    waiting = now - progress_at
                    reason = ('logout' if observation.state == 'logout' else
                              'network' if network in ('dns', 'connection', 'timeout') or
                              (isinstance(diagnostics.document_status, int) and diagnostics.document_status >= 500)
                              else 'stalled')
                    due = observation.state == 'logout' or (reason == 'network' and waiting >= 5) or waiting >= 180
                    # Never navigate over an authentication form or repeat a
                    # delivered/uncertain password request. The monitor keeps
                    # waiting rather than silently stopping when a budget ends.
                    if (due and now >= recover_at and not pending and not automatic.blocked and
                            not owner and not owned_popup and not certificate and origin_kind(url) == 'servicenow'):
                        recoveries += 1
                        recover_at = now + (5, 15, 60, 300)[min(recoveries-1, 3)]
                        diagnostics.record('login_recovery', recovery_reason=reason, attempt=recoveries,
                                           delay_s=round(recover_at-now))
                        try:
                            navigate(page, url, stop)
                        except Cancelled:
                            raise
                        except Exception as error:
                            diagnostics.record('login_loop_error', **error_facts(error))
                        progress_at = time.monotonic()
                    need_help = required or certificate or (waiting >= 180 and not network) or (pending and waiting >= 30)
                    visibility(surface, need_help)
                    activity('Wymagane ręczne logowanie' if need_help else
                             'Oczekiwanie na połączenie z ServiceNow' if reason == 'network' else
                             'Odzyskiwanie sesji ServiceNow' if observation.state == 'logout' else
                             'Sprawdzanie sesji ServiceNow', 'waiting' if need_help or reason == 'network' else 'working')
            except Cancelled:
                diagnostics.record('login_cancelled')
                return False
            except BrowserClosedError:
                raise
            except Exception as error:
                diagnostics.record('login_loop_error', **error_facts(error))
                if page.is_closed():
                    raise BrowserClosedError('Przeglądarka logowania została zamknięta.') from None
            page.wait_for_timeout(100)
        diagnostics.record('login_cancelled')
        return False
    finally:
        clear_login_activity(page)
        if runtime:
            runtime.login_rendering.close('not_needed')
            runtime.login_rendering.diagnostics = runtime.diagnostics
        for release in reversed(detach):
            try:
                release()
            except Exception:
                pass


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


from neto_incident_monitor.table_loading import TableLoading


class App(DynamicColumns, TableLoading):
    def __init__(self, root, history_path=None, enable_tray=True, instance=None, apply_startup=True, windows_startup="disabled"):
        self.root = root
        self.events = queue.Queue()
        self.filter_revisions = {}
        self.dashboard_requests = queue.Queue()
        self.dashboard_drilldown_requests = queue.Queue(maxsize=1)
        self.threatened_requests = queue.Queue()
        from neto_incident_monitor.monitoring import RefreshControl
        self.refresh_control = RefreshControl()
        self.stop = threading.Event()
        self.browser_window = None
        self.worker = None
        self.items = {}
        self.snapshots = {}
        self.updating_filter_url = None
        self.next_check = None
        self.check_deadlines = {}
        self.windows_startup = windows_startup
        self.history = History(history_path or DATA / "history.json")
        self.alert_writer = ThreadPoolExecutor(max_workers=1, thread_name_prefix="alerts")
        self.history_writer = ThreadPoolExecutor(max_workers=1, thread_name_prefix="history")
        self.row_numbers = {}
        self.tray = None
        self.tray_ready = False
        self.quitting = False
        self.instance = instance
        self.schedule = Schedule()
        self.auth_waiting = False
        settings = initialize_default_filters(read_json(CONFIG, {}))
        from neto_incident_monitor.browser_policy import BrowserOptions
        self.browser_options = BrowserOptions(settings)
        self.browser_runtime = None
        from neto_incident_monitor.teams_notifications import Sender
        self.teams_sender = Sender(self.events)
        self.teams_webhook = settings.get("teams_webhook", "")
        self.saved_teams = settings.get('teams_enabled', False), self.teams_webhook
        self.saving_teams = False
        from neto_incident_monitor.google_chat_notifications import Sender as GoogleChatSender
        self.google_chat_sender = GoogleChatSender(self.events)
        self.google_chat_webhook = settings.get("google_chat_webhook", "")
        self.saved_google_chat = settings.get("google_chat_enabled", False), self.google_chat_webhook
        self.saving_google_chat = False
        self.filters = load_filters(settings, tolerate_invalid=True)
        from neto_incident_monitor.template_library import migrate
        self.notification_library, self.filters = migrate(settings.get('notification_library', {}), self.filters)
        self.disabled_filter_urls = frozenset(entry["url"] for entry in self.filters if not entry.get("enabled", True))
        self.legacy_visible_columns = settings.get("visible_columns", DEFAULT)
        self.filter_visible_columns = settings.get("filter_visible_columns", {})
        self.columns_filter_url = None
        self.column_profiles = load_profiles(settings.get("filter_column_profiles", {}))
        self.visible_columns = []
        self.column_availability = {}
        self.column_widths = settings.get("column_widths", {})
        from neto_incident_monitor.ui import build_ui
        build_ui(self, settings)
        self.filter_selected()
        invalid_count = sum(bool(entry.get('url_invalid')) for entry in self.filters)
        if invalid_count:
            self.status.set(f'Wyłączono filtry z nieprawidłowym adresem: {invalid_count}. Popraw ich adresy w edycji filtra.')
        if getattr(settings, 'protection_errors', []):
            self.status.set(' '.join(dict.fromkeys(settings.protection_errors)))
        self.teams_enabled.trace_add("write", self.change_teams)
        from neto_incident_monitor.google_chat_ui import changed as google_chat_changed
        self.google_chat_enabled.trace_add("write", lambda *_: google_chat_changed(self))
        self.saved_notify_threatened = self.notify_threatened.get()
        self.notify_threatened.trace_add("write", self.save_notify_threatened)
        self.auto_login.trace_add("write", self.save_auto_login)
        self.dashboard_auto_refresh.trace_add('write', self.save_dashboard_auto_refresh)
        self.minimize_browser.trace_add("write", self.save_browser_minimize)
        self.hide_browser.trace_add("write", self.save_browser_minimize)
        self.saved_minimize = self.minimize_to_tray.get()
        self.minimize_to_tray.trace_add("write", self.save_minimize_preference)
        self.saving_startup = False
        for key in ("start_monitoring", "start_with_windows", "start_minimized"):
            getattr(self, key).trace_add("write", lambda *_, key=key: self.save_startup_preference(key))
        self.refresh_history()
        self.update_counts()
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<Unmap>", self.on_unmap, add="+")
        root.bind('<Control-Shift-F12>', lambda event: self.threatened_view.simulate_read(), add='+')
        self.window_save_timer = None
        self.window_layout = dict(settings.get("window_layout", {}))
        self.saved_window_layout = dict(self.window_layout)
        self.window_restoring = True
        root.bind("<Configure>", self.window_changed, add="+")
        def restore_window():
            if self.window_layout.get("maximized", False):
                root.state("zoomed")
            if apply_startup and self.start_minimized.get():
                if self.minimize_to_tray.get() and self.tray_ready:
                    self.hide_window()
                else:
                    root.iconify()
            self.window_restoring = False
            if apply_startup and self.start_monitoring.get() and any(f.get("enabled", True) for f in self.filters):
                root.after(200, self.start)
        root.after_idle(restore_window)
        root.after(200, self.drain)
        if enable_tray:
            try:
                from neto_incident_monitor.tray import Tray
                self.tray = Tray(self.events,
                                 browser_visible=lambda: bool(self.browser_window and self.browser_window.visible))
                self.tray.start()
            except Exception:
                LOG.exception("Nie udało się uruchomić zasobnika")
                self.tray = None
                self.status.set("Zasobnik niedostępny. Monitoring działa w oknie; błędy zapisano w logu.")

    def save_startup_preference(self, key):
        if self.saving_startup:
            return
        variable = getattr(self, key)
        enabled = variable.get()
        if key == "start_with_windows":
            from neto_incident_monitor.startup import set_windows_startup, windows_startup_status
            try:
                set_windows_startup(enabled)
                status = "current" if enabled else "disabled"
                LOG.info("Autostart Windows: wynik=%s.", status)
            except OSError:
                LOG.warning("Autostart Windows: wynik=write_failed.")
                try:
                    status = windows_startup_status()
                except OSError:
                    status = "unknown"
                messagebox.showerror("Uruchamianie aplikacji",
                                     "Nie udało się zmienić wpisu autostartu.", parent=self.settings_window)
            self.saving_startup = True
            try:
                self.start_with_windows.set(status in ("current", "repaired"))
                self.windows_startup = status
                self.startup_status_text.set(self.windows_startup_description())
            finally:
                self.saving_startup = False
            return
        try:
            settings = read_json(CONFIG, {})
            settings[key] = enabled
            save_json(CONFIG, settings)
        except Exception as error:
            self.saving_startup = True
            variable.set(not enabled)
            self.saving_startup = False
            messagebox.showerror("Uruchamianie aplikacji", f"Nie udało się zapisać ustawienia: {error}", parent=self.settings_window)

    def windows_startup_description(self):
        if self.windows_startup in ("stale", "unknown"):
            return "Nie udało się potwierdzić poprawnego wpisu autostartu."
        return "Uruchamiaj aplikację po zalogowaniu do Windows."

    def approve_large_list(self, url, name, count):
        if next((entry.get("allow_large_list", False) for entry in self.filters if entry["url"] == url), False):
            return True
        request = {"url": url, "name": name, "count": count, "deadline": time.monotonic() + 15,
                   "done": threading.Event(), "accepted": False}
        self.events.put(("large_list_prompt", request))
        from neto_incident_monitor.browser_actions import ACTION_TICK
        try:
            while not self.stop.is_set():
                remaining = request["deadline"] - time.monotonic()
                if remaining <= 0:
                    return False
                tick = ACTION_TICK.get()
                if tick:
                    tick()
                if request["done"].wait(min(remaining, 0.1)):
                    return request["accepted"] and not self.stop.is_set()
            return False
        finally:
            request["done"].set()

    def show_large_list_prompt(self, request):
        from neto_incident_monitor.widgets import RoundedButton, Toggle
        if request["done"].is_set() or self.quitting:
            request["done"].set()
            return
        dialog = tk.Toplevel(self.root, background=BG)
        dialog.withdraw()
        dialog.title("Potwierdzenie odczytu listy")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        content = ttk.Frame(dialog, padding=24)
        content.pack(fill="both", expand=True)
        font = ("Segoe UI", 10)
        ttk.Label(content, text=f'Lista „{request["name"]}” zawiera {request["count"]:,} wpisów.\nOdczytać całą listę?'.replace(',', ' '),
                  wraplength=480, justify="left", font=font).pack(anchor="w", pady=(0, 12))
        remember = tk.BooleanVar(value=False)
        remember_row = ttk.Frame(content)
        remember_row.pack(fill="x")
        ttk.Label(remember_row, text="Zapamiętaj zgodę", font=font).pack(side="left")
        remember_toggle = Toggle(remember_row, remember)
        remember_toggle.configure(background=BG)
        remember_toggle.pack(side="right")
        countdown = tk.StringVar()
        ttk.Label(content, textvariable=countdown, font=font).pack(anchor="w", pady=12)
        buttons = ttk.Frame(content)
        buttons.pack(fill="x")
        def finish(accepted, rejected=False):
            if request["done"].is_set() or time.monotonic() >= request["deadline"]:
                request["done"].set()
                dialog.destroy()
                return
            index = self.event_filter_index(request["url"])
            if index is not None and (rejected or (accepted and remember.get())):
                entry = self.filters[index - 1]
                field = "enabled" if rejected else "allow_large_list"
                old = entry.get(field, True if rejected else False)
                entry[field] = not rejected
                try:
                    self.persist_filters()
                except (OSError, ValueError) as error:
                    entry[field] = old
                    accepted = False
                    messagebox.showerror("Duża lista", f"Nie udało się zapisać ustawienia: {error}", parent=dialog)
                self.refresh_filters()
            request["accepted"] = accepted
            request["done"].set()
            dialog.destroy()
        RoundedButton(buttons, text="Kontynuuj odczyt", command=lambda: finish(True), primary=True).pack(side="right")
        RoundedButton(buttons, text="Wyłącz filtr", command=lambda: finish(False, True)).pack(side="right", padx=8)
        dialog.protocol("WM_DELETE_WINDOW", lambda: finish(False, True))
        timer = None
        def cleanup(event):
            if event.widget is dialog and timer is not None:
                dialog.after_cancel(timer)
        dialog.bind("<Destroy>", cleanup, add="+")
        def tick():
            nonlocal timer
            timer = None
            if not dialog.winfo_exists():
                return
            remaining = max(0, int(request["deadline"] - time.monotonic() + 0.999))
            if request["done"].is_set() or remaining == 0 or self.stop.is_set():
                request["done"].set()
                dialog.destroy()
                return
            countdown.set(f"Pominięcie odczytu za {remaining} s.")
            timer = dialog.after(100, tick)
        tick()
        if not dialog.winfo_exists():
            return
        dialog.update_idletasks()
        width, height = max(420, dialog.winfo_reqwidth()), dialog.winfo_reqheight()
        x = max(0, (dialog.winfo_screenwidth() - width) // 2)
        y = max(0, (dialog.winfo_screenheight() - height) // 2)
        geometry = f"{width}x{height}+{x}+{y}"
        dialog.geometry(geometry)
        dialog.deiconify()
        dialog.lift()
        dialog.attributes("-topmost", True)
        # Reapply after mapping: Windows can reposition transient windows.
        dialog.after_idle(lambda: dialog.geometry(geometry) if dialog.winfo_exists() else None)

    def make_table(self, parent, history):
        columns = [(key, label, width) for key, label, width in FIELDS if key != "time"]
        if history:
            columns.insert(0, ("time", "Wykryto", 150))
        table = ttk.Treeview(parent, columns=[key for key, _, _ in columns], show="headings")
        table.history_view = history
        order = self.column_order(table)
        table.configure(displaycolumns=tuple(key for key in order if key in getattr(self, "visible_columns", DEFAULT)))
        table.tag_configure("alternate", background="#2b2f37")
        table.sort_column = None
        table.sort_descending = False
        table.default_order = ()
        table.heading_titles = {key: title for key, title, _ in columns}
        for key, title, width in columns:
            table.heading(key, text=title, anchor="w", command=lambda column=key: self.toggle_sort(table, column))
            table.column(key, width=max(70, int(getattr(self, "column_widths", {}).get(key, width))), minwidth=70, stretch=False)
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        table.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(parent, orient="vertical", command=table.yview)
        horizontal = ttk.Scrollbar(parent, orient="horizontal", command=table.xview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        table.column_drag = None
        table.bind("<ButtonPress-1>", self.column_drag_start, add="+")
        table.bind("<B1-Motion>", self.column_drag_motion, add="+")
        table.bind("<ButtonRelease-1>", self.column_drag_end, add="+")
        table.bind("<Triple-ButtonPress-1>", self.column_drag_start, add="+")
        table.bind("<Escape>", self.column_drag_cancel, add="+")
        table.bind("<Button-3>", self.incident_context_menu)
        table.priority_dots = PriorityDots(table)
        return table


    @staticmethod
    def column_at(table, x):
        identifier = table.identify_column(x)
        if not identifier or identifier == "#0":
            return None
        index = int(identifier[1:]) - 1
        columns = tuple(table["displaycolumns"])
        return columns[index] if 0 <= index < len(columns) else None

    def column_drag_start(self, event):
        table = event.widget
        if table.identify_region(event.x, event.y) == "separator":
            table.column_resizing = True
            return
        if table.identify_region(event.x, event.y) != "heading":
            return
        column = self.column_at(table, event.x)
        if column is not None:
            table.column_drag = {"column": column, "x": event.x, "moved": False}
            table.focus_set()
            return "break"

    def column_drag_motion(self, event):
        table = event.widget
        drag = table.column_drag
        if drag is None:
            return
        if abs(event.x - drag["x"]) >= 8:
            drag["moved"] = True
            table.configure(cursor="fleur")
        if drag["moved"]:
            self.show_column_drop_marker(table, event.x, event.y)
        return "break"

    def show_column_drop_marker(self, table, x, y):
        drag = table.column_drag
        target = self.column_at(table, x)
        visible = list(table["displaycolumns"])
        if (table.identify_region(x, y) != "heading"
                or target is None or target == drag["column"]):
            self.hide_column_drop_marker(table)
            return
        widths = [table.column(key, "width") for key in visible]
        index = visible.index(target)
        # Match the actual drop: before a column when moving left, after it
        # when moving right. Account for horizontal scrolling as well.
        boundary = index + (visible.index(drag["column"]) < index)
        position = sum(widths[:boundary]) - round(sum(widths) * table.xview()[0]) + 1
        position = max(4, min(table.winfo_width() - 5, position))
        marker = getattr(table, "column_drop_marker", None)
        if marker is None:
            marker = tk.Canvas(table, width=9, background=SURFACE,
                               highlightthickness=0, borderwidth=0)
            table.column_drop_marker = marker
        height = max(24, table.winfo_height() - 2)
        marker.configure(height=height)
        marker.delete("all")
        marker.create_polygon(0, 0, 9, 0, 4, 7, fill=ACCENT, outline="")
        marker.create_line(4, 7, 4, height, fill=ACCENT, width=2)
        marker.place(x=position - 4, y=1)
        tk.Misc.lift(marker)

    @staticmethod
    def hide_column_drop_marker(table):
        marker = getattr(table, "column_drop_marker", None)
        if marker is not None:
            marker.place_forget()

    def column_drag_cancel(self, event):
        table = event.widget
        if table.column_drag is not None:
            self.hide_column_drop_marker(table)
            table.column_drag = None
            table.configure(cursor="")
            return "break"

    def column_drag_end(self, event):
        table = event.widget
        drag = table.column_drag
        if drag is None:
            if getattr(table, "column_resizing", False):
                table.column_resizing = False
                self.root.after_idle(lambda: self.sync_column_widths(table))
            return
        self.hide_column_drop_marker(table)
        table.column_drag = None
        table.configure(cursor="")
        if table.identify_region(event.x, event.y) != "heading":
            return "break"
        target = self.column_at(table, event.x)
        if target is None:
            return "break"
        if not drag["moved"]:
            if target == drag["column"]:
                self.toggle_sort(table, target)
            return "break"
        self.reorder_column(table, drag["column"], target)
        return "break"

    def toggle_sort(self, table, column):
        if table.sort_column != column:
            table.sort_column, table.sort_descending = column, False
        elif not table.sort_descending:
            table.sort_descending = True
        else:
            table.sort_column, table.sort_descending = None, False
        if self.large_tables():
            (self.refresh_current if table is self.current_table else self.refresh_history)()
        else:
            self.apply_sort(table)

    def apply_sort(self, table):
        for column, title in table.heading_titles.items():
            indicator = " ▼" if table.sort_descending else " ▲"
            table.heading(column, text=title + (indicator if column == table.sort_column else ""))
        ordered = list(table.default_order)
        if table.sort_column:
            column = table.sort_column
            present = [item for item in ordered if table.set(item, column).strip() not in ("", "—")]
            present_set = set(present)
            missing = [item for item in ordered if item not in present_set]

            def key(item):
                value = table.set(item, column).strip()
                if column in ("time", "created", "updated"):
                    for pattern in ("%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M", "%Y-%m-%d"):
                        try:
                            return (0, datetime.strptime(value, pattern))
                        except ValueError:
                            pass
                # Natural ordering: priority 2 precedes 10, as do incident IDs.
                parts = tuple((0, int(part)) if part.isdigit() else (1, part.casefold())
                              for part in re.split(r"(\d+)", value))
                return (1, parts)

            ordered = sorted(present, key=key, reverse=table.sort_descending) + missing
        for index, item in enumerate(ordered):
            table.move(item, "", index)
            table.item(item, tags=("alternate",) if index % 2 else ())

    def selected_filter_index(self):
        selected = self.filter_table.selection() if hasattr(self, "filter_table") else ()
        return int(selected[0]) + 1 if selected else None

    def selected_filter_url(self):
        index = self.selected_filter_index()
        return self.filters[index - 1]["url"] if index else ""

    def filter_selected(self):
        url = self.selected_filter_url()
        if url != self.columns_filter_url:
            self.columns_filter_url = url
        if hasattr(self, "phase"):
            self.update_phase_text()
        if hasattr(self, "current_table"):
            self.configure_filter_button.configure(state="normal" if self.selected_filter_index() else "disabled")
            self.prepare_dynamic_tables()
            self.apply_visible_columns()
            self.refresh_current()
            self.refresh_history()
            self.update_counts()
        self.update_refresh_controls()

    def open_filter(self, event):
        table = self.filter_table
        if event.x >= table.winfo_width() - 42:
            return 'break'
        index = int(table.canvasy(event.y) // table.ROW)
        items = table.get_children()
        if 0 <= index < len(items):
            table.drag_cancel()
            table.selection_set(items[index])
            try:
                url = normalize_url(self.selected_filter_url())
            except ValueError:
                return 'break'
            webbrowser.open(url)
        return 'break'

    def configure_filter_notifications(self, item):
        from neto_incident_monitor.filter_settings import show_filter_settings
        show_filter_settings(self, int(item))

    def configure_selected_filter(self):
        selected = self.filter_table.selection()
        if selected:
            self.configure_filter_notifications(selected[0])

    def notification_guard(self, url, channel, endpoint, template):
        generation = self.monitor_generation
        revision = self.filter_revisions.get(url)

        def allow_send():
            if self.stop.is_set() or generation is not self.monitor_generation:
                return False
            try:
                from neto_incident_monitor.secret_config import load_config, UnavailableSecret
                settings = load_config(CONFIG, {}, migrate_plaintext=False)
                current = next((entry for entry in settings.get("filters", []) if entry["url"] == url), None)
                if not current or not current.get("enabled", True) or not current.get("notify_" + channel, True):
                    return False
                key = channel + "_webhook"
                custom = current.get(key, "")
                if isinstance(custom, UnavailableSecret):
                    return False
                from neto_incident_monitor.template_library import resolve
                current_template = resolve(current.get("notification_templates", {}).get(key, {}),
                                           settings.get("notification_library", {}))
                return bool(settings.get(channel + "_enabled")
                            and (custom or settings.get(key)) == endpoint
                            and current_template == template
                            and not self.stop.is_set() and generation is self.monitor_generation
                            and revision is self.filter_revisions.get(url))
            except (OSError, ValueError, KeyError, TypeError):
                return False

        return allow_send

    def alert_routes(self, url):
        from neto_incident_monitor.secret_config import load_config, UnavailableSecret
        from neto_incident_monitor.threatened import THREATENED_URL
        settings = load_config(CONFIG, {}, migrate_plaintext=False)
        entry = next((item for item in settings.get("filters", []) if item["url"] == url), None)
        if url == THREATENED_URL:
            if not settings.get("notify_threatened", True):
                return {}
            entry = {}
        if entry is None or not entry.get("enabled", True):
            return {}
        revision = settings.get("notification_revision")
        if not revision:
            return {}
        if url == THREATENED_URL and settings.get("threatened_notification_revision"):
            revision += ":" + settings["threatened_notification_revision"]
        routes = {}
        for channel in ("teams", "google_chat"):
            key = channel + "_webhook"
            custom = entry.get(key, "")
            endpoint = "" if isinstance(custom, UnavailableSecret) else custom or settings.get(key, "")
            if endpoint and not isinstance(endpoint, UnavailableSecret) and settings.get(channel + "_enabled") and entry.get("notify_" + channel, True):
                routes[channel] = (revision, endpoint)
        if settings.get("notify") and entry.get("notify_windows", True):
            routes["windows"] = (revision, "")
        return routes

    def prepare_threatened_alerts(self, incidents, request_id=None):
        from neto_incident_monitor.threatened import THREATENED_URL
        title = f"Incydenty zagrożone SLA · {len(incidents)}"
        lines = []
        for item in sorted(incidents, key=lambda item: (item["deadline"], item["number"])):
            categories = ", ".join(item["categories"])
            percent = str(item["percent"]).replace(".", ",")
            lines.append(f'{item["number"]} · {categories} · Pozostało {item["remaining"]} · {percent}%')
        for channel, (revision, _) in self.alert_routes(THREATENED_URL).items():
            body = lines
            if channel == "windows" and len(lines) > 1:
                body = [lines[0], f"Pozostałe nowe zagrożenia: {len(lines) - 1}"]
            yield dict(url=THREATENED_URL, channel=channel, target=revision, title=title,
                       message="\n".join([*body, THREATENED_URL]),
                       links={THREATENED_URL: THREATENED_URL,
                              **{item["number"]: item["url"] for item in incidents}},
                       request_id=request_id)

    def deliver_alerts(self, recover=False):
        from neto_incident_monitor import teams_notifications, google_chat_notifications
        for key, job in self.history.pending_alerts(recover=recover):
            if self.stop.is_set():
                return
            channel = job["channel"]
            route = self.alert_routes(job["url"]).get(channel)
            if not route or route[0] != job["target"]:
                self.history.transition_alert(key, "pending", "cancelled")
                App.log_threatened_delivery(key, job, "cancelled", 0)
                continue
            if not self.history.transition_alert(key, "pending", "sending"):
                continue
            state = "uncertain"
            accepted = 0
            try:
                if channel == "windows":
                    from plyer import notification
                    notification.notify(title=job["title"], message=job["message"],
                                        app_name="Neto Incident Monitor", timeout=10)
                    accepted = 1
                else:
                    if channel == "teams":
                        parts = teams_notifications.message_chunks(job["title"], job["message"], job["links"])
                        send = lambda part: teams_notifications.send(route[1], job["title"], part, job["links"])
                    else:
                        parts = google_chat_notifications.payloads(job["title"], job["message"], job["links"])
                        send = lambda part: google_chat_notifications.send(route[1], part)
                    for part in parts:
                        if self.stop.is_set() or self.alert_routes(job["url"]).get(channel) != route:
                            raise RuntimeError("Alert delivery interrupted")
                        send(part)
                        accepted += 1
                        if channel == "google_chat":
                            self.stop.wait(1.1)
                state = "accepted"
            except Exception:
                self.events.put(("status", f"Wynik wysyłki {channel} jest niepewny. Potwierdzone części: {accepted}."))
            finally:
                self.history.transition_alert(key, "sending", state)
                App.log_threatened_delivery(key, job, state, accepted)

    @staticmethod
    def log_threatened_delivery(key, job, state, accepted):
        from neto_incident_monitor.threatened import THREATENED_URL
        if job.get("url") != THREATENED_URL:
            return
        request = job.get("request_id")
        channel = job.get("channel")
        if type(request) is int and channel in ("windows", "teams", "google_chat") and re.fullmatch(r"[a-f0-9]{32}", key):
            LOG.info("Zagrożenia SLA: żądanie=%d, zadanie=%s, kanał=%s, wynik=%s, przyjęte części=%d",
                     request, key, channel, state, accepted)

    def prepare_filter_alerts(self, url, name, incidents):
        from neto_incident_monitor.notification_templates import standard, render
        from neto_incident_monitor.template_library import resolve
        entry = next((item for item in self.filters if item["url"] == url), {})
        title, message = standard(name, incidents)
        links = {item["number"]: item["url"] for item in incidents if item.get("url")}
        for channel, (target, _) in self.alert_routes(url).items():
            template = resolve(entry.get("notification_templates", {}).get(channel + "_webhook", {}),
                               getattr(self, "notification_library", {}))
            custom = channel != "windows" and template.get("enabled")
            yield dict(url=url, channel=channel, target=target, links=links,
                       title="" if custom else title,
                       message=render(template, name, incidents) if custom else message)

    def notify_filter(self, url, incidents, manual=False):
        entry = next((entry for entry in self.filters if entry["url"] == url), None)
        if not entry or (not manual and not entry.get("enabled", True)) or not incidents:
            return
        from neto_incident_monitor.notification_templates import standard
        title, message = standard(entry['name'], incidents)
        from neto_incident_monitor.secret_config import UnavailableSecret
        def webhook(key):
            custom = entry.get(key, '')
            return '' if isinstance(custom, UnavailableSecret) else custom or getattr(self, key, '')
        teams_webhook = webhook('teams_webhook')
        google_chat_webhook = webhook('google_chat_webhook')
        def channel_text(key):
            config = entry.get('notification_templates', {}).get(key, {})
            from neto_incident_monitor.template_library import resolve
            config = resolve(config, getattr(self, 'notification_library', {}))
            if config.get('enabled'):
                from neto_incident_monitor.notification_templates import render
                return '', render(config, entry['name'], incidents)
            return title, message
        def sender_options(channel, endpoint):
            if manual or not hasattr(self, "monitor_generation"):
                return {}
            import copy
            from neto_incident_monitor.template_library import resolve
            template = resolve(entry.get("notification_templates", {}).get(channel + "_webhook", {}),
                               getattr(self, "notification_library", {}))
            return {"allow_send": self.notification_guard(url, channel, endpoint, copy.deepcopy(template))}

        if self.teams_enabled.get() and entry.get("notify_teams", True) and teams_webhook:
            links = {item["number"]: item["url"] for item in incidents if item.get("url")}
            self.teams_sender.submit(teams_webhook, *channel_text('teams_webhook'), **({"links": links} if links else {}),
                                     **sender_options("teams", teams_webhook))
        if self.google_chat_enabled.get() and entry.get("notify_google_chat", True) and google_chat_webhook:
            links = {item["number"]: item["url"] for item in incidents if item.get("url")}
            self.google_chat_sender.submit(google_chat_webhook, *channel_text('google_chat_webhook'), links=links,
                                           **sender_options('google_chat', google_chat_webhook))
        if self.notify.get() and entry.get("notify_windows", True):
            try:
                from plyer import notification
                self.root.bell()
                notification.notify(title=title, message=message, app_name="Neto Incident Monitor", timeout=10)
            except Exception:
                LOG.exception("Błąd powiadomienia filtra")
                self.status.set("Incydenty zapisano. Nie udało się wysłać powiadomienia Windows.")

    def refresh_filters(self):
        updating_index = self.event_filter_index(self.updating_filter_url)
        self.filter_table.updating_item = str(updating_index - 1) if updating_index is not None else None
        self.disabled_filter_urls = frozenset(entry["url"] for entry in self.filters if not entry.get("enabled", True))
        self.filter_table.enabled_rows = {str(i): entry.get("enabled", True) for i, entry in enumerate(self.filters)}
        self.filter_table.on_toggle = self.toggle_filter
        self.filter_table.on_select = self.filter_selected
        self.filter_table.on_reorder = self.reorder_filter
        self.filter_table.bind('<Double-1>', self.open_filter)
        selected = self.filter_table.selection()
        self.filter_table.delete(*self.filter_table.get_children())
        for index, entry in enumerate(self.filters):
            self.filter_table.insert("", "end", iid=str(index), values=(entry["name"], urlparse(entry["url"]).hostname))
        self.filter_count.set(str(len(self.filters)))
        self.filter_table.configure(height=max(1, min(4, len(self.filters))))
        if self.filters:
            self.filter_table.selection_set(selected[0] if selected and selected[0] in self.filter_table.get_children() else "0")
        else:
            self.filter_selected()

    def reorder_filter(self, item, slot):
        source = int(item)
        target = slot - (1 if slot > source else 0)
        if target == source or self.quitting:
            return
        old = self.filters
        selected_url = self.selected_filter_url()
        proposed = list(old)
        moved = proposed.pop(source)
        proposed.insert(target, moved)
        self.filters = proposed
        try:
            self.persist_filters()
        except (OSError, ValueError) as error:
            self.filters = old
            messagebox.showerror("Kolejność filtrów", f"Nie udało się zapisać kolejności: {error}", parent=self.root)
            return
        positions = {entry["url"]: i for i, entry in enumerate(proposed, 1)}
        self.snapshots = {positions[old[i - 1]["url"]]: value for i, value in self.snapshots.items()}
        self.column_availability = {positions[old[i - 1]["url"]]: value for i, value in self.column_availability.items()}
        self.refresh_filters()
        self.filter_table.selection_set(str(positions[selected_url] - 1))

    def event_filter_index(self, identity):
        if isinstance(identity, int):
            return identity
        return next((i for i, entry in enumerate(self.filters, 1) if entry["url"] == identity), None)

    def add_default_filters(self, event=None):
        if self.quitting:
            return 'break'
        if self.worker and self.worker.is_alive():
            messagebox.showinfo('Filtry domyślne', 'Zatrzymaj monitoring przed dodaniem filtrów domyślnych.', parent=self.root)
            return 'break'
        from neto_incident_monitor.default_filters import default_filters
        urls = set()
        for entry in self.filters:
            try:
                urls.add(normalize_url(entry['url']))
            except ValueError:
                pass
        names = {entry['name'].strip().casefold() for entry in self.filters}
        additions = [entry for entry in load_filters({'filters': default_filters()})
                     if entry['url'] not in urls and entry['name'].strip().casefold() not in names]
        if not additions:
            messagebox.showinfo('Filtry domyślne', 'Wszystkie filtry domyślne są już na liście.', parent=self.root)
            return 'break'
        previous = self.filters
        self.filters = previous + additions
        try:
            self.persist_filters()
        except (OSError, ValueError):
            self.filters = previous
            messagebox.showerror('Filtry domyślne', 'Nie udało się zapisać filtrów domyślnych.', parent=self.root)
            return 'break'
        self.refresh_filters()
        messagebox.showinfo('Filtry domyślne', f'Dodano brakujące filtry: {len(additions)}.', parent=self.root)
        return 'break'

    def persist_filters(self):
        settings = read_json(CONFIG, {})
        old_policies = {
            item["url"]: (bool(item.get("first_only")), bool(item.get("allow_large_list")))
            for item in settings.get("filters", []) if isinstance(item, dict) and "url" in item
        }
        settings["filters"] = self.filters
        if isinstance(getattr(self, "notification_library", None), dict):
            settings["notification_library"] = self.notification_library
        settings["urls"] = [entry["url"] for entry in self.filters]
        save_json(CONFIG, settings)
        changed = {
            item["url"]: object() for item in self.filters
            if item["url"] in old_policies and old_policies[item["url"]] !=
            (bool(item.get("first_only")), bool(item.get("allow_large_list")))
        }
        if changed:
            self.filter_revisions = {**getattr(self, "filter_revisions", {}), **changed}

    def save_sidebar_width(self, width):
        try:
            settings = read_json(CONFIG, {})
            settings["sidebar_width"] = width
            save_json(CONFIG, settings)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Układ okna", f"Nie udało się zapisać szerokości panelu: {exc}", parent=self.root)

    def toggle_filter(self, item):
        if self.quitting:
            return
        index = int(item)
        entry = self.filters[index]
        old = entry.get("enabled", True)
        if not old:
            try:
                normalize_url(entry['url'])
            except ValueError as error:
                messagebox.showerror('Adres filtra', str(error), parent=self.root)
                return
        entry["enabled"] = not old
        try:
            self.persist_filters()
        except (OSError, ValueError) as exc:
            entry["enabled"] = old
            messagebox.showerror("Filtry", f"Nie udało się zapisać ustawienia: {exc}", parent=self.root)
            return
        self.filter_revisions = {**getattr(self, "filter_revisions", {}), entry["url"]: object()}
        self.refresh_filters()
        self.filter_table.selection_set(item)
        self.snapshots.pop(index + 1, None)
        self.column_availability.pop(index + 1, None)
        self.refresh_current()
        self.apply_visible_columns()
        self.update_counts()
        self.schedule.request()

    def edit_filter(self, edit=False):
        from neto_incident_monitor.widgets import RoundedButton
        if self.worker and self.worker.is_alive():
            return
        selected = self.filter_table.selection()
        if edit and not selected:
            messagebox.showinfo("Filtry", "Wybierz filtr do edycji.")
            return
        index = int(selected[0]) if edit else None
        entry = self.filters[index] if edit else {"name": "", "url": ""}
        dialog = tk.Toplevel(self.root)
        dialog.configure(background=BG)
        dialog.title("Edytuj filtr" if edit else "Dodaj filtr")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.columnconfigure(0, weight=1)
        name = tk.StringVar(value=entry["name"])
        ttk.Label(dialog, text="Nazwa").grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))
        name_input = ttk.Entry(dialog, textvariable=name, width=70)
        name_input.grid(row=1, column=0, sticky="ew", padx=12)
        ttk.Label(dialog, text="Pełny adres listy z filtrem:").grid(row=2, column=0, sticky="w", padx=12, pady=(12, 4))
        address = tk.Text(dialog, height=4, width=75, wrap="char", background=SURFACE,
                          foreground=TEXT, insertbackground=TEXT, selectbackground="#513039",
                          selectforeground=TEXT, relief="flat")
        address.insert("1.0", entry["url"])
        address.grid(row=3, column=0, sticky="ew", padx=12)

        def accept():
            try:
                urls = validate_urls(address.get("1.0", "end"))
                if len(urls) != 1 or not name.get().strip():
                    raise ValueError("Podaj nazwę i jeden adres filtra.")
                if any(other["url"] == urls[0] for i, other in enumerate(self.filters) if i != index):
                    raise ValueError("Ten adres jest już zapisany jako inny filtr.")
                updated = {**entry, "name": name.get().strip(), "url": urls[0], "enabled": entry.get("enabled", True)}
                updated.pop('url_invalid', None)
                if entry.get('url') != urls[0]:
                    updated.pop('resolved_list_url', None)
                proposed = [dict(item) for item in self.filters]
                if edit:
                    proposed[index] = updated
                else:
                    proposed.append(updated)
                old = self.filters
                self.filters = proposed
                try:
                    self.persist_filters()
                except Exception:
                    self.filters = old
                    raise
                if edit and entry["url"] != updated["url"]:
                    self.snapshots.pop(index + 1, None)
                    self.column_availability.pop(index + 1, None)
                self.refresh_filters()
                dialog.destroy()
            except (ValueError, OSError) as exc:
                messagebox.showerror("Filtr", str(exc), parent=dialog)

        RoundedButton(dialog, text="Zapisz", command=accept, background=BG).grid(row=4, column=0, sticky="e", padx=12, pady=12)
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - dialog.winfo_reqwidth()) // 2
        y = (dialog.winfo_screenheight() - dialog.winfo_reqheight()) // 2
        dialog.geometry(f"+{max(0, x)}+{max(0, y)}")
        name_input.focus_set()

    def remove_filter(self):
        if self.worker and self.worker.is_alive():
            return
        selected = self.filter_table.selection()
        if selected:
            index = int(selected[0])
            old = self.filters
            self.filters = [entry for i, entry in enumerate(old) if i != index]
            try:
                self.persist_filters()
            except OSError as exc:
                self.filters = old
                messagebox.showerror("Filtry", str(exc))
                return
            self.snapshots.clear()
            self.column_availability.clear()
            self.refresh_filters()

    def update_phase_text(self):
        phase = getattr(self, "monitoring_phase", "Gotowy do uruchomienia")
        index = self.selected_filter_index()
        name = self.filters[index - 1]["name"] if index else ""
        self.phase.set(phase)
        self.selected_filter_name.set(name)
        self.phase_label.set_status(phase)

    def set_phase(self, phase):
        self.monitoring_phase = phase
        self.update_phase_text()
        self.set_activity(phase, 'error' if phase.startswith('Błąd') else
                          'success' if phase == 'Monitoring aktywny' else
                          'waiting' if phase == 'Oczekiwanie na logowanie' else
                          'working' if phase in ('Uruchamianie przeglądarki', 'Ponowne uruchamianie przeglądarki', 'Sprawdzanie list') else None)
        self.auth_waiting = phase in ("Oczekiwanie na logowanie", "Uruchamianie przeglądarki")
        self.check_button.configure(state="disabled" if self.auth_waiting or not self.worker or not self.worker.is_alive() or self.quitting else "normal")
        self.update_tray()

    def set_activity(self, text, tone=None, kind='phase'):
        """Called only by the Tk thread; workers report through the event queue."""
        self.activity_kind = kind
        if hasattr(self, 'activity_pill'):
            self.activity_pill.set_status(text, tone)

    def update_counts(self):
        numbers = set(self.snapshots.get(self.selected_filter_index(), {}))
        self.current_count.set(str(len(numbers)))
        self.tabs.tab(1, text="Historia zgłoszeń")
        self.update_tray()

    def update_tray(self):
        if self.tray and self.tray_ready:
            try:
                self.tray.update(getattr(self, "monitoring_phase", "Gotowy do uruchomienia"))
            except Exception:
                LOG.exception("Błąd aktualizacji zasobnika")

    def clear_table(self, table):
        self.cancel_table_load(table)
        children = table.get_children()
        for item in children:
            self.items.pop((table, item), None)
            self.row_numbers.pop((table, item), None)
        if children:
            table.delete(*children)

    def refresh_history(self):
        if self.large_tables():
            self.load_table(self.table, history=True)
            return
        self.cancel_table_load(self.table)
        self.table.load_dirty = False
        selected = {self.row_numbers.get((self.table, item)) for item in self.table.selection()}
        self.clear_table(self.table)
        records = self.history.snapshot(self.selected_filter_url())
        for position, (number, record) in enumerate(sorted(records.items(), key=lambda pair: pair[1]["detected"], reverse=True)):
            incident = record["incident"]
            item = self.table.insert("", "end", values=self.table_values(self.table, incident,
                time.strftime("%d.%m.%Y %H:%M", time.localtime(record["detected"]))),
                tags=("alternate",) if position % 2 else ())
            self.items[(self.table, item)] = incident["url"]
            self.row_numbers[(self.table, item)] = number
            if number in selected:
                self.table.selection_add(item)
        self.table.default_order = self.table.get_children()
        self.apply_sort(self.table)

    def refresh_current(self):
        if self.large_tables():
            self.load_table(self.current_table)
            return
        self.cancel_table_load(self.current_table)
        self.current_table.load_dirty = False
        selected = {self.row_numbers.get((self.current_table, item)) for item in self.current_table.selection()}
        self.clear_table(self.current_table)
        combined = {}
        for index, snapshot in sorted(self.snapshots.items()):
            if index != self.selected_filter_index():
                continue
            for number, incident in snapshot.items():
                entry = combined.setdefault(number, {"incident": {}, "filters": []})
                # Lists may expose different columns; retain nonempty fields.
                entry["incident"].update({key: value for key, value in incident.items() if value})
                name = self.filters[index - 1]["name"]
                if name not in entry["filters"]:
                    entry["filters"].append(name)
        for position, (number, entry) in enumerate(sorted(combined.items(), key=lambda pair: int(re.sub(r"\D", "", pair[0]) or 0), reverse=True)):
            incident = entry["incident"]
            item = self.current_table.insert("", "end", values=self.table_values(self.current_table, incident),
                tags=("alternate",) if position % 2 else ())
            self.items[(self.current_table, item)] = incident.get("url", "")
            self.row_numbers[(self.current_table, item)] = number
            if number in selected:
                self.current_table.selection_add(item)
        self.current_table.default_order = self.current_table.get_children()
        self.apply_sort(self.current_table)

    def clear_history(self):
        from neto_incident_monitor.widgets import confirm_dialog
        if not self.history.snapshot(self.selected_filter_url()):
            messagebox.showinfo("Historia zgłoszeń", "Historia jest już pusta.", parent=self.root)
            return
        confirmed = confirm_dialog(
            self.root,
            "Wyczyść historię zgłoszeń",
            "Czy usunąć historię wybranego filtra?\n\n"
            "Tej operacji nie można cofnąć. Bieżąca lista i pamięć wcześniej widzianych incydentów pozostaną zachowane.",
            )
        if not confirmed:
            return
        self.write_history("clear", self.selected_filter_url())

    def write_history(self, operation, *args):
        if self.quitting:
            return
        future = self.history_writer.submit(getattr(self.history, operation), *args)
        future.add_done_callback(lambda result: self.events.put(
            ("history_written", (operation, result.exception()))))

    def show_window(self):
        self.root.deiconify()
        if getattr(self, "window_layout", {}).get("maximized", False):
            self.root.state("zoomed")
        self.root.lift()
        self.root.focus_force()

    def hide_window(self):
        if self.tray_ready:
            self.root.withdraw()
        else:
            self.status.set("Zasobnik nie jest gotowy — okno pozostaje widoczne.")

    def window_changed(self, event):
        if event.widget is not self.root or self.quitting or self.window_restoring:
            return
        state = self.root.state()
        if state not in ("normal", "zoomed"):
            return
        self.window_layout["maximized"] = state == "zoomed"
        if state == "normal":
            self.window_layout["geometry"] = self.root.geometry()
        if self.window_save_timer is not None:
            self.root.after_cancel(self.window_save_timer)
        self.window_save_timer = self.root.after(700, self.save_window_layout)

    def save_window_layout(self):
        self.window_save_timer = None
        if self.window_layout == self.saved_window_layout:
            return
        try:
            settings = read_json(CONFIG, {})
            settings["window_layout"] = dict(self.window_layout)
            save_json(CONFIG, settings)
            self.saved_window_layout = dict(self.window_layout)
        except (OSError, ValueError):
            LOG.exception("Nie udało się zapisać rozmiaru okna")

    def save_minimize_preference(self, *_):
        value = self.minimize_to_tray.get()
        if value == self.saved_minimize:
            return
        try:
            settings = read_json(CONFIG, {})
            settings["minimize_to_tray"] = value
            save_json(CONFIG, settings)
            self.saved_minimize = value
        except (OSError, ValueError):
            LOG.exception("Nie udało się zapisać ustawienia minimalizacji")
            self.minimize_to_tray.set(self.saved_minimize)
            self.status.set("Nie udało się zapisać ustawienia minimalizacji. Przywrócono poprzednią wartość.")

    def on_unmap(self, event):
        if event.widget is self.root and not self.quitting:
            self.root.after_idle(self.handle_minimize)

    def handle_minimize(self):
        if (not self.quitting and self.minimize_to_tray.get() and self.tray_ready
                and self.root.state() == "iconic"):
            self.hide_window()

    def check_now(self):
        self.request_refresh('all')

    def refresh_coordinator(self):
        if not hasattr(self, 'refresh_control'):
            from neto_incident_monitor.monitoring import RefreshControl
            self.refresh_control = RefreshControl()
        return self.refresh_control

    def request_refresh(self, scope, url=None):
        if (not self.worker or not self.worker.is_alive() or self.stop.is_set()
                or self.auth_waiting or self.quitting):
            return False
        if scope == 'filter':
            url = url or self.selected_filter_url()
            if not any(f['url'] == url and f.get('enabled', True) for f in self.filters):
                return False
        if scope not in ('all', 'dashboard', 'threatened', 'filter'):
            raise ValueError('Nieznany zakres aktualizacji.')
        if not self.refresh_coordinator().reserve(scope, url):
            return False
        if scope in ('all', 'dashboard'):
            if self.dashboard_view.request_refresh(coordinated=True) is False:
                self.refresh_coordinator().finish()
                self.update_refresh_controls()
                return False
        if scope in ('all', 'threatened'):
            self.threatened_view.request_refresh(coordinated=True)
        self.update_refresh_controls()
        self.schedule.request()
        self.status.set('Zlecono pełną aktualizację: zagrożenia → dashboard → filtry.' if scope == 'all' else
                        'Zlecono aktualizację wybranego zakresu.')
        return True

    def update_refresh_controls(self):
        if not hasattr(self, 'check_button'):
            return
        running = bool(self.worker and self.worker.is_alive() and not self.stop.is_set() and not self.quitting)
        available = running and not getattr(self, 'auth_waiting', False) and not self.refresh_coordinator().busy
        self.check_button.configure(state='normal' if available else 'disabled')
        if hasattr(self, 'dashboard_view'):
            self.dashboard_view.refresh_button.configure(state='normal' if available else 'disabled')
        if hasattr(self, 'threatened_view'):
            self.threatened_view.refresh_button.configure(state='normal' if available and not self.threatened_view.pending else 'disabled')
        if hasattr(self, 'refresh_filter_button'):
            entry = next((f for f in self.filters if f['url'] == self.selected_filter_url()), None)
            self.refresh_filter_button.configure(state='normal' if available and entry and entry.get('enabled', True) else 'disabled')
            self.open_filter_button.configure(state='normal' if entry and not entry.get('url_invalid') else 'disabled')

    def open_selected_filter(self):
        try:
            url = normalize_url(self.selected_filter_url())
        except ValueError:
            return
        webbrowser.open(url)

    def interruption(self, message):
        self.status.set(message)
        self.show_window()
        try:
            from plyer import notification
            self.root.bell()
            notification.notify(title="ServiceNow — przerwa w monitoringu", message=message[:240],
                                app_name="Neto Incident Monitor", timeout=15)
        except Exception:
            LOG.exception("Nie udało się pokazać alertu o przerwie w monitoringu")

    def session_expired(self, message):
        self.interruption(message)
        if self.teams_enabled.get() and self.teams_webhook:
            self.teams_sender.submit(self.teams_webhook, "ServiceNow — sesja wygasła", message)
        if self.google_chat_enabled.get() and self.google_chat_webhook:
            self.google_chat_sender.submit(self.google_chat_webhook, "ServiceNow — sesja wygasła", message)

    def configure_google_chat(self):
        from neto_incident_monitor.google_chat_ui import show_config
        show_config(self)

    def save_auto_login(self, *_):
        try:
            settings = read_json(CONFIG, {})
            settings["auto_login"] = self.auto_login.get()
            save_json(CONFIG, settings)
            self.browser_options.update(auto_login=settings['auto_login'])
        except (OSError, ValueError):
            self.status.set("Nie udało się zapisać ustawienia automatycznego logowania.")

    def save_dashboard_auto_refresh(self, *_):
        try:
            settings = read_json(CONFIG, {})
            settings['dashboard_auto_refresh'] = self.dashboard_auto_refresh.get()
            save_json(CONFIG, settings)
        except (OSError, ValueError):
            self.status.set('Nie udało się zapisać ustawienia aktualizacji dashboardu.')

    def save_notify_threatened(self, *_):
        from uuid import uuid4

        enabled = self.notify_threatened.get()
        if enabled == self.saved_notify_threatened:
            return
        try:
            settings = read_json(CONFIG, {})
            settings["notify_threatened"] = enabled
            settings["threatened_notification_revision"] = uuid4().hex
            save_json(CONFIG, settings)
        except (OSError, ValueError) as error:
            LOG.warning("Nie zapisano ustawienia alertów SLA (%s).", type(error).__name__)
            self.notify_threatened.set(self.saved_notify_threatened)
            self.status.set("Nie udało się zapisać ustawienia alertów SLA. Przywrócono poprzednią wartość.")
        else:
            self.saved_notify_threatened = enabled
            LOG.info("Zapisano ustawienie alertów SLA: włączone=%s.", enabled)

    def save_browser_minimize(self, *_):
        try:
            settings = read_json(CONFIG, {})
            settings["minimize_browser"] = self.minimize_browser.get()
            settings["hide_browser"] = self.hide_browser.get()
            save_json(CONFIG, settings)
            self.browser_options.update(minimize_browser=settings['minimize_browser'], hide_browser=settings['hide_browser'])
        except (OSError, ValueError):
            self.status.set("Nie udało się zapisać ustawienia minimalizacji przeglądarki.")

    def change_teams(self, *_):
        if self.saving_teams:
            return
        if self.teams_enabled.get() and not self.teams_webhook:
            self.configure_teams()
            if not self.teams_webhook:
                self.teams_enabled.set(False)
                return
        self.persist_teams()

    def persist_teams(self):
        try:
            settings = read_json(CONFIG, {})
            settings.update(teams_enabled=self.teams_enabled.get(), teams_webhook=self.teams_webhook)
            save_json(CONFIG, settings)
            self.saved_teams = self.teams_enabled.get(), self.teams_webhook
            return True
        except (OSError, ValueError):
            self.saving_teams = True
            enabled, self.teams_webhook = self.saved_teams
            self.teams_enabled.set(enabled)
            self.saving_teams = False
            self.status.set("Nie udało się zapisać konfiguracji Teams.")
            return False

    def configure_teams(self):
        from neto_incident_monitor.widgets import RoundedButton
        from neto_incident_monitor.teams_notifications import validate_webhook
        dialog = tk.Toplevel(self.root)
        dialog.configure(background=BG)
        dialog.title("Powiadomienia Teams")
        dialog.transient(self.root)
        dialog.grab_set()
        content = ttk.Frame(dialog, padding=20)
        content.pack(fill="both", expand=True)
        ttk.Label(content, text="Adres Webhook").pack(anchor="w")
        address = tk.StringVar(value=self.teams_webhook)
        field = ttk.Entry(content, textvariable=address, show="•", width=65)
        field.pack(fill="x", pady=8)
        shown = tk.BooleanVar(value=False)
        ttk.Checkbutton(content, text="Pokaż adres", variable=shown, style="App.TCheckbutton",
                        command=lambda: field.configure(show="" if shown.get() else "•")).pack(anchor="w")
        buttons = ttk.Frame(content)
        buttons.pack(fill="x", pady=(16, 0))

        def accepted():
            try:
                value = validate_webhook(address.get())
                return value
            except ValueError as error:
                messagebox.showerror("Teams", str(error), parent=dialog)

        def save():
            value = accepted()
            if value:
                self.teams_webhook = value
                if self.persist_teams():
                    dialog.destroy()
                else:
                    messagebox.showerror('Teams', 'Nie udało się zabezpieczyć lub zapisać konfiguracji.', parent=dialog)

        def test():
            value = accepted()
            if value:
                self.teams_sender.submit(value, "Test powiadomień ServiceNow", "Połączenie z aplikacją działa.", True)

        RoundedButton(buttons, background=BG, text="Wyślij test", command=test).pack(side="left")
        RoundedButton(buttons, background=BG, text="Instrukcja", command=lambda: self.show_teams_instruction(dialog)).pack(side="left", padx=8)
        RoundedButton(buttons, background=BG, text="Zapisz", command=save).pack(side="right")
        RoundedButton(buttons, background=BG, text="Anuluj", command=dialog.destroy).pack(side="right", padx=8)
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - dialog.winfo_reqwidth()) // 2
        y = (dialog.winfo_screenheight() - dialog.winfo_reqheight()) // 2
        dialog.geometry(f"+{max(0, x)}+{max(0, y)}")
        field.focus_set()
        self.root.wait_window(dialog)

    def show_teams_instruction(self, parent):
        try:
            if webbrowser.open('https://netology-my.sharepoint.com/:v:/g/personal/piotr_zaradzki_netology_com_pl/IQCv86cQd-JrTLpRyIrcA8ZPAVtyK6Ya9HGxTT4NMxRQ8S0?nav=eyJyZWZlcnJhbEluZm8iOnsicmVmZXJyYWxBcHAiOiJPbmVEcml2ZUZvckJ1c2luZXNzIiwicmVmZXJyYWxBcHBQbGF0Zm9ybSI6IldlYiIsInJlZmVycmFsTW9kZSI6InZpZXciLCJyZWZlcnJhbFZpZXciOiJNeUZpbGVzTGlua0NvcHkifX0&e=wLs9Sr'):
                return
        except Exception:
            LOG.exception("Nie udało się otworzyć filmu instruktażowego Teams")
        messagebox.showerror("Instrukcja Teams", "Nie udało się otworzyć filmu w przeglądarce.", parent=parent)

    def start(self):
        if self.quitting:
            return
        if self.worker and self.worker.is_alive():
            return
        try:
            filters = load_filters({"filters": self.filters}, tolerate_invalid=True)
            urls = validate_urls("\n".join(entry["url"] for entry in filters if not entry.get('url_invalid')))
            interval = int(self.interval.get())
            task_interval = int(self.task_interval.get())
            if min(interval, task_interval) < 15:
                raise ValueError("Minimalny odstęp wynosi 15 sekund.")
            settings = {"urls": urls, "filters": filters,
                        "interval": interval, "task_interval": task_interval, "notify": self.notify.get(), "auto_login": self.auto_login.get(),
                        "minimize_to_tray": self.minimize_to_tray.get(),
                        "minimize_browser": self.minimize_browser.get(), "hide_browser": self.hide_browser.get()}
            existing = read_json(CONFIG, {})
            existing.update(settings)
            settings = existing
            save_json(CONFIG, settings)
            self.filters = filters
        except (ValueError, OSError) as exc:
            messagebox.showerror("Konfiguracja", str(exc))
            return
        self.browser_options.update(**{key: settings[key] for key in self.browser_options.KEYS})
        self.login_cancel_message = None
        self.monitor_generation = object()
        self.stop.clear()
        if hasattr(self, "alert_writer"):
            self.alert_writer.submit(self.deliver_alerts, True)
        self.threatened_next_read = None
        self.refresh_coordinator().finish()
        self.refresh_coordinator().reserve('startup')
        self.schedule.consume()
        self.snapshots.clear()
        self.column_availability.clear()
        self.update_counts()
        self.last_read.set("Ostatnia aktualizacja: —")
        self.next_check = None
        self.check_deadlines = {}
        self.set_phase("Uruchamianie przeglądarki")
        self.clear_table(self.current_table)
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.interval_entry.configure(state="disabled")
        self.task_interval_entry.configure(state="disabled")
        self.notify_check.configure(state="disabled")
        for button in self.filter_buttons:
            button.configure(state="disabled")
        self.threatened_view.request_refresh(automatic=True)
        if self.dashboard_auto_refresh.get():
            self.dashboard_view.request_refresh(automatic=True)
        self.worker = threading.Thread(target=self.monitor, args=(settings,), daemon=True)
        try:
            self.worker.start()
        except RuntimeError:
            self.dashboard_view.cancel_request()
            self.refresh_coordinator().finish()
            self.stop.set()
            self.events.put(('finished', None))
            self.events.put(('phase', 'Nie udało się uruchomić monitoringu'))
            LOG.error('Nie udało się uruchomić wątku monitoringu.')
            return
        self.dashboard_view.refresh_button.configure(state='normal')
        self.threatened_view.set_monitoring(True)
        self.update_refresh_controls()

    def monitor(self, settings):
        from collections import deque
        failures = deque()
        try:
            while not self.stop.is_set():
                try:
                    self._monitor_browser(settings)
                    break
                except (TargetClosedError, BrowserClosedError):
                    if self.stop.is_set():
                        break
                    LOG.warning("Chromium zostało zamknięte; ponowne uruchomienie monitoringu.")
                    self.events.put(("filter_updating", None))
                    self.events.put(("phase", "Ponowne uruchamianie przeglądarki"))
                    self.events.put(("status", "Przeglądarka została zamknięta. Otwieram ją ponownie i wznawiam monitoring."))
                    now = time.monotonic()
                    while failures and now - failures[0] >= 60:
                        failures.popleft()
                    failures.append(now)
                    if len(failures) > 3:
                        from neto_incident_monitor.login_diagnostics import LoginDiagnostics
                        LoginDiagnostics(source='monitor').record('browser_restart_limited', attempt=len(failures))
                        self.events.put(('phase', 'Monitoring zatrzymany'))
                        self.events.put(('interruption', 'Chromium zamykało się wielokrotnie w krótkim czasie. Automatyczne ponowienia zatrzymano. Uruchom monitoring ponownie po sprawdzeniu przeglądarki.'))
                        break
                    # Back off without delaying an explicit Stop request.
                    from neto_incident_monitor.login_diagnostics import LoginDiagnostics
                    LoginDiagnostics(source='monitor').record('browser_restart_delay', attempt=len(failures), delay_s=2 ** len(failures))
                    if self.stop.wait(2 ** len(failures)):
                        break
        finally:
            self.refresh_coordinator().finish()
            self.events.put(("finished", None))

    def _monitor_browser(self, settings):
        self.threatened_delay_reason = 'browser'
        from uuid import uuid4
        from neto_incident_monitor.login_diagnostics import TRACE, LoginDiagnostics
        TRACE.set(uuid4().hex)
        run_diagnostics = LoginDiagnostics(source='monitor')
        from neto_incident_monitor.browser_policy import BrowserOptions, BrowserRuntime
        from neto_incident_monitor.browser_actions import ACTION_TICK
        options = getattr(self, 'browser_options', None) or BrowserOptions(settings)
        action_token = ACTION_TICK.set(None)
        self.browser_runtime = None
        self.browser_window = None
        health = Health()
        generation = getattr(self, "monitor_generation", None)

        class FilterInvalidated(Exception):
            pass
        try:
            from playwright.sync_api import sync_playwright
            from neto_incident_monitor.filter_state import FilterState
            membership = (FilterState(STATE, normalize_url)
                          if getattr(getattr(self, "history", None), "membership", None) is None else None)
            with sync_playwright() as playwright:
                run_diagnostics.record('browser_launch_attempt')
                from neto_incident_monitor.browser_icon import browser_launch_options
                context = playwright.chromium.launch_persistent_context(
                    str(DATA / "browser-profile"), headless=False, no_viewport=True,
                    # Let Chromium own the fixed caption. WM_SETTEXT races
                    # against tab-title updates and causes taskbar flicker.
                    **browser_launch_options())
                run_diagnostics.record('browser_launched')
                # Wake an idle monitoring cycle immediately when Chromium exits.
                context.on("close", lambda *_: self.schedule.request())
                try:
                    from neto_incident_monitor.authentication import install_input_guard
                    install_input_guard(context)
                    self.monitor_settings = settings
                    page = context.pages[0] if context.pages else context.new_page()
                    def window_factory():
                        from neto_incident_monitor.browser_window import BrowserWindow
                        return BrowserWindow(context.browser,
                            visibility_changed=lambda: self.events.put(('browser_visibility', None)))
                    self.browser_runtime = BrowserRuntime(page, options, window_factory,
                        set_chromium_window_state, run_diagnostics,
                        lambda window: setattr(self, 'browser_window', window))
                    ACTION_TICK.set(self.browser_runtime.tick)
                    self.browser_runtime.set_activity('login')
                    self.events.put(('activity', ('Otwieranie ServiceNow', 'working', 'login')))
                    try:
                        opened = open_login_target(page, settings["urls"][0], self.stop,
                            on_error=lambda facts: setattr(self.browser_runtime, 'navigation_error', facts['error_category']))
                        if not opened:
                            return
                    except LoginTargetUnavailable:
                        # Keep the monitoring owner/context alive. The login
                        # coordinator owns deferred safe recovery and Stop.
                        run_diagnostics.record('login_recovery', recovery_reason='network', attempt=1)
                    self.events.put(("phase", "Oczekiwanie na logowanie"))
                    self.events.put(("status", "Zaloguj się w przeglądarce. Monitoring rozpocznie się automatycznie po załadowaniu listy."))
                    if not self.restore_login(page, settings["urls"][0], settings):
                        return
                    intervals = {"inc": settings["interval"], "task": settings.get("task_interval", 3600)}
                    resolved = {url: effective_list_url(url, settings['filters']) for url in settings['urls']}
                    def list_kind(url):
                        return 'task' if urlparse(resolved[url]).path in ('/sc_task_list.do', '/sc_request_list.do', '/sc_req_item_list.do') else 'inc'
                    deadlines = {"inc": 0, "task": 0}
                    force = True
                    from neto_incident_monitor.pagination import MAX_READ_SECONDS
                    from neto_incident_monitor.read_budget import Budget, budget_scope
                    retry_urls = set()
                    remaining_after_login = {}
                    while not self.stop.is_set():
                        task = self.refresh_coordinator().scheduled()
                        scope, target_url = task
                        self.events.put(('refresh_state', None))
                        if scope in ('startup', 'all', 'threatened', 'scheduled'):
                            self.read_threatened_request(page)
                        if scope in ('startup', 'all', 'dashboard', 'scheduled'):
                            self.threatened_delay_reason = 'dashboard'
                            self.read_dashboard_request(page)
                        self.read_dashboard_drilldown(page)
                        self.read_due_threatened(page)
                        due = {kind for kind in intervals if force or time.monotonic() >= deadlines[kind]}
                        if scope in ('startup', 'all'):
                            due = set(intervals)
                        elif scope in ('dashboard', 'threatened', 'filter'):
                            # A local refresh leaves the periodic filter deadlines intact.
                            due = set()
                        retries = retry_urls if scope in ('startup', 'all', 'scheduled') else set()
                        active = {list_kind(url)
                                  for url in settings["urls"] if url not in self.disabled_filter_urls}
                        self.events.put(("check_deadlines", {kind: deadlines[kind] for kind in active - due}))
                        if due or scope == 'filter' or retries:
                            self.events.put(("checking", None))
                        cycle_error = False
                        for filter_index, url in enumerate(settings["urls"], 1):
                            kind = list_kind(url)
                            if kind not in due and not (scope == 'filter' and url == target_url) and url not in retries:
                                continue
                            if url in self.disabled_filter_urls:
                                continue
                            filter_name = next(entry['name'] for entry in settings['filters'] if entry['url'] == url)
                            if self.stop.is_set():
                                break
                            self.read_due_threatened(page)
                            if self.stop.is_set():
                                break
                            self.events.put(("filter_updating", url))
                            self.threatened_delay_reason = 'filter'
                            revision = getattr(self, 'filter_revisions', {}).get(url)
                            first_only = next((bool(entry.get('first_only')) for entry in self.filters
                                               if entry['url'] == url), False)
                            read_stage = {'stage': 'prepare', 'page': 0}
                            read_started = time.monotonic()
                            resumed = remaining_after_login.pop(url, None)
                            if resumed is not None and resumed[2] is revision:
                                seconds, read_diagnostics, _ = resumed
                                read_diagnostics.record("filter_read_resumed")
                            else:
                                seconds = MAX_READ_SECONDS
                                read_diagnostics = LoginDiagnostics(source="pagination", filter_index=filter_index)
                                read_diagnostics.record("filter_read_start")
                            outcome = "interrupted"
                            filter_budget = Budget(seconds)
                            try:
                                # Filters are read sequentially, so one tab is
                                # sufficient. Opening additional tabs restores
                                # a minimized Chromium window on Windows.
                                if page.is_closed():
                                    page = context.new_page()
                                    self.browser_runtime.page = page
                                    self.browser_runtime.tick(force=True)
                                current = page
                                self.browser_runtime.set_activity('filters')
                                available = ColumnDiscovery()
                                def observe_stage(stage, index):
                                    nonlocal available
                                    if stage == "retry":
                                        available = ColumnDiscovery()
                                    read_stage.update(stage=stage, page=index)

                                def validate_revision():
                                    if (url in self.disabled_filter_urls or
                                            revision is not getattr(self, "filter_revisions", {}).get(url)):
                                        raise FilterInvalidated()

                                browser_tick = ACTION_TICK.get()

                                def filter_tick():
                                    validate_revision()
                                    if browser_tick:
                                        browser_tick()

                                filter_tick_token = ACTION_TICK.set(filter_tick)
                                try:
                                    with budget_scope(filter_budget):
                                        incidents, page_count = read_all(
                                            current, url, self.stop, lambda p: collect(p, available), empty_list, authentication_page,
                                            lambda p, address: navigate(p, address, self.stop),
                                            lambda index, count: self.events.put(("status",
                                                f"{filter_name}: strona {index}, odczytano {count} incydentów…"
                                                if index else f"{filter_name}: powrót do pierwszej strony…")),
                                            approve_large=lambda count: self.approve_large_list(url, filter_name, count),
                                            on_stage=observe_stage,
                                            filter_index=filter_index, diagnostics=read_diagnostics)
                                finally:
                                    ACTION_TICK.reset(filter_tick_token)
                                validate_revision()
                                if is_short_url(url):
                                    direct = resolved_list_url(current, url)
                                    if not direct:
                                        raise ValueError('Nie rozpoznano docelowej listy skrótu.')
                                    resolved[url] = direct
                                missing_links = sum(not incident.get("url") for incident in incidents.values())
                                if missing_links:
                                    read_diagnostics.record("filter_links_degraded", row_count=missing_links)
                                for incident in incidents.values():
                                    incident["_available_columns"] = sorted(available)
                                read_stage['stage'] = 'history_write'
                                from neto_incident_monitor.browser_actions import checkpoint
                                read_diagnostics.record("filter_commit_start", records_read=len(incidents))
                                def confirm_commit():
                                    checkpoint(self.stop)
                                    validate_revision()

                                new = self.history.commit_filter(
                                    membership, url, filter_name, incidents,
                                    first_only,
                                    confirm_commit,
                                    prepare_alerts=(lambda numbers: self.prepare_filter_alerts(
                                        url, filter_name, [incidents[n] for n in sorted(numbers)]))
                                    if hasattr(self, "alert_writer") else None)
                                read_diagnostics.record("filter_commit_complete", records_read=len(incidents))
                                outcome = "success"
                                if is_short_url(url):
                                    self.events.put(("filter_resolved", (url, direct, revision, generation)))
                                if available.schema is not None:
                                    self.events.put(("columns", (url, available.schema, revision, generation)))
                                health.success(url)
                                retry_urls.discard(url)
                                self.events.put(("snapshot", (url, incidents, revision, generation)))
                                if new and hasattr(self, "alert_writer"):
                                    self.alert_writer.submit(self.deliver_alerts)
                                elif new:
                                    self.events.put(("filter_notification", (url, [incidents[n] for n in sorted(new)], revision, generation)))
                                self.events.put(("read", (time.time(), filter_name)))
                                self.events.put(("status", f"{filter_name}: {len(incidents)} incydentów na {page_count} stronach; nowych w tym odczycie: {len(new)}."))
                            except FilterInvalidated:
                                outcome = "discarded"
                            except LargeListRejected:
                                outcome = "rejected"
                                self.events.put(("status", f"Pominięto dużą listę: {filter_name}."))
                            except Cancelled:
                                outcome = "cancelled"
                                return
                            except AuthenticationRequired:
                                outcome = "waiting_login"
                                remaining_after_login[url] = (
                                    max(0, filter_budget.end - time.monotonic()), read_diagnostics, revision)
                                self.events.put(("phase", "Oczekiwanie na logowanie"))
                                message = "Sesja ServiceNow wygasła. Zaloguj się w przeglądarce — monitoring wznowi się automatycznie."
                                self.events.put(("status", message))
                                if health.authentication():
                                    self.events.put(("session_expired", message))
                                if not self.restore_login(current, url, settings):
                                    return
                                health.resumed()
                                retry_urls.add(url)
                                self.schedule.request()
                                break
                            except TargetClosedError:
                                raise
                            except Exception as exc:
                                outcome = "error"
                                read_diagnostics.record("filter_read_error", pagination_stage=read_stage["stage"],
                                    page_index=read_stage["page"], **error_facts(exc))
                                LOG.error("Błąd odczytu filtra (%s); etap=%s; strona=%d; czas=%.1fs; filtr=%d.",
                                          type(exc).__name__, read_stage['stage'], read_stage['page'],
                                          time.monotonic() - read_started, filter_index)
                                cycle_error = True
                                self.events.put(("phase", "Błąd odczytu"))
                                reason = getattr(exc, "reason", None)
                                if read_stage["stage"] == "history_write":
                                    message = "Nie udało się zapisać historii i stanu filtra. Zachowano poprzedni wynik."
                                elif reason in ("query_mismatch", "view_mismatch"):
                                    message = "ServiceNow zwrócił inne warunki lub widok listy. Zachowano poprzedni wynik."
                                elif reason:
                                    message = "Nie potwierdzono pełnego odczytu filtra. Zachowano poprzedni wynik."
                                else:
                                    message = "Odczyt filtra nie powiódł się. Próba ponownie w kolejnym cyklu."
                                self.events.put(("status", message))
                                if health.failure(url):
                                    self.events.put(("interruption", f"Lista „{filter_name}”: trzy kolejne odczyty nie powiodły się. Otwórz aplikację i sprawdź sesję lub połączenie. Automatyczne próby będą kontynuowane."))
                            finally:
                                read_diagnostics.record("filter_read_end", filter_outcome=outcome,
                                    pagination_stage=read_stage["stage"], page_index=read_stage["page"],
                                    duration_ms=round((time.monotonic() - read_started) * 1000))
                                self.events.put(("filter_updating", None))
                        self.read_due_threatened(page)
                        now = time.monotonic()
                        for kind in due:
                            deadlines[kind] = now + intervals[kind]
                        active = {list_kind(url)
                                  for url in settings["urls"] if url not in self.disabled_filter_urls}
                        next_read = min((deadlines[kind] for kind in active), default=now + min(intervals.values()))
                        if getattr(self, 'threatened_next_read', None) is not None:
                            next_read = min(next_read, self.threatened_next_read)
                        self.events.put(("waiting", (next_read, cycle_error)))
                        self.events.put(("check_deadlines", {kind: deadlines[kind] for kind in active}))
                        self.refresh_coordinator().finish()
                        self.events.put(('refresh_state', None))
                        self.threatened_delay_reason = 'idle'
                        if wait_for_browser_cycle(page, self.schedule, max(0, next_read - now), self.stop):
                            break
                        force = False
                finally:
                    if self.browser_runtime:
                        self.browser_runtime.close()
                    self.browser_window = None
                    self.events.put(("browser_visibility", None))
                    context.close()
        except Cancelled:
            return
        except (TargetClosedError, BrowserClosedError):
            raise
        except Exception as exc:
            run_diagnostics.record('monitor_error', **error_facts(exc))
            LOG.error("Nie udało się uruchomić monitoringu (%s).", type(exc).__name__)
            self.events.put(("phase", "Błąd uruchomienia"))
            self.events.put(("status", f"Nie udało się uruchomić monitoringu ({type(exc).__name__}). Sprawdź połączenie i dostęp do ServiceNow."))
            if not self.stop.is_set():
                self.events.put(("interruption", "Monitoring zatrzymał się z powodu błędu przeglądarki lub aplikacji. Otwórz aplikację, aby zobaczyć szczegóły i uruchomić go ponownie."))
        finally:
            ACTION_TICK.reset(action_token)
            self.browser_runtime = None
            run_diagnostics.record('monitor_finished')

    def restore_login(self, page, url, settings):
        self.threatened_delay_reason = 'login'
        def visibility_failure():
            self.events.put(('interruption', 'Nie udało się pokazać okna logowania Chromium. '
                             'Użyj opcji Pokaż przeglądarkę w zasobniku lub uruchom monitoring '
                             'z wyłączonym ukrywaniem przeglądarki.'))
        runtime = getattr(self, 'browser_runtime', None)
        if runtime:
            runtime.page = page
        authenticated = wait_for_login(page, url, self.stop, settings.get('auto_login', False),
                              settings.get('minimize_browser', False), self.browser_window,
                              on_visibility_failure=visibility_failure, runtime=runtime,
                              on_activity=lambda text, tone: self.events.put(('activity', (text, tone, 'login'))))
        if authenticated and not self.stop.is_set():
            self.events.put(('phase', 'Oczekiwanie'))
            return True
        return False


    def read_due_threatened(self, page):
        deadline = getattr(self, 'threatened_next_read', None)
        if not self.stop.is_set() and deadline is not None and time.monotonic() >= deadline:
            self.read_threatened_request(page, periodic=True)

    @diagnostic_read
    def read_threatened_request(self, page, periodic=False):
        if not hasattr(self, 'threatened_requests'):
            return
        request = None
        while not self.threatened_requests.empty():
            try:
                request = self.threatened_requests.get_nowait()
            except queue.Empty:
                break
        if request is None and periodic:
            request = getattr(self, 'threatened_last_request', None)
        if request is None:
            return
        deadline = getattr(self, 'threatened_next_read', None)
        self.threatened_last_request = request
        from neto_incident_monitor.threatened import read_threatened_dashboard, read_threatened_details
        from neto_incident_monitor.login_diagnostics import LoginDiagnostics
        from neto_incident_monitor.dashboard import diagnostic_steps
        diagnostics = LoginDiagnostics(source='dashboard', section='threatened', request_id=request)
        runtime = getattr(self, 'browser_runtime', None)
        if periodic and deadline is not None:
            diagnostics.record('threatened_schedule', lateness_ms=max(0, round((time.monotonic()-deadline)*1000)),
                delay_reason=getattr(self, 'threatened_delay_reason', 'idle'))
        try:
            from neto_incident_monitor.section_runner import run_section
            from neto_incident_monitor.threatened import KEYS
            settings = getattr(self, 'monitor_settings', {})
            def restore():
                self.events.put(('phase', 'Oczekiwanie na logowanie'))
                return self.restore_login(page, settings['urls'][0], settings)
            def state(value):
                self.events.put(('threatened_state', (request, value)))
                self.events.put(('activity', ('Pobieranie danych: Incydenty zagrożone', 'working', 'threatened')))
            import sqlite3
            details = None
            def read():
                nonlocal details
                details = None
                with runtime.dashboard_read(page, diagnostics) if runtime else nullcontext():
                    scores = read_threatened_dashboard(page, self.stop)
                    if hasattr(self, 'alert_writer') and set(scores) == set(KEYS):
                        try:
                            details = read_threatened_details(page, self.stop, scores)
                        except (Cancelled, AuthenticationRequired, TargetClosedError, BrowserClosedError):
                            raise
                        except Exception as exc:
                            diagnostics.record('section_read_error', **error_facts(exc))
                    return scores
            values = run_section(page, self.stop, read, diagnostics, restore, state,
                lambda values: set(values) == set(KEYS) and all(type(v) is int and v >= 0 for v in values.values()))
            self.events.put(('threatened_result', (request, values, time.time())))
            if hasattr(self, 'alert_writer'):
                from neto_incident_monitor.browser_actions import checkpoint
                saved = None
                if details is not None:
                    try:
                        saved, arrivals = self.history.commit_threatened(
                            details, time.time(), lambda: checkpoint(self.stop),
                            lambda incidents: self.prepare_threatened_alerts(incidents, request))
                        diagnostics.record('threatened_details_complete', records_read=len(details), row_count=arrivals)
                        if arrivals:
                            self.alert_writer.submit(self.deliver_alerts)
                    except (OSError, ValueError, sqlite3.Error) as exc:
                        diagnostics.record('section_read_error', **error_facts(exc))
                if saved is None:
                    diagnostics.record('threatened_details_incomplete')
                self.events.put(('threatened_details', (request, saved)))
        except (TargetClosedError, BrowserClosedError):
            self.threatened_requests.put(request)
            raise
        except Cancelled:
            self.events.put(('threatened_state', (request, 'Dane nieaktualne')))
        except Exception as exc:
            diagnostics.record('section_read_error', **error_facts(exc))
            LOG.warning('Nie odczytano zagrożeń SLA (%s).', type(exc).__name__)
            self.events.put(('threatened_result', (request, None, None)))
        finally:
            # Count from completion, including failed reads; never accumulate overdue runs.
            self.threatened_next_read = time.monotonic() + 60
            self.events.put(('threatened_finished', request))
            if runtime:
                try:
                    runtime.set_activity('filters')
                except Exception as exc:
                    diagnostics.record('browser_cleanup_error', **error_facts(exc))

    def request_dashboard_drilldown(self, request):
        if self.quitting or self.stop.is_set() or not self.worker or not self.worker.is_alive():
            return False
        try:
            self.dashboard_drilldown_requests.put_nowait(request)
        except queue.Full:
            return False
        self.schedule.request()
        return True

    @diagnostic_read
    def read_dashboard_drilldown(self, page):
        from neto_incident_monitor.dashboard_drilldown import collect_drilldown
        from neto_incident_monitor.login_diagnostics import LoginDiagnostics

        if not hasattr(self, 'dashboard_drilldown_requests'):
            return
        try:
            request = self.dashboard_drilldown_requests.get_nowait()
        except queue.Empty:
            return
        token, section, title, period = request
        diagnostics = LoginDiagnostics(source='dashboard', section=section)
        url = None
        try:
            url = collect_drilldown(page, section, title, self.stop, diagnostics, period,
                                    runtime=getattr(self, 'browser_runtime', None))
        except Cancelled:
            diagnostics.record('login_cancelled')
        except Exception as error:
            diagnostics.record('section_read_error', **error_facts(error))
        finally:
            self.events.put(('dashboard_drilldown_result', (token, url)))

    @diagnostic_read
    def read_dashboard_request(self, page):
        if not hasattr(self, 'dashboard_requests'):
            return
        request = None
        while True:
            try:
                request = self.dashboard_requests.get_nowait()
            except queue.Empty:
                break
        if request is None:
            return
        request_id, year, month = request
        from neto_incident_monitor.dashboard_progress import DashboardProgress, progress_steps
        from neto_incident_monitor.dashboard import read_dashboard, read_held_dashboard, read_requests_dashboard, TITLES, HELD_TITLES, REQUEST_TITLES
        from neto_incident_monitor.section_runner import run_section
        from neto_incident_monitor.login_diagnostics import LoginDiagnostics
        from datetime import datetime
        progress = DashboardProgress(lambda percent, text, state:
            self.events.put(('dashboard_progress', (request_id, percent, text, state))))
        self.events.put(('dashboard_updating', (request_id, year, month, 'running')))
        success, values, failures = False, {}, []
        restarting = False
        section = 'Dashboard SLA'
        try:
            for section, alias, expected, reader in (
                ('Dashboard SLA', 'sla', TITLES, lambda: read_dashboard(page, year, month, self.stop)),
                ('Wstrzymane L1', 'held', HELD_TITLES, lambda: read_held_dashboard(page, self.stop)),
                ('Wnioski L1', 'requests', REQUEST_TITLES, lambda: read_requests_dashboard(page, self.stop))):
                if self.stop.is_set():
                    raise Cancelled()
                diagnostics = LoginDiagnostics(source='dashboard', section=alias, request_id=request_id)
                def state(value):
                    self.events.put(('dashboard_section_status', (request_id, section, value)))
                def read():
                    runtime = getattr(self, 'browser_runtime', None)
                    with runtime.dashboard_read(page, diagnostics) if runtime else nullcontext():
                        with progress_steps(progress, section):
                            return reader()
                def restore():
                    state('Oczekuje')
                    progress.waiting()
                    settings = self.monitor_settings
                    return self.restore_login(page, settings['urls'][0], settings)
                try:
                    result = run_section(page, self.stop, read, diagnostics, restore, state,
                        lambda v: set(v) == set(expected) and all(type(n) is int and n >= 0 for n in v.values()))
                    values.update(result)
                    progress.section_done(section)
                    state('Zaktualizowany')
                    metadata = {'section': alias, 'read_at': datetime.now().astimezone().isoformat(timespec='seconds'),
                                'diagnostics': diagnostics, 'values': dict(result)}
                except (TargetClosedError, BrowserClosedError, Cancelled, AuthenticationRequired, LoginTargetUnavailable):
                    raise
                except Exception as exc:
                    state('Błąd odczytu')
                    failures.append(section)
                    LOG.warning('Dashboard: sekcja %s nie powiodła się (%s).', alias, type(exc).__name__)
                    metadata = {'section': alias, 'error': True, 'diagnostics': diagnostics}
                self.events.put(('dashboard_result', (request_id, year, month, dict(values), None,
                    'Trwa aktualizacja dashboardu…', metadata)))
            message = ('Nie udało się odczytać: ' + ', '.join(failures) + '. Pozostałe dane są dostępne.') if failures else ''
            self.events.put(('dashboard_result', (request_id, year, month, dict(values), None, message)))
            success = not failures and not self.stop.is_set()
        except (TargetClosedError, BrowserClosedError):
            self.dashboard_requests.put(request)
            restarting = True
            raise
        except Cancelled:
            self.events.put(('dashboard_section_status', (request_id, section, 'Dane nieaktualne')))
        except Exception as exc:
            self.events.put(('dashboard_section_status', (request_id, section, 'Błąd odczytu')))
            self.events.put(('dashboard_result', (request_id, year, month, None, True)))
        finally:
            progress.finish(success)
            self.events.put(('dashboard_updating', (request_id, year, month,
                             'retrying' if restarting else 'finished')))

    def drain(self):
        if getattr(self, "reset_data_on_exit", False) is True:
            return
        if self.instance and self.instance.poll():
            self.show_window()
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind in ("snapshot", "columns", "filter_resolved", "filter_notification") and len(value) == 4:
                    url, payload, revision, generation = value
                    if (generation is not getattr(self, "monitor_generation", None) or
                            revision is not getattr(self, "filter_revisions", {}).get(url)):
                        continue
                    value = (url, payload)
                if kind == 'refresh_state':
                    self.update_refresh_controls()
                    continue
                if kind == 'threatened_state':
                    self.threatened_view.set_state(*value)
                    continue
                if kind == 'threatened_result':
                    self.threatened_view.apply_result(*value)
                    if value[0] == self.threatened_view.request_id and value[1] is None:
                        self.set_activity('Błąd odczytu: Incydenty zagrożone', 'error', 'threatened_error')
                    continue
                if kind == 'threatened_details':
                    self.threatened_view.apply_details(*value)
                    continue
                if kind == 'threatened_finished':
                    self.threatened_view.finish_request(value)
                    if getattr(self, 'activity_kind', None) == 'threatened':
                        self.set_activity('Odczyt zagrożeń SLA zakończony', kind='phase')
                    continue
                if kind == 'activity':
                    self.set_activity(*value)
                    continue
                if kind == 'dashboard_progress':
                    if value[0] == self.dashboard_view.request_id:
                        self.dashboard_progress.apply(*value)
                    continue
                if kind == 'dashboard_section_status':
                    self.dashboard_view.set_section_state(*value)
                    if value[0] == self.dashboard_view.request_id and value[2] == 'W trakcie aktualizacji':
                        self.set_activity(f'Pobieranie danych: {value[1]}', 'working', 'dashboard')
                    elif value[0] == self.dashboard_view.request_id and value[2] == 'Błąd odczytu':
                        self.set_activity(f'Błąd odczytu: {value[1]}', 'error', 'dashboard_error')
                    continue
                if kind == 'dashboard_updating':
                    if not self.dashboard_view.set_updating(*value):
                        continue
                    updating = self.dashboard_view.active_request is not None
                    self.dashboard_button.updating = updating
                    self.dashboard_button.redraw()
                    self.update_refresh_controls()
                    if not updating:
                        if getattr(self, 'activity_kind', None) == 'dashboard':
                            self.set_activity('Oczekiwanie na sprawdzenie filtrów', kind='phase')
                    continue
                if kind == 'dashboard_drilldown_result':
                    if self.stop.is_set():
                        self.dashboard_view.cancel_drilldown()
                    else:
                        self.dashboard_view.apply_drilldown(value)
                    continue
                if kind == 'dashboard_result':
                    self.dashboard_view.apply_result(value)
                    continue
                if kind == 'filter_resolved':
                    short, direct = value
                    from neto_incident_monitor.service_now_urls import normalize_list_url
                    direct = normalize_list_url(direct, allow_short=False)
                    entry = next((entry for entry in self.filters if entry['url'] == short), None)
                    if entry is not None and entry.get('resolved_list_url') != direct:
                        entry['resolved_list_url'] = direct
                        try:
                            self.persist_filters()
                        except OSError:
                            self.status.set('Rozpoznano listę, ale nie udało się zapisać jej rodzaju.')
                        self.columns_filter_url = None
                        self.filter_selected()
                elif kind == "filter_updating":
                    self.updating_filter_url = value
                    index = self.event_filter_index(value)
                    self.filter_table.updating_item = str(index - 1) if index is not None else None
                    self.filter_table.redraw()
                    if value:
                        name = next((entry['name'] for entry in self.filters if entry['url'] == value), 'Nieznany filtr')
                        self.set_activity(f'Aktualizowanie filtra: {name}', 'working', 'filter')
                    elif getattr(self, 'activity_kind', None) == 'filter':
                        self.set_activity('Przygotowanie kolejnego odczytu', kind='phase')
                elif kind == "check_deadlines":
                    self.check_deadlines = value
                elif kind == "large_list_prompt":
                    self.show_large_list_prompt(value)
                elif kind == "status":
                    self.status.set(value)
                elif kind == "tray_ready":
                    self.tray_ready = True
                    self.update_tray()
                    self.handle_minimize()
                elif kind == "tray_failed":
                    self.tray_ready = False
                    self.show_window()
                    self.status.set("Zasobnik niedostępny — aplikacja pozostaje w oknie.")
                elif kind == "show":
                    self.show_window()
                elif kind == "show_browser":
                    if self.browser_runtime:
                        self.browser_runtime.request_show()
                elif kind == "hide_browser":
                    if self.browser_runtime:
                        self.browser_runtime.commands.put('hide')
                elif kind == "browser_visibility":
                    if self.tray and self.tray_ready:
                        self.tray.icon.update_menu()
                elif kind == "check_now":
                    self.check_now()
                elif kind == "interruption":
                    self.interruption(value)
                elif kind == "session_expired":
                    self.session_expired(value)
                elif kind == "history_written":
                    operation, error = value
                    if error is not None:
                        LOG.error("Zapis historii nie powiódł się (%s).", type(error).__name__)
                        self.status.set("Nie udało się zapisać zmiany historii.")
                    else:
                        self.refresh_history()
                        self.refresh_current()
                        self.update_counts()
                        if operation == "clear":
                            self.status.set("Historia wyczyszczona.")
                elif kind == "filter_notification":
                    url, incidents = value
                    if not self.stop.is_set() and not getattr(self, "quitting", False):
                        self.notify_filter(url, incidents)
                elif kind == "teams_result":
                    success, test, detail = value
                    if test:
                        (messagebox.showinfo if success else messagebox.showerror)("Test Teams", detail, parent=self.root)
                    elif not success:
                        self.status.set(detail)
                elif kind == "google_chat_result":
                    success, test, detail = value
                    if test:
                        (messagebox.showinfo if success else messagebox.showerror)("Test Google Chat", detail, parent=self.root)
                    elif not success:
                        self.status.set(detail)
                elif kind == "stop_monitor":
                    self.stop.set()
                elif kind == "quit":
                    self.quit_app()
                    return
                elif kind == "phase":
                    self.next_check = None
                    self.check_deadlines = {}
                    self.set_phase(value)
                    if value == "Błąd uruchomienia" and self.root.state() == "withdrawn":
                        self.show_window()
                elif kind == "checking":
                    self.next_check = None
                    self.set_phase("Sprawdzanie list")
                elif kind == "waiting":
                    self.next_check, error = value
                    self.set_phase("Błąd odczytu" if error else "Monitoring aktywny")
                    if not error:
                        self.set_activity('Oczekiwanie na kolejne sprawdzenie', 'success')
                elif kind == "read":
                    timestamp, name = value
                    self.last_read.set(f"Ostatnia aktualizacja: {time.strftime('%H:%M:%S', time.localtime(timestamp))} • {name}")
                elif kind == "columns":
                    index, available = value
                    index = self.event_filter_index(index)
                    if index is None:
                        continue
                    if not self.filters[index - 1].get("enabled", True):
                        continue
                    if isinstance(available, list):
                        self.column_availability[index] = {c["key"] for c in available}
                        self.accept_column_schema(self.filters[index - 1]["url"], available)
                elif kind == "snapshot":
                    filter_index, incidents = value
                    filter_index = self.event_filter_index(filter_index)
                    if filter_index is None:
                        continue
                    if not self.filters[filter_index - 1].get("enabled", True):
                        continue
                    self.snapshots[filter_index] = incidents
                    self.refresh_current()
                    self.refresh_history()
                    self.apply_visible_columns()
                    self.update_counts()
                elif kind == "finished":
                    self.dashboard_view.cancel_request()
                    if hasattr(self, "dashboard_drilldown_requests"):
                        try:
                            self.dashboard_drilldown_requests.get_nowait()
                        except queue.Empty:
                            pass
                        self.dashboard_view.cancel_drilldown()
                    self.threatened_view.set_monitoring(False)
                    while not self.threatened_requests.empty():
                        try:
                            self.threatened_requests.get_nowait()
                        except queue.Empty:
                            break
                    self.dashboard_view.finish_pending()
                    self.dashboard_view.refresh_button.configure(state='disabled')
                    self.dashboard_view.request_id += 1
                    self.dashboard_progress.hide()
                    self.dashboard_view.set_message('Monitoring zatrzymany — odczyt dashboardu jest niedostępny. Kafelki zachowują ostatni wynik.')
                    while not self.dashboard_requests.empty():
                        try:
                            self.dashboard_requests.get_nowait()
                        except queue.Empty:
                            break
                    self.check_deadlines = {}
                    self.updating_filter_url = None
                    self.filter_table.updating_item = None
                    self.filter_table.redraw()
                    self.next_check = None
                    if self.stop.is_set():
                        self.set_phase("Monitoring zatrzymany")
                        self.status.set(getattr(self, 'login_cancel_message', None) or "Odczyty zatrzymane. Lista zachowuje ostatni udany wynik.")
                    self.start_button.configure(state="normal")
                    self.stop_button.configure(state="disabled")
                    self.check_button.configure(state="disabled")
                    self.interval_entry.configure(state="normal")
                    self.task_interval_entry.configure(state="normal")
                    self.notify_check.configure(state="normal")
                    for button in self.filter_buttons:
                        button.configure(state="normal")
        except queue.Empty:
            pass
        now = time.monotonic()
        if now - getattr(self, "last_age_refresh", 0) >= 1:
            self.last_age_refresh = now
            for table in (self.current_table, self.table):
                if not self.table_visible(table):
                    continue
                changed = False
                visible_items = set(table.identify_row(y) for y in range(0, table.winfo_height(), 12))
                for item in visible_items - {''}:
                    value = age_minutes(table.set(item, "created"), table.set(item, "number"))
                    if table.set(item, "age_minutes") != value:
                        table.set(item, "age_minutes", value)
                        changed = True
                if changed and table.sort_column == "age_minutes" and table not in getattr(self, '_table_jobs', {}):
                    if self.large_tables():
                        (self.refresh_current if table is self.current_table else self.refresh_history)()
                    else:
                        self.apply_sort(table)
        def remaining(kind):
            deadline = self.check_deadlines.get(kind)
            return "-" if deadline is None else f"{max(0, int(deadline - now + 0.999))} s"
        self.countdown.set(f"Następna aktualizacja INC: {remaining('inc')}  SCTASK/REQ/RITM: {remaining('task')}")
        self.update_refresh_controls()
        if not self.quitting:
            self.root.after(200, self.drain)

    def open_incident(self, event):
        from neto_incident_monitor.service_now_urls import safe_record_url
        if event.widget.identify_region(event.x, event.y) == "separator":
            return self.fit_column(event)
        if event.widget.identify_region(event.x, event.y) == "heading":
            return self.column_drag_start(event)
        item = event.widget.identify_row(event.y)
        if item:
            key = (event.widget, item)
            url = safe_record_url(self.items[key], self.row_numbers[key])
            if url:
                webbrowser.open(url)

    def incident_context_menu(self, event):
        from neto_incident_monitor.service_now_urls import safe_record_url
        table = event.widget
        item = table.identify_row(event.y)
        key = (table, item)
        if not item or key not in self.row_numbers:
            return
        table.selection_set(item)
        table.focus(item)
        number, url = self.row_numbers[key], self.items[key]
        url = safe_record_url(url, number)
        menu = getattr(self, "incident_menu", None)
        if menu is not None:
            menu.destroy()
        menu = IncidentMenu(self.root)
        self.incident_menu = menu
        def open_selected():
            if url:
                webbrowser.open(url)
        def copy(value):
            self.root.clipboard_clear()
            self.root.clipboard_append(value)
        if url:
            menu.add_command(label="Otwórz incydent", command=open_selected)
        menu.add_separator()
        menu.add_command(label="Kopiuj numer", command=lambda: copy(number))
        if url:
            menu.add_command(label="Kopiuj link", command=lambda: copy(url))
        menu.add_separator()
        menu.add_command(label="Test powiadomienia", command=lambda: self.test_record_notification(table, number, url))
        menu.show(event.x_root, event.y_root)
        return "break"

    def test_record_notification(self, table, number, url):
        filter_url = self.selected_filter_url()
        entry = next((entry for entry in self.filters if entry["url"] == filter_url), None)
        if not entry:
            return
        windows = self.notify.get() and entry.get("notify_windows", True)
        teams = self.teams_enabled.get() and entry.get("notify_teams", True) and self.teams_webhook
        google_chat = self.google_chat_enabled.get() and entry.get("notify_google_chat", True) and self.google_chat_webhook
        if not windows and not teams and not google_chat:
            messagebox.showinfo("Test powiadomienia", "Włącz powiadomienia Windows, Teams lub Google Chat dla tego filtra.", parent=self.root)
            return
        if table is self.current_table:
            incident = self.snapshots.get(self.selected_filter_index(), {}).get(number)
        else:
            record = self.history.record(number, filter_url)
            incident = record["incident"] if record else None
        if incident is not None:
            self.notify_filter(filter_url, [{**incident, "number": number, "url": url}], manual=True)

    def close(self):
        self.quit_app()

    def request_data_reset(self):
        from neto_incident_monitor.data_reset import DataReset
        from neto_incident_monitor.widgets import confirm_dialog

        if self.quitting or not confirm_dialog(
            self.root, "Usuń wszystkie dane aplikacji",
            "Usunięte zostaną ustawienia, filtry i szablony, ustawienia kanałów, historia i stan wykryć, "
            "oczekujące alerty, pamięć dashboardu, logi oraz profil Chromium z sesją logowania. "
            "Operacja jest nieodwracalna. Aplikacja się zamknie, a przy następnym uruchomieniu "
            "może być potrzebne ponowne logowanie.",
            confirm_text="Usuń dane i zamknij",
        ):
            return
        if self.quitting:
            return
        try:
            DataReset().request()
        except OSError:
            LOG.warning("Nie można zapisać żądania resetu danych.")
            messagebox.showerror("Reset danych", "Nie można rozpocząć resetu danych.", parent=self.root)
            return
        self.reset_started = time.monotonic()
        LOG.info("Reset danych: rozpoczęto zamykanie aplikacji.")
        self.quit_app(reset_data=True)

    def quit_app(self, *, reset_data=False):
        if self.quitting:
            return
        self.reset_data_on_exit = reset_data
        self.stop_table_loads()
        if self.window_save_timer is not None:
            self.root.after_cancel(self.window_save_timer)
            self.window_save_timer = None
        if not reset_data:
            self.save_window_layout()
        self.quitting = True
        self.stop.set()
        self.schedule.request()
        self.show_window()
        if reset_data:
            self.root.attributes("-disabled", True)
            self.teams_sender.stop()
            self.google_chat_sender.stop()
        self.set_phase("Zamykanie aplikacji")
        self.start_button.configure(state="disabled")
        for button in self.filter_buttons:
            button.configure(state="disabled")
        self.finish_quit()

    def finish_quit(self):
        if self.worker and self.worker.is_alive():
            self.status.set("Zamykanie przeglądarki — oczekiwanie na zakończenie odczytu…")
            self.root.after(300, self.finish_quit)
        else:
            if not hasattr(self, "_shutdown_writes"):
                self._shutdown_writes = [
                    executor.submit(lambda: None)
                    for executor in (self.history_writer, self.alert_writer)
                ]
            if any(not future.done() for future in self._shutdown_writes):
                self.status.set("Zamykanie aplikacji. Oczekiwanie na zapis danych…")
                self.root.after(100, self.finish_quit)
                return
            if getattr(self, "reset_data_on_exit", False) and any(
                sender.thread.is_alive() for sender in (self.teams_sender, self.google_chat_sender)
            ):
                self.status.set("Reset danych. Oczekiwanie na zakończenie wysyłki…")
                self.root.after(100, self.finish_quit)
                return
            self.history_writer.shutdown(wait=False)
            self.alert_writer.shutdown(wait=False)
            if self.tray:
                try:
                    self.tray.stop()
                except Exception:
                    LOG.exception("Błąd zamykania zasobnika")
            if getattr(self, "reset_data_on_exit", False):
                LOG.info("Reset danych: zakończono pracę monitora i zadania zapisu (%.2f s).",
                         time.monotonic() - self.reset_started)
                self.reset_data_ready = True
            self.root.destroy()


def main(instance=None):
    from neto_incident_monitor.single_instance import SingleInstance
    from neto_incident_monitor.data_reset import DataReset, finish_with_retry
    owns_instance = instance is None
    instance = instance or SingleInstance(DATA)
    window = None
    try:
        if not instance.primary:
            instance.request_show()
            return
        if owns_instance and not finish_with_retry(DataReset()):
            return False
        window = tk.Tk()

        def callback_error(error_type, error, traceback):
            LOG.error("Błąd obsługi interfejsu", exc_info=(error_type, error, traceback))
            messagebox.showerror("Neto Incident Monitor", f"Błąd aplikacji: {error}", parent=window)

        window.report_callback_exception = callback_error
        from neto_incident_monitor.startup import reconcile_windows_startup
        try:
            startup_status = reconcile_windows_startup()
            LOG.info("Autostart Windows: wynik=%s.", startup_status)
        except OSError:
            startup_status = "unknown"
            LOG.warning("Autostart Windows: wynik=check_failed.")
        app = App(window, instance=instance, windows_startup=startup_status)
        window.mainloop()
        reset_requested = getattr(app, "reset_data_ready", False)
        if owns_instance and reset_requested:
            from neto_incident_monitor.login_diagnostics import close_diagnostics
            close_diagnostics()
            finish_with_retry(DataReset())
        return reset_requested
    except Exception as error:
        LOG.exception("Błąd aplikacji")
        messagebox.showerror("Neto Incident Monitor", str(error))
        if window is not None:
            window.destroy()
    finally:
        if owns_instance:
            instance.close()


if __name__ == "__main__":
    main()
