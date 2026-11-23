"""Local ServiceNow monitor with a shared browser session."""
from neto_incident_monitor import config_io
from neto_incident_monitor.dashboard_ui import handle_read_event as handle_dashboard_read_event
from neto_incident_monitor.threatened_ui import handle_read_event as handle_threatened_read_event
from neto_incident_monitor.dynamic_columns import DynamicColumns, load_profiles
from neto_incident_monitor.filter_definition import ready_definition
from neto_incident_monitor.filter_metadata import discover_query, saved_query
from neto_incident_monitor.analytics_api import READ_MESSAGES
from neto_incident_monitor.theme import BG, SURFACE, TEXT, MUTED, ACCENT
from neto_incident_monitor.columns import FIELDS, DEFAULT, age_minutes
from neto_incident_monitor.widgets import IncidentMenu, PriorityDots, update_grid_scrollbar
from neto_incident_monitor.login_diagnostics import diagnostic_read
from contextlib import nullcontext
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
from neto_incident_monitor.window_style import current_grab_path
from urllib.parse import urlparse, unquote
from neto_incident_monitor.service_now_urls import effective_list_url, is_short_url
from neto_incident_monitor.history import History
from neto_incident_monitor.alert_retention import AlertRetention
from neto_incident_monitor.monitoring import Schedule, ReadPart
from neto_incident_monitor.read_errors import (
    AuthenticationRequired, BrowserClosedError, Cancelled,
)
from playwright._impl._errors import TargetClosedError

from neto_incident_monitor.runtime_paths import ROOT, DATA
STATE = DATA / "seen.json"
from neto_incident_monitor.login_diagnostics import error_facts
LOG = logging.getLogger("servicenow")


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


def incident_values(incident):
    values = []
    for key, _, _ in FIELDS:
        if key in ("read", "time"):
            continue
        value = age_minutes(incident.get("_created_utc") or incident.get("created"), incident.get("number")) if key == "age_minutes" else incident.get(key) or "—"
        if key == "priority" and str(value).strip()[:1] in PriorityDots.COLORS:
            value = "\u2003\u2002" + str(value).strip()
        values.append(value)
    return tuple(values)


from neto_incident_monitor.table_loading import TableLoading


