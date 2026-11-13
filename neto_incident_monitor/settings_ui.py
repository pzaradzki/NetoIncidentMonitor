"""Settings window with aligned controls and descriptive option groups."""
import tkinter as tk
from math import ceil
from time import monotonic
from tkinter import ttk

from neto_incident_monitor.monitoring import DEFAULT_TASK_INTERVAL
from neto_incident_monitor.theme import SURFACE, MUTED
from neto_incident_monitor.widgets import RoundedButton, Toggle


SETTINGS_WINDOW_SIZE = (700, 700)


class ScheduleIntervalAutosave:
    def __init__(self, timer_owner, fields, status, save):
        self.timer_owner = timer_owner
        self.fields = fields
        self.status = status
        self.save = save
        self.saved_values = self.values()
        self.timer = None
        self.deadline = None
        for field in fields:
            field.trace_add('write', self.edited)

    def values(self):
        return tuple(field.get() for field in self.fields)

    def cancel(self):
        if self.timer is not None:
            self.timer_owner.after_cancel(self.timer)
            self.timer = None

    def edited(self, *_):
        self.cancel()
        if self.values() == self.saved_values:
            self.status.set('')
            return
        self.deadline = monotonic() + 5
        self.tick()

    def tick(self):
        self.timer = None
        remaining = self.deadline - monotonic()
        if remaining <= 0:
            self.flush()
            return
        self.status.set(f'Zapis interwałów za {ceil(remaining)} s.')
        self.timer = self.timer_owner.after(min(1000, ceil(remaining * 1000)), self.tick)

    def flush(self):
        self.cancel()
        values = self.values()
        if values == self.saved_values:
            return True
        if not self.save():
            return False
        self.saved_values = values
        return True


