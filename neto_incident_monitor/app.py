"""Local ServiceNow list monitor. Browser access only; no ServiceNow API."""
from neto_incident_monitor.dynamic_columns import DynamicColumns, load_profiles
from neto_incident_monitor.columns import ColumnDiscovery
from neto_incident_monitor.theme import BG, SURFACE, TEXT, MUTED, ACCENT
from neto_incident_monitor.columns import FIELDS, DEFAULT, age_minutes
from neto_incident_monitor.widgets import IncidentMenu, PriorityDots
import json
import logging
import queue
import re
import threading
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
from neto_incident_monitor.notifications import batch_text
from playwright._impl._errors import TargetClosedError

from neto_incident_monitor.runtime_paths import ROOT, DATA
DATA.mkdir(parents=True, exist_ok=True)
CONFIG = DATA / "config.json"
STATE = DATA / "seen.json"
INC = re.compile(r"\b(?:INC|SCTASK)\d{7,}\b", re.I)
LOG = logging.getLogger("servicenow")


class BrowserClosedError(RuntimeError):
    """The monitored browser was closed and can be started again."""


def wait_for_browser_cycle(page, schedule, seconds, stop):
    """Keep Playwright events flowing while waiting for the next read."""
    deadline = time.monotonic() + seconds
    while not stop.is_set():
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


def read_json(path, default):
    if path == CONFIG:
        from neto_incident_monitor.secret_config import load_config
        return load_config(path, default)
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, value):
    if path == CONFIG:
        from neto_incident_monitor.secret_config import save_config
        return save_config(path, value)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def normalize_url(url):
    from neto_incident_monitor.service_now_urls import normalize_list_url
    return normalize_list_url(url)


def validate_urls(text):
    urls = [line.strip() for line in text.splitlines() if line.strip()]
    if not urls:
        raise ValueError("Wklej przynajmniej jeden adres listy z filtrem.")
    return list(dict.fromkeys(normalize_url(url) for url in urls))


