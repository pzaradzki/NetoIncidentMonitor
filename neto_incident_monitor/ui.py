"""Presentation layer for the local incident monitor."""
import tkinter as tk
from tkinter import ttk
from neto_incident_monitor.widgets import Toggle, RoundedButton, DashboardButton, FilterList, TabTooltip, update_grid_scrollbar
from PIL import Image, ImageDraw, ImageTk

from neto_incident_monitor.theme import BG, SURFACE, TEXT, MUTED, ACCENT, VIEW_TITLE_FONT
from neto_incident_monitor.settings_ui import SETTINGS_WINDOW_SIZE, build_settings


MIN_SIDEBAR_WIDTH = 235
DEFAULT_SIDEBAR_WIDTH = 329


def build_ui(app, settings):
    root = app.root
    from neto_incident_monitor.window_style import install_window_style
    install_window_style(root)
    from neto_incident_monitor import __version__
    root.title(f"Neto Incident Monitor v{__version__}")
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
    style.configure('TCombobox', padding=(10, 7), fieldbackground=SURFACE,
                    background='#373c46', foreground=TEXT, arrowcolor=MUTED,
                    bordercolor='#484e58', lightcolor=SURFACE, darkcolor=SURFACE,
                    selectbackground=SURFACE, selectforeground=TEXT, arrowsize=16)
    style.map('TCombobox',
              fieldbackground=[('disabled', '#292c33'), ('readonly', SURFACE)],
              foreground=[('disabled', '#747b88'), ('readonly', TEXT)],
              selectbackground=[('readonly', SURFACE)], selectforeground=[('readonly', TEXT)],
              background=[('active', '#424751'), ('!active', '#373c46')],
              bordercolor=[('focus', '#929dab'), ('!focus', '#484e58')],
              lightcolor=[('focus', '#929dab'), ('!focus', SURFACE)],
              darkcolor=[('focus', '#929dab'), ('!focus', SURFACE)])
    root.option_add('*TCombobox*Listbox.background', SURFACE)
    root.option_add('*TCombobox*Listbox.foreground', TEXT)
    root.option_add('*TCombobox*Listbox.selectBackground', '#513039')
    root.option_add('*TCombobox*Listbox.selectForeground', '#ffe3e6')
    root.option_add('*TCombobox*Listbox.font', ('Segoe UI', 10))
    root.option_add('*TCombobox*Listbox.relief', 'flat')
    root.option_add('*TCombobox*Listbox.borderWidth', 0)
    style.configure("TSeparator", background="#424751")
    style.map("Treeview.Heading", background=[("active", "#424751")])
    style.configure("TCheckbutton", background=BG, foreground=TEXT, padding=(0, 4),
                    indicatorbackground=SURFACE, indicatorforeground=ACCENT)
    style.map("TCheckbutton", background=[("active", BG)],
              indicatorbackground=[("selected", ACCENT), ("active", "#424751")])
    from neto_incident_monitor.widgets import checkbox_images
    root.checkbox_images = checkbox_images(root, background=BG)
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
    from neto_incident_monitor.runtime_paths import ROOT
    logo = Image.open(ROOT / "assets" / "netology-logo.png")
    logo = logo.resize((155, 32), Image.Resampling.LANCZOS)
    root.brand_logo = ImageTk.PhotoImage(logo, master=root)
    ttk.Label(header, image=root.brand_logo).pack(side="left", anchor="n", pady=(10, 0), padx=(0, 24))
    title = ttk.Frame(header)
    title.pack(side="left", fill='x', expand=True, padx=(0, 20))
    title_row = ttk.Frame(title)
    title_row.pack(fill='x')
    ttk.Label(title_row, text="Incident Monitor", style="Title.TLabel").pack(side='left')
    from neto_incident_monitor.widgets import StatusPill
    activity_host = tk.Frame(title_row, bg=BG, width=1, height=28)
    activity_host.pack(side='left', fill='x', expand=True, padx=(12, 0))
    activity_host.pack_propagate(False)
    app.activity_pill = StatusPill(activity_host, compact=True, fit=True)
    app.activity_pill.pack(side='left', anchor='center')
    app.activity_pill.set_status('Monitoring zatrzymany')
    app.controls = ttk.Frame(header)
    app.controls.pack(side="right")
    app.start_button = RoundedButton(app.controls, text="Uruchom monitoring", icon="play", command=app.start,
                                     primary=True, background=BG)
    app.start_button.pack(side="left", padx=4)
    app.stop_button = RoundedButton(app.controls, text="Zatrzymaj", icon="stop", command=app.stop_monitoring, background=BG)
    app.stop_button.configure(state="disabled")
    app.stop_button.pack(side="left", padx=4)
    app.check_button = RoundedButton(app.controls, text="Sprawdź teraz", icon="refresh", command=app.check_now, background=BG)
    app.check_button.configure(state="disabled")
    app.check_button.pack(side="left", padx=4)

    def show_settings():
        window = app.settings_window
        width, height = SETTINGS_WINDOW_SIZE
        x = max(0, (window.winfo_screenwidth() - width) // 2)
        y = max(0, (window.winfo_screenheight() - height) // 2)
        window.geometry(f"{width}x{height}+{x}+{y}")
        window.update_idletasks()
        window.deiconify()
        window.lift()
    RoundedButton(app.controls, text="Ustawienia", icon="gear", command=show_settings,
                  background=BG).pack(side="left", padx=(4, 0))

    body = ttk.Frame(root, padding=(24, 0))
    body.pack(fill="both", expand=True)
    body.columnconfigure(2, weight=1)
    body.rowconfigure(0, weight=1)
    sidebar_area = ttk.Frame(body, style="White.TFrame")
    sidebar_area.grid(row=0, column=0, sticky="ns")
    splitter = tk.Frame(body, width=20, background=BG, cursor="sb_h_double_arrow")
    splitter.grid(row=0, column=1, sticky="ns")
    sidebar_area.rowconfigure(0, weight=1)
    app.sidebar_canvas = canvas = tk.Canvas(sidebar_area, width=DEFAULT_SIDEBAR_WIDTH, background=SURFACE,
                                            highlightthickness=0, borderwidth=0)
    canvas.grid(row=0, column=0, sticky="ns")
    scroll = ttk.Scrollbar(sidebar_area, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scroll.set)
    sidebar = ttk.Frame(canvas, style="White.TFrame", padding=16)
    sidebar_window = canvas.create_window((0, 0), window=sidebar, anchor="nw", width=DEFAULT_SIDEBAR_WIDTH)
    sidebar.rowconfigure(3, weight=1)
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
    app.dashboard_button = DashboardButton(sidebar)
    app.dashboard_button.grid(row=0, column=0, sticky="ew", pady=(0, 8))
    from neto_incident_monitor.widgets import ThreatenedIncidentsButton
    app.threatened_incidents_button = ThreatenedIncidentsButton(sidebar)
    app.threatened_incidents_button.grid(row=1, column=0, sticky="ew", pady=(0, 20))
    list_header = ttk.Frame(sidebar, style="White.TFrame")
    list_header.grid(row=2, column=0, sticky="ew", pady=(2, 12))
    ttk.Label(list_header, text="Monitorowane filtry", style="SidebarTitle.TLabel").pack(side="left")
    app.filter_count = tk.StringVar(value="0")
    tk.Label(list_header, textvariable=app.filter_count, bg="#392930", fg=ACCENT,
             font=("Segoe UI", 9, "bold"), padx=7, pady=2).pack(side="right")
    lists = ttk.Frame(sidebar, style="White.TFrame")
    lists.grid(row=3, column=0, sticky="nsew")
    lists.rowconfigure(1, weight=1)
    lists.columnconfigure(0, weight=1)
    app.filter_table = FilterList(lists)
    app.filter_table.grid(row=1, column=0, sticky="nsew")
    filter_scroll = app.filter_scroll = ttk.Scrollbar(lists, orient="vertical", command=app.filter_table.yview)
    filter_scroll.grid(row=1, column=1, sticky="ns", padx=(8, 0))
    filter_scroll.grid_remove()

    app.filter_table.configure(yscrollcommand=lambda first, last: update_grid_scrollbar(filter_scroll, first, last))
    filter_actions = ttk.Frame(sidebar, style="White.TFrame")
    filter_actions.grid(row=4, column=0, sticky="ew", pady=(10, 0))
    filter_actions.columnconfigure(0, weight=1)
    filter_actions.columnconfigure(1, weight=1)
    app.filter_buttons = []
    for i, (text, callback) in enumerate([
        ("+  Dodaj filtr", lambda: app.edit_filter()), ("Edytuj", lambda: app.edit_filter(True)), ("Usuń", app.remove_filter)
    ]):
        button = RoundedButton(filter_actions, text=text, command=callback, primary=i == 0,
                               icon={1: "edit", 2: "trash"}.get(i))
        if i == 0:
            button.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        else:
            button.grid(row=1, column=i - 1, sticky="ew", padx=(0, 4) if i == 1 else (4, 0))
        app.filter_buttons.append(button)
    app.import_button = import_button = RoundedButton(filter_actions, text="Importuj z ServiceNow", command=app.import_favorites)
    import_button.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
    app.settings_window = tk.Toplevel(root)
    app.settings_window.withdraw()
    app.settings_window.title("Ustawienia")
    app.settings_window.configure(background=SURFACE)
    app.settings_window.resizable(False, False)
    app.settings_window.transient(root)
    build_settings(app, settings)
    app.refresh_filters()

    content_host = ttk.Frame(body)
    content_host.grid(row=0, column=2, sticky="nsew")
    content_host.rowconfigure(0, weight=1)
    content_host.columnconfigure(0, weight=1)
    main = ttk.Frame(content_host)
    main.grid(row=0, column=0, sticky="nsew")
    from neto_incident_monitor.dashboard_ui import build_dashboard
    app.dashboard_view = build_dashboard(content_host, app)
    app.dashboard_view.grid(row=0, column=0, sticky="nsew")
    from neto_incident_monitor.threatened_ui import build_threatened_view
    app.threatened_view = build_threatened_view(content_host, app)
    app.threatened_view.grid(row=0, column=0, sticky='nsew')
    def select_view(view):
        if view != 'incidents':
            app.cancel_column_fit()
        app.active_view = view
        app.dashboard_button.selected = view == 'dashboard'
        app.dashboard_button.redraw()
        app.threatened_incidents_button.selected = view == 'threatened'
        app.threatened_incidents_button.redraw()
        app.filter_table.show_selection = view == 'incidents'
        app.filter_table.redraw()

    def show_incidents():
        select_view('incidents')
        main.tkraise()
        app.activate_filter_view()

    def show_dashboard():
        select_view('dashboard')
        app.dashboard_view.tkraise()

    def show_threatened():
        select_view('threatened')
        app.threatened_view.tkraise()

    app.show_incident_view = show_incidents
    app.show_dashboard_view = show_dashboard
    app.show_threatened_view = show_threatened
    app.filter_table.on_activate = show_incidents
    app.dashboard_button.command = show_dashboard
    app.threatened_incidents_button.command = show_threatened
    show_dashboard()
    def align_header_title(event=None):
        offset = max(0, main.winfo_rootx() - header.winfo_rootx() - 24 - 155 - 24 - 6)
        title.pack_configure(padx=(offset, 0))

    main.bind("<Configure>", align_header_title, add="+")
    sidebar_area.bind("<Configure>", align_header_title, add="+")
    root.after_idle(align_header_title)
    main.columnconfigure(0, weight=1)
    main.rowconfigure(2, weight=1)
    app.phase = tk.StringVar(value="Gotowy do uruchomienia")
    heading = tk.Frame(main, bg=BG)
    heading.grid(row=0, column=0, sticky='ew', pady=(0, 12))
    heading.columnconfigure(0, weight=1)
    app.selected_filter_name = tk.StringVar()
    filter_title = tk.Label(heading, font=VIEW_TITLE_FONT, bg=BG, fg=TEXT, width=1, anchor='w')
    filter_title.grid(row=0, column=0, sticky='sew')
    from tkinter.font import Font
    title_font = Font(root, font=VIEW_TITLE_FONT)

    def fit_filter_title(*_):
        title = app.selected_filter_name.get()
        limit = max(0, filter_title.winfo_width() - 6)
        if title_font.measure(title) > limit:
            while title and title_font.measure(title + '…') > limit:
                title = title[:-1]
            title = title + '…' if title else ''
        filter_title.configure(text=title)

    app.selected_filter_name.trace_add('write', fit_filter_title)
    filter_title.bind('<Configure>', fit_filter_title)
    app.table_load_status = tk.StringVar(value='')
    load_label = ttk.Label(main, textvariable=app.table_load_status, style='Muted.TLabel')
    load_label.grid(row=1, column=0, sticky='w')
    load_label.grid_remove()
    app.table_load_status.trace_add('write', lambda *_:
        load_label.grid() if app.table_load_status.get() else load_label.grid_remove())
    from neto_incident_monitor.read_status_ui import ReadStatusBar
    app.filter_read_bar = ReadStatusBar(main)
    app.filter_read_bar.grid(row=3, column=0, sticky='ew')
    app.update_phase_text()
    app.current_count = tk.StringVar(value="0")

    actions = ttk.Frame(heading)
    actions.grid(row=0, column=1, sticky='se')
    for attribute, text, icon, command in (
        ('configure_filter_button', 'Konfiguruj', 'gear', app.configure_selected_filter),
        ('columns_button', 'Kolumny', 'columns', app.configure_columns),
        ('refresh_filter_button', 'Aktualizuj', 'refresh', lambda: app.request_refresh('filter')),
        ('open_filter_button', 'Otwórz w SNOW', None, app.open_selected_filter),
    ):
        button = RoundedButton(actions, text=text, icon=icon, command=command, background=BG)
        button.configure(state='disabled')
        button.pack(side='left', padx=(8, 0))
        setattr(app, attribute, button)
    app.filter_read_bar.set_actions(edit=app.filter_buttons[1], retry=app.refresh_filter_button)

    def match_dashboard_heading_height(event=None):
        # The dashboard's period selectors can be taller than its buttons at higher DPI.
        height = app.dashboard_view.heading_row.winfo_reqheight()
        for row in (heading, app.threatened_view.heading_row):
            row.rowconfigure(0, minsize=height)

    app.dashboard_view.heading_row.bind('<Configure>', match_dashboard_heading_height, add='+')
    root.after_idle(match_dashboard_heading_height)
    app.clear_history_button = RoundedButton(main, text="Wyczyść historię", icon="trash", command=app.clear_history, background=BG)
    app.tabs = ttk.Notebook(main, style="Clean.TNotebook")
    app.tabs.grid(row=2, column=0, sticky="nsew")
    current = ttk.Frame(app.tabs, style="White.TFrame")
    history = ttk.Frame(app.tabs, style="White.TFrame")
    app.tabs.add(current, text="Bieżące zgłoszenia")
    app.tabs.add(history, text="Historia zgłoszeń")
    app.history_tooltip = TabTooltip(app.tabs, 1,
        "Lista wcześniej wykrytych zgłoszeń. Pokazuje dane zapisane w chwili wykrycia — mogą różnić się od aktualnych danych w ServiceNow.")
    def minimum_view_width():
        tabs_width = sum(image.width() for image in root.tab_images)
        return max(tabs_width + app.clear_history_button.winfo_reqwidth() + 12, actions.winfo_reqwidth() + 112, 620)

    def update_history_action(event=None):
        if app.tabs.select() == str(history):
            app.clear_history_button.place(in_=app.tabs, relx=1, y=3, anchor='ne')
            tk.Misc.lift(app.clear_history_button)
        else:
            app.clear_history_button.place_forget()

    app.tabs.bind("<<NotebookTabChanged>>", update_history_action, add="+")
    app.tabs.bind("<<NotebookTabChanged>>", app.show_table_tab, add="+")
    desired_width = max(MIN_SIDEBAR_WIDTH, int(settings.get("sidebar_width", DEFAULT_SIDEBAR_WIDTH)))
    drag_origin = None

    def fit_sidebar(event=None):
        if not actions.winfo_exists() or not canvas.winfo_exists():
            return
        required = minimum_view_width()
        body.columnconfigure(2, minsize=required)
        root.minsize(48 + MIN_SIDEBAR_WIDTH + 20 + required, 680)
        maximum = max(MIN_SIDEBAR_WIDTH, body.winfo_width() - 48 - 20 - required)
        canvas.configure(width=min(desired_width, maximum))

    def start_resize(event):
        nonlocal drag_origin
        drag_origin = (event.x_root, canvas.winfo_width())
        splitter.configure(background="#373c46")

    def drag_resize(event):
        nonlocal desired_width
        if drag_origin is None:
            return
        required = minimum_view_width()
        maximum = max(MIN_SIDEBAR_WIDTH, body.winfo_width() - 48 - 20 - required)
        desired_width = max(MIN_SIDEBAR_WIDTH, min(maximum, drag_origin[1] + event.x_root - drag_origin[0]))
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
    root.after_idle(fit_sidebar)
    app.splitter = splitter
    app.current_table = app.make_table(current, False)
    app.current_table.bind('<Map>', lambda _event: app.queue_filter_display(), add='+')
    app.table = app.make_table(history, True)
    app.current_table.bind("<Double-1>", app.open_incident)
    app.table.bind("<Double-1>", app.open_incident)
    app.status = tk.StringVar()
    app.session_status = tk.StringVar(value='Łączenie…')
    app.work_status = tk.StringVar()
    footer_color = BG
    footer_font = ('Segoe UI', 9)
    footer_status_font = (*footer_font, 'bold')
    footer_padding = 3
    app.footer_line = tk.Frame(body, bg=ReadStatusBar.BORDER, height=1)
    app.footer_line.grid(row=1, column=0, columnspan=3, sticky='ew', pady=(6, 0))
    app.footer_surface = tk.Frame(body, bg=footer_color)
    app.footer_surface.grid(row=2, column=0, columnspan=3, sticky='nsew')

    session_bar = app.session_bar = tk.Frame(body, bg=footer_color, padx=4, pady=footer_padding)
    session_bar.grid(row=2, column=0, sticky='new')
    light = tk.Canvas(session_bar, width=9, height=9, bg=footer_color, highlightthickness=0)
    light.pack(side='left', padx=(0, 5))
    dot = light.create_oval(1, 1, 8, 8, outline='')
    displayed_session = tk.StringVar()
    state_label = tk.Label(session_bar, textvariable=displayed_session, bg=footer_color, fg=TEXT,
                           font=footer_status_font, anchor='w', justify='left', width=1)
    state_label.pack(side='left', fill='x', expand=True)
    state_label.bind('<Configure>', lambda event: state_label.configure(wraplength=max(60, event.width - 4)))

    work_bar = app.work_bar = tk.Frame(body, bg=footer_color, pady=footer_padding)
    work_bar.grid(row=2, column=2, sticky='new')
    work_bar.columnconfigure(1, weight=1)
    activity_icon = tk.Canvas(work_bar, width=17, height=15, bg=footer_color, highlightthickness=0)
    activity_icon.grid(row=0, column=0, sticky='w', padx=(0, 6))
    pulse = activity_icon.create_line(1, 8, 4, 8, 7, 2, 10, 13, 13, 8, 16, 8,
                                      width=1.5, capstyle='round', joinstyle='round')
    displayed_work = tk.StringVar()
    work_label = tk.Label(work_bar, textvariable=displayed_work, bg=footer_color, fg=TEXT,
                          font=footer_status_font, width=1, anchor='w', justify='left')
    work_label.grid(row=0, column=1, sticky='ew')
    app.footer_actions = tk.Frame(work_bar, bg=footer_color)
    app.footer_actions.grid(row=0, column=2, sticky='e', padx=(8, 6))
    app.footer_actions.grid_remove()
    app.login_window_button = RoundedButton(app.footer_actions, text='Pokaż okno logowania',
                                            background=footer_color,
                                            command=lambda: app.events.put(('show_browser', None)), compact=True)
    notice = tk.Frame(work_bar, bg=footer_color)
    notice.grid(row=1, column=0, columnspan=3, sticky='ew', padx=(0, 6), pady=(4, 0))
    notice.grid_remove()
    notice_label = tk.Label(notice, textvariable=app.status, bg=footer_color, fg=MUTED, width=1,
                            anchor='w', justify='left', font=footer_font)
    notice_label.pack(side='left', fill='x', expand=True)
    RoundedButton(notice, text='Zamknij', compact=True, background=footer_color,
                  command=lambda: app.status.set('')).pack(side='right', padx=(8, 0))
    notice_label.bind('<Configure>', lambda event: notice_label.configure(wraplength=max(100, event.width - 4)))
    work_label.bind('<Configure>', lambda event: work_label.configure(wraplength=max(100, event.width - 4)))

    def show_notice(*_):
        if app.status.get():
            notice.grid()
        else:
            notice.grid_remove()

    def show_footer_status(*_):
        color = {'ready': '#86ceaa', 'failed': '#ffadb8', 'waiting': '#f5c77b'}.get(app.session_state, MUTED)
        light.itemconfigure(dot, fill=color)
        displayed_session.set(f'ServiceNow · {app.session_status.get()}')
        idle = 'Oczekuje na następny odczyt' if app.cycle_active and app.session_state == 'ready' else 'Brak zleceń'
        work = app.work_status.get()
        displayed_work.set(f'Aktywność · {work or idle}')
        activity_color = {'ready': '#a8cbfa', 'waiting': '#f5c77b'}.get(app.session_state, MUTED) if work else MUTED
        activity_icon.itemconfigure(pulse, fill=activity_color)

    app.status.trace_add('write', show_notice)
    for variable in (app.session_status, app.work_status, app.phase):
        variable.trace_add('write', show_footer_status)
    show_footer_status()