def build_settings(app, settings):
    window = app.settings_window
    interval_autosave = None

    def close_settings(_event=None):
        if interval_autosave is None or interval_autosave.flush():
            window.withdraw()
        return 'break'

    window.protocol('WM_DELETE_WINDOW', close_settings)
    window.bind('<Escape>', close_settings)
    width, height = SETTINGS_WINDOW_SIZE
    window.minsize(width, 600)
    window.geometry(f'{width}x{height}')
    header = ttk.Frame(window, style="White.TFrame", padding=(28, 24, 28, 0))
    header.pack(fill="x")
    ttk.Label(header, text="Ustawienia", style="White.TLabel",
              font=("Segoe UI", 18, "bold")).pack(anchor="w")
    ttk.Label(header, text="Dostosuj monitorowanie, powiadomienia i działanie aplikacji.",
              style="WhiteMuted.TLabel").pack(anchor="w", pady=(4, 22))
    footer = ttk.Frame(window, style="White.TFrame", padding=(28, 12, 28, 24))
    footer.pack(fill="x", side="bottom")
    RoundedButton(footer, text="Zamknij", command=close_settings).pack(side="right")
    from neto_incident_monitor.release_check import check_updates
    update_button = RoundedButton(footer, text="Sprawdź aktualizacje",
                                  command=lambda: check_updates(window, update_button))
    update_button.pack(side="left")
    viewport = ttk.Frame(window, style="White.TFrame")
    viewport.pack(fill="both", expand=True)
    viewport.columnconfigure(0, weight=1)
    viewport.rowconfigure(0, weight=1)
    canvas = tk.Canvas(viewport, bg=SURFACE, highlightthickness=0, bd=0)
    canvas.grid(row=0, column=0, sticky="nsew")
    scroll = ttk.Scrollbar(viewport, orient="vertical", command=canvas.yview)
    scroll.grid(row=0, column=1, sticky="ns")
    canvas.configure(yscrollcommand=scroll.set)
    panel = ttk.Frame(canvas, style="White.TFrame", padding=(28, 0))
    content = canvas.create_window(0, 0, window=panel, anchor="nw")

    def update_scroll(event=None):
        height = panel.winfo_reqheight()
        canvas.configure(scrollregion=(0, 0, canvas.winfo_width(), max(height, canvas.winfo_height())))
        if height > canvas.winfo_height():
            scroll.grid()
        else:
            scroll.grid_remove()
            canvas.yview_moveto(0)

    def resize_content(event):
        canvas.itemconfigure(content, width=event.width)
        update_scroll()

    canvas.bind("<Configure>", resize_content)
    panel.bind("<Configure>", update_scroll)
    window.bind("<MouseWheel>", lambda event: canvas.yview_scroll(-int(event.delta / 120), "units"))

    def section(title, parent=panel):
        area = ttk.Frame(parent, style="White.TFrame")
        area.pack(fill="x", pady=(0, 16))
        tk.Label(area, text=title, bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 6))
        tk.Frame(area, bg="#3a3f48", height=1).pack(fill="x")
        return area

    def row(area, title, description):
        container = ttk.Frame(area, style="White.TFrame", padding=(0, 10))
        container.pack(fill="x")
        container.columnconfigure(0, weight=1)
        ttk.Label(container, text=title, style="White.TLabel",
                  font=("Segoe UI", 10, "bold"), wraplength=440,
                  justify='left').grid(row=0, column=0, sticky="w")
        if description:
            label = {"textvariable": description} if isinstance(description, tk.StringVar) else {"text": description}
            ttk.Label(container, **label, style="WhiteMuted.TLabel",
                      font=("Segoe UI", 9), wraplength=440, justify="left").grid(row=1, column=0, sticky="w", pady=(3, 0))
        controls = ttk.Frame(container, style="White.TFrame")
        controls.grid(row=0, column=1, rowspan=2 if description else 1, sticky="e", padx=(20, 0))
        return controls

    monitoring = section("MONITOROWANIE")
    controls = row(monitoring, "Incydenty (INC)", "Odstęp między kolejnymi sprawdzeniami list incydentów.")
    app.interval = tk.StringVar(value=str(settings.get("interval", 60)))
    app.interval_entry = ttk.Entry(controls, textvariable=app.interval, width=6, justify="center")
    app.interval_entry.pack(side="left")
    ttk.Label(controls, text="sekund", style="WhiteMuted.TLabel").pack(side="left", padx=(8, 0))

    controls = row(monitoring, "Zgłoszenia katalogowe (SCTASK, REQ, RITM)", "Odstęp między kolejnymi sprawdzeniami list katalogowych.")
    app.task_interval = tk.StringVar(value=str(settings.get("task_interval", DEFAULT_TASK_INTERVAL)))
    app.task_interval_entry = ttk.Entry(controls, textvariable=app.task_interval, width=6, justify="center")
    app.task_interval_entry.pack(side="left")
    ttk.Label(controls, text="sekund", style="WhiteMuted.TLabel").pack(side="left", padx=(8, 0))

    if getattr(app, 'session', None) is not None:
        app.schedule_interval_status = tk.StringVar(master=window)
        interval_autosave = app.schedule_interval_autosave = ScheduleIntervalAutosave(
            app.root, (app.interval, app.task_interval), app.schedule_interval_status, app.save_schedule_intervals)
        ttk.Label(footer, textvariable=app.schedule_interval_status, style='WhiteMuted.TLabel',
                  wraplength=330).pack(side='left', padx=(12, 0))

        def cancel_on_destroy(event):
            if event.widget is window:
                interval_autosave.cancel()

        window.bind('<Destroy>', cancel_on_destroy, add='+')

    controls = row(monitoring, "Automatycznie zaktualizuj dashboard przy starcie monitoringu",
                   "Pobierz dane dashboardu po zalogowaniu do ServiceNow. Kolejne odczyty uruchamiaj przyciskiem Aktualizuj.")
    app.dashboard_auto_refresh = tk.BooleanVar(value=settings.get('dashboard_auto_refresh', False))
    Toggle(controls, app.dashboard_auto_refresh).pack(side='right')

    notifications = section("POWIADOMIENIA")
    controls = row(notifications, "Powiadomienia Windows", "Powiadomienia systemowe i sygnał dźwiękowy.")
    app.notify = tk.BooleanVar(value=settings.get("notify", False))
    app.notify_check = Toggle(controls, app.notify)
    app.notify_check.pack(side="right")
    controls = row(notifications, "Microsoft Teams", "Wysyłanie powiadomień do skonfigurowanego kanału.")
    app.teams_enabled = tk.BooleanVar(value=settings.get("teams_enabled", False))
    app.teams_check = Toggle(controls, app.teams_enabled)
    app.teams_check.pack(side="right")
    RoundedButton(controls, text="Konfiguruj", command=app.configure_teams).pack(side="right", padx=(0, 14))
    controls = row(notifications, "Google Chat", "Wysyłanie powiadomień do przestrzeni przez webhook.")
    app.google_chat_enabled = tk.BooleanVar(value=settings.get("google_chat_enabled", False))
    Toggle(controls, app.google_chat_enabled).pack(side="right")
    RoundedButton(controls, text="Konfiguruj", command=app.configure_google_chat).pack(side="right", padx=(0, 14))
    controls = row(notifications, "Powiadomienia o zagrożeniu SLA",
                   "Wysyłaj alerty przez włączone kanały. Wyłączanie alertów jest niezalecane.")
    app.notify_threatened = tk.BooleanVar(value=settings.get("notify_threatened", True))
    Toggle(controls, app.notify_threatened).pack(side="right")

    startup = section("URUCHAMIANIE I OKNO APLIKACJI")
    app.start_with_windows = tk.BooleanVar(value=app.windows_startup in ("current", "repaired"))
    app.startup_status_text = tk.StringVar(value=app.windows_startup_description())
    # Keep registration support internally; Windows autostart is not exposed in UI.
    for key, title, description in (
        ("start_monitoring", "Uruchom monitoring przy starcie aplikacji", "Wymaga włączonego filtra; może wymagać zalogowania do ServiceNow."),
        ("start_minimized", "Uruchom aplikację zminimalizowaną", "Rozpoczynaj pracę ze zminimalizowanym oknem."),
    ):
        controls = row(startup, title, description)
        variable = tk.BooleanVar(value=settings.get(key, False))
        setattr(app, key, variable)
        Toggle(controls, variable).pack(side="right")
    controls = row(startup, "Minimalizacja do zasobnika", "Ukrywaj zminimalizowane okno w zasobniku systemowym.")
    app.minimize_to_tray = tk.BooleanVar(value=settings.get("minimize_to_tray", False))
    app.minimize_check = Toggle(controls, app.minimize_to_tray)
    app.minimize_check.pack(side="right")

    browser = section("PRZEGLĄDARKA I LOGOWANIE")
    controls = row(browser, "Automatyczne logowanie", "Używaj zapamiętanego konta, gdy jest to możliwe.")
    app.auto_login = tk.BooleanVar(value=settings.get("auto_login", True))
    app.auto_login_check = Toggle(controls, app.auto_login)
    app.auto_login_check.pack(side="right")
    if not getattr(app, 'session', None):
        controls = row(browser, "Minimalizacja przeglądarki", "Minimalizuj Chromium podczas sprawdzania filtrów. Automatyczne logowanie i dashboard działają w tle; ręczne logowanie przywołuje przeglądarkę.")
        app.minimize_browser = tk.BooleanVar(value=settings.get("minimize_browser", True))
        app.minimize_browser_check = Toggle(controls, app.minimize_browser)
        app.minimize_browser_check.pack(side="right")

        controls = row(browser, "Całkowicie ukryj okno przeglądarki", "Ukrywaj Chromium także na pasku zadań podczas sprawdzania filtrów. Automatyczne logowanie i dashboard pozostają widoczne w tle; ręczne logowanie przechodzi na pierwszy plan.")
        app.hide_browser = tk.BooleanVar(value=settings.get("hide_browser", True))
        Toggle(controls, app.hide_browser).pack(side="right")

    data = section("DANE APLIKACJI")
    controls = row(data, "Przywrócenie stanu początkowego",
                   "Usuń lokalne dane monitora i zamknij aplikację.")
    RoundedButton(controls, text="Usuń wszystkie dane aplikacji…", command=app.request_data_reset).pack(side="right")