def load_filters(settings, tolerate_invalid=False):
    """Migrate the previous URL-only configuration without touching seen state."""
    entries = settings.get("filters") or [
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
    from neto_incident_monitor.service_now_urls import normalize_list_url, safe_record_url
    for frame in page.frames:
        try:
            frame_url = normalize_list_url(frame.url, allow_short=False)
        except ValueError:
            continue
        rows = frame.locator("table:visible").evaluate_all("""tables => tables.flatMap(table => {
          const visible = el => !!(el.getClientRects().length &&
            getComputedStyle(el).visibility !== 'hidden');
          const fieldName = th => (th.getAttribute('glide_field') || th.getAttribute('name') || th.getAttribute('data-name') || (/^(Numer|Number)$/i.test(th.textContent.trim()) ? 'number' : th.textContent.trim())).replace(/^(?:incident|sc_task)\\./, '');
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
            return /^(?:(?:incident|sc_task)\\.)?number$/.test(name) || /^(Numer|Number)$/i.test(th.innerText.trim());
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
            state: column(['state', 'incident_state'], ['stan', 'state']),
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
            const base = known || 'sn:' + raw;
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
        })""")
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


def navigate(page, url):
    # SSO can start a second navigation before goto has finished. Keep that
    # navigation alive so that the user can complete authentication.
    url = normalize_url(url)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        actual = page.url
        if (not is_short_url(url) and isinstance(actual, str) and urlparse(actual).hostname == urlparse(url).hostname
                and actual.startswith(f"https://{urlparse(url).netloc}/now/nav/ui/classic/params/target/")):
            # Authentication/session restoration can wrap an otherwise direct
            # URL. Reopen the requested list rather than the navigation shell.
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
    except Exception as exc:
        if "interrupted by another navigation" not in str(exc):
            raise


def authentication_page(page, url):
    actual = urlparse(page.url)
    return (actual.hostname != urlparse(url).hostname
            or any(part in actual.path.lower() for part in ("login", "sso", "auth")))


def wait_for_login(page, url, stop, auto_login=False, minimize_after_login=False, browser_window=None):
    """Wait for a real incident list; never navigate over an SSO login page."""
    last_navigation = 0
    from neto_incident_monitor.automatic_login import AutomaticLogin
    from neto_incident_monitor.login_diagnostics import LoginDiagnostics
    diagnostics = LoginDiagnostics(auto_login=bool(auto_login), minimize=bool(minimize_after_login), hidden=bool(browser_window))
    automatic = AutomaticLogin(diagnostics=diagnostics) if auto_login else None
    manual_shown = False
    login_started = time.monotonic()
    last_inspection_warning = None
    while not stop.is_set():
        if page.is_closed():
            diagnostics.record("browser_closed")
            raise BrowserClosedError("Przeglądarka logowania została zamknięta.")
        try:
            diagnostics.inspect(page, automatic)
            if automatic and authentication_page(page, url):
                automatic.step(page)
            if (minimize_after_login or browser_window) and not manual_shown and authentication_page(page, url):
                # Allow redirects and saved-account login to finish in the
                # background; surface MFA, blocked login or a stalled attempt.
                delay = 20 if automatic else 5
                if (automatic and automatic.blocked) or time.monotonic() - login_started >= delay:
                    if browser_window:
                        browser_window.show()
                    set_chromium_window_state(page, "normal")
                    page.bring_to_front()
                    manual_shown = True
                    diagnostics.record("manual_login_shown", automatic_blocked=bool(automatic and automatic.blocked))
            if not authentication_page(page, url):
                from neto_incident_monitor.service_now_urls import is_short_url, resolved_list_url
                target_url = resolved_list_url(page, url) if is_short_url(url) else url
                expected_host = urlparse(url).hostname
                list_loaded = any(urlparse(frame.url).hostname == expected_host
                                  and urlparse(frame.url).path == urlparse(target_url or '').path
                                  for frame in page.frames)
                if list_loaded and (collect(page) or empty_list(page, target_url)):
                    if browser_window:
                        browser_window.hide()
                    elif minimize_after_login:
                        minimize_chromium(page)
                    diagnostics.record("login_complete")
                    return True
                if not list_loaded and time.monotonic() - last_navigation >= 5:
                    last_navigation = time.monotonic()
                    diagnostics.record("reopen_requested_list")
                    navigate(page, url)
        except Exception as exc:
            diagnostics.record("login_loop_error", error_type=type(exc).__name__)
            # SSO transitions can destroy execution contexts while we inspect them.
            if page.is_closed():
                raise
            now = time.monotonic()
            if last_inspection_warning is None or now - last_inspection_warning >= 30:
                # Exception messages can contain URLs or form data. Log only type.
                LOG.warning("Nie udało się sprawdzić stanu logowania (%s); ponawiam odczyt.", type(exc).__name__)
                last_inspection_warning = now
        page.wait_for_timeout(500)
    diagnostics.record("login_cancelled")
    return False


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
    except Exception:
        LOG.warning("Nie udało się zmienić stanu okna przeglądarki na %s.", state)
    finally:
        if session:
            try:
                session.detach()
            except Exception:
                pass


class App(DynamicColumns):
    def __init__(self, root, history_path=None, enable_tray=True, instance=None, apply_startup=True):
        self.root = root
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.browser_window = None
        self.worker = None
        self.items = {}
        self.snapshots = {}
        self.updating_filter_url = None
        self.new_numbers = set()
        self.next_check = None
        self.check_deadlines = {}
        self.history = History(history_path or DATA / "history.json")
        self.row_numbers = {}
        self.tray = None
        self.tray_ready = False
        self.quitting = False
        self.instance = instance
        self.schedule = Schedule()
        self.auth_waiting = False
        settings = read_json(CONFIG, {})
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
        self.highlight_unread.trace_add("write", self.change_unread_highlighting)
        self.teams_enabled.trace_add("write", self.change_teams)
        from neto_incident_monitor.google_chat_ui import changed as google_chat_changed
        self.google_chat_enabled.trace_add("write", lambda *_: google_chat_changed(self))
        self.auto_login.trace_add("write", self.save_auto_login)
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
                self.tray = Tray(self.events, self.unread_highlighting_enabled(),
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
        try:
            settings = read_json(CONFIG, {})
            if key == "start_with_windows":
                from neto_incident_monitor.startup import set_windows_startup
                set_windows_startup(enabled)
            settings[key] = enabled
            save_json(CONFIG, settings)
        except Exception as error:
            self.saving_startup = True
            variable.set(not enabled)
            self.saving_startup = False
            if key == "start_with_windows":
                try:
                    set_windows_startup(not enabled)
                except Exception:
                    LOG.exception("Nie udało się przywrócić ustawienia autostartu")
            messagebox.showerror("Uruchamianie aplikacji", f"Nie udało się zapisać ustawienia: {error}", parent=self.settings_window)

    def unread_highlighting_enabled(self):
        preference = getattr(self, "highlight_unread", None)
        return preference.get() if preference is not None else True

    def change_unread_highlighting(self, *_):
        try:
            settings = read_json(CONFIG, {})
            settings["highlight_unread"] = self.highlight_unread.get()
            save_json(CONFIG, settings)
        except (OSError, ValueError) as error:
            self.highlight_unread.trace_remove("write", self.highlight_unread.trace_info()[0][1])
            self.highlight_unread.set(not self.highlight_unread.get())
            self.highlight_unread.trace_add("write", self.change_unread_highlighting)
            messagebox.showerror("Ustawienia", f"Nie udało się zapisać ustawienia: {error}", parent=self.settings_window)
            return
        if self.highlight_unread.get():
            self.mark_all_button.pack(side="right")
        else:
            self.mark_all_button.pack_forget()
        menu = getattr(self, "incident_menu", None)
        if menu is not None and menu.winfo_exists():
            menu.destroy()
        self.refresh_history()
        self.refresh_current()
        self.apply_visible_columns()
        self.update_counts()

    def approve_large_list(self, url, name, count):
        if next((entry.get("allow_large_list", False) for entry in self.filters if entry["url"] == url), False):
            return True
        request = {"url": url, "name": name, "count": count, "deadline": time.monotonic() + 15,
                   "done": threading.Event(), "accepted": False}
        self.events.put(("large_list_prompt", request))
        while not self.stop.is_set():
            remaining = request["deadline"] - time.monotonic()
            if remaining <= 0:
                request["done"].set()
                return False
            if request["done"].wait(min(remaining, 0.1)):
                return request["accepted"]
        request["done"].set()
        return False

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
        columns = [("read", "Przeczytanie", 145),
                   *[(key, label, width) for key, label, width in FIELDS if key not in ("read", "time")]]
        if history:
            columns.insert(0, ("time", "Wykryto", 150))
        table = ttk.Treeview(parent, columns=[key for key, _, _ in columns], show="headings")
        table.history_view = history
        order = self.column_order(table)
        table.configure(displaycolumns=tuple(key for key in order if key in getattr(self, "visible_columns", DEFAULT)))
        table.tag_configure("unread", background="#382c33", foreground="#ffdce1")
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
            if "unread" not in table.item(item, "tags"):
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
            self.refresh_current()
            self.refresh_history()
            self.apply_visible_columns()
            self.update_counts()

    def configure_filter_notifications(self, item):
        from neto_incident_monitor.filter_settings import show_filter_settings
        show_filter_settings(self, int(item))

    def configure_selected_filter(self):
        selected = self.filter_table.selection()
        if selected:
            self.configure_filter_notifications(selected[0])

    def notify_filter(self, url, incidents, manual=False):
        entry = next((entry for entry in self.filters if entry["url"] == url), None)
        if not entry or (not manual and not entry.get("enabled", True)) or not incidents:
            return
        from neto_incident_monitor.teams_notifications import incident_text
        _, message = incident_text(incidents)
        catalog_tasks = all(item["number"].startswith("SCTASK") for item in incidents)
        singular, plural = ("zadanie katalogowe", "zadania katalogowe") if catalog_tasks else ("incydent", "incydenty")
        heading = f"Wykryto {singular}" if len(incidents) == 1 else f"Wykryto {plural}: {len(incidents)}"
        title = entry["name"]
        message = heading + "\n" + message
        if self.teams_enabled.get() and entry.get("notify_teams", True) and self.teams_webhook:
            links = {item["number"]: item["url"] for item in incidents if item.get("url")}
            self.teams_sender.submit(self.teams_webhook, title, message, **({"links": links} if links else {}))
        if self.google_chat_enabled.get() and entry.get("notify_google_chat", True) and self.google_chat_webhook:
            links = {item["number"]: item["url"] for item in incidents if item.get("url")}
            self.google_chat_sender.submit(self.google_chat_webhook, title, message, links=links)
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

    def persist_filters(self):
        settings = read_json(CONFIG, {})
        settings["filters"] = self.filters
        settings["urls"] = [entry["url"] for entry in self.filters]
        save_json(CONFIG, settings)

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
        self.auth_waiting = phase in ("Oczekiwanie na logowanie", "Uruchamianie przeglądarki")
        self.check_button.configure(state="disabled" if self.auth_waiting or not self.worker or not self.worker.is_alive() or self.quitting else "normal")
        self.update_tray()

    def update_counts(self):
        numbers = set(self.snapshots.get(self.selected_filter_index(), {}))
        self.current_count.set(str(len(numbers)))
        self.new_count.set(str(len(self.new_numbers)))
        unread = sum(not record["read"] for record in self.history.snapshot(self.selected_filter_url()).values())
        self.unread_count.set(str(unread))
        self.tabs.tab(1, text="Historia zgłoszeń")
        self.update_tray()

    def update_tray(self):
        if self.tray and self.tray_ready:
            try:
                self.tray.update(self.history.unread() if self.unread_highlighting_enabled() else 0,
                                 getattr(self, "monitoring_phase", "Gotowy do uruchomienia"),
                                 unread_enabled=self.unread_highlighting_enabled())
            except Exception:
                LOG.exception("Błąd aktualizacji zasobnika")

    def clear_table(self, table):
        for item in table.get_children():
            self.items.pop((table, item), None)
            self.row_numbers.pop((table, item), None)
            table.delete(item)

    def refresh_history(self):
        selected = {self.row_numbers.get((self.table, item)) for item in self.table.selection()}
        self.clear_table(self.table)
        records = self.history.snapshot(self.selected_filter_url())
        for number, record in sorted(records.items(), key=lambda pair: pair[1]["detected"], reverse=True):
            incident = record["incident"]
            label = "Nieprzeczytany" if not record["read"] else "Przeczytany"
            item = self.table.insert("", "end", values=self.table_values(self.table, incident, label,
                time.strftime("%d.%m.%Y %H:%M", time.localtime(record["detected"]))),
                tags=("unread",) if self.unread_highlighting_enabled() and not record["read"] else ("alternate",) if len(self.table.get_children()) % 2 else ())
            self.items[(self.table, item)] = incident["url"]
            self.row_numbers[(self.table, item)] = number
            if number in selected:
                self.table.selection_add(item)
        self.table.default_order = self.table.get_children()
        self.apply_sort(self.table)

    def refresh_current(self):
        selected = {self.row_numbers.get((self.current_table, item)) for item in self.current_table.selection()}
        records = self.history.snapshot(self.selected_filter_url())
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
        for number, entry in sorted(combined.items(), key=lambda pair: int(re.sub(r"\D", "", pair[0]) or 0), reverse=True):
            incident = entry["incident"]
            unread = number in records and not records[number]["read"]
            label = "Nieprzeczytany" if unread else "Przeczytany" if number in records else "—"
            item = self.current_table.insert("", "end", values=self.table_values(self.current_table, incident, label),
                tags=("unread",) if self.unread_highlighting_enabled() and unread else ("alternate",) if len(self.current_table.get_children()) % 2 else ())
            self.items[(self.current_table, item)] = incident.get("url", "")
            self.row_numbers[(self.current_table, item)] = number
            if number in selected:
                self.current_table.selection_add(item)
        self.current_table.default_order = self.current_table.get_children()
        self.apply_sort(self.current_table)

    def mark_selected(self):
        table = self.current_table if self.tabs.index(self.tabs.select()) == 0 else self.table
        self.mark_read([self.row_numbers[(table, item)] for item in table.selection()])

    def mark_all(self):
        self.mark_read(list(self.history.snapshot(self.selected_filter_url())))

    def clear_history(self):
        from neto_incident_monitor.widgets import confirm_dialog
        if not self.history.snapshot(self.selected_filter_url()):
            messagebox.showinfo("Historia zgłoszeń", "Historia jest już pusta.", parent=self.root)
            return
        confirmed = confirm_dialog(
            self.root,
            "Wyczyść historię zgłoszeń",
            "Czy usunąć historię wybranego filtra i jego oznaczenia przeczytania?\n\n"
            "Tej operacji nie można cofnąć. Bieżąca lista i pamięć wcześniej widzianych incydentów pozostaną zachowane.",
            )
        if not confirmed:
            return
        try:
            self.history.clear(self.selected_filter_url())
        except OSError as exc:
            LOG.exception("Nie udało się wyczyścić historii")
            messagebox.showerror("Historia zgłoszeń", f"Nie udało się zapisać zmiany: {exc}", parent=self.root)
            return
        self.refresh_history()
        self.refresh_current()
        self.update_counts()
        self.status.set("Historia wyczyszczona. Pamięć wcześniej widzianych incydentów została zachowana.")

    def mark_read(self, numbers):
        if not numbers or not self.unread_highlighting_enabled():
            return
        try:
            self.history.mark_read(numbers, self.selected_filter_url())
        except OSError as exc:
            LOG.exception("Błąd zapisu oznaczeń przeczytania")
            self.show_window()
            messagebox.showerror("Historia", f"Nie udało się zapisać oznaczeń: {exc}", parent=self.root)
            return
        self.refresh_history()
        self.refresh_current()
        self.update_counts()

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
        if self.worker and self.worker.is_alive() and not self.auth_waiting and not self.quitting:
            self.schedule.request()
            self.next_check = None
            self.status.set("Zlecono sprawdzenie wszystkich list. Jeśli odczyt trwa, kolejna próba ruszy po jego zakończeniu.")

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
        except (OSError, ValueError):
            self.status.set("Nie udało się zapisać ustawienia automatycznego logowania.")

    def save_browser_minimize(self, *_):
        try:
            settings = read_json(CONFIG, {})
            settings["minimize_browser"] = self.minimize_browser.get()
            settings["hide_browser"] = self.hide_browser.get()
            save_json(CONFIG, settings)
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

    def notify_batch(self, incidents):
        records = self.history.snapshot(self.selected_filter_url())
        unread = [incident for incident in incidents
                  if incident["number"] in records and not records[incident["number"]]["read"]]
        text = batch_text(unread)
        if text is None:
            return
        title, message = text
        if self.teams_enabled.get() and self.teams_webhook:
            from neto_incident_monitor.teams_notifications import incident_text
            teams_title, teams_message = incident_text(unread)
            self.teams_sender.submit(self.teams_webhook, teams_title, teams_message)
        if self.google_chat_enabled.get() and self.google_chat_webhook:
            from neto_incident_monitor.teams_notifications import incident_text
            chat_title, chat_message = incident_text(unread)
            links = {item["number"]: item["url"] for item in unread if item.get("url")}
            self.google_chat_sender.submit(self.google_chat_webhook, chat_title, chat_message, links=links)
        if not self.notify.get():
            return
        try:
            from plyer import notification
            self.root.bell()
            notification.notify(title=title, message=message, app_name="Neto Incident Monitor", timeout=10)
        except Exception as exc:
            LOG.exception("Błąd zbiorczego powiadomienia Windows")
            self.status.set(f"Incydenty zapisano w historii. Błąd powiadomienia Windows: {exc}")

    def start(self):
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
        self.stop.clear()
        self.schedule.consume()
        self.snapshots.clear()
        self.column_availability.clear()
        self.new_numbers.clear()
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
        self.worker = threading.Thread(target=self.monitor, args=(settings,), daemon=True)
        self.worker.start()

    def monitor(self, settings):
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
                    # Back off without delaying an explicit Stop request.
                    if self.stop.wait(2):
                        break
        finally:
            self.events.put(("finished", None))

    def _monitor_browser(self, settings):
        self.browser_window = None
        health = Health()
        try:
            from playwright.sync_api import sync_playwright
            from neto_incident_monitor.filter_state import FilterState
            membership = FilterState(STATE, normalize_url)
            with sync_playwright() as playwright:
                context = playwright.chromium.launch_persistent_context(
                    str(DATA / "browser-profile"), headless=False, no_viewport=True,
                    args=["--start-minimized"] if settings.get("minimize_browser", False) or settings.get("hide_browser", False) else [])
                # Wake an idle monitoring cycle immediately when Chromium exits.
                context.on("close", lambda *_: self.schedule.request())
                try:
                    page = context.pages[0] if context.pages else context.new_page()
                    if settings.get("hide_browser", False):
                        from neto_incident_monitor.browser_window import BrowserWindow
                        self.browser_window = BrowserWindow(context.browser,
                            visibility_changed=lambda: self.events.put(("browser_visibility", None)))
                        self.browser_window.hide()
                    elif settings.get("minimize_browser", False):
                        minimize_chromium(page)
                    navigate(page, settings["urls"][0])
                    if not settings.get("minimize_browser", False) and not settings.get("hide_browser", False):
                        page.bring_to_front()
                    self.events.put(("phase", "Oczekiwanie na logowanie"))
                    self.events.put(("status", "Zaloguj się w przeglądarce. Monitoring rozpocznie się automatycznie po załadowaniu listy."))
                    if not wait_for_login(page, settings["urls"][0], self.stop, settings.get("auto_login", False), settings.get("minimize_browser", False), self.browser_window):
                        return
                    intervals = {"inc": settings["interval"], "task": settings.get("task_interval", 3600)}
                    resolved = {url: effective_list_url(url, settings['filters']) for url in settings['urls']}
                    def list_kind(url):
                        return 'task' if urlparse(resolved[url]).path.endswith('/sc_task_list.do') else 'inc'
                    deadlines = {"inc": 0, "task": 0}
                    force = True
                    while not self.stop.is_set():
                        due = {kind for kind in intervals if force or time.monotonic() >= deadlines[kind]}
                        active = {list_kind(url)
                                  for url in settings["urls"] if url not in self.disabled_filter_urls}
                        self.events.put(("check_deadlines", {kind: deadlines[kind] for kind in active - due}))
                        self.events.put(("checking", None))
                        cycle_error = False
                        for filter_index, url in enumerate(settings["urls"], 1):
                            kind = list_kind(url)
                            if kind not in due:
                                continue
                            if url in self.disabled_filter_urls:
                                continue
                            filter_name = next(entry['name'] for entry in settings['filters'] if entry['url'] == url)
                            if self.stop.is_set():
                                break
                            self.events.put(("filter_updating", url))
                            try:
                                # Filters are read sequentially, so one tab is
                                # sufficient. Opening additional tabs restores
                                # a minimized Chromium window on Windows.
                                if page.is_closed():
                                    page = context.new_page()
                                    if self.browser_window:
                                        self.browser_window.hide()
                                    elif settings.get("minimize_browser", False):
                                        minimize_chromium(page)
                                current = page
                                available = ColumnDiscovery()
                                incidents, page_count = read_all(
                                    current, url, self.stop, lambda p: collect(p, available), empty_list, authentication_page, navigate,
                                    lambda index, count: self.events.put(("status",
                                        f"{filter_name}: strona {index}, odczytano {count} incydentów…"
                                        if index else f"{filter_name}: powrót do pierwszej strony…")),
                                    approve_large=lambda count: self.approve_large_list(url, filter_name, count))
                                if url in self.disabled_filter_urls:
                                    continue
                                if is_short_url(url):
                                    direct = resolved_list_url(current, url)
                                    if not direct:
                                        raise ValueError('Nie rozpoznano docelowej listy skrótu.')
                                    resolved[url] = direct
                                    self.events.put(('filter_resolved', (url, direct)))
                                for incident in incidents.values():
                                    incident["_available_columns"] = sorted(available)
                                if available.schema is not None:
                                    self.events.put(("columns", (url, available.schema)))
                                options = next((entry for entry in self.filters if entry["url"] == url), {})
                                arrivals = membership.arrivals(url, incidents)
                                new = membership.arrivals(url, incidents, options.get("first_only", False))
                                for number in sorted(arrivals):
                                    self.history.add(incidents[number], filter_name, url, reappeared=True)
                                membership.commit(url, incidents)
                                health.success(url)
                                self.events.put(("snapshot", (url, incidents)))
                                if new:
                                    self.events.put(("filter_notification", (url, [incidents[n] for n in sorted(new)])))
                                self.events.put(("read", (time.time(), filter_name)))
                                self.events.put(("status", f"{filter_name}: {len(incidents)} incydentów na {page_count} stronach; nowych w tym odczycie: {len(new)}."))
                            except LargeListRejected:
                                self.events.put(("status", f"Pominięto dużą listę: {filter_name}."))
                            except Cancelled:
                                return
                            except AuthenticationRequired:
                                self.events.put(("phase", "Oczekiwanie na logowanie"))
                                message = "Sesja ServiceNow wygasła. Zaloguj się w przeglądarce — monitoring wznowi się automatycznie."
                                self.events.put(("status", message))
                                if health.authentication():
                                    self.events.put(("session_expired", message))
                                if not settings.get("minimize_browser", False) and not settings.get("hide_browser", False):
                                    current.bring_to_front()
                                if not wait_for_login(current, url, self.stop, settings.get("auto_login", False), settings.get("minimize_browser", False), self.browser_window):
                                    return
                                health.resumed()
                                self.schedule.request()
                                break
                            except TargetClosedError:
                                raise
                            except Exception as exc:
                                LOG.exception("Błąd odczytu filtra %s", filter_name)
                                cycle_error = True
                                self.events.put(("phase", "Błąd odczytu"))
                                self.events.put(("status", f"Błąd odczytu: {exc}. Próba ponownie w kolejnym cyklu."))
                                if health.failure(url):
                                    self.events.put(("interruption", f"Lista „{filter_name}”: trzy kolejne odczyty nie powiodły się. Otwórz aplikację i sprawdź sesję lub połączenie. Automatyczne próby będą kontynuowane."))
                            finally:
                                self.events.put(("filter_updating", None))
                        now = time.monotonic()
                        for kind in due:
                            deadlines[kind] = now + intervals[kind]
                        active = {list_kind(url)
                                  for url in settings["urls"] if url not in self.disabled_filter_urls}
                        next_read = min((deadlines[kind] for kind in active), default=now + min(intervals.values()))
                        self.events.put(("waiting", (next_read, cycle_error)))
                        self.events.put(("check_deadlines", {kind: deadlines[kind] for kind in active}))
                        if wait_for_browser_cycle(page, self.schedule, max(0, next_read - now), self.stop):
                            break
                        force = self.schedule.woken_by_request is True or intervals["inc"] == intervals["task"]
                finally:
                    self.browser_window = None
                    self.events.put(("browser_visibility", None))
                    context.close()
        except (TargetClosedError, BrowserClosedError):
            raise
        except Exception as exc:
            LOG.exception("Nie udało się uruchomić monitoringu")
            self.events.put(("phase", "Błąd uruchomienia"))
            self.events.put(("status", f"Nie udało się uruchomić monitoringu: {exc}"))
            if not self.stop.is_set():
                self.events.put(("interruption", "Monitoring zatrzymał się z powodu błędu przeglądarki lub aplikacji. Otwórz aplikację, aby zobaczyć szczegóły i uruchomić go ponownie."))

    def drain(self):
        if self.instance and self.instance.poll():
            self.show_window()
        try:
            while True:
                kind, value = self.events.get_nowait()
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
                    if self.browser_window:
                        self.browser_window.show()
                elif kind == "hide_browser":
                    if self.browser_window:
                        self.browser_window.hide()
                elif kind == "browser_visibility":
                    if self.tray and self.tray_ready:
                        self.tray.icon.update_menu()
                elif kind == "check_now":
                    self.check_now()
                elif kind == "interruption":
                    self.interruption(value)
                elif kind == "session_expired":
                    self.session_expired(value)
                elif kind == "filter_notification":
                    url, incidents = value
                    self.notify_filter(url, incidents)
                elif kind == "batch_notification":
                    self.notify_batch(value)
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
                elif kind == "mark_all":
                    self.mark_all()
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
                    self.check_deadlines = {}
                    self.updating_filter_url = None
                    self.filter_table.updating_item = None
                    self.filter_table.redraw()
                    self.next_check = None
                    if self.stop.is_set():
                        self.set_phase("Monitoring zatrzymany")
                        self.status.set("Odczyty zatrzymane. Lista zachowuje ostatni udany wynik.")
                    self.start_button.configure(state="normal")
                    self.stop_button.configure(state="disabled")
                    self.check_button.configure(state="disabled")
                    self.interval_entry.configure(state="normal")
                    self.task_interval_entry.configure(state="normal")
                    self.notify_check.configure(state="normal")
                    for button in self.filter_buttons:
                        button.configure(state="normal")
                elif kind == "incident":
                    name, incident, notify = value
                    self.new_numbers.add(incident["number"])
                    self.update_counts()
                    # A confirmed clear can happen after the worker persisted
                    # a record but before this queued event is processed.
                    # Do not resurrect a record that the user just removed.
                    if incident["number"] not in self.history.snapshot(self.selected_filter_url()):
                        continue
                    self.refresh_history()
                    self.refresh_current()
                    if notify:
                        self.notify_batch([incident])
        except queue.Empty:
            pass
        now = time.monotonic()
        if now - getattr(self, "last_age_refresh", 0) >= 1:
            self.last_age_refresh = now
            for table in (self.current_table, self.table):
                for item in table.get_children():
                    value = age_minutes(table.set(item, "created"), table.set(item, "number"))
                    if table.set(item, "age_minutes") != value:
                        table.set(item, "age_minutes", value)
                if table.sort_column == "age_minutes":
                    self.apply_sort(table)
        def remaining(kind):
            deadline = self.check_deadlines.get(kind)
            return "-" if deadline is None else f"{max(0, int(deadline - now + 0.999))} s"
        self.countdown.set(f"Następna aktualizacja INC: {remaining('inc')}  STASK: {remaining('task')}")
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
            if url and webbrowser.open(url):
                self.mark_read([self.row_numbers[key]])

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
            if url and webbrowser.open(url):
                self.mark_read([number])
        def copy(value):
            self.root.clipboard_clear()
            self.root.clipboard_append(value)
        if url:
            menu.add_command(label="Otwórz incydent", command=open_selected)
        menu.add_separator()
        menu.add_command(label="Kopiuj numer", command=lambda: copy(number))
        if url:
            menu.add_command(label="Kopiuj link", command=lambda: copy(url))
        if self.unread_highlighting_enabled():
            menu.add_separator()
            menu.add_command(label="Oznacz jako przeczytany", command=lambda: self.mark_read([number]))
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
            record = self.history.snapshot(filter_url).get(number)
            incident = record["incident"] if record else None
        if incident is not None:
            self.notify_filter(filter_url, [{**incident, "number": number, "url": url}], manual=True)

    def close(self):
        self.quit_app()

    def quit_app(self):
        if self.window_save_timer is not None:
            self.root.after_cancel(self.window_save_timer)
            self.window_save_timer = None
        self.save_window_layout()
        self.quitting = True
        self.stop.set()
        self.schedule.request()
        self.show_window()
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
            if self.tray:
                try:
                    self.tray.stop()
                except Exception:
                    LOG.exception("Błąd zamykania zasobnika")
            self.root.destroy()


def main():
    from neto_incident_monitor.single_instance import SingleInstance
    instance = SingleInstance(DATA)
    window = None
    try:
        if not instance.primary:
            instance.request_show()
            return
        window = tk.Tk()

        def callback_error(error_type, error, traceback):
            LOG.error("Błąd obsługi interfejsu", exc_info=(error_type, error, traceback))
            messagebox.showerror("Neto Incident Monitor", f"Błąd aplikacji: {error}", parent=window)

        window.report_callback_exception = callback_error
        App(window, instance=instance)
        window.mainloop()
    except Exception as error:
        LOG.exception("Błąd aplikacji")
        messagebox.showerror("Neto Incident Monitor", str(error))
        if window is not None:
            window.destroy()
    finally:
        instance.close()


if __name__ == "__main__":
    main()
