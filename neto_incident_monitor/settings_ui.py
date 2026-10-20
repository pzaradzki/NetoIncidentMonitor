"""Settings window with aligned controls and descriptive option groups."""
import tkinter as tk
from tkinter import ttk

from neto_incident_monitor.theme import SURFACE, MUTED
from neto_incident_monitor.widgets import RoundedButton, Toggle


def build_settings(app, settings):
    window = app.settings_window
    window.minsize(700, 600)
    window.geometry("700x700")
    header = ttk.Frame(window, style="White.TFrame", padding=(28, 24, 28, 0))
    header.pack(fill="x")
    ttk.Label(header, text="Ustawienia", style="White.TLabel",
              font=("Segoe UI", 18, "bold")).pack(anchor="w")
    ttk.Label(header, text="Dostosuj monitorowanie, powiadomienia i działanie aplikacji.",
              style="WhiteMuted.TLabel").pack(anchor="w", pady=(4, 22))
    footer = ttk.Frame(window, style="White.TFrame", padding=(28, 12, 28, 24))
    footer.pack(fill="x", side="bottom")
    RoundedButton(footer, text="Zamknij", command=window.withdraw).pack(side="right")
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
                  font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        if description:
            ttk.Label(container, text=description, style="WhiteMuted.TLabel",
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

    controls = row(monitoring, "Zadania katalogowe (SCTASK)", "Odstęp między kolejnymi sprawdzeniami list zadań katalogowych.")
    app.task_interval = tk.StringVar(value=str(settings.get("task_interval", 3600)))
    app.task_interval_entry = ttk.Entry(controls, textvariable=app.task_interval, width=6, justify="center")
    app.task_interval_entry.pack(side="left")
    ttk.Label(controls, text="sekund", style="WhiteMuted.TLabel").pack(side="left", padx=(8, 0))

    notifications = section("POWIADOMIENIA")
    ttk.Label(notifications, text="Przełączniki globalne. Powiadomienia poszczególnych filtrów ustawisz\nprzez ikonę dzwonka przy filtrze.",
              style="WhiteMuted.TLabel").pack(anchor="w", pady=(8, 2))
    controls = row(notifications, "Powiadomienia Windows", "Powiadomienia systemowe i sygnał dźwiękowy.")
    app.notify = tk.BooleanVar(value=settings.get("notify", True))
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

    startup = section("URUCHAMIANIE I OKNO APLIKACJI")
    for key, title, description in (
        ("start_with_windows", "Uruchom aplikację przy starcie systemu", "Uruchamiaj aplikację po zalogowaniu do Windows."),
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
    app.auto_login = tk.BooleanVar(value=settings.get("auto_login", False))
    app.auto_login_check = Toggle(controls, app.auto_login)
    app.auto_login_check.pack(side="right")
    controls = row(browser, "Minimalizacja przeglądarki", "Uruchamiaj Chromium zminimalizowane. Pokazuj okno, gdy potrzebne jest ręczne logowanie.")
    app.minimize_browser = tk.BooleanVar(value=settings.get("minimize_browser", settings.get("auto_login", False)))
    app.minimize_browser_check = Toggle(controls, app.minimize_browser)
    app.minimize_browser_check.pack(side="right")

    controls = row(browser, "Całkowicie ukryj okno przeglądarki", "Ukrywaj Chromium także na pasku zadań. Pokazuj okno, gdy potrzebne jest ręczne logowanie. Zmiana działa po ponownym uruchomieniu monitoringu.")
    app.hide_browser = tk.BooleanVar(value=settings.get("hide_browser", False))
    Toggle(controls, app.hide_browser).pack(side="right")

    display = section("LISTA INCYDENTÓW")
    controls = row(display, "Podświetlaj nieprzeczytane incydenty", "")
    app.highlight_unread = tk.BooleanVar(value=settings.get("highlight_unread", False))
    Toggle(controls, app.highlight_unread).pack(side="right")
