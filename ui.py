"""Presentation layer for the local incident monitor."""
import tkinter as tk
from tkinter import ttk
from widgets import Toggle, RoundedButton, FilterList, TabTooltip
from PIL import Image, ImageDraw, ImageTk

from theme import BG, SURFACE, TEXT, MUTED, ACCENT


def build_ui(app, settings):
    root = app.root
    from window_style import install_window_style
    install_window_style(root)
    root.title("Neto Incident Monitor")
    saved_geometry = settings.get("window_layout", {}).get("geometry", "1440x850")
    import re
    root.geometry(saved_geometry if isinstance(saved_geometry, str) and re.fullmatch(r"\d+x\d+(?:[+-]\d+[+-]\d+)?", saved_geometry) else "1440x850")
    root.minsize(1120, 680)
    root.configure(background=BG)
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", font=("Segoe UI", 10), background=BG, foreground=TEXT)
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("White.TFrame", background=SURFACE)
    style.configure("White.TLabel", background=SURFACE)
    style.configure("Muted.TLabel", foreground=MUTED)
    style.configure("WhiteMuted.TLabel", background=SURFACE, foreground=MUTED)
    style.configure("Title.TLabel", font=("Segoe UI", 23, "bold"))
    style.configure("Section.TLabel", font=("Segoe UI", 11, "bold"))
    style.configure("TButton", padding=(12, 8), background="#343840", borderwidth=0)
    style.map("TButton", background=[("active", "#424751"), ("disabled", "#292c33")],
              foreground=[("disabled", "#707782")])
    style.configure("Primary.TButton", background=ACCENT, foreground=TEXT)
    style.map("Primary.TButton", background=[("disabled", "#493039"), ("active", "#f04b59")],
              foreground=[("disabled", "#9b737c"), ("!disabled", TEXT)])
    style.configure("TEntry", padding=6, fieldbackground=SURFACE, foreground=TEXT,
                    insertcolor=TEXT, bordercolor="#484e58", lightcolor=SURFACE, darkcolor=SURFACE)
    style.map("TEntry", bordercolor=[("focus", "#929dab")],
              lightcolor=[("focus", "#929dab")], darkcolor=[("focus", "#929dab")],
              fieldbackground=[("disabled", "#292c33")], foreground=[("disabled", "#747b88")])
    style.configure("TSeparator", background="#424751")
    style.map("Treeview.Heading", background=[("active", "#424751")])
    style.configure("TCheckbutton", background=BG, foreground=TEXT, padding=(0, 4),
                    indicatorbackground=SURFACE, indicatorforeground=ACCENT)
    style.map("TCheckbutton", background=[("active", BG)],
              indicatorbackground=[("selected", ACCENT), ("active", "#424751")])
    root.checkbox_images = []
    for checked in (False, True):
        picture = Image.new("RGB", (24 * 4, 24 * 4), BG)
        draw = ImageDraw.Draw(picture)
        draw.rounded_rectangle((2 * 4, 3 * 4, 19 * 4, 20 * 4), radius=4 * 4,
                               fill=ACCENT if checked else SURFACE,
                               outline=ACCENT if checked else "#737c8b", width=4)
        if checked:
            draw.line([(6 * 4, 11 * 4), (9 * 4, 14 * 4), (15 * 4, 8 * 4)], fill=TEXT, width=2 * 4)
        root.checkbox_images.append(ImageTk.PhotoImage(picture.resize((24, 24), Image.Resampling.LANCZOS), master=root))
    style.element_create("AppCheck.indicator", "image", root.checkbox_images[0],
                         ("selected", root.checkbox_images[1]), sticky="w")
    style.layout("App.TCheckbutton", [("Checkbutton.padding", {"sticky": "nswe", "children": [
        ("AppCheck.indicator", {"side": "left", "sticky": ""}),
        ("Checkbutton.focus", {"side": "left", "sticky": "w", "children": [
            ("Checkbutton.label", {"sticky": "nswe"})]})]})])
    style.configure("App.TCheckbutton", background=BG, foreground=TEXT, padding=(0, 2))
    style.map("App.TCheckbutton", background=[("active", BG)], foreground=[("active", TEXT)])
    style.configure("Clean.TNotebook", background=BG, borderwidth=0,
                    bordercolor=SURFACE, lightcolor=SURFACE, darkcolor=SURFACE,
                    tabmargins=(0, 0, 0, 10))
    # Identical image dimensions and no native tab border: selecting a tab
    # changes only its color, without the clam theme's raised-tab geometry.
    root.tab_images = []
    for color in ("#30343c", ACCENT):
        picture = Image.new("RGB", (210 * 4, 42 * 4), BG)
        draw = ImageDraw.Draw(picture)
        draw.rounded_rectangle((0, 0, 206 * 4, 42 * 4 - 1), radius=8 * 4, fill=color)
        root.tab_images.append(ImageTk.PhotoImage(picture.resize((210, 42), Image.Resampling.LANCZOS), master=root))
    style.element_create("CleanNotebook.tab", "image", root.tab_images[0],
                         ("selected", root.tab_images[1]), border=8, sticky="nsew")
    style.layout("Clean.TNotebook.Tab", [("CleanNotebook.tab", {"sticky": "nswe", "children": [
        ("Notebook.padding", {"sticky": "nswe", "children": [("Notebook.label", {"sticky": ""})]})]})])
    style.configure("Clean.TNotebook.Tab", padding=(12, 4), foreground=MUTED, font=("Segoe UI", 10))
    style.map("Clean.TNotebook.Tab", foreground=[("selected", TEXT)],
              padding=[("selected", (12, 4)), ("!selected", (12, 4))],
              expand=[("selected", (0, 0, 0, 0)), ("!selected", (0, 0, 0, 0))])
    style.configure("Treeview", background=SURFACE, fieldbackground=SURFACE, foreground=TEXT,
                    rowheight=38, borderwidth=0, font=("Segoe UI", 10),
                    lightcolor=SURFACE, darkcolor=SURFACE, bordercolor=SURFACE)
    style.configure("Treeview.Heading", background="#30343c", foreground=MUTED,
                    padding=(10, 12), font=("Segoe UI", 9, "bold"), relief="flat")
    style.map("Treeview", background=[("selected", "#513039")], foreground=[("selected", "#ffe3e6")])
    style.configure("Filters.Treeview", rowheight=40, background=SURFACE, fieldbackground=SURFACE)
    style.configure("SidebarTitle.TLabel", background=SURFACE, font=("Segoe UI", 11, "bold"))
    style.configure("Sidebar.TButton", background="#392930", foreground="#ef6672", padding=(10, 9))
    style.map("Sidebar.TButton", background=[("active", "#513039"), ("disabled", "#292c33")],
              foreground=[("disabled", "#747b88")])
    style.configure("Quiet.TButton", background=SURFACE, foreground=MUTED, padding=(6, 8))
    style.map("Quiet.TButton", background=[("active", "#30343c"), ("disabled", SURFACE)],
              foreground=[("disabled", "#747b88")])
    for orientation in ("Vertical", "Horizontal"):
        scrollbar_style = f"{orientation}.TScrollbar"
        style.configure(scrollbar_style, background="#424751", troughcolor=SURFACE,
                        borderwidth=0, arrowsize=13, gripcount=0,
                        lightcolor="#424751", darkcolor="#424751", bordercolor="#424751")
        for option in ("background", "lightcolor", "darkcolor", "bordercolor"):
            style.map(scrollbar_style, **{option: [("active", "#606875"), ("!active", "#424751")]})

    header = ttk.Frame(root, padding=(24, 20, 24, 14))
    header.pack(fill="x")
    from runtime_paths import ROOT
    logo = Image.open(ROOT / "assets" / "netology-logo.png")
    logo = logo.resize((155, 32), Image.Resampling.LANCZOS)
    root.brand_logo = ImageTk.PhotoImage(logo, master=root)
    ttk.Label(header, image=root.brand_logo).pack(side="left", anchor="n", pady=(10, 0), padx=(0, 24))
    title = ttk.Frame(header)
    title.pack(side="left")
    ttk.Label(title, text="Incident Monitor", style="Title.TLabel").pack(anchor="w")
    app.controls = ttk.Frame(header)
    app.controls.pack(side="right")
    app.start_button = RoundedButton(app.controls, text="Uruchom monitoring", icon="play", command=app.start,
                                     primary=True, background=BG)
    app.start_button.pack(side="left", padx=4)
    app.stop_button = RoundedButton(app.controls, text="Zatrzymaj", icon="stop", command=app.stop.set, background=BG)
    app.stop_button.configure(state="disabled")
    app.stop_button.pack(side="left", padx=4)
    app.check_button = RoundedButton(app.controls, text="Sprawdź teraz", icon="refresh", command=app.check_now, background=BG)
    app.check_button.configure(state="disabled")
    app.check_button.pack(side="left", padx=4)

    def show_settings():
        window = app.settings_window
        window.update_idletasks()
        x = max(0, (root.winfo_screenwidth() - window.winfo_reqwidth()) // 2)
        y = max(0, (root.winfo_screenheight() - window.winfo_reqheight()) // 2)
        window.geometry(f"+{x}+{y}")
        window.deiconify()
        window.lift()
    RoundedButton(app.controls, text="Ustawienia", icon="gear", command=show_settings,
                  background=BG).pack(side="left", padx=4)

    body = ttk.Frame(root, padding=(24, 0, 24, 20))
    body.pack(fill="both", expand=True)
    body.columnconfigure(2, weight=1)
    body.rowconfigure(0, weight=1)
    sidebar_area = ttk.Frame(body, style="White.TFrame")
    sidebar_area.grid(row=0, column=0, sticky="ns")
    splitter = tk.Frame(body, width=20, background=BG, cursor="sb_h_double_arrow")
    splitter.grid(row=0, column=1, sticky="ns")
    sidebar_area.rowconfigure(0, weight=1)
    app.sidebar_canvas = canvas = tk.Canvas(sidebar_area, width=235, background=SURFACE,
                                            highlightthickness=0, borderwidth=0)
    canvas.grid(row=0, column=0, sticky="ns")
    scroll = ttk.Scrollbar(sidebar_area, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scroll.set)
    sidebar = ttk.Frame(canvas, style="White.TFrame", padding=16)
    sidebar_window = canvas.create_window((0, 0), window=sidebar, anchor="nw", width=235)
    sidebar.rowconfigure(1, weight=1)
    sidebar.columnconfigure(0, weight=1)

    def resize_sidebar(_=None):
        canvas.itemconfigure(sidebar_window, width=canvas.winfo_width())
        canvas.itemconfigure(sidebar_window, height=max(sidebar.winfo_reqheight(), canvas.winfo_height()))
        canvas.configure(scrollregion=canvas.bbox("all"))
        if sidebar.winfo_reqheight() > canvas.winfo_height():
            scroll.grid(row=0, column=1, sticky="ns")
        else:
            scroll.grid_remove()
            canvas.yview_moveto(0)

    sidebar.bind("<Configure>", resize_sidebar)
    canvas.bind("<Configure>", resize_sidebar)
    list_header = ttk.Frame(sidebar, style="White.TFrame")
    list_header.grid(row=0, column=0, sticky="ew", pady=(2, 12))
    ttk.Label(list_header, text="Monitorowane filtry", style="SidebarTitle.TLabel").pack(side="left")
    app.filter_count = tk.StringVar(value="0")
    tk.Label(list_header, textvariable=app.filter_count, bg="#392930", fg=ACCENT,
             font=("Segoe UI", 9, "bold"), padx=7, pady=2).pack(side="right")
    lists = ttk.Frame(sidebar, style="White.TFrame")
    lists.grid(row=1, column=0, sticky="nsew")
    lists.rowconfigure(1, weight=1)
    lists.columnconfigure(0, weight=1)
    app.filter_table = FilterList(lists)
    app.filter_table.grid(row=1, column=0, sticky="nsew")
    filter_scroll = app.filter_scroll = ttk.Scrollbar(lists, orient="vertical", command=app.filter_table.yview)
    filter_scroll.grid(row=1, column=1, sticky="ns")
    app.filter_table.configure(yscrollcommand=filter_scroll.set)
    filter_actions = ttk.Frame(sidebar, style="White.TFrame")
    filter_actions.grid(row=2, column=0, sticky="ew", pady=(10, 0))
    filter_actions.columnconfigure(0, weight=1)
    filter_actions.columnconfigure(1, weight=1)
    app.filter_buttons = []
    for i, (text, callback) in enumerate([
        ("+  Dodaj filtr", lambda: app.edit_filter()), ("Edytuj", lambda: app.edit_filter(True)), ("Usuń", app.remove_filter)
    ]):
        button = RoundedButton(filter_actions, text=text, command=callback, primary=i == 0)
        if i == 0:
            button.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        else:
            button.grid(row=1, column=i - 1, sticky="ew", padx=(0, 4) if i == 1 else (4, 0))
        app.filter_buttons.append(button)
    app.refresh_filters()
    app.settings_window = tk.Toplevel(root)
    app.settings_window.withdraw()
    app.settings_window.title("Ustawienia")
    app.settings_window.configure(background=SURFACE)
    app.settings_window.resizable(False, False)
    app.settings_window.transient(root)
    app.settings_window.protocol("WM_DELETE_WINDOW", app.settings_window.withdraw)
    app.settings_window.bind("<Escape>", lambda event: app.settings_window.withdraw())
    settings_panel = ttk.Frame(app.settings_window, style="White.TFrame", padding=24)
    settings_panel.pack(fill="both", expand=True)
    app.settings_window.minsize(620, 420)
    settings_panel.columnconfigure(0, weight=1, uniform="settings")
    settings_panel.columnconfigure(2, weight=1, uniform="settings")
    settings_panel.rowconfigure(1, weight=1)
    ttk.Label(settings_panel, text="Ustawienia", font=("Segoe UI", 17, "bold"),
              style="White.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 24))
    monitoring_settings = ttk.Frame(settings_panel, style="White.TFrame")
    monitoring_settings.grid(row=1, column=0, sticky="nsew", padx=(0, 22))
    monitoring_settings.columnconfigure(0, weight=1)
    ttk.Separator(settings_panel, orient="vertical").grid(row=1, column=1, sticky="ns")
    browser_settings = ttk.Frame(settings_panel, style="White.TFrame")
    browser_settings.grid(row=1, column=2, sticky="nsew", padx=(22, 0))
    browser_settings.columnconfigure(0, weight=1)
    ttk.Label(monitoring_settings, text="Monitoring i powiadomienia",
              style="SidebarTitle.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
    ttk.Label(browser_settings, text="Aplikacja i przeglądarka",
              style="SidebarTitle.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
    interval_box = ttk.Frame(monitoring_settings, style="White.TFrame")
    interval_box.grid(row=1, column=0, sticky="ew", pady=(12, 8))
    ttk.Label(interval_box, text="Częstotliwość odczytu", style="WhiteMuted.TLabel", font=("Segoe UI", 9)).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
    app.interval = tk.StringVar(value=str(settings.get("interval", 60)))
    app.interval_entry = ttk.Entry(interval_box, textvariable=app.interval, width=7, justify="center")
    app.interval_entry.grid(row=1, column=0, sticky="w")
    ttk.Label(interval_box, text="sekund", style="WhiteMuted.TLabel").grid(row=1, column=1, sticky="w", padx=10)
    app.notify = tk.BooleanVar(value=settings.get("notify", True))
    alerts = ttk.Frame(monitoring_settings, style="White.TFrame")
    alerts.grid(row=2, column=0, sticky="ew", pady=(24, 0))
    ttk.Label(alerts, text="Powiadomienia", style="White.TLabel").grid(row=0, column=0, sticky="w")
    ttk.Label(alerts, text="Windows i dźwięk", style="WhiteMuted.TLabel", font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w")
    alerts.columnconfigure(0, weight=1)
    app.notify_check = Toggle(alerts, app.notify)
    app.notify_check.grid(row=0, column=1, rowspan=2, sticky="e", padx=(8, 0))
    teams = ttk.Frame(monitoring_settings, style="White.TFrame")
    teams.grid(row=3, column=0, sticky="ew", pady=(24, 0))
    teams.columnconfigure(0, weight=1)
    ttk.Label(teams, text="Powiadomienia Teams", style="White.TLabel", font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w")
    app.teams_enabled = tk.BooleanVar(value=settings.get("teams_enabled", False))
    app.teams_check = Toggle(teams, app.teams_enabled)
    app.teams_check.grid(row=0, column=1, sticky="e")
    RoundedButton(teams, text="Konfiguruj", command=app.configure_teams).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 0))
    minimize = ttk.Frame(browser_settings, style="White.TFrame")
    minimize.grid(row=1, column=0, sticky="ew", pady=(20, 0))
    ttk.Label(minimize, text="Minimalizuj", style="White.TLabel").grid(row=0, column=0, sticky="w")
    ttk.Label(minimize, text="do zasobnika", style="WhiteMuted.TLabel", font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w")
    minimize.columnconfigure(0, weight=1)
    app.minimize_to_tray = tk.BooleanVar(value=settings.get("minimize_to_tray", False))
    app.minimize_check = Toggle(minimize, app.minimize_to_tray)
    app.minimize_check.grid(row=0, column=1, rowspan=2, sticky="e", padx=(8, 0))
    login = ttk.Frame(browser_settings, style="White.TFrame")
    login.grid(row=2, column=0, sticky="ew", pady=(20, 0))
    login.columnconfigure(0, weight=1)
    ttk.Label(login, text="Automatyczne", style="White.TLabel").grid(row=0, column=0, sticky="w")
    ttk.Label(login, text="logowanie", style="WhiteMuted.TLabel").grid(row=1, column=0, sticky="w")
    app.auto_login = tk.BooleanVar(value=settings.get("auto_login", False))
    app.auto_login_check = Toggle(login, app.auto_login)
    app.auto_login_check.grid(row=0, column=1, rowspan=2, sticky="e")
    browser = ttk.Frame(browser_settings, style="White.TFrame")
    browser.grid(row=3, column=0, sticky="ew", pady=(20, 0))
    browser.columnconfigure(0, weight=1)
    ttk.Label(browser, text="Minimalizuj przeglądarkę", wraplength=220, style="White.TLabel", font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w")
    ttk.Label(browser, text="po zalogowaniu", wraplength=220, style="WhiteMuted.TLabel", font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w")
    app.minimize_browser = tk.BooleanVar(value=settings.get("minimize_browser", settings.get("auto_login", False)))
    app.minimize_browser_check = Toggle(browser, app.minimize_browser)
    app.minimize_browser_check.grid(row=0, column=1, rowspan=2, sticky="e", padx=(8, 0))

    RoundedButton(settings_panel, text="Zamknij", command=app.settings_window.withdraw).grid(
        row=2, column=2, sticky="e", pady=(28, 0))

    main = ttk.Frame(body)
    main.grid(row=0, column=2, sticky="nsew")
    def align_header_title(event=None):
        offset = max(0, main.winfo_rootx() - header.winfo_rootx() - 24 - 155 - 24 - 6)
        title.pack_configure(padx=(offset, 0))

    main.bind("<Configure>", align_header_title, add="+")
    sidebar_area.bind("<Configure>", align_header_title, add="+")
    root.after_idle(align_header_title)
    main.columnconfigure(0, weight=1)
    main.rowconfigure(2, weight=1)
    app.phase = tk.StringVar(value="● Gotowy do uruchomienia")
    state = ttk.Frame(main, padding=(0, 0, 0, 12))
    state.grid(row=0, column=0, sticky="ew")
    app.phase_label = ttk.Label(state, textvariable=app.phase, font=("Segoe UI", 10, "bold"), foreground=MUTED)
    app.phase_label.pack(side="left")
    app.countdown = tk.StringVar(value="Następne sprawdzenie: —")
    ttk.Label(state, textvariable=app.countdown, style="Muted.TLabel").pack(side="right")

    app.current_count = tk.StringVar(value="0")
    app.new_count = tk.StringVar(value="0")
    app.unread_count = tk.StringVar(value="0")

    toolbar = ttk.Frame(main)
    toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 10))
    toolbar.pack_propagate(False)
    actions = ttk.Frame(main)
    RoundedButton(actions, text="Kolumny", icon="columns", command=app.configure_columns, background=BG).pack(side="right", padx=(8, 0))
    RoundedButton(actions, text="Wyczyść historię", icon="trash", command=app.clear_history, background=BG).pack(side="right", padx=(8, 0))
    RoundedButton(actions, text="Przeczytaj wszystkie", icon="checks", command=app.mark_all, background=BG).pack(side="right")
    app.tabs = ttk.Notebook(main, style="Clean.TNotebook")
    app.tabs.grid(row=2, column=0, sticky="nsew")
    current = ttk.Frame(app.tabs, style="White.TFrame")
    history = ttk.Frame(app.tabs, style="White.TFrame")
    app.tabs.add(current, text="Bieżące incydenty")
    app.tabs.add(history, text="Historia zgłoszeń")
    app.history_tooltip = TabTooltip(app.tabs, 1,
        "Lista wcześniej wykrytych zgłoszeń. Pokazuje dane zapisane w chwili wykrycia — mogą różnić się od aktualnych danych w ServiceNow.")
    def align_actions(event=None):
        # The incident pane always fits both tabs and the action buttons.
        required = sum(image.width() for image in app.root.tab_images) + actions.winfo_reqwidth() + 12
        body.columnconfigure(2, minsize=required)
        root.minsize(48 + 235 + 20 + required, 680)
        actions.place(in_=app.tabs, relx=1, x=0, y=3, anchor="ne")
        toolbar.configure(height=1)
        actions.lift()

    app.tabs.bind("<Configure>", align_actions)
    desired_width = max(235, int(settings.get("sidebar_width", 235)))
    drag_origin = None

    def fit_sidebar(event=None):
        required = sum(image.width() for image in root.tab_images) + actions.winfo_reqwidth() + 12
        maximum = max(235, body.winfo_width() - 48 - 20 - required)
        canvas.configure(width=min(desired_width, maximum))

    def start_resize(event):
        nonlocal drag_origin
        drag_origin = (event.x_root, canvas.winfo_width())
        splitter.configure(background="#373c46")

    def drag_resize(event):
        nonlocal desired_width
        if drag_origin is None:
            return
        required = sum(image.width() for image in root.tab_images) + actions.winfo_reqwidth() + 12
        maximum = max(235, body.winfo_width() - 48 - 20 - required)
        desired_width = max(235, min(maximum, drag_origin[1] + event.x_root - drag_origin[0]))
        fit_sidebar()

    def finish_resize(event):
        nonlocal drag_origin
        if drag_origin is not None:
            drag_resize(event)
            drag_origin = None
            splitter.configure(background=BG)
            app.save_sidebar_width(desired_width)

    splitter.bind("<ButtonPress-1>", start_resize)
    splitter.bind("<B1-Motion>", drag_resize)
    splitter.bind("<ButtonRelease-1>", finish_resize)
    body.bind("<Configure>", fit_sidebar, add="+")
    root.after_idle(align_actions)
    root.after_idle(fit_sidebar)
    app.splitter = splitter
    app.current_table = app.make_table(current, False)
    app.table = app.make_table(history, True)
    app.current_table.bind("<Double-1>", app.open_incident)
    app.table.bind("<Double-1>", app.open_incident)
    app.last_read = tk.StringVar(value="Ostatnia aktualizacja: —")
    app.status = tk.StringVar(value="Uruchom monitoring i zaloguj się w otwartej przeglądarce.")