class App(DynamicColumns, TableLoading):
    def __init__(self, root, history_path=None, enable_tray=True, instance=None, apply_startup=True,
                 windows_startup="disabled"):
        self.root = root
        self.events = queue.Queue()
        self.filter_revisions = {}
        self.filter_config_lock = threading.RLock()
        self.dashboard_request_stop = None
        self.stop = threading.Event()
        self.browser_window = None
        self.items = {}
        self.snapshots = {}
        self.filter_read_status = {}
        self.next_check = None
        self.check_deadlines = {}
        self.windows_startup = windows_startup
        self.history = History(history_path or DATA / "history.json")
        self.alert_writer = ThreadPoolExecutor(max_workers=1, thread_name_prefix="alerts")
        self.history_writer = ThreadPoolExecutor(max_workers=1, thread_name_prefix="history")
        self.alert_retention = AlertRetention(self.history.store, self.history_writer, self.stop)
        self.row_numbers = {}
        self._column_fit_jobs = {}
        self.tray = None
        self.tray_ready = False
        self.quitting = False
        self.instance = instance
        self.schedule = Schedule()
        self.cycle_active = False
        self.session_state = 'starting'
        self.session_part = None
        self.default_layout_refresh = (None, '', ())
        self.dashboard_scope_refresh = (None, '')
        self.session_work_detail = ''
        self.connection_dialog = None
        self.password_save_dialog = None
        self.syncing_auto_login = False
        self.apply_startup = apply_startup
        settings = config_io.initialize_default_filters(config_io.read_json(config_io.CONFIG, {}))
        from neto_incident_monitor.browser_policy import BrowserOptions
        browser_settings = dict(settings, auto_login=settings.get('auto_login', True),
                                hide_browser=True, minimize_browser=False)
        self.browser_options = BrowserOptions(browser_settings)
        self.browser_runtime = None
        from neto_incident_monitor.shared_session import SharedSession
        self.session = SharedSession(self, DATA / 'browser-profile')
        self.worker = self.session.thread
        self.monitor_generation = object()
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
        self.filters = config_io.load_filters(settings, tolerate_invalid=True)
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
        for setting in (self.google_chat_enabled, self.teams_enabled):
            setting.trace_add('write', self.refresh_filter_notifications)
        self.saved_notify_windows = self.notify.get()
        self.notify.trace_add('write', self.save_notify_windows)
        self.teams_enabled.trace_add("write", self.change_teams)
        from neto_incident_monitor.google_chat_ui import changed as google_chat_changed
        self.google_chat_enabled.trace_add("write", lambda *_: google_chat_changed(self))
        self.saved_notify_threatened = self.notify_threatened.get()
        self.notify_threatened.trace_add("write", self.save_notify_threatened)
        self.auto_login.trace_add("write", self.save_auto_login)
        self.dashboard_auto_refresh.trace_add('write', self.save_dashboard_auto_refresh)
        self.saved_minimize = self.minimize_to_tray.get()
        self.minimize_to_tray.trace_add("write", self.save_minimize_preference)
        self.saving_startup = False
        for key in ("start_monitoring", "start_with_windows", "start_minimized"):
            getattr(self, key).trace_add("write", lambda *_, key=key: self.save_startup_preference(key))
        self.refresh_history()
        self.update_counts()
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<Unmap>", self.on_unmap, add="+")
        from neto_incident_monitor.window_style import MainWindowPresentation
        self.main_window = MainWindowPresentation(root)
        self.main_window_observation = None
        self.main_window_last_state = None
        for event in ('<Map>', '<Unmap>', '<FocusIn>', '<FocusOut>'):
            root.bind(event, self.main_window_changed, add='+')
        root.bind('<Control-Shift-F12>', lambda event: self.threatened_view.simulate_read(), add='+')
        root.bind('<Control-Shift-KeyRelease-F11>', self.toggle_debug_browser, add='+')
        self.window_save_timer = None
        self.window_layout = dict(settings.get("window_layout", {}))
        self.saved_window_layout = dict(self.window_layout)
        self.window_restoring = True
        root.bind("<Configure>", self.window_changed, add="+")
        root.after(200, self.drain)
        if enable_tray:
            try:
                from neto_incident_monitor.tray import Tray
                self.tray = Tray(self.events, login_waiting=lambda: self.session.manual_login)
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
            settings = config_io.read_json(config_io.CONFIG, {})
            settings[key] = enabled
            config_io.save_json(config_io.CONFIG, settings)
        except Exception as error:
            self.saving_startup = True
            variable.set(not enabled)
            self.saving_startup = False
            messagebox.showerror("Uruchamianie aplikacji", f"Nie udało się zapisać ustawienia: {error}", parent=self.settings_window)

    def windows_startup_description(self):
        if self.windows_startup in ("stale", "unknown"):
            return "Nie udało się potwierdzić poprawnego wpisu autostartu."
        return "Uruchamiaj aplikację po zalogowaniu do Windows."

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
        vertical.grid_remove()
        horizontal.grid_remove()
        table.configure(yscrollcommand=lambda first, last: update_grid_scrollbar(vertical, first, last),
                        xscrollcommand=lambda first, last: update_grid_scrollbar(horizontal, first, last))
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
        region = table.identify_region(event.x, event.y)
        if region == "separator":
            self.cancel_column_fit(table)
            table.column_resizing = True
            return
        if region != "heading":
            return
        self.cancel_column_fit(table)
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
        self.update_filter_info_button()
        self.update_refresh_controls()

    def update_filter_info_button(self):
        update = getattr(self, 'update_open_filter_query', None)
        if update is not None:
            update()

    def filter_info_definition(self, entry):
        if not entry.get('url') or entry.get('url_invalid'):
            return None
        account = self.session.layout_account
        definition = saved_query(entry, account.key if account else None, for_display=True)
        if definition is None and ready_definition(entry) and not is_short_url(entry['url']):
            return entry['list_definition']
        return definition

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
        if getattr(self, 'favorites_import', None) is not None:
            return
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
                settings = load_config(config_io.CONFIG, {}, migrate_plaintext=False)
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
        settings = load_config(config_io.CONFIG, {}, migrate_plaintext=False)
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
        elif url != THREATENED_URL:
            filter_revision = settings.get('filter_notification_revisions', {}).get(url)
            if filter_revision:
                revision += ':' + filter_revision
        routes = {}
        for channel in ("teams", "google_chat"):
            key = channel + "_webhook"
            custom = entry.get(key, "")
            endpoint = "" if isinstance(custom, UnavailableSecret) else custom or settings.get(key, "")
            if endpoint and not isinstance(endpoint, UnavailableSecret) and settings.get(channel + "_enabled") and entry.get("notify_" + channel, True):
                routes[channel] = (revision, endpoint)
        if settings.get("notify") and entry.get("notify_windows", True):
            windows_revision = settings.get('windows_notification_revision')
            routes['windows'] = (f'{revision}:windows:{windows_revision}' if windows_revision else revision, '')
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
                       message="\n".join(body),
                       links={item["number"]: item["url"] for item in incidents},
                       request_id=request_id)

    def submit_alert_delivery(self, recover=False):
        future = self.alert_writer.submit(self.deliver_alerts, recover)
        def completed(result):
            if not result.cancelled() and result.exception() is not None:
                App.alert_delivery_error(self, result.exception(), 'worker')
        future.add_done_callback(completed)
        return future

    @staticmethod
    def alert_delivery_error(app, error, stage, diagnostics=None):
        from neto_incident_monitor.login_diagnostics import LoginDiagnostics
        diagnostics = diagnostics or LoginDiagnostics(source='monitor')
        diagnostics.record('alert_delivery', delivery_stage=stage, delivery_outcome='error', **error_facts(error))
        app.events.put(('status', 'Nie udało się obsłużyć kolejki powiadomień. '
                       'Zachowano zadania; wynik rozpoczętej wysyłki może być niepewny.'))

    def deliver_alerts(self, recover=False):
        import sqlite3
        from neto_incident_monitor.login_diagnostics import LoginDiagnostics
        diagnostics = LoginDiagnostics(source='monitor')
        started = time.monotonic()
        outcome = 'cancelled'
        diagnostics.record('alert_delivery', delivery_stage='read', delivery_outcome='started')
        try:
            for attempt in range(1, 4):
                if self.stop.is_set():
                    return
                try:
                    jobs = self.history.pending_alerts(recover=recover)
                    break
                except (sqlite3.Error, OSError) as error:
                    diagnostics.record('alert_delivery', delivery_stage='read', attempt=attempt,
                                       delivery_outcome='retry' if attempt < 3 else 'error', **error_facts(error))
                    if attempt == 3:
                        raise
                    if self.stop.wait((1, 5)[attempt - 1]):
                        return
            state = {'stage': 'route'}
            try:
                App._deliver_alert_jobs(self, jobs, diagnostics, state)
            except Exception as error:
                outcome = 'error'
                App.alert_delivery_error(self, error, state['stage'], diagnostics)
                return
            outcome = 'cancelled' if self.stop.is_set() else state.get('outcome', 'complete')
        except Exception as error:
            outcome = 'error'
            App.alert_delivery_error(self, error, 'read', diagnostics)
        finally:
            diagnostics.record('alert_delivery', delivery_stage='worker', delivery_outcome=outcome,
                               duration_ms=round((time.monotonic() - started) * 1000))

    def _deliver_alert_jobs(self, jobs, diagnostics, state_context):
        from neto_incident_monitor import teams_notifications, google_chat_notifications
        from neto_incident_monitor.threatened import THREATENED_URL
        for key, job in jobs:
            if self.stop.is_set():
                return
            state_context['stage'] = 'route'
            channel = job["channel"]
            with getattr(self, 'filter_config_lock', nullcontext()):
                route = self.alert_routes(job['url']).get(channel)
                state_context['stage'] = 'claim'
                valid = bool(route and route[0] == job['target'])
                claimed = self.history.transition_alert(key, 'pending', 'sending' if valid else 'cancelled')
            if not valid:
                diagnostics.record('alert_delivery', delivery_stage='claim', delivery_outcome='cancelled',
                                   action_id=key, channel=channel)
                App.log_threatened_delivery(key, job, "cancelled", 0)
                continue
            if not claimed:
                continue
            state = "uncertain"
            accepted = 0
            diagnostics.record('alert_delivery', delivery_stage='send', delivery_outcome='started',
                               action_id=key, channel=channel)
            try:
                title, message, links = job['title'], job['message'], job['links']
                if job['url'] == THREATENED_URL:
                    # Older pending jobs stored the dashboard URL on the final line.
                    message = message.removesuffix('\n' + THREATENED_URL)
                if channel == "windows":
                    from neto_incident_monitor import windows_notifications
                    windows_notifications.notify(title, message, diagnostics=diagnostics, action_id=key)
                    accepted = 1
                else:
                    if channel == "teams":
                        parts = teams_notifications.message_chunks(title, message, links)
                        send = lambda part: teams_notifications.send(route[1], title, part, links)
                    else:
                        parts = google_chat_notifications.payloads(title, message, links)
                        send = lambda part: google_chat_notifications.send(route[1], part)
                    for part in parts:
                        if self.stop.is_set() or self.alert_routes(job["url"]).get(channel) != route:
                            raise RuntimeError("Alert delivery interrupted")
                        send(part)
                        accepted += 1
                        if channel == "google_chat":
                            self.stop.wait(1.1)
                state = "accepted"
            except Exception as error:
                state_context['outcome'] = 'uncertain'
                diagnostics.record('alert_delivery', delivery_stage='send', delivery_outcome='uncertain',
                                   action_id=key, channel=channel, accepted_parts=accepted, **error_facts(error))
                self.events.put(("status", f"Wynik wysyłki {channel} jest niepewny. Potwierdzone części: {accepted}."))
            finally:
                state_context['stage'] = 'finish'
                self.history.transition_alert(key, "sending", state)
                diagnostics.record('alert_delivery', delivery_stage='finish', delivery_outcome=state,
                                   action_id=key, channel=channel, accepted_parts=accepted)
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
                from neto_incident_monitor import windows_notifications
                self.root.bell()
                windows_notifications.notify(title, message)
            except Exception:
                LOG.exception("Błąd powiadomienia filtra")
                self.status.set("Incydenty zapisano. Nie udało się wysłać powiadomienia Windows.")

    def refresh_filter_notifications(self, *_, redraw=True):
        channels = tuple(channel for channel, setting in (
            ('windows', self.notify), ('google_chat', self.google_chat_enabled), ('teams', self.teams_enabled)
        ) if setting.get())
        self.filter_table.notification_channels = channels
        self.filter_table.notification_rows = {
            str(index): tuple(bool(entry.get(f'notify_{channel}', True)) for channel in channels)
            for index, entry in enumerate(self.filters)
        }
        if redraw:
            self.filter_table.redraw()

    def refresh_filters(self, selected_url=None):
        self.disabled_filter_urls = frozenset(entry["url"] for entry in self.filters if not entry.get("enabled", True))
        self.update_session_filters()
        self.filter_table.enabled_rows = {str(i): entry.get("enabled", True) for i, entry in enumerate(self.filters)}
        self.filter_table.on_toggle = self.toggle_filter
        self.filter_table.on_select = self.filter_selected
        self.filter_table.on_reorder = self.reorder_filter
        self.filter_table.bind('<Double-1>', self.open_filter)
        selected = self.filter_table.selection()
        if selected_url is not None:
            index = self.event_filter_index(selected_url)
            selected = (str(index - 1),) if index is not None else ()
        self.refresh_filter_notifications(redraw=False)
        self.filter_table.replace_rows((str(index), entry["name"])
                                       for index, entry in enumerate(self.filters))
        self.filter_count.set(str(len(self.filters)))
        self.filter_table.configure(height=max(1, min(4, len(self.filters))))
        if self.filters:
            self.filter_table.selection_set(selected[0] if selected and selected[0] in self.filter_table.get_children() else "0")
        else:
            self.filter_selected()

    def reorder_filter(self, item, slot):
        if getattr(self, 'favorites_import', None) is not None:
            return
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
        self.remap_filter_view(old)
        self.refresh_filters(selected_url)

    def remap_filter_view(self, previous):
        positions = {entry['url']: index for index, entry in enumerate(self.filters, 1)}
        previous_urls = {index: entry['url'] for index, entry in enumerate(previous, 1)}
        if hasattr(self, 'filter_read_status'):
            self.filter_read_status = {url: result for url, result in self.filter_read_status.items() if url in positions}
        for field in ('snapshots', 'column_availability'):
            data = getattr(self, field)
            setattr(self, field, {positions[previous_urls[index]]: value for index, value in data.items()
                                  if previous_urls.get(index) in positions})

    def event_filter_index(self, identity):
        if isinstance(identity, int):
            return identity
        return next((i for i, entry in enumerate(self.filters, 1) if entry["url"] == identity), None)

    def add_default_filters(self, event=None):
        if getattr(self, 'favorites_import', None) is not None:
            return
        if self.quitting:
            return 'break'
        if self.monitoring_is_active():
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
        additions = [entry for entry in config_io.load_filters({'filters': default_filters()})
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

    def persist_filters(self, proposed=None):
        settings = config_io.read_json(config_io.CONFIG, {})
        previous = settings.get('filters', []) if proposed is None else self.filters
        filters = self.filters if proposed is None else proposed
        old_enabled = {
            item["url"]: item.get("enabled", True)
            for item in previous if isinstance(item, dict) and "url" in item
        }
        settings["filters"] = filters
        if isinstance(getattr(self, "notification_library", None), dict):
            settings["notification_library"] = self.notification_library
        settings["urls"] = [entry["url"] for entry in filters]
        config_io.save_json(config_io.CONFIG, settings)
        current_enabled = {
            item["url"]: item.get("enabled", True)
            for item in filters
        }
        changed = {url: object() for url in old_enabled.keys() | current_enabled.keys()
                   if url not in old_enabled or url not in current_enabled or old_enabled[url] != current_enabled[url]}
        if changed:
            self.filter_revisions = {**getattr(self, "filter_revisions", {}), **changed}
        if proposed is not None:
            self.filters = filters

    def save_filter_change(self, proposed, action, selected_url):
        from neto_incident_monitor.login_diagnostics import LoginDiagnostics

        diagnostics = LoginDiagnostics(source='monitor')
        started = time.monotonic()
        diagnostics.record('filter_config_change', filter_change=action, outcome='started')
        previous = self.filters
        try:
            with self.filter_config_lock:
                self.persist_filters(proposed)
                self.disabled_filter_urls = frozenset(entry['url'] for entry in proposed if not entry.get('enabled', True))
                self.update_session_filters()
        except (OSError, ValueError) as error:
            diagnostics.record('filter_config_change', filter_change=action, outcome='error',
                               duration_ms=round((time.monotonic() - started) * 1000), **error_facts(error))
            raise
        self.remap_filter_view(previous)
        self.refresh_filters(selected_url)
        self.schedule.request()
        diagnostics.record('filter_config_change', filter_change=action, outcome='returned', item_count=len(proposed),
                           duration_ms=round((time.monotonic() - started) * 1000))

    def save_sidebar_width(self, width):
        try:
            settings = config_io.read_json(config_io.CONFIG, {})
            settings["sidebar_width"] = width
            config_io.save_json(config_io.CONFIG, settings)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Układ okna", f"Nie udało się zapisać szerokości panelu: {exc}", parent=self.root)

    def handle_filter_limit(self, url, count):
        from neto_incident_monitor.filter_api import MAX_FILTER_RECORDS

        index = self.event_filter_index(url)
        if index is None or self.quitting:
            return
        entry = self.filters[index - 1]
        name = entry['name']
        total = f'{count:,}'.replace(',', ' ')
        limit = f'{MAX_FILTER_RECORDS:,}'.replace(',', ' ')
        detail = f'Lista zawiera {total} zgłoszeń. Zawęź warunki w ServiceNow, aby filtr zwracał maksymalnie {limit}.'
        enabled = entry.get('enabled', True)
        save_failed = False
        if enabled:
            proposed = list(self.filters)
            proposed[index - 1] = dict(entry, enabled=False)
            try:
                self.save_filter_change(proposed, 'disable_limit', self.selected_filter_url())
            except (OSError, ValueError):
                save_failed = True
        title = ('Nie udało się wyłączyć filtra' if save_failed else
                 'Filtr wyłączony z harmonogramu' if enabled else 'Za dużo zgłoszeń w filtrze')
        self.update_filter_read_result(url, error=detail, title=title, action='edit', warning=not save_failed)
        if enabled:
            minimized = self.root.state() in ('withdrawn', 'iconic')
            visible = not minimized and self.active_view == 'incidents' and self.selected_filter_url() == url
            if minimized:
                self.show_window()
            if save_failed:
                messagebox.showerror('Filtr ServiceNow',
                    f'Nie udało się zapisać wyłączenia filtra „{name}”.', parent=self.root)
            elif not visible:
                messagebox.showinfo('Filtr ServiceNow',
                    f'Filtr „{name}” został wyłączony, ponieważ zawiera ponad {MAX_FILTER_RECORDS} elementów.',
                    parent=self.root)

    def toggle_filter(self, item):
        if getattr(self, 'favorites_import', None) is not None:
            return
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
        self.disabled_filter_urls = frozenset(f["url"] for f in self.filters if not f.get("enabled", True))
        self.update_session_filters()
        self.filter_table.enabled_rows[item] = entry["enabled"]
        self.snapshots.pop(index + 1, None)
        self.filter_read_status.pop(entry['url'], None)
        self.column_availability.pop(index + 1, None)
        self.filter_table.selection_set(item)
        self.schedule.request()

    def edit_filter(self, edit=False):
        if self.quitting or getattr(self, 'favorites_import', None) is not None:
            return
        from neto_incident_monitor.widgets import RoundedButton
        selected = self.filter_table.selection()
        if edit and not selected:
            messagebox.showinfo("Filtry", "Wybierz filtr do edycji.")
            return
        entry = self.filters[int(selected[0])] if edit else {"name": "", "url": ""}
        original_url = entry['url']
        original_revision = self.filter_revisions.get(original_url)
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
                if self.quitting or getattr(self, 'favorites_import', None) is not None:
                    return
                urls = validate_urls(address.get("1.0", "end"))
                if len(urls) != 1 or not name.get().strip():
                    raise ValueError("Podaj nazwę i jeden adres filtra.")
                position = self.event_filter_index(original_url) if edit else None
                if edit and (position is None or original_revision is not self.filter_revisions.get(original_url)):
                    raise ValueError('Filtr zmienił się w trakcie edycji. Otwórz ustawienia filtra ponownie.')
                if any(other['url'] == urls[0] and index != position
                       for index, other in enumerate(self.filters, 1)):
                    raise ValueError("Ten adres jest już zapisany jako inny filtr.")
                current = self.filters[position - 1] if edit else entry
                updated = {**current, "name": name.get().strip(), "url": urls[0], "enabled": current.get("enabled", True)}
                updated.pop('url_invalid', None)
                if original_url != urls[0]:
                    from uuid import uuid4
                    updated.pop('resolved_list_url', None)
                    updated.pop('list_definition', None)
                    updated['filter_instance'] = uuid4().hex
                proposed = list(self.filters)
                if edit:
                    proposed[position - 1] = updated
                else:
                    proposed.append(updated)
                action = 'add' if not edit else 'rename' if original_url == urls[0] else 'replace'
                self.save_filter_change(proposed, action, updated['url'])
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
        if self.quitting or getattr(self, 'favorites_import', None) is not None:
            return
        selected = self.filter_table.selection()
        if selected:
            index = int(selected[0])
            proposed = list(self.filters)
            proposed.pop(index)
            selected_url = proposed[min(index, len(proposed) - 1)]['url'] if proposed else ''
            try:
                self.save_filter_change(proposed, 'remove', selected_url)
            except (OSError, ValueError) as exc:
                messagebox.showerror("Filtry", str(exc))

    def update_phase_text(self):
        phase = getattr(self, "monitoring_phase", "Gotowy do uruchomienia")
        index = self.selected_filter_index()
        name = self.filters[index - 1]["name"] if index else ""
        self.phase.set(phase)
        self.selected_filter_name.set(name)
        self.update_filter_read_bar()

    def update_filter_read_bar(self):
        if hasattr(self, 'filter_read_bar'):
            from neto_incident_monitor.read_status import ReadStatus
            self.filter_read_bar.show(self.filter_read_status.get(self.selected_filter_url(), ReadStatus()))

    def update_filter_read_result(self, url, *, accepted=None, error=None, title='', action='retry', warning=False):
        from neto_incident_monitor.read_status import ReadStatus
        previous = self.filter_read_status.get(url, ReadStatus())
        detail = error or ''
        if not accepted and previous.read_at is not None:
            detail = f'{detail} Zachowano wynik poprzedniego odczytu.'.strip()
        self.filter_read_status[url] = (previous.accepted(*accepted) if accepted else
                                        previous.failed(detail, title=title, action=action, warning=warning))
        if url == self.selected_filter_url():
            self.update_filter_read_bar()

    def set_phase(self, phase):
        self.monitoring_phase = phase
        self.update_phase_text()
        if self.quitting:
            self.activity_pill.set_status('Zamykanie aplikacji', 'waiting')
        else:
            self.activity_pill.set_status('Monitoring aktywny' if self.cycle_active else 'Monitoring zatrzymany',
                                          'success' if self.cycle_active else 'neutral')
        self.update_tray()

    def update_session_work(self, pending):
        if not hasattr(self, 'work_status'):
            return
        part = self.session_part[1] if self.session_part else None
        filters = {entry['url']: (str(index), entry['name']) for index, entry in enumerate(self.filters)}
        filter_scopes = ('filter', 'filter_definition', 'filter_layout')

        def valid_filter(item):
            url, revision = item.target
            return url in filters and revision is self.filter_revisions.get(url)

        if part and part.scope in filter_scopes and not valid_filter(part):
            part = None
        queued = pending - {part}
        for scope, button in (('dashboard', self.dashboard_button), ('threatened', self.threatened_incidents_button)):
            state = (bool(part and part.scope == scope), any(item.scope == scope for item in queued))
            if (button.updating, button.queued) != state:
                button.updating, button.queued = state
                button.redraw()

        active_row = filters[part.target[0]][0] if part and part.scope in filter_scopes else None
        queued_rows = frozenset(filters[item.target[0]][0] for item in queued
                                if item.scope in filter_scopes and valid_filter(item))
        if (self.filter_table.updating_item, self.filter_table.queued_items) != (active_row, queued_rows):
            self.filter_table.updating_item = active_row
            self.filter_table.queued_items = queued_rows
            self.filter_table.redraw()

        text = 'Oczekuje w kolejce' if queued and self.session_state != 'failed' else ''
        if part:
            name = f' „{filters[part.target[0]][1]}”' if part.scope in filter_scopes else ''
            text = {'dashboard': 'Aktualizuje Dashboard SLA', 'threatened': 'Aktualizuje Incydenty zagrożone SLA',
                    'filter': 'Aktualizuje filtr' + name, 'filter_definition': 'Odświeża zapytanie filtra' + name,
                    'filter_layout': 'Odświeża układ kolumn filtra' + name,
                    'default_layouts': 'Aktualizuje układy list ServiceNow',
                    'dashboard_scope': 'Odświeża zakres Dashboardu SLA',
                    'favorites': 'Importuje Ulubione'}[part.scope]
            if self.session_state == 'waiting':
                text += ' • Oczekuje na logowanie'
            elif self.session_work_detail:
                text = self.session_work_detail
        if self.work_status.get() != text:
            self.work_status.set(text)

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

    def show_window(self, *, activate=True):
        self.root.deiconify()
        if getattr(self, "window_layout", {}).get("maximized", False):
            self.root.state("zoomed")
        if activate and not self.quitting:
            self.root.after_idle(self.activate_main_window)

    def toggle_debug_browser(self, _event=None):
        if not self.quitting:
            if self.browser_runtime is None and not self.session.ready_once:
                self.status.set('Podgląd Chromium będzie dostępny po połączeniu z ServiceNow.')
            else:
                enabled = self.browser_options.toggle_debug_browser()
                self.status.set('Podgląd Chromium włączony' if enabled else 'Podgląd Chromium wyłączony')
                self.schedule.request()
        return 'break'

    def activate_main_window(self):
        if (self.quitting or self.root.state() not in ('normal', 'zoomed')
                or current_grab_path(self.root)):
            return False
        try:
            return self.main_window.activate()
        except (OSError, tk.TclError):
            return False

    def main_window_changed(self, event):
        if (event.widget is self.root or (event.type in (tk.EventType.FocusIn, tk.EventType.FocusOut)
                                        and event.widget.winfo_toplevel() is self.root)):
            self.queue_main_window_observation()

    def queue_main_window_observation(self):
        if not self.quitting and self.main_window_observation is None:
            self.main_window_observation = self.root.after_idle(self.observe_main_window)

    def observe_main_window(self):
        from neto_incident_monitor.login_diagnostics import LoginDiagnostics

        self.main_window_observation = None
        if self.quitting:
            return
        try:
            before = current = self.main_window.inspect()
            raised = released = False
            if not current.foreground or current.exposure in ('hidden', 'minimized'):
                released = self.main_window.release()
            elif self.session_state == 'ready' and not current_grab_path(self.root):
                raised = self.main_window.uncover(current)
                if raised:
                    current = self.main_window.inspect()
            if self.window_restoring and not raised and not released:
                return
        except (OSError, tk.TclError):
            return
        if current != self.main_window_last_state or raised or released:
            self.main_window_last_state = current
            LoginDiagnostics(source='monitor').record('session_visibility', visibility_reason='main_window_observed',
                foreground_confirmed=current.foreground, previous_window_exposure=before.exposure,
                window_exposure=current.exposure, temporarily_raised=raised, temporary_raise_released=released)

    def focus_after_login(self, reason='initial_main_window', attempt=1):
        if (self.quitting or self.session_state != 'ready' or self.root.state() not in ('normal', 'zoomed')
                or current_grab_path(self.root)):
            return
        from neto_incident_monitor.login_diagnostics import LoginDiagnostics
        from neto_incident_monitor.window_style import WindowPresentation

        started = time.monotonic()
        before = WindowPresentation('unavailable')
        try:
            before = self.main_window.inspect()
        except (OSError, tk.TclError):
            pass
        # A retry must not pull the monitor back from another window the user selected.
        activated = self.activate_main_window() if attempt == 1 or before.foreground else False

        def confirm_focus():
            if self.quitting or self.session_state != 'ready' or self.root.state() not in ('normal', 'zoomed'):
                return
            current = WindowPresentation('unavailable')
            keyboard = raised = False
            try:
                current = self.main_window.inspect()
                if not current_grab_path(self.root):
                    raised = self.main_window.uncover(current)
                    if raised:
                        current = self.main_window.inspect()
                focused = self.root.focus_displayof()
                keyboard = current.foreground and focused is not None and focused.winfo_toplevel() is self.root
            except (OSError, tk.TclError, KeyError):
                pass
            LoginDiagnostics(source='monitor').record('session_visibility', visibility_reason=reason,
                attempt=attempt, foreground_confirmed=current.foreground, keyboard_focus_confirmed=keyboard,
                previous_window_exposure=before.exposure, window_exposure=current.exposure,
                window_activation_accepted=activated, temporarily_raised=raised, elapsed_s=time.monotonic() - started)
            if attempt == 1 and current.foreground and not keyboard:
                self.focus_after_login(reason, attempt=2)

        self.root.after(60, confirm_focus)

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
            settings = config_io.read_json(config_io.CONFIG, {})
            settings["window_layout"] = dict(self.window_layout)
            config_io.save_json(config_io.CONFIG, settings)
            self.saved_window_layout = dict(self.window_layout)
        except (OSError, ValueError):
            LOG.exception("Nie udało się zapisać rozmiaru okna")

    def save_minimize_preference(self, *_):
        value = self.minimize_to_tray.get()
        if value == self.saved_minimize:
            return
        try:
            settings = config_io.read_json(config_io.CONFIG, {})
            settings["minimize_to_tray"] = value
            config_io.save_json(config_io.CONFIG, settings)
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

    def request_refresh(self, scope, url=None):
        return self.enqueue_refresh(scope, url)

    def update_refresh_controls(self):
        if not hasattr(self, 'check_button'):
            return
        if not hasattr(self, 'refresh_filter_button') or not hasattr(self, 'threatened_view'):
            return
        available = self.session.ready_once and self.session_state in ('ready', 'waiting') and not self.quitting
        def enable(button, enabled):
            if button.enabled != bool(enabled):
                button.configure(state='normal' if enabled else 'disabled')
        _, pending = self.session.work.pending_refreshes()
        full_pending = self.session.work.has_full_read(self.full_refresh_parts())
        dashboard_pending = any(part.scope == 'dashboard' for part in pending)
        enable(self.check_button, available and not full_pending)
        enable(self.dashboard_view.refresh_button, available and not dashboard_pending)
        enable(self.threatened_view.refresh_button, available and ReadPart('threatened') not in pending)
        url = self.selected_filter_url()
        entry = next((item for item in self.filters if item['url'] == url), None)
        filter_pending = ReadPart('filter', (url, self.filter_revisions.get(url))) in pending
        enable(self.refresh_filter_button, available and entry and not entry.get('url_invalid') and not filter_pending)
        enable(self.open_filter_button, entry and not entry.get('url_invalid'))
        enable(self.start_button, self.session_state == 'ready' and not self.cycle_active and not self.quitting)
        enable(self.stop_button, self.cycle_active and not self.quitting)
        enable(self.import_button, available and not getattr(self, 'favorites_import', None))
        for button in self.filter_buttons:
            enable(button, not self.quitting and not getattr(self, 'favorites_import', None))
        cycle = self.session.cycle
        initial = set(tuple(cycle.initial)) if self.cycle_active and cycle is not None else set()
        dashboard_queued = dashboard_pending or any(part.scope == 'dashboard' for part in initial)
        self.dashboard_view.lock_queued_period(dashboard_queued)
        self.dashboard_view.set_scope_waiting(dashboard_queued and any(part.scope == 'dashboard_scope' for part in pending))
        self.update_session_work(pending | initial)
        self.sync_read_bar_actions()

    def sync_read_bar_actions(self):
        if hasattr(self, 'filter_read_bar'):
            self.filter_read_bar.sync_action()
        for view in ('dashboard_view', 'threatened_view'):
            panel = getattr(self, view, None)
            if panel is not None and hasattr(panel, 'read_bar'):
                panel.read_bar.sync_action()

    def update_session_filters(self):
        parts = {}
        for index, entry in enumerate(self.filters, 1):
            if entry.get('url_invalid'):
                continue
            url = entry['url']
            resolved = effective_list_url(url, self.filters)
            kind = 'task' if urlparse(resolved).path in ('/sc_task_list.do', '/sc_request_list.do', '/sc_req_item_list.do') else 'inc'
            parts[url] = ReadPart('filter', (url, self.filter_revisions.get(url)),
                                  {'name': entry['name'], 'index': index, 'kind': kind, 'resolved': resolved,
                                   'scheduled': entry.get('enabled', True)})
        self.session.update_filters(parts)

    def full_refresh_parts(self):
        return [ReadPart('dashboard', self.dashboard_view.selected_period()), ReadPart('threatened'),
                *self.session.filter_parts]

    def enqueue_refresh(self, scope, url):
        if not self.session.ready_once or self.session_state not in ('ready', 'waiting') or self.quitting:
            return False
        if scope not in ('all', 'dashboard', 'threatened', 'filter', 'filter_definition', 'filter_layout'):
            raise ValueError('Nieznany zakres aktualizacji.')
        self.update_session_filters()
        parts = []
        if scope == 'all':
            parts = self.full_refresh_parts()
        elif scope == 'dashboard':
            parts.append(ReadPart('dashboard', self.dashboard_view.selected_period()))
        elif scope == 'threatened':
            parts.append(ReadPart('threatened'))
        else:
            part = self.session.manual_filter_parts.get(url or self.selected_filter_url())
            if part is not None:
                data = {'requested_at': time.monotonic()} if scope == 'filter_layout' else None
                parts.append(part if scope == 'filter' else ReadPart(scope, part.target, data))
        if not parts:
            return False
        self.session.submit(scope, parts)
        self.update_refresh_controls()
        return True

    def can_refresh_default_layouts(self):
        return bool(self.session and self.session_state == 'ready' and self.session.connected
                    and self.session.layout_account is not None and not self.quitting
                    and self.default_layout_refresh[0] is None)

    def request_default_layout_refresh(self):
        if not self.can_refresh_default_layouts():
            return False
        part = ReadPart('default_layouts', self.session.layout_account,
                        {'requested_at': time.monotonic(), 'completed': []})
        request_id, _ = self.session.submit('default_layouts', [part])
        self.default_layout_refresh = (request_id, 'queued', ())
        self.update_refresh_controls()
        return True

    def can_refresh_dashboard_scope(self):
        return bool(self.session and self.session_state == 'ready' and self.session.connected
                    and self.session.layout_account is not None and not self.quitting
                    and self.dashboard_scope_refresh[0] is None)

    def request_dashboard_scope_refresh(self):
        if not self.can_refresh_dashboard_scope():
            return False
        part = ReadPart('dashboard_scope', self.session.layout_account, {})
        request_id, _ = self.session.submit('dashboard_scope', [part])
        self.dashboard_scope_refresh = (request_id, 'queued')
        self.update_refresh_controls()
        return True

    def execute_session_part(self, page, part, stop, source):
        from neto_incident_monitor.browser_actions import checkpoint
        checkpoint(stop)
        if part.scope == 'default_layouts':
            return self.session.refresh_default_layouts(page, part, stop)
        if part.scope == 'dashboard_scope':
            from neto_incident_monitor.dashboard_scope import refresh_scope
            return refresh_scope(self.session, page, part, stop)
        if part.scope in ('dashboard', 'threatened'):
            request = self.session.prepare_analytics_read(part, stop)
            if request is None:
                return False
            if part.scope == 'dashboard':
                return self.read_dashboard_request(page, request=request, stop=stop)
            return self.read_threatened_request(page, periodic=source == 'threatened', request=request, stop=stop)
        if part.scope == 'favorites':
            from neto_incident_monitor.favorites_worker import read_on_session
            return read_on_session(page, part.data, self.session, stop)
        url, revision = part.target
        metadata_only = part.scope in ('filter_definition', 'filter_layout')
        outside_schedule = source == 'manual' and (metadata_only or not part.data['scheduled'])
        job = self.session.active_job if source == 'manual' else None
        request_id = job.id if job is not None else None
        self.session.update_layout_account(page, stop)
        if self.history.membership is None and self.session.legacy_membership is None:
            from neto_incident_monitor.filter_state import FilterState
            self.session.legacy_membership = FilterState(STATE, normalize_url)
        remaining = {}
        for _ in range(2):
            current = self.session.manual_filter_parts.get(url)
            if (not self.session.filter_is_current(part) or revision is not self.filter_revisions.get(url)
                    or (not outside_schedule and url in self.disabled_filter_urls)):
                return False
            result = self.read_filter(page, url, current.data['name'], current.data['index'],
                                      self.session.legacy_membership, self.session.health, remaining,
                                      self.monitor_generation, stop, part=part, outside_schedule=outside_schedule,
                                      request_id=request_id)
            if result != 'waiting_login':
                return result == 'success'
        return False

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
            from neto_incident_monitor import windows_notifications
            self.root.bell()
            windows_notifications.notify("ServiceNow — przerwa w monitoringu", message, timeout=15)
        except Exception:
            LOG.exception("Nie udało się pokazać alertu o przerwie w monitoringu")

    def session_expired(self, message):
        self.status.set(message)
        if self.teams_enabled.get() and self.teams_webhook:
            self.teams_sender.submit(self.teams_webhook, "ServiceNow — sesja wygasła", message)
        if self.google_chat_enabled.get() and self.google_chat_webhook:
            self.google_chat_sender.submit(self.google_chat_webhook, "ServiceNow — sesja wygasła", message)

    def configure_google_chat(self):
        from neto_incident_monitor.google_chat_ui import show_config
        show_config(self)

    def persist_auto_login(self, enabled):
        settings = config_io.read_json(config_io.CONFIG, {})
        settings['auto_login'] = enabled
        config_io.save_json(config_io.CONFIG, settings)
        self.browser_options.update(auto_login=enabled)

    def save_auto_login(self, *_):
        if self.syncing_auto_login:
            return
        try:
            self.persist_auto_login(self.auto_login.get())
        except (OSError, ValueError):
            self.status.set("Nie udało się zapisać ustawienia automatycznego logowania.")

    def save_dashboard_auto_refresh(self, *_):
        try:
            settings = config_io.read_json(config_io.CONFIG, {})
            settings['dashboard_auto_refresh'] = self.dashboard_auto_refresh.get()
            config_io.save_json(config_io.CONFIG, settings)
        except (OSError, ValueError):
            self.status.set('Nie udało się zapisać ustawienia aktualizacji dashboardu.')

    def save_notify_windows(self, *_):
        from neto_incident_monitor.login_diagnostics import LoginDiagnostics

        enabled = self.notify.get()
        previous = self.saved_notify_windows
        if enabled == previous:
            return
        diagnostics = LoginDiagnostics(source='monitor')
        fields = dict(channel='windows', notify_enabled=enabled, previous_notify_enabled=previous)
        started = time.monotonic()
        diagnostics.record('notification_preference', outcome='started', **fields)
        try:
            with self.filter_config_lock:
                settings = config_io.read_json(config_io.CONFIG, {})
                settings['notify'] = enabled
                config_io.save_json(config_io.CONFIG, settings)
        except (OSError, ValueError) as error:
            self.notify.set(previous)
            self.status.set('Nie udało się zapisać powiadomień Windows. Przywrócono poprzednią wartość.')
            diagnostics.record('notification_preference', outcome='error', **fields, **error_facts(error),
                               duration_ms=round((time.monotonic() - started) * 1000))
        else:
            self.saved_notify_windows = enabled
            diagnostics.record('notification_preference', outcome='returned', **fields,
                               duration_ms=round((time.monotonic() - started) * 1000))
        self.refresh_filter_notifications()

    def save_notify_threatened(self, *_):
        from uuid import uuid4

        enabled = self.notify_threatened.get()
        if enabled == self.saved_notify_threatened:
            return
        try:
            settings = config_io.read_json(config_io.CONFIG, {})
            settings["notify_threatened"] = enabled
            settings["threatened_notification_revision"] = uuid4().hex
            config_io.save_json(config_io.CONFIG, settings)
        except (OSError, ValueError) as error:
            LOG.warning("Nie zapisano ustawienia alertów SLA (%s).", type(error).__name__)
            self.notify_threatened.set(self.saved_notify_threatened)
            self.status.set("Nie udało się zapisać ustawienia alertów SLA. Przywrócono poprzednią wartość.")
        else:
            self.saved_notify_threatened = enabled
            LOG.info("Zapisano ustawienie alertów SLA: włączone=%s.", enabled)

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
            settings = config_io.read_json(config_io.CONFIG, {})
            settings.update(teams_enabled=self.teams_enabled.get(), teams_webhook=self.teams_webhook)
            config_io.save_json(config_io.CONFIG, settings)
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

    def import_favorites(self):
        if self.quitting or getattr(self, 'favorites_import', None) is not None:
            return
        if not self.session.ready_once or self.session_state not in ('ready', 'waiting'):
            self.status.set('Import jest dostępny po potwierdzeniu sesji ServiceNow.')
            return
        from neto_incident_monitor.favorites_ui import FavoritesImport
        self.favorites_import = FavoritesImport(self)
        self.update_refresh_controls()

    def start(self):
        return self.start_session_cycle()

    def monitoring_is_active(self):
        return self.cycle_active

    def read_schedule_intervals(self, values=None):
        inc, task = values if values is not None else (self.interval.get(), self.task_interval.get())
        try:
            intervals = {'inc': int(inc), 'task': int(task)}
            for value in intervals.values():
                float(value)  # Deadlines are expressed as floating-point seconds.
        except (ValueError, OverflowError):
            raise ValueError('Podaj interwały w pełnych sekundach.') from None
        if min(intervals.values()) < 15:
            raise ValueError('Minimalny interwał wynosi 15 sekund.')
        return intervals

    def persist_schedule_intervals(self, intervals):
        settings = config_io.read_json(config_io.CONFIG, {})
        settings.update(interval=intervals['inc'], task_interval=intervals['task'])
        config_io.save_json(config_io.CONFIG, settings)

    def save_schedule_intervals(self):
        from neto_incident_monitor.login_diagnostics import LoginDiagnostics

        if self.quitting:
            return False
        diagnostics = LoginDiagnostics(source='monitor')
        try:
            intervals = self.read_schedule_intervals()
        except ValueError as error:
            self.schedule_interval_status.set(str(error))
            diagnostics.record('schedule_interval_change', interval_stage='rejected')
            return False
        fields = dict(inc_interval_s=intervals['inc'], task_interval_s=intervals['task'])
        started = time.monotonic()
        diagnostics.record('schedule_interval_change', interval_stage='saving', **fields)
        try:
            self.persist_schedule_intervals(intervals)
        except (ValueError, OSError) as error:
            self.schedule_interval_status.set('Nie udało się zapisać. Nadal obowiązują poprzednie interwały.')
            diagnostics.record('schedule_interval_change', interval_stage='error', **fields, **error_facts(error),
                               duration_ms=round((time.monotonic() - started) * 1000))
            return False
        self.session.update_intervals(intervals)
        self.schedule_interval_status.set('Zapisano interwały.')
        diagnostics.record('schedule_interval_change', interval_stage='saved', **fields,
                           duration_ms=round((time.monotonic() - started) * 1000))
        return True

    def start_session_cycle(self):
        from neto_incident_monitor.monitoring import ReadPart
        if self.quitting or self.cycle_active or self.session_state != 'ready':
            return
        self.update_session_filters()
        if not self.session.filter_parts:
            self.status.set('Włącz przynajmniej jeden filtr, aby uruchomić monitoring.')
            return
        try:
            intervals = self.read_schedule_intervals(self.schedule_interval_autosave.saved_values)
            self.persist_schedule_intervals(intervals)
        except (ValueError, OSError):
            messagebox.showerror('Konfiguracja', 'Sprawdź interwały odczytów i dostęp do konfiguracji.', parent=self.root)
            return
        initial = [ReadPart('dashboard', self.dashboard_view.selected_period())] if self.dashboard_auto_refresh.get() else []
        initial.append(ReadPart('threatened'))
        self.cycle_active = True
        self.set_phase('Monitoring aktywny')
        self.session.start_cycle(initial, intervals)
        self.submit_alert_delivery(True)
        self.update_refresh_controls()

    def stop_monitoring(self):
        self.session.stop_cycle()
        if self.dashboard_request_stop is not None and self.dashboard_request_stop.is_set():
            self.dashboard_view.cancel_request()
            self.dashboard_request_stop = None
        self.cycle_active = False
        self.check_deadlines = {}
        self.next_check = None
        self.set_phase('Monitoring zatrzymany')
        self.update_refresh_controls()

    def read_shared_filter_definition(self, page, entry, stop, diagnostics, revision, generation, part):
        from neto_incident_monitor.browser_actions import checkpoint
        from neto_incident_monitor.dashboard_context import DashboardReadError

        session = self.session
        scope = part.scope
        account = session.layout_account
        metadata = saved_query(entry, account.key if account else None)
        if account is None:
            raise DashboardReadError('filter_layout_account', retryable=False)
        if metadata is None or scope == 'filter_definition':
            metadata, direct = discover_query(page, stop, diagnostics, entry, account.key,
                                              session.filter_field_schemas, fresh=scope == 'filter_definition')
            request = dict(done=threading.Event(), saved=False, stop=stop, url=entry['url'],
                           revision=revision, generation=generation, definition=metadata, direct=direct,
                           layout_generation=session.layout_generation, diagnostics=diagnostics)
            self.events.put(('save_filter_definition', request))
            try:
                while not request['done'].wait(.05):
                    checkpoint(stop)
            finally:
                request['done'].set()
            checkpoint(stop)
            if not request['saved']:
                raise DashboardReadError('filter_definition_save', retryable=False)
        else:
            diagnostics.record('filter_definition', outcome='returned', reused=True,
                               api_target=metadata['table'])
        if scope == 'filter_definition':
            return None
        columns = session.filter_layout(page, stop, diagnostics, metadata['table'], metadata['view'],
                                        refresh=scope == 'filter_layout',
                                        requested_at=part.data['requested_at'] if scope == 'filter_layout' else None)
        return dict(metadata, columns=columns)

    def read_filter(self, page, url, filter_name, filter_index, membership, health,
                    remaining_after_login, generation, stop, *, part, outside_schedule=False, request_id=None):
        from neto_incident_monitor.browser_actions import ACTION_TICK
        from neto_incident_monitor.login_diagnostics import LoginDiagnostics
        from neto_incident_monitor.filter_api import (
            FilterListLimitExceeded, MAX_FILTER_RECORDS, MAX_READ_SECONDS, read_filter_records)
        from neto_incident_monitor.read_budget import Budget, budget_scope
        from neto_incident_monitor.analytics_api import data_duration, measure_data_requests

        class FilterInvalidated(Exception):
            pass

        definition_only = part.scope == 'filter_definition'
        layout_only = part.scope == 'filter_layout'
        layout_generation = self.session.layout_generation
        _, revision = part.target

        def report(kind, value):
            self.events.put(('filter_activity', (url, (kind, value), revision, generation,
                                                  False, False, layout_generation)))

        def is_current():
            return (revision is getattr(self, 'filter_revisions', {}).get(url)
                    and (outside_schedule or url not in self.disabled_filter_urls)
                    and self.session.filter_is_current(part)
                    and layout_generation is self.session.layout_generation)

        def validate_revision():
            if not is_current():
                raise FilterInvalidated()

        read_stage = {'stage': 'prepare', 'page': 0}
        read_started = time.monotonic()
        retry_used = False
        resumed = remaining_after_login.pop(url, None)
        recovered_login = resumed is not None and resumed[2] is revision
        if recovered_login:
            seconds, read_diagnostics, _, retry_used = resumed
            read_diagnostics.record("filter_read_resumed")
        else:
            seconds = MAX_READ_SECONDS
            read_diagnostics = LoginDiagnostics(source="filter_read", filter_index=filter_index,
                                                outside_schedule=outside_schedule, request_id=request_id)
            read_diagnostics.record("filter_read_start")
        outcome = "interrupted"
        filter_budget = Budget(seconds)
        try:
            if page.is_closed():
                raise BrowserClosedError('Karta robocza została zamknięta.')
            current = page
            if self.browser_runtime:
                self.browser_runtime.set_activity('filters')
            from neto_incident_monitor.browser_actions import checkpoint
            from neto_incident_monitor.dashboard_context import DashboardReadError
            browser_tick = ACTION_TICK.get()

            def filter_tick():
                validate_revision()
                if browser_tick:
                    browser_tick()

            filter_tick_token = ACTION_TICK.set(filter_tick)
            try:
                validate_revision()
                with budget_scope(filter_budget):
                    entry = next((item for item in self.filters if item['url'] == url), None)
                    if entry is None:
                        raise FilterInvalidated()
                    read_stage['stage'] = 'definition'
                    if definition_only or layout_only:
                        report('filter_progress', 'odświeżanie metadanych z ServiceNow…')
                    definition = self.read_shared_filter_definition(current, entry, stop, read_diagnostics,
                                                                   revision, generation, part)
                    if definition_only or layout_only:
                        report('filter_progress', 'Zapisano zapytanie.' if definition_only else
                               'Zapisano układ. Filtry użyją go przy następnym odczycie.')
                        outcome = 'success'
                        return outcome
                    read_stage['stage'] = 'api_read'
                    while True:
                        read_stage['page'] = 1
                        try:
                            with measure_data_requests() as times:
                                incidents = read_filter_records(current, stop, read_diagnostics, definition)
                            break
                        except DashboardReadError as error:
                            if retry_used or not error.retryable:
                                raise
                            retry_used = True
                            read_diagnostics.record('section_read_retry', attempt=1, read_reason=error.reason)
            finally:
                ACTION_TICK.reset(filter_tick_token)
            validate_revision()
            schema = definition['columns']
            available = sorted(column['key'] for column in schema)
            for incident in incidents.values():
                values = incident.get('_values')
                incident["_available_columns"] = (available if values is None else
                                                   [key for key in available if key in values])
            read_stage['stage'] = 'history_write'
            from neto_incident_monitor.browser_actions import checkpoint
            read_diagnostics.record("filter_commit_start", records_read=len(incidents))
            def confirm_commit():
                checkpoint(stop)
                validate_revision()

            with getattr(self, 'filter_config_lock', nullcontext()):
                confirm_commit()
                entry = next((item for item in self.filters if item['url'] == url), {})
                filter_name = entry.get('name', filter_name)
                instance = {'filter_instance': entry['filter_instance']} if entry.get('filter_instance') else {}
                new = self.history.commit_filter(
                    membership, url, filter_name, incidents, confirm_commit,
                    prepare_alerts=(lambda numbers: self.prepare_filter_alerts(
                        url, filter_name, [incidents[n] for n in sorted(numbers)]))
                    if not outside_schedule else None,
                    **instance)
            duration = data_duration(times)
            read_diagnostics.record("filter_commit_complete", records_read=len(incidents), api_data_ms=duration)
            outcome = "success"
            self.events.put(("columns", (url, schema, revision, generation, outside_schedule,
                                          True, layout_generation)))
            health.success(part.target)
            self.events.put(("snapshot", (url, incidents, revision, generation, outside_schedule, False,
                                          layout_generation, (time.time(), duration))))
            if new and not outside_schedule:
                self.submit_alert_delivery()
        except FilterInvalidated:
            outcome = "discarded"
        except FilterListLimitExceeded as error:
            if not is_current():
                outcome = 'discarded'
                return outcome
            outcome = 'rejected'
            read_diagnostics.record('filter_read_error', filter_stage='api_read', page_index=1,
                                    read_reason=error.reason, total_rows=error.total, page_size=MAX_FILTER_RECORDS,
                                    final_failure=True)
            self.events.put(('filter_limit', (url, error.total, revision, generation, False, False, layout_generation)))
        except Cancelled:
            outcome = 'cancelled' if is_current() else 'discarded'
            return outcome
        except AuthenticationRequired:
            if not is_current():
                outcome = 'discarded'
                return outcome
            seconds_left = max(0, filter_budget.end - time.monotonic())
            if recovered_login or not seconds_left:
                outcome = 'error'
                self.session.connected = False
                read_diagnostics.record('filter_read_error', filter_stage=read_stage['stage'],
                    page_index=read_stage['page'], read_reason='authentication_required', final_failure=True)
                message = 'Nie udało się przywrócić sesji ServiceNow. Połącz się ponownie i odśwież filtr.'
                if definition_only or layout_only:
                    report('status', message)
                else:
                    report('filter_error', (message, 'authentication_required'))
                return outcome
            outcome = "waiting_login"
            remaining_after_login[url] = (
                seconds_left, read_diagnostics, revision, retry_used)
            message = "Sesja ServiceNow wygasła. Zaloguj się w przeglądarce — monitoring wznowi się automatycznie."
            if health.authentication():
                self.events.put(("session_expired", message))
            if not self.session.authenticate(current, stop):
                outcome = 'cancelled' if is_current() else 'discarded'
                return outcome
            if not is_current():
                outcome = 'discarded'
                remaining_after_login.pop(url, None)
                return outcome
            health.resumed()
        except (TargetClosedError, BrowserClosedError):
            raise
        except Exception as exc:
            if not is_current():
                outcome = 'discarded'
                return outcome
            outcome = "error"
            reason = getattr(exc, "reason", None)
            read_diagnostics.record("filter_read_error", filter_stage=read_stage["stage"],
                page_index=read_stage["page"], read_reason=reason, **error_facts(exc))
            LOG.error("Błąd odczytu filtra (%s); etap=%s; strona=%d; czas=%.1fs; filtr=%d.",
                      type(exc).__name__, read_stage['stage'], read_stage['page'],
                      time.monotonic() - read_started, filter_index)
            if read_stage["stage"] == "history_write":
                message = "Nie udało się zapisać historii i stanu filtra."
            elif reason == 'api_timeout':
                message = 'ServiceNow nie odpowiedział w wyznaczonym czasie.'
            elif reason == 'api_network':
                message = 'Połączenie przerwało się podczas odczytu. Spróbuj ponownie.'
            elif reason in ("query_mismatch", "view_mismatch"):
                message = "Warunki lub widok listy w ServiceNow różnią się od zapisanej definicji."
            elif reason in READ_MESSAGES:
                message = READ_MESSAGES[reason]
            elif reason:
                message = "ServiceNow nie zwróciło kompletnych danych filtra."
            else:
                message = "Nie udało się pobrać listy zgłoszeń. Spróbuj ponownie."
            if not (definition_only or layout_only):
                report('filter_error', (message, reason))
            else:
                report('status', message)
            if not outside_schedule and health.failure(part.target):
                report('interruption', f'Lista „{filter_name}”: trzy kolejne odczyty nie powiodły się. Otwórz aplikację i sprawdź sesję lub połączenie. Automatyczne próby będą kontynuowane.')
        finally:
            read_diagnostics.record("filter_read_end", filter_outcome=outcome,
                filter_stage=read_stage["stage"], page_index=read_stage["page"],
                duration_ms=round((time.monotonic() - read_started) * 1000))
        return outcome

    def read_threatened_request(self, page, periodic=False, *, request, stop):
        from neto_incident_monitor.browser_actions import checkpoint
        from neto_incident_monitor.threatened_read import read_threatened_request

        def commit(details, timestamp, counters, duration):
            return self.history.commit_threatened(
                details, timestamp, lambda: checkpoint(stop),
                lambda incidents: self.prepare_threatened_alerts(incidents, request),
                counters=counters, duration_ms=duration)

        return read_threatened_request(
            page, request=request, stop=stop, events=self.events,
            restore=lambda: self.session.authenticate(page, stop),
            deadline=self.session.threatened_next_read if periodic else None,
            delay_reason=self.session.threatened_delay_reason,
            commit=commit, deliver=self.submit_alert_delivery, finished=self.session.finish_threatened_read)

    def read_dashboard_request(self, page, *, request, stop):
        from neto_incident_monitor.dashboard_read import read_dashboard_request

        return read_dashboard_request(page, request=request, stop=stop, events=self.events,
                                      restore=lambda: self.session.authenticate(page, stop))

    def save_discovered_filter_definition(self, request):
        from neto_incident_monitor.dashboard import measured_record
        diagnostics = request['diagnostics']
        try:
            with self.filter_config_lock:
                url = request['url']
                if (request['done'].is_set() or request['stop'].is_set() or self.quitting
                        or request['generation'] is not self.monitor_generation
                        or request['revision'] is not self.filter_revisions.get(url)):
                    return
                index = self.event_filter_index(url)
                if index is None:
                    return
                proposed = list(self.filters)
                entry = dict(proposed[index - 1], list_definition=request['definition'])
                if is_short_url(url):
                    entry['resolved_list_url'] = request['direct']
                if (request['layout_generation'] is not self.session.layout_generation
                        or self.session.layout_account is None
                        or saved_query(entry, self.session.layout_account.key) is None):
                    return
                proposed[index - 1] = entry
                try:
                    self.persist_filters(proposed)
                except (OSError, ValueError) as error:
                    measured_record(diagnostics, 'filter_definition', outcome='error', **error_facts(error))
                    self.status.set('Nie udało się zapisać definicji filtra.')
                    return
                measured_record(diagnostics, 'filter_definition', outcome='returned')
                request['saved'] = True
            self.update_session_filters()
            self.schedule.request()
            self.update_filter_info_button()
        finally:
            request['done'].set()

    def handle_session_event(self, kind, value):
        if kind == 'session_prepare_read':
            request = value
            if request['done'].is_set():
                return True
            try:
                if not self.quitting and not request['stop'].is_set():
                    part = request['part']
                    if part.scope == 'dashboard':
                        request['value'] = self.dashboard_view.active_request or self.dashboard_view.request_refresh(
                            selected=part.target)
                        if request['value']:
                            self.dashboard_request_stop = request['stop']
                    else:
                        request['value'] = (self.threatened_view.request_id if self.threatened_view.pending else
                                            self.threatened_view.request_refresh())
            finally:
                request['done'].set()
        elif kind == 'session_waiting':
            self.session_state = 'waiting'
            self.session_status.set('Sprawdzanie sesji…')
            if hasattr(self, 'reconnect_button'):
                self.reconnect_button.pack_forget()
            self.update_refresh_controls()
        elif kind == 'session_cancel_prepared':
            scope, request = value
            if scope == 'dashboard' and self.dashboard_view.active_request == request:
                self.dashboard_view.cancel_request()
                self.dashboard_request_stop = None
                self.dashboard_button.updating = False
                self.dashboard_button.redraw()
            elif scope == 'threatened':
                self.threatened_view.finish_request(request)
            self.update_refresh_controls()
        elif kind == 'session_activity':
            _, _, manual = value
            self.session_status.set('Wymagane logowanie' if manual else 'Łączenie…')
            if manual:
                self.login_window_button.pack(side='left', padx=4)
            else:
                self.login_window_button.pack_forget()
            self.update_tray()
        elif kind == 'session_password_save':
            self.show_password_save_prompt(value)
        elif kind == 'session_password_save_finished':
            dialog = value.get('dialog')
            if dialog is not None and self.password_save_dialog is dialog:
                self.password_save_dialog = None
                dialog.destroy()
        elif kind in ('session_layout_account', 'session_layout_saved'):
            if kind == 'session_layout_account':
                self.update_filter_info_button()
        elif kind == 'session_default_layout_started':
            if value == self.default_layout_refresh[0]:
                self.default_layout_refresh = (value, 'running', ())
        elif kind == 'session_default_layout_result':
            request_id, outcome, completed = value
            if request_id == self.default_layout_refresh[0]:
                self.default_layout_refresh = (None, outcome, completed)
        elif kind == 'session_dashboard_scope_queued':
            self.dashboard_scope_refresh = (value, 'queued')
        elif kind == 'session_dashboard_scope_started':
            if value == self.dashboard_scope_refresh[0]:
                self.dashboard_scope_refresh = (value, 'running')
        elif kind == 'session_dashboard_scope_result':
            request_id, outcome = value
            if request_id == self.dashboard_scope_refresh[0]:
                self.dashboard_scope_refresh = (None, outcome)
        elif kind == 'session_ready':
            self.session_state = 'ready'
            self.session_status.set('Połączono')
            self.login_window_button.pack_forget()
            if self.connection_dialog:
                self.connection_dialog.destroy()
                self.connection_dialog = None
            if hasattr(self, 'reconnect_button'):
                self.reconnect_button.pack_forget()
            if self.window_restoring:
                self.set_phase('Gotowy do uruchomienia')
                if self.apply_startup and self.start_minimized.get():
                    if not (self.minimize_to_tray.get() and self.tray_ready):
                        self.root.iconify()
                else:
                    self.show_window(activate=False)
                    self.root.after_idle(self.focus_after_login)
                self.window_restoring = False
                if self.apply_startup and self.start_monitoring.get() and self.session.filter_parts:
                    self.start_session_cycle()
            elif value is True:
                self.root.after_idle(self.focus_after_login, 'recovered_main_window')
            self.update_refresh_controls()
        elif kind == 'session_problem':
            self.session_state = 'failed'
            self.session_status.set('Brak połączenia')
            self.login_window_button.pack_forget()
            self.update_refresh_controls()
            if not self.quitting:
                if self.session.ready_once:
                    self.show_reconnect_action()
                else:
                    self.show_connection_problem()
        elif kind == 'session_idle':
            active, next_read, deadlines = value
            if self.cycle_active == active:
                self.next_check = next_read
                self.check_deadlines = deadlines
        elif kind == 'session_part_started':
            self.session_part = value
            self.session_work_detail = ''
        elif kind == 'session_part_finished':
            if self.session_part and self.session_part[0] is value:
                self.session_part = None
                self.session_work_detail = ''
        elif kind == 'session_job_finished':
            skipped = value[2] if len(value) > 2 else 0
            if skipped and not self.status.get():
                self.status.set(f'Pominięte odczyty po zmianie filtrów: {skipped}.')
        else:
            return False
        if kind in ('session_waiting', 'session_ready', 'session_problem', 'session_layout_account', 'session_layout_saved',
                    'session_default_layout_started', 'session_default_layout_result'):
            refresh_preview = getattr(self, 'refresh_saved_layout_preview', None)
            if refresh_preview is not None:
                refresh_preview()
        if kind in ('session_waiting', 'session_ready', 'session_problem', 'session_layout_account',
                    'session_dashboard_scope_queued', 'session_dashboard_scope_started', 'session_dashboard_scope_result'):
            refresh_scope_preview = getattr(self, 'refresh_dashboard_scope_preview', None)
            if refresh_scope_preview is not None:
                refresh_scope_preview()
        return True

    def show_password_save_prompt(self, request):
        if request['done'].is_set() or self.quitting:
            return
        from neto_incident_monitor.widgets import RoundedButton
        from neto_incident_monitor.window_style import activate_window, window_is_foreground

        dialog = tk.Toplevel(self.root, background=BG)
        dialog.withdraw()
        self.password_save_dialog = request['dialog'] = dialog
        dialog.title('Zapis poświadczeń w Chromium')
        dialog.resizable(False, False)
        dialog.protocol('WM_DELETE_WINDOW', lambda: None)
        panel = ttk.Frame(dialog, padding=20)
        panel.pack(fill='both', expand=True)
        ttk.Label(panel, text='Aby autologowanie działało, zapisz poświadczenia w Chromium. '
                  'Użyj przycisku Zapisz w przeglądarce, a następnie wybierz Zapisano. '
                  'Jeśli komunikat Chromium się schował, kliknij ikonę klucza przy pasku adresu.',
                  wraplength=430).pack(anchor='w', pady=(0, 12))
        error = tk.StringVar(master=dialog)
        ttk.Label(panel, textvariable=error, wraplength=430).pack(anchor='w')
        actions = ttk.Frame(panel)
        actions.pack(fill='x', pady=(10, 0))

        def finish(choice):
            if request['done'].is_set() or self.quitting:
                return
            if choice == 'disabled':
                try:
                    self.persist_auto_login(False)
                except (OSError, ValueError):
                    request['save_failed'] = True
                    error.set('Nie udało się zapisać wyłączenia autologowania. Spróbuj ponownie.')
                    return
                self.syncing_auto_login = True
                try:
                    self.auto_login.set(False)
                finally:
                    self.syncing_auto_login = False
            request['choice'] = choice
            try:
                request['restore_main_focus'] = window_is_foreground(dialog)
            except (OSError, tk.TclError):
                request['restore_main_focus'] = False
            self.password_save_dialog = None
            dialog.destroy()
            request['done'].set()

        RoundedButton(actions, text='Zapisano', command=lambda: finish('saved'),
                      primary=True).pack(side='right')
        RoundedButton(actions, text='Wyłącz autologowanie', command=lambda: finish('disabled')).pack(
            side='right', padx=(0, 8))
        dialog.update_idletasks()
        width, height = dialog.winfo_reqwidth(), dialog.winfo_reqheight()
        x = max(0, (dialog.winfo_screenwidth() - width) // 2)
        y = max(0, (dialog.winfo_screenheight() - height) // 2)
        geometry = f'+{x}+{y}'
        dialog.geometry(geometry)
        self.session_status.set('Oczekiwanie na zapis poświadczeń')
        dialog.deiconify()

        def focus_prompt():
            if self.password_save_dialog is not dialog or request['done'].is_set() or self.quitting:
                return
            try:
                dialog.geometry(geometry)
                dialog.lift()
                request['foreground_confirmed'] = activate_window(dialog)
            except (OSError, tk.TclError):
                request['foreground_confirmed'] = False

        dialog.after_idle(focus_prompt)

    def show_connection_problem(self):
        from neto_incident_monitor.widgets import RoundedButton
        if self.connection_dialog:
            self.connection_dialog.lift()
            return
        dialog = self.connection_dialog = tk.Toplevel(self.root, background=BG)
        dialog.title('Połączenie z ServiceNow')
        dialog.resizable(False, False)
        panel = ttk.Frame(dialog, padding=20)
        panel.pack(fill='both', expand=True)
        ttk.Label(panel, text='Nie udało się potwierdzić sesji ServiceNow. Sprawdź połączenie i spróbuj ponownie.',
                  wraplength=400).pack(anchor='w', pady=(0, 16))
        def close():
            self.connection_dialog = None
            dialog.destroy()
            if not self.session.ready_once:
                self.quit_app()
        def retry():
            self.connection_dialog = None
            dialog.destroy()
            self.session.retry()
        dialog.protocol('WM_DELETE_WINDOW', close)
        RoundedButton(panel, text='Spróbuj ponownie', command=retry,
                      primary=True, background=BG).pack(side='right')
        RoundedButton(panel, text='Zamknij', command=close, background=BG).pack(side='right', padx=8)

    def show_reconnect_action(self):
        from neto_incident_monitor.widgets import RoundedButton
        if not hasattr(self, 'reconnect_button'):
            self.reconnect_button = RoundedButton(self.footer_actions, text='Połącz ponownie',
                                                   command=self.session.retry,
                                                   background=self.footer_actions.cget('background'), compact=True)
        self.reconnect_button.pack(side='left', padx=4)

    def drain(self):
        if getattr(self, "reset_data_on_exit", False) is True:
            return
        # Windows can switch foreground without Tk delivering a matching focus event.
        main_window = getattr(self, 'main_window', None)
        if main_window is not None and main_window.raise_needs_release():
            self.queue_main_window_observation()
        if self.instance and self.instance.poll():
            if getattr(self, 'password_save_dialog', None):
                self.password_save_dialog.lift()
            elif self.session.ready_once:
                self.show_window()
            elif self.connection_dialog:
                self.connection_dialog.lift()
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'save_filter_definition':
                    self.save_discovered_filter_definition(value)
                    continue
                if kind.startswith('session_') and self.handle_session_event(kind, value):
                    continue
                outside_schedule = preserve_layout = False
                flags = ()
                if kind in ("snapshot", "columns", "filter_notification", 'filter_activity', 'filter_limit') and len(value) >= 4:
                    url, payload, revision, generation, *flags = value
                    if (generation is not getattr(self, "monitor_generation", None) or
                            revision is not getattr(self, "filter_revisions", {}).get(url)):
                        continue
                    if len(flags) > 2 and flags[2] is not None and flags[2] is not self.session.layout_generation:
                        continue
                    value = (url, payload)
                    outside_schedule = bool(flags and flags[0])
                    preserve_layout = len(flags) > 1 and flags[1]
                    if kind == 'filter_limit':
                        self.handle_filter_limit(url, payload)
                        continue
                    if kind == 'filter_activity':
                        index = self.event_filter_index(url)
                        if index is None:
                            continue
                        kind, value = payload
                        name = self.filters[index - 1]['name']
                        if kind == 'filter_progress':
                            if value.endswith('…'):
                                self.session_work_detail = f'{name}: {value}'
                            continue
                        elif kind == 'filter_error':
                            detail, reason = value
                            title = 'Nie udało się połączyć z ServiceNow' if reason in ('api_network', 'api_timeout') else ''
                            self.update_filter_read_result(url, error=detail, title=title)
                            continue
                if kind == 'refresh_state':
                    self.update_refresh_controls()
                    continue
                if kind.startswith('threatened_') and handle_threatened_read_event(self, kind, value):
                    continue
                if kind.startswith('dashboard_') and handle_dashboard_read_event(self, kind, value):
                    continue
                if kind == "status":
                    self.status.set(value)
                elif kind == "tray_ready":
                    self.tray_ready = True
                    self.update_tray()
                    self.handle_minimize()
                elif kind == "tray_failed":
                    self.tray_ready = False
                    if self.session.ready_once:
                        self.show_window()
                    self.status.set("Zasobnik niedostępny — aplikacja pozostaje w oknie.")
                elif kind == "show":
                    if getattr(self, 'password_save_dialog', None):
                        self.password_save_dialog.lift()
                    elif self.session.ready_once:
                        self.show_window()
                    elif self.connection_dialog:
                        self.connection_dialog.lift()
                elif kind == "show_browser":
                    if self.browser_runtime and self.session.manual_login:
                        self.browser_runtime.request_show()
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
                    self.stop_monitoring()
                elif kind == "quit":
                    self.quit_app()
                    return
                elif kind == "columns":
                    index, available = value
                    index = self.event_filter_index(index)
                    if index is None:
                        continue
                    if not outside_schedule and not self.filters[index - 1].get("enabled", True):
                        continue
                    if isinstance(available, list):
                        self.column_availability[index] = {c["key"] for c in available}
                        self.accept_column_schema(self.filters[index - 1]["url"], available,
                                                  preserve_layout=preserve_layout)
                elif kind == "snapshot":
                    filter_index, incidents = value
                    filter_index = self.event_filter_index(filter_index)
                    if filter_index is None:
                        continue
                    if not outside_schedule and not self.filters[filter_index - 1].get("enabled", True):
                        continue
                    self.snapshots[filter_index] = incidents
                    url = self.filters[filter_index - 1]['url']
                    timing = flags[3] if len(flags) > 3 else None
                    if timing is not None:
                        self.update_filter_read_result(url, accepted=timing)
                    self.refresh_current()
                    self.refresh_history()
                    self.apply_visible_columns()
                    self.update_counts()
        except queue.Empty:
            pass
        now = time.monotonic()
        if now - getattr(self, "last_age_refresh", 0) >= 1:
            self.last_age_refresh = now
            url = self.selected_filter_url()
            snapshot = self.snapshots.get(self.selected_filter_index(), {})
            for table in (self.current_table, self.table):
                if not self.table_visible(table):
                    continue
                changed = False
                visible_items = set(table.identify_row(y) for y in range(0, table.winfo_height(), 12))
                for item in visible_items - {''}:
                    number = self.row_numbers.get((table, item)) or table.set(item, "number")
                    incident = snapshot.get(number, {}) if table is self.current_table else (
                        (self.history.record(number, url) or {}).get('incident', {}) if url else {})
                    value = age_minutes(incident.get('_created_utc') or table.set(item, "created"), number)
                    if table.set(item, "age_minutes") != value:
                        table.set(item, "age_minutes", value)
                        changed = True
                if changed and table.sort_column == "age_minutes" and table not in getattr(self, '_table_jobs', {}):
                    if self.large_tables():
                        (self.refresh_current if table is self.current_table else self.refresh_history)()
                    else:
                        self.apply_sort(table)
        self.update_refresh_controls()
        if not self.quitting:
            self.alert_retention.tick()
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
        self.cancel_column_fit()
        self.stop_table_loads()
        if self.window_save_timer is not None:
            self.root.after_cancel(self.window_save_timer)
            self.window_save_timer = None
        if not reset_data:
            self.save_window_layout()
        self.quitting = True
        self.dashboard_view.cache_writer.close(discard=reset_data)
        self.main_window.release()
        self.stop.set()
        self.schedule.request()
        self.session.shutdown()
        self.import_button.configure(state='disabled')
        if self.session.ready_once:
            self.show_window()
        if getattr(self, 'connection_dialog', None):
            self.connection_dialog.destroy()
            self.connection_dialog = None
        if getattr(self, 'password_save_dialog', None):
            self.password_save_dialog.destroy()
            self.password_save_dialog = None
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
            if not self.dashboard_view.cache_writer.idle or any(not future.done() for future in self._shutdown_writes):
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


def _show_startup_problem(window, error):
    from neto_incident_monitor.widgets import RoundedButton
    window.title('Neto Incident Monitor — lokalne dane')
    window.configure(background=BG)
    window.resizable(False, False)
    panel = ttk.Frame(window, padding=24)
    panel.pack(fill='both', expand=True)
    area = 'konfiguracji' if error.area == 'configuration' else 'historii i stanu filtrów'
    reason = 'Nieprawidłowy format' if error.category == 'invalid' else 'Brak dostępu do plików'
    ttk.Label(panel, text=f'{reason} {area}.', wraplength=480).pack(anchor='w')
    ttk.Label(panel, text='Monitoring i powiadomienia nie zostały uruchomione. '
              'Konfiguracja i historia pozostały bez zmian. Zamknij aplikację '
              'i przywróć poprawne dane z kopii lub sprawdź dostęp do plików.',
              wraplength=480).pack(anchor='w', pady=(12, 20))
    RoundedButton(panel, text='Zamknij', command=window.destroy, background=BG).pack(side='right')
    window.protocol('WM_DELETE_WINDOW', window.destroy)
    window.bind('<Escape>', lambda _: window.destroy())
    window.mainloop()


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
        from neto_incident_monitor.data_validation import preflight, StartupDataError
        from neto_incident_monitor.login_diagnostics import LoginDiagnostics
        validation = LoginDiagnostics(source='configuration')
        try:
            preflight(config_io.CONFIG, DATA / 'history.json')
        except StartupDataError as error:
            validation.record('startup_validation', data_area=error.area, validation_result=error.category)
            _show_startup_problem(window, error)
            return False
        validation.record('startup_validation', validation_result='accepted')
        from neto_incident_monitor.startup import reconcile_windows_startup
        try:
            startup_status = reconcile_windows_startup()
            LOG.info("Autostart Windows: wynik=%s.", startup_status)
        except OSError:
            startup_status = "unknown"
            LOG.warning("Autostart Windows: wynik=check_failed.")
        window.withdraw()
        app = App(window, instance=instance, windows_startup=startup_status)
        app.update_refresh_controls()
        app.session.thread.start()
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
