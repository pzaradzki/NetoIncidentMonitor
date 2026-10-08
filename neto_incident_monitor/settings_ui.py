"""Settings window with aligned controls and descriptive option groups."""
import tkinter as tk
from tkinter import ttk

from neto_incident_monitor.theme import SURFACE, MUTED
from neto_incident_monitor.widgets import RoundedButton, Toggle


def build_settings(app, settings):
    window = app.settings_window
    panel = ttk.Frame(window, style="White.TFrame", padding=(28, 24))
    panel.pack(fill="both", expand=True)
    window.minsize(700, 600)
    ttk.Label(panel, text="Ustawienia", style="White.TLabel",
              font=("Segoe UI", 18, "bold")).pack(anchor="w")
    ttk.Label(panel, text="Dostosuj monitorowanie, powiadomienia i działanie aplikacji.",
              style="WhiteMuted.TLabel").pack(anchor="w", pady=(4, 22))

    def section(title):
        area = ttk.Frame(panel, style="White.TFrame")
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
                  font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(container, text=description, style="WhiteMuted.TLabel",
                  font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", pady=(3, 0))
        controls = ttk.Frame(container, style="White.TFrame")
        controls.grid(row=0, column=1, rowspan=2, sticky="e", padx=(20, 0))
        return controls

    monitoring = section("MONITOROWANIE")
    controls = row(monitoring, "Częstotliwość odczytu", "Odstęp między kolejnymi sprawdzeniami list.")
    app.interval = tk.StringVar(value=str(settings.get("interval", 60)))
    app.interval_entry = ttk.Entry(controls, textvariable=app.interval, width=6, justify="center")
    app.interval_entry.pack(side="left")
    ttk.Label(controls, text="sekund", style="WhiteMuted.TLabel").pack(side="left", padx=(8, 0))

    notifications = section("POWIADOMIENIA")
    controls = row(notifications, "Powiadomienia Windows", "Powiadomienia systemowe i sygnał dźwiękowy.")
    app.notify = tk.BooleanVar(value=settings.get("notify", True))
    app.notify_check = Toggle(controls, app.notify)
    app.notify_check.pack(side="right")
    controls = row(notifications, "Microsoft Teams", "Wysyłanie powiadomień do skonfigurowanego kanału.")
    app.teams_enabled = tk.BooleanVar(value=settings.get("teams_enabled", False))
    app.teams_check = Toggle(controls, app.teams_enabled)
    app.teams_check.pack(side="right")
    RoundedButton(controls, text="Konfiguruj", command=app.configure_teams).pack(side="right", padx=(0, 14))

    application = section("APLIKACJA I LOGOWANIE")
    controls = row(application, "Minimalizacja do zasobnika", "Kontynuuj pracę w tle po zminimalizowaniu okna.")
    app.minimize_to_tray = tk.BooleanVar(value=settings.get("minimize_to_tray", False))
    app.minimize_check = Toggle(controls, app.minimize_to_tray)
    app.minimize_check.pack(side="right")
    controls = row(application, "Automatyczne logowanie", "Używaj zapamiętanego konta, gdy jest to możliwe.")
    app.auto_login = tk.BooleanVar(value=settings.get("auto_login", False))
    app.auto_login_check = Toggle(controls, app.auto_login)
    app.auto_login_check.pack(side="right")
    controls = row(application, "Minimalizacja przeglądarki", "Minimalizuj okno Chromium po zalogowaniu.")
    app.minimize_browser = tk.BooleanVar(value=settings.get("minimize_browser", settings.get("auto_login", False)))
    app.minimize_browser_check = Toggle(controls, app.minimize_browser)
    app.minimize_browser_check.pack(side="right")

    footer = ttk.Frame(panel, style="White.TFrame")
    footer.pack(fill="x", side="bottom", pady=(4, 0))
    RoundedButton(footer, text="Zamknij", command=window.withdraw).pack(side="right")
