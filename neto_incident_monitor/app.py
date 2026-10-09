"""Local ServiceNow list monitor. Browser access only; no ServiceNow API."""
from neto_incident_monitor.theme import BG, SURFACE, TEXT, MUTED, ACCENT
from neto_incident_monitor.columns import FIELDS, DEFAULT, DATA_FIELDS, LOCAL
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
from neto_incident_monitor.history import History
from neto_incident_monitor.monitoring import Schedule, Health
from neto_incident_monitor.pagination import read_all, AuthenticationRequired, Cancelled
from neto_incident_monitor.notifications import batch_text

from neto_incident_monitor.runtime_paths import ROOT, DATA
DATA.mkdir(parents=True, exist_ok=True)
CONFIG = DATA / "config.json"
STATE = DATA / "seen.json"
INC = re.compile(r"\bINC\d{7,}\b", re.I)
LOG = logging.getLogger("servicenow")


def read_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, value):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def normalize_url(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username:
        raise ValueError("Każdy adres musi być poprawnym adresem HTTPS.")
    prefix = "/now/nav/ui/classic/params/target/"
    if not parsed.path.startswith(prefix):
        return url
    # Decode the navigation envelope exactly once. Encoded filter values
    # inside sysparm_query must retain their own percent escaping.
    target = urlparse(unquote(parsed.path[len(prefix):]))
    if target.scheme or target.netloc or target.path not in ("incident_list.do", "/incident_list.do"):
        raise ValueError("Link nawigacyjny musi wskazywać listę incident_list.do na tym samym serwerze.")
    return parsed._replace(path="/incident_list.do", params="", query=target.query, fragment=target.fragment).geturl()


def validate_urls(text):
    urls = [line.strip() for line in text.splitlines() if line.strip()]
    if not urls:
        raise ValueError("Wklej przynajmniej jeden adres listy z filtrem.")
    return list(dict.fromkeys(normalize_url(url) for url in urls))


def load_filters(settings):
    """Migrate the previous URL-only configuration without touching seen state."""
    entries = settings.get("filters") or [
        {"name": f"Filtr {index}", "url": url}
        for index, url in enumerate(settings.get("urls", []), 1)
    ]
    return [{**entry, "url": normalize_url(entry["url"])} for entry in entries]


def incident_values(incident):
    values = []
    for key in ("number", *DATA_FIELDS):
        value = incident.get(key) or "—"
        if key == "priority" and str(value).strip()[:1] in PriorityDots.COLORS:
            value = "\u2003\u2002" + str(value).strip()
        values.append(value)
    return tuple(values)


def collect(page, available=None):
    """Read incident fields by header identity, including empty-list metadata."""
    found = {}
    for frame in page.frames:
        rows = frame.locator("table:visible").evaluate_all("""tables => tables.flatMap(table => {
          const visible = el => !!(el.getClientRects().length &&
            getComputedStyle(el).visibility !== 'hidden');
          const headers = Array.from(table.querySelectorAll('th'))
            .filter(th => th.closest('table') === table && visible(th));
          const header = headers.find(th => {
            const name = th.getAttribute('name') || th.getAttribute('data-name') || '';
            return /^(incident\\.)?number$/.test(name) || /^(Numer|Number)$/i.test(th.innerText.trim());
          });
          if (!header) return [];
          const column = (names, labels) => headers.find(th => {
            const name = (th.getAttribute('name') || th.getAttribute('data-name') || '').replace(/^incident\\./, '');
            return names.includes(name) || labels.includes(th.innerText.trim().toLowerCase());
          });
          const fields = {
            short_description: column(['short_description'], ['krótki opis', 'short description']),
            priority: column(['priority'], ['priorytet', 'priority']),
            location: column(['location'], ['lokalizacja', 'location']),
            created: column(['sys_created_on'], ['utworzono', 'created']),
            updated: column(['sys_updated_on'], ['zaktualizowano', 'updated']),
            state: column(['state', 'incident_state'], ['stan', 'state']),
            caller: column(['caller_id'], ['zgłaszający', 'caller']),
            assigned_to: column(['assigned_to'], ['przypisane do', 'assigned to']),
            description: column(['description'], ['opis', 'description']),
            parent_incident: column(['parent_incident', 'parent'], ['incydent nadrzędny', 'parent incident']),
            configuration_item: column(['cmdb_ci'], ['objęty element konfiguracji', 'element konfiguracji', 'configuration item']),
            assignment_group: column(['assignment_group'], ['grupa przypisania', 'assignment group'])
          };
          return [{available: ['number', ...Object.entries(fields).filter(([key, th]) => th).map(([key]) => key)]}, ...Array.from(table.rows).filter(tr => tr.closest('table') === table && visible(tr))
            .flatMap(tr => {
              const cell = tr.cells[header.cellIndex];
              if (!cell || cell.tagName !== 'TD') return [];
              return Array.from(cell.querySelectorAll('a')).filter(visible).map(a => ({
                label: a.innerText, href: a.href, row: tr.innerText,
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
                continue
            match = INC.fullmatch(row["label"].strip())
            if match:
                number = match.group().upper()
                found[number] = {"number": number, "url": row["href"],
                                 **{key: " ".join(value.split()) for key, value in row["fields"].items()},
                                 "summary": " ".join(row["fields"]["short_description"].split())
                                 or number}
    return found


def empty_list(page, url):
    """Accept the empty-list message only on the expected incident-list frame."""
    expected_host = urlparse(url).hostname
    for frame in page.frames:
        parsed = urlparse(frame.url)
        if parsed.hostname != expected_host or not parsed.path.endswith("/incident_list.do"):
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
        if (isinstance(actual, str) and urlparse(actual).hostname == urlparse(url).hostname
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


def wait_for_login(page, url, stop, auto_login=False, minimize_after_login=False):
    """Wait for a real incident list; never navigate over an SSO login page."""
    last_navigation = 0
    from neto_incident_monitor.automatic_login import AutomaticLogin
    automatic = AutomaticLogin() if auto_login else None
    while not stop.is_set():
        if page.is_closed():
            raise RuntimeError("Przeglądarka logowania została zamknięta. Uruchom monitoring ponownie.")
        try:
            if automatic and authentication_page(page, url):
                automatic.step(page)
            if not authentication_page(page, url):
                expected_host = urlparse(url).hostname
                list_loaded = any(urlparse(frame.url).hostname == expected_host
                                  and urlparse(frame.url).path.endswith("/incident_list.do")
                                  for frame in page.frames)
                if list_loaded and (collect(page) or empty_list(page, url)):
                    if minimize_after_login:
                        minimize_chromium(page)
                    return True
                if not list_loaded and time.monotonic() - last_navigation >= 5:
                    last_navigation = time.monotonic()
                    navigate(page, url)
        except Exception:
            # SSO transitions can destroy execution contexts while we inspect them.
            if page.is_closed():
                raise
        page.wait_for_timeout(500)
    return False


def minimize_chromium(page):
    """Minimize only the Chromium window containing the authenticated tab."""
    session = None
    try:
        session = page.context.new_cdp_session(page)
        window = session.send("Browser.getWindowForTarget")
        session.send("Browser.setWindowBounds", {
            "windowId": window["windowId"], "bounds": {"windowState": "minimized"}})
    except Exception:
        LOG.warning("Nie udało się zminimalizować przeglądarki po logowaniu.")
    finally:
        if session:
            try:
                session.detach()
            except Exception:
                pass


class App:
    def __init__(self, root, history_path=None, enable_tray=True, instance=None):
        self.root = root
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.worker = None
        self.items = {}
        self.snapshots = {}
        self.new_numbers = set()
        self.next_check = None
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
        self.filters = load_filters(settings)
        self.disabled_filter_urls = frozenset(entry["url"] for entry in self.filters if not entry.get("enabled", True))
        self.visible_columns = settings.get("visible_columns", DEFAULT)
        self.column_availability = {}
        self.column_orders = settings.get("column_order", {})
        self.column_widths = settings.get("column_widths", {})
        from neto_incident_monitor.ui import build_ui
        build_ui(self, settings)
        self.teams_enabled.trace_add("write", self.change_teams)
        self.auto_login.trace_add("write", self.save_auto_login)
        self.minimize_browser.trace_add("write", self.save_browser_minimize)
        self.saved_minimize = self.minimize_to_tray.get()
        self.minimize_to_tray.trace_add("write", self.save_minimize_preference)
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
            self.window_restoring = False
        root.after_idle(restore_window)
        root.after(200, self.drain)
        if enable_tray:
            try:
                from neto_incident_monitor.tray import Tray
                self.tray = Tray(self.events)
                self.tray.start()
            except Exception:
                LOG.exception("Nie udało się uruchomić zasobnika")
                self.tray = None
                self.status.set("Zasobnik niedostępny. Monitoring działa w oknie; błędy zapisano w logu.")

    def make_table(self, parent, history):
        columns = [("read", "Przeczytanie", 145),
                   *[(key, label, width) for key, label, width in FIELDS if key == "number" or key in DATA_FIELDS]]
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

    def column_order(self, table):
        keys = [key for key, _, _ in FIELDS if key in table["columns"]]
        default = [key for key in DEFAULT if key in keys] + [key for key in keys if key not in DEFAULT]
        orders = getattr(self, "column_orders", {})
        saved = orders.get("shared", orders.get("current", orders.get("history", [])))
        order = list(dict.fromkeys(key for key in saved if key in default and key != "time"))
        order += [key for key in default if key not in order and key != "time"]
        return order + (["time"] if table.history_view else [])

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
                or target is None or target == drag["column"] or target == "time" or drag["column"] == "time"):
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

    def reorder_column(self, table, source, target):
        if source == "time" or target == "time":
            return
        visible = list(table["displaycolumns"])
        if source not in visible or target not in visible or source == target:
            return
        original = list(visible)
        position = visible.index(target)
        visible.remove(source)
        visible.insert(position, source)
        # Hidden fields keep their places; moving a header never loses them.
        reordered = iter(visible)
        order = [next(reordered) if key in original else key for key in self.column_order(table)]
        proposed = {"shared": [key for key in order if key != "time"]}
        try:
            settings = read_json(CONFIG, {})
            settings["column_order"] = proposed
            save_json(CONFIG, settings)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Kolejność kolumn", f"Nie udało się zapisać kolejności: {exc}", parent=self.root)
            return
        self.column_orders = proposed
        self.apply_visible_columns()

    def sync_column_widths(self, source):
        widths = dict(self.column_widths)
        widths.update({key: source.column(key, "width") for key in source["displaycolumns"]})
        try:
            settings = read_json(CONFIG, {})
            settings["column_widths"] = widths
            save_json(CONFIG, settings)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Szerokości kolumn", f"Nie udało się zapisać szerokości: {exc}", parent=self.root)
            return
        self.column_widths = widths
        for table in (self.current_table, self.table):
            for key, width in widths.items():
                if key in table["columns"]:
                    table.column(key, width=width)

    def available_columns(self, history=False):
        if history:
            incidents = [record["incident"] for record in self.history.snapshot(self.selected_filter_url()).values()]
            if not incidents:
                return None
            available = set()
            for incident in incidents:
                available.update(incident.get("_available_columns", [key for key in DATA_FIELDS if key in incident]))
            return available | LOCAL
        available = self.column_availability.get(self.selected_filter_index())
        return available | LOCAL if available is not None else None

    def apply_visible_columns(self):
        for table, history in ((self.current_table, False), (self.table, True)):
            available = self.available_columns(history)
            order = self.column_order(table)
            visible = [key for key in order if key in self.visible_columns and (available is None or key in available)]
            table.configure(displaycolumns=tuple(visible))
            if table.sort_column and table.sort_column not in visible:
                table.sort_column = None
                self.apply_sort(table)
        self.update_column_warnings()

    def update_column_warnings(self):
        available = self.available_columns()
        for key, badge in getattr(self, "column_badges", {}).items():
            if badge.winfo_exists():
                if available is not None and key not in available:
                    badge.grid()
                else:
                    badge.hide()
                    badge.grid_remove()

    def configure_columns(self):
        from neto_incident_monitor.widgets import RoundedButton, ColumnWarning
        dialog = tk.Toplevel(self.root)
        dialog.title("Widoczne kolumny")
        dialog.configure(background=BG)
        dialog.transient(self.root)
        content = ttk.Frame(dialog, padding=20)
        content.pack(fill="both", expand=True)
        ttk.Label(content, text="Wybierz kolumny", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(content, text="Zmiana dotyczy bieżącej listy i historii.\nKolumny niewidoczne w ServiceNow są automatycznie ukrywane.",
                  foreground=MUTED).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 12))
        choices = {}
        self.column_badges = {}
        for index, (key, label, _) in enumerate(FIELDS):
            variable = tk.BooleanVar(value=key in self.visible_columns)
            choices[key] = variable
            row = ttk.Frame(content)
            row.grid(row=2 + index // 2, column=index % 2, sticky="w", padx=(0, 18), pady=3)
            row.columnconfigure(1, minsize=24)
            check = ttk.Checkbutton(row, text=label, variable=variable, style="App.TCheckbutton")
            check.grid(row=0, column=0, sticky="w")
            badge = ColumnWarning(row, label)
            badge.grid(row=0, column=1, padx=(4, 0))
            self.column_badges[key] = badge
        self.update_column_warnings()
        def closed(event):
            if event.widget is dialog:
                self.column_badges = {}
        dialog.bind("<Destroy>", closed, add="+")

        reset_order = False
        def restore_defaults():
            nonlocal reset_order
            reset_order = True
            for key, variable in choices.items():
                variable.set(key in DEFAULT)

        def save():
            selected = [key for key, variable in choices.items() if variable.get()]
            try:
                settings = read_json(CONFIG, {})
                settings["visible_columns"] = selected
                if reset_order:
                    settings["column_order"] = {}
                save_json(CONFIG, settings)
            except (OSError, ValueError) as exc:
                messagebox.showerror("Kolumny", f"Nie udało się zapisać ustawień: {exc}", parent=dialog)
                return
            self.visible_columns = selected
            if reset_order:
                self.column_orders = {}
            self.apply_visible_columns()
            dialog.destroy()
        actions = ttk.Frame(content)
        actions.grid(row=2 + (len(FIELDS) + 1) // 2, column=0, columnspan=2, sticky="ew", pady=(16, 0))
        RoundedButton(actions, text="Przywróć domyślne", command=restore_defaults, background=BG).pack(side="left", padx=(0, 12))
        RoundedButton(actions, text="Zapisz", command=save, primary=True, background=BG).pack(side="right")
        RoundedButton(actions, text="Anuluj", command=dialog.destroy, background=BG).pack(side="right", padx=8)
        dialog.update_idletasks()
        dialog.geometry(f"+{max(0, (dialog.winfo_screenwidth()-dialog.winfo_reqwidth())//2)}+{max(0, (dialog.winfo_screenheight()-dialog.winfo_reqheight())//2)}")
        dialog.grab_set()

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
        if hasattr(self, "phase"):
            self.update_phase_text()
        if hasattr(self, "current_table"):
            self.refresh_current()
            self.refresh_history()
            self.apply_visible_columns()
            self.update_counts()

    def configure_filter_notifications(self, item):
        from neto_incident_monitor.filter_settings import show_filter_settings
        show_filter_settings(self, int(item))

    def notify_filter(self, url, incidents):
        entry = next((entry for entry in self.filters if entry["url"] == url), None)
        if not entry or not entry.get("enabled", True) or not incidents:
            return
        from neto_incident_monitor.teams_notifications import incident_text
        _, message = incident_text(incidents)
        heading = "Wykryto incydent" if len(incidents) == 1 else f"Wykryto incydenty: {len(incidents)}"
        title = entry["name"]
        message = heading + "\n" + message
        if self.teams_enabled.get() and entry.get("notify_teams", True) and self.teams_webhook:
            self.teams_sender.submit(self.teams_webhook, title, message)
        if self.notify.get() and entry.get("notify_windows", True):
            try:
                from plyer import notification
                self.root.bell()
                notification.notify(title=title, message=message, app_name="Neto Incident Monitor", timeout=10)
            except Exception:
                LOG.exception("Błąd powiadomienia filtra")
                self.status.set("Incydenty zapisano. Nie udało się wysłać powiadomienia Windows.")

    def refresh_filters(self):
        self.disabled_filter_urls = frozenset(entry["url"] for entry in self.filters if not entry.get("enabled", True))
        self.filter_table.enabled_rows = {str(i): entry.get("enabled", True) for i, entry in enumerate(self.filters)}
        self.filter_table.on_toggle = self.toggle_filter
        self.filter_table.on_settings = self.configure_filter_notifications
        self.filter_table.on_select = self.filter_selected
        selected = self.filter_table.selection()
        self.filter_table.delete(*self.filter_table.get_children())
        for index, entry in enumerate(self.filters):
            self.filter_table.insert("", "end", iid=str(index), values=(entry["name"], urlparse(entry["url"]).hostname))
        self.filter_count.set(str(len(self.filters)))
        self.filter_table.configure(height=max(1, min(4, len(self.filters))))
        if len(self.filters) > 4:
            self.filter_scroll.grid()
        else:
            self.filter_scroll.grid_remove()
        if self.filters:
            self.filter_table.selection_set(selected[0] if selected and selected[0] in self.filter_table.get_children() else "0")
        else:
            self.filter_selected()

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
                if any(normalize_url(other["url"]) == urls[0] for i, other in enumerate(self.filters) if i != index):
                    raise ValueError("Ten adres jest już zapisany jako inny filtr.")
                updated = {**entry, "name": name.get().strip(), "url": urls[0], "enabled": entry.get("enabled", True)}
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
        self.phase.set(f"{name} • {phase}" if name else f"• {phase}")

    def set_phase(self, phase):
        colors = {"Monitoring aktywny": "#7ac99e", "Oczekiwanie na logowanie": "#e9bc70",
                  "Błąd odczytu": "#ff7a85", "Błąd uruchomienia": "#ff7a85"}
        self.monitoring_phase = phase
        self.update_phase_text()
        self.phase_label.configure(foreground=colors.get(phase, MUTED))
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
                self.tray.update(self.history.unread(), getattr(self, "monitoring_phase", "Gotowy do uruchomienia"))
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
            item = self.table.insert("", "end", values=(
                time.strftime("%d.%m.%Y %H:%M", time.localtime(record["detected"])), label,
                *incident_values(incident)),
                tags=("unread",) if not record["read"] else ("alternate",) if len(self.table.get_children()) % 2 else ())
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
        for number, entry in sorted(combined.items()):
            incident = entry["incident"]
            unread = number in records and not records[number]["read"]
            label = "Nieprzeczytany" if unread else "Przeczytany" if number in records else "—"
            item = self.current_table.insert("", "end", values=(label,
                *incident_values(incident)),
                tags=("unread",) if unread else ("alternate",) if len(self.current_table.get_children()) % 2 else ())
            self.items[(self.current_table, item)] = incident["url"]
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
        if not numbers:
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
            save_json(CONFIG, settings)
        except (OSError, ValueError):
            self.status.set("Nie udało się zapisać ustawienia minimalizacji przeglądarki.")

    def change_teams(self, *_):
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
        except (OSError, ValueError):
            self.status.set("Nie udało się zapisać konfiguracji Teams.")

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
        ttk.Label(content, text="Adres webhooka Power Automate").pack(anchor="w")
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
                self.persist_teams()
                dialog.destroy()

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
            instruction = (ROOT / "docs" / "INSTRUKCJA_TEAMS.md").read_text(encoding="utf-8")
        except OSError:
            messagebox.showerror("Instrukcja Teams", "Nie znaleziono instrukcji w tej wersji aplikacji.", parent=parent)
            return
        window = tk.Toplevel(parent)
        window.configure(background=BG)
        window.title("Instrukcja konfiguracji Teams")
        window.geometry("850x650")
        window.minsize(550, 400)
        window.transient(parent)
        window.grab_set()
        frame = ttk.Frame(window, padding=16)
        frame.pack(fill="both", expand=True)
        text = tk.Text(frame, wrap="word", font=("Segoe UI", 10), background=SURFACE,
                       foreground=TEXT, insertbackground=TEXT, selectbackground="#513039", selectforeground=TEXT, relief="flat", padx=18, pady=16)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        text.pack(fill="both", expand=True)
        text.tag_configure("title", font=("Segoe UI", 16, "bold"), spacing1=12, spacing3=10)
        text.tag_configure("heading", font=("Segoe UI", 12, "bold"), spacing1=16, spacing3=8)
        text.tag_configure("code", font=("Consolas", 10), background="#392930")
        code = False
        for line in instruction.splitlines():
            if line.startswith("```"):
                code = not code
                continue
            tag = "code" if code else "title" if line.startswith("# ") else "heading" if line.startswith("## ") else ""
            if tag in ("title", "heading"):
                line = line.lstrip("# ")
            if not code:
                line = line.replace("**", "").replace("`", "")
                line = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", line)
            text.insert("end", line + "\n", tag)
        text.configure(state="disabled")
        def close():
            window.destroy()
            if parent.winfo_exists():
                parent.grab_set()
        window.protocol("WM_DELETE_WINDOW", close)
        ttk.Button(window, text="Zamknij", command=close).pack(anchor="e", padx=16, pady=(0, 12))

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
            urls = validate_urls("\n".join(entry["url"] for entry in self.filters))
            interval = int(self.interval.get())
            if interval < 15:
                raise ValueError("Minimalny odstęp wynosi 15 sekund.")
            filters = load_filters({"filters": self.filters})
            settings = {"urls": urls, "filters": filters,
                        "interval": interval, "notify": self.notify.get(), "auto_login": self.auto_login.get(),
                        "minimize_to_tray": self.minimize_to_tray.get(),
                        "minimize_browser": self.minimize_browser.get()}
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
        self.set_phase("Uruchamianie przeglądarki")
        self.clear_table(self.current_table)
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.interval_entry.configure(state="disabled")
        self.notify_check.configure(state="disabled")
        for button in self.filter_buttons:
            button.configure(state="disabled")
        self.worker = threading.Thread(target=self.monitor, args=(settings,), daemon=True)
        self.worker.start()

    def monitor(self, settings):
        health = Health()
        try:
            from playwright.sync_api import sync_playwright
            from neto_incident_monitor.filter_state import FilterState
            membership = FilterState(STATE, normalize_url)
            with sync_playwright() as playwright:
                context = playwright.chromium.launch_persistent_context(str(DATA / "browser-profile"), headless=False, no_viewport=True)
                try:
                    page = context.pages[0] if context.pages else context.new_page()
                    navigate(page, settings["urls"][0])
                    page.bring_to_front()
                    self.events.put(("phase", "Oczekiwanie na logowanie"))
                    self.events.put(("status", "Zaloguj się w przeglądarce. Monitoring rozpocznie się automatycznie po załadowaniu listy."))
                    if not wait_for_login(page, settings["urls"][0], self.stop, settings.get("auto_login", False), settings.get("minimize_browser", False)):
                        return
                    while not self.stop.is_set():
                        self.events.put(("checking", None))
                        cycle_error = False
                        for filter_index, url in enumerate(settings["urls"], 1):
                            if url in self.disabled_filter_urls:
                                continue
                            filter_name = settings["filters"][filter_index - 1]["name"]
                            if self.stop.is_set():
                                break
                            try:
                                # Filters are read sequentially, so one tab is
                                # sufficient. Opening additional tabs restores
                                # a minimized Chromium window on Windows.
                                if page.is_closed():
                                    page = context.new_page()
                                    if settings.get("minimize_browser", False):
                                        minimize_chromium(page)
                                current = page
                                available = set()
                                incidents, page_count = read_all(
                                    current, url, self.stop, lambda p: collect(p, available), empty_list, authentication_page, navigate,
                                    lambda index, count: self.events.put(("status",
                                        f"{filter_name}: strona {index}, odczytano {count} incydentów…"
                                        if index else f"{filter_name}: powrót do pierwszej strony…")))
                                if url in self.disabled_filter_urls:
                                    continue
                                for incident in incidents.values():
                                    incident["_available_columns"] = sorted(available)
                                self.events.put(("columns", (filter_index, available)))
                                options = next((entry for entry in self.filters if entry["url"] == url), {})
                                arrivals = membership.arrivals(url, incidents)
                                new = membership.arrivals(url, incidents, options.get("first_only", False))
                                for number in sorted(arrivals):
                                    self.history.add(incidents[number], filter_name, url, reappeared=True)
                                membership.commit(url, incidents)
                                health.success(url)
                                self.events.put(("snapshot", (filter_index, incidents)))
                                if new:
                                    self.events.put(("filter_notification", (url, [incidents[n] for n in sorted(new)])))
                                self.events.put(("read", (time.time(), filter_name)))
                                self.events.put(("status", f"{filter_name}: {len(incidents)} incydentów na {page_count} stronach; nowych w tym odczycie: {len(new)}."))
                            except Cancelled:
                                return
                            except AuthenticationRequired:
                                self.events.put(("phase", "Oczekiwanie na logowanie"))
                                message = "Sesja ServiceNow wygasła. Zaloguj się w przeglądarce — monitoring wznowi się automatycznie."
                                self.events.put(("status", message))
                                if health.authentication():
                                    self.events.put(("session_expired", message))
                                current.bring_to_front()
                                if not wait_for_login(current, url, self.stop, settings.get("auto_login", False), settings.get("minimize_browser", False)):
                                    return
                                health.resumed()
                                self.schedule.request()
                                break
                            except Exception as exc:
                                LOG.exception("Błąd odczytu filtra %s", filter_name)
                                cycle_error = True
                                self.events.put(("phase", "Błąd odczytu"))
                                self.events.put(("status", f"Błąd odczytu: {exc}. Próba ponownie w kolejnym cyklu."))
                                if health.failure(url):
                                    self.events.put(("interruption", f"Lista „{filter_name}”: trzy kolejne odczyty nie powiodły się. Otwórz aplikację i sprawdź sesję lub połączenie. Automatyczne próby będą kontynuowane."))
                        self.events.put(("waiting", (time.monotonic() + settings["interval"], cycle_error)))
                        if self.schedule.wait(settings["interval"], self.stop):
                            break
                finally:
                    context.close()
        except Exception as exc:
            LOG.exception("Nie udało się uruchomić monitoringu")
            self.events.put(("phase", "Błąd uruchomienia"))
            self.events.put(("status", f"Nie udało się uruchomić monitoringu: {exc}"))
            if not self.stop.is_set():
                self.events.put(("interruption", "Monitoring zatrzymał się z powodu błędu przeglądarki lub aplikacji. Otwórz aplikację, aby zobaczyć szczegóły i uruchomić go ponownie."))
        finally:
            self.events.put(("finished", None))

    def drain(self):
        if self.instance and self.instance.poll():
            self.show_window()
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "status":
                    self.status.set(value)
                elif kind == "tray_ready":
                    self.tray_ready = True
                    self.update_tray()
                elif kind == "tray_failed":
                    self.tray_ready = False
                    self.show_window()
                    self.status.set("Zasobnik niedostępny — aplikacja pozostaje w oknie.")
                elif kind == "show":
                    self.show_window()
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
                elif kind == "mark_all":
                    self.mark_all()
                elif kind == "stop_monitor":
                    self.stop.set()
                elif kind == "quit":
                    self.quit_app()
                    return
                elif kind == "phase":
                    self.next_check = None
                    self.set_phase(value)
                    if value in ("Oczekiwanie na logowanie", "Błąd uruchomienia") and self.root.state() == "withdrawn":
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
                    if not self.filters[index - 1].get("enabled", True):
                        continue
                    if available:
                        self.column_availability[index] = set(available)
                    self.apply_visible_columns()
                elif kind == "snapshot":
                    filter_index, incidents = value
                    if not self.filters[filter_index - 1].get("enabled", True):
                        continue
                    self.snapshots[filter_index] = incidents
                    self.refresh_current()
                    self.refresh_history()
                    self.apply_visible_columns()
                    self.update_counts()
                elif kind == "finished":
                    self.next_check = None
                    if self.stop.is_set():
                        self.set_phase("Monitoring zatrzymany")
                        self.status.set("Odczyty zatrzymane. Lista zachowuje ostatni udany wynik.")
                    self.start_button.configure(state="normal")
                    self.stop_button.configure(state="disabled")
                    self.check_button.configure(state="disabled")
                    self.interval_entry.configure(state="normal")
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
        if self.next_check is None:
            self.countdown.set("Następne sprawdzenie: —")
        else:
            remaining = max(0, int(self.next_check - time.monotonic() + 0.999))
            self.countdown.set(f"Następne sprawdzenie: za {remaining} s")
        if not self.quitting:
            self.root.after(200, self.drain)

    def open_incident(self, event):
        if event.widget.identify_region(event.x, event.y) == "heading":
            return self.column_drag_start(event)
        item = event.widget.identify_row(event.y)
        if item:
            key = (event.widget, item)
            url = self.items[key]
            if urlparse(url).scheme == "https" and webbrowser.open(url):
                self.mark_read([self.row_numbers[key]])

    def incident_context_menu(self, event):
        table = event.widget
        item = table.identify_row(event.y)
        key = (table, item)
        if not item or key not in self.row_numbers:
            return
        table.selection_set(item)
        table.focus(item)
        number, url = self.row_numbers[key], self.items[key]
        menu = getattr(self, "incident_menu", None)
        if menu is not None:
            menu.destroy()
        menu = IncidentMenu(self.root)
        self.incident_menu = menu
        def open_selected():
            if urlparse(url).scheme == "https" and webbrowser.open(url):
                self.mark_read([number])
        def copy(value):
            self.root.clipboard_clear()
            self.root.clipboard_append(value)
        menu.add_command(label="Otwórz incydent", command=open_selected)
        menu.add_separator()
        menu.add_command(label="Kopiuj numer", command=lambda: copy(number))
        menu.add_command(label="Kopiuj link", command=lambda: copy(url))
        menu.add_separator()
        menu.add_command(label="Oznacz jako przeczytany", command=lambda: self.mark_read([number]))
        menu.show(event.x_root, event.y_root)
        return "break"

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
