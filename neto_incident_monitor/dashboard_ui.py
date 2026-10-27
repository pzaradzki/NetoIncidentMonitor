"""Dashboard controls and main-thread presentation of browser results."""
from datetime import date
import webbrowser
import tkinter as tk
from tkinter import ttk

from neto_incident_monitor.theme import BG, SURFACE, TEXT, MUTED
from neto_incident_monitor.widgets import RoundedButton, PriorityDots, StatusPill


def bind_dashboard_wheel(widget, callback):
    # Combobox popdowns are native Tcl windows, not Python widget instances.
    # Keep native controls' wheel behavior and visit only Python-owned widgets.
    if isinstance(widget, ttk.Combobox):
        return
    widget.bind('<MouseWheel>', callback)
    for child in tuple(widget.children.values()):
        bind_dashboard_wheel(child, callback)


def build_dashboard(parent, app, cache_path=None):
    from neto_incident_monitor.runtime_paths import DATA
    from neto_incident_monitor.dashboard_cache import load_snapshot, save_snapshot
    cache_path = cache_path if cache_path is not None else DATA / 'dashboard-cache.json'
    panel = tk.Frame(parent, bg=BG)
    canvas = tk.Canvas(panel, bg=BG, highlightthickness=0, borderwidth=0)
    scroll = ttk.Scrollbar(panel, orient='vertical', command=canvas.yview)
    canvas.pack(side='left', fill='both', expand=True)
    content = tk.Frame(canvas, bg=BG)
    content.columnconfigure(0, weight=1)
    window = canvas.create_window((0, 0), window=content, anchor='nw')
    def scrollbar(first, last):
        scroll.set(first, last)
        if content.winfo_reqheight() > canvas.winfo_height():
            scroll.pack(side='right', fill='y', padx=(6, 0))
        else:
            scroll.pack_forget()
    canvas.configure(yscrollcommand=scrollbar)
    def update_scroll_layout(event=None):
        width, height = canvas.winfo_width(), canvas.winfo_height()
        canvas.itemconfigure(window, width=width)
        canvas.configure(scrollregion=(0, 0, width, max(height, content.winfo_reqheight())))
        if content.winfo_reqheight() <= height:
            canvas.yview_moveto(0)
    content.bind('<Configure>', update_scroll_layout)
    canvas.bind('<Configure>', update_scroll_layout)
    panel.values = {}
    panel.value_labels = {}
    panel.data_period = None
    panel.snapshot_values = {}
    panel.restored_snapshot = False
    panel.request_id = 0
    panel.section_states = {}
    panel.section_pills = {}
    def section_header(parent, section):
        frame = tk.Frame(parent, bg=BG)
        tk.Label(frame, text=section, bg=BG, fg=TEXT,
                 font=('Segoe UI', 12, 'bold')).pack(side='left')
        pill = StatusPill(frame, compact=True)
        pill.pack(side='left', padx=(12, 0))
        pill.set_status('Dane nieaktualne')
        panel.section_pills[section] = pill
        panel.section_states[section] = 'Dane nieaktualne'
        return frame

    def set_section_state(request_id, section, state):
        if request_id == panel.request_id and section in panel.section_pills:
            panel.section_states[section] = state
            panel.section_pills[section].set_status(state)
    panel.set_section_state = set_section_state

    def finish_pending():
        for section, state in panel.section_states.items():
            if state in ('Oczekuje', 'W trakcie aktualizacji'):
                set_section_state(panel.request_id, section, 'Dane nieaktualne')
    panel.finish_pending = finish_pending
    panel.message = tk.StringVar(panel, value="Wybierz okres i kliknij Aktualizuj. Wymagany uruchomiony monitoring.")
    panel.month = tk.StringVar(panel, value="")
    panel.year = tk.StringVar(panel, value=str(date.today().year))
    toolbar = tk.Frame(content, bg=BG)
    toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 14))
    section_header(toolbar, 'Dashboard SLA').pack(side='left', anchor='s')
    period = tk.Frame(toolbar, bg=BG)
    period.pack(side='right')
    months = ("Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", "Lipiec",
              "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień")
    panel.month.set(months[date.today().month - 1])
    panel.last_read_text = '—'
    def set_message(description):
        year, month = panel.data_period or (int(panel.year.get()), months.index(panel.month.get()) + 1)
        panel.message.set(f'Dane za okres {months[month - 1].lower()} {year}. • '
                          f'Ostatnio odczytano: {panel.last_read_text} • {description}')
    panel.set_message = set_message
    set_message('Wybierz okres i kliknij Aktualizuj. Wymagany uruchomiony monitoring.')
    def period_changed(event=None):
        panel.request_id += 1
        for section in panel.section_pills:
            set_section_state(panel.request_id, section, 'Dane nieaktualne')
        set_message('Zmieniono okres — kliknij Aktualizuj. Kafelki pokazują poprzedni odczyt.')

    for label, variable, options, width in (("Miesiąc", panel.month, months, 16),
                                ("Rok", panel.year, tuple(str(y) for y in range(2026, 2031)), 7)):
        field = tk.Frame(period, bg=BG)
        field.pack(side="left", padx=(0, 10))
        tk.Label(field, text=label, bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 5))
        combo = ttk.Combobox(field, values=options, state="readonly", width=width, textvariable=variable)
        combo.pack()
        combo.bind('<<ComboboxSelected>>', period_changed)

    def request(automatic=False):
        if not automatic and (not app.worker or not app.worker.is_alive()):
            set_message('Najpierw uruchom monitoring i zaloguj się w ServiceNow.')
            return
        panel.request_id += 1
        for section in panel.section_pills:
            set_section_state(panel.request_id, section, 'Oczekuje')
        app.dashboard_requests.put((panel.request_id, int(panel.year.get()), months.index(panel.month.get()) + 1))
        set_message('Oczekiwanie na zalogowanie i odczyt dashboardu…' if automatic else
                          'Oczekiwanie na odczyt w przeglądarce… Poprzednie dane mogą być nieaktualne.')
        if not automatic:
            app.schedule.request()

    panel.request_refresh = request

    refresh = RoundedButton(period, text="Aktualizuj", icon="refresh", command=request, background=BG)
    refresh.pack(side="left", anchor="s")
    panel.refresh_button = refresh
    refresh.configure(state='disabled')
    def open_dashboard():
        from neto_incident_monitor.dashboard import DASHBOARD_URL
        try:
            opened = webbrowser.open(DASHBOARD_URL)
        except Exception:
            opened = False
        if not opened:
            set_message('Nie udało się otworzyć dashboardu w przeglądarce.')

    RoundedButton(period, text='Otwórz Dashboard', command=open_dashboard,
                  background=BG).pack(side='left', anchor='s', padx=(8, 0))
    metrics = tk.Frame(content, bg=BG)
    metrics.grid(row=1, column=0, sticky="ew")
    metrics.columnconfigure(0, weight=5, uniform="metrics")
    for row in (0, 1):
        metrics.rowconfigure(row, weight=1, uniform='metric_rows')
    for column in range(1, 6):
        metrics.columnconfigure(column, weight=4, uniform="metrics")

    def tile(title, column, row, rowspan=1, total=False, dot=None, title_wrap=0, columns=6):
        color = "#30272f" if total else SURFACE
        card = tk.Frame(metrics, bg=color, highlightthickness=1,
                        highlightbackground="#73414c" if total else "#3c424c", padx=12, pady=16)
        card.grid(row=row, column=column, rowspan=rowspan, sticky="nsew",
                  padx=(0 if column == 0 else 6, 0 if column == columns - 1 else 6),
                  pady=(0 if row == 0 else 6, 0 if row == 1 else 6))
        label = tk.Frame(card, bg=color)
        label.pack(anchor="w")
        if dot:
            tk.Label(label, text="●", fg=dot, bg=color, font=("Segoe UI", 10)).pack(side="left", padx=(0, 5))
        tk.Label(label, text=title, bg=color, fg=MUTED, font=("Segoe UI", 9),
                 wraplength=title_wrap, justify='left').pack(side="left")
        variable = panel.values[title] = tk.StringVar(panel, value="—")
        value_label = panel.value_labels[title] = tk.Label(
            card, textvariable=variable, bg=color, fg=TEXT if row == 0 or total else MUTED,
            font=("Segoe UI", 28))
        value_label.pack(anchor="w", expand=True, pady=(18, 0))
    tile("Liczba zgłoszeń", 0, 0, total=True)
    tile("WJRUW", 0, 1, total=True)
    for priority in range(1, 6):
        tile(f"Zgłoszenia P{priority}", priority, 0, dot=PriorityDots.COLORS[str(priority)])
        tile(f"Przekroczone P{priority}", priority, 1)
    section_header(content, 'Wstrzymane L1').grid(row=2, column=0, sticky='w', pady=(24, 14))
    metrics = tk.Frame(content, bg=BG)
    metrics.grid(row=3, column=0, sticky='ew')
    for column in range(2):
        metrics.columnconfigure(column, weight=1, uniform='held')
    tile('Wstrzymane L1 >14 dni', 0, 0, columns=2)
    tile('Wstrzymane L1 >7 dni', 1, 0, columns=2)
    section_header(content, 'Wnioski L1').grid(row=4, column=0, sticky='w', pady=(24, 14))
    metrics = tk.Frame(content, bg=BG)
    metrics.grid(row=5, column=0, sticky='ew')
    for column in range(4):
        metrics.columnconfigure(column, weight=1, uniform='requests')
    from neto_incident_monitor.dashboard import REQUEST_TITLES
    for column, title in enumerate(REQUEST_TITLES):
        tile(title, column, 0, title_wrap=140, columns=4)
    def result(payload, restored_at=None):
        from datetime import datetime
        request_id, year, month, values, error, *extra = payload
        if request_id != panel.request_id:
            return
        if error:
            set_message('Nie udało się odczytać danych. Sprawdź logowanie w przeglądarce i spróbuj ponownie. Poprzedni odczyt jest nieaktualny.')
        else:
            if panel.data_period != (year, month):
                panel.snapshot_values = {}
            panel.snapshot_values.update(values)
            values = panel.snapshot_values
            panel.data_period = (year, month)
            for title in panel.values:
                if title != 'WJRUW' and title not in values:
                    panel.values[title].set('—')
            for title, value in values.items():
                panel.values[title].set(str(value))
            from neto_incident_monitor.dashboard import calculate_wjruw
            indicator = calculate_wjruw(values)
            panel.values['WJRUW'].set('Brak danych' if indicator is None else f'{indicator:.2f}%'.replace('.', ','))
            panel.value_labels['WJRUW'].configure(font=('Segoe UI', 12 if indicator is None else 28))
            read_at = restored_at or datetime.now().isoformat(timespec='seconds')
            timestamp = datetime.fromisoformat(read_at)
            panel.restored_snapshot = bool(restored_at)
            panel.last_read_text = f'{timestamp:%d.%m.%Y %H:%M:%S}'
            description = 'Zapisane dane mogą być nieaktualne.' if restored_at else 'Dane zostały zaktualizowane.'
            if not restored_at:
                try:
                    save_snapshot(cache_path, year, month, dict(values), read_at)
                except OSError as exc:
                    import logging
                    logging.getLogger('servicenow').warning(
                        'Zapis dashboard-cache.json: %s, errno=%s, winerror=%s.',
                        type(exc).__name__, exc.errno, getattr(exc, 'winerror', None))
                    description += ' Nie udało się zapisać odczytu na dysku.'
            if extra and extra[0]:
                description = extra[0] + (' Nie udało się zapisać odczytu na dysku.' if 'Nie udało się zapisać' in description else '')
            set_message(description)
    panel.apply_result = result
    cached = load_snapshot(cache_path)
    if cached:
        panel.month.set(months[cached['month'] - 1])
        panel.year.set(str(cached['year']))
        result((panel.request_id, cached['year'], cached['month'], cached['values'], None),
               restored_at=cached['read_at'])
    notice = tk.Frame(content, bg='#27364a')
    notice.grid(row=6, column=0, sticky='ew', pady=(20, 0))
    notice.columnconfigure(2, weight=1)
    notice_accent = tk.Frame(notice, bg='#9ac4f4', width=3)
    notice_accent.grid(row=0, column=0, sticky='ns')
    notice_icon = tk.Label(notice, text='ⓘ', bg='#27364a', fg='#9ac4f4',
                           font=('Segoe UI', 14), padx=12)
    notice_icon.grid(row=0, column=1, sticky='n', pady=7)
    notice_text = tk.Label(notice, textvariable=panel.message, wraplength=650,
                           bg='#27364a', fg=TEXT, font=('Segoe UI', 9),
                           justify='left', anchor='w', padx=0, pady=10)
    notice_text.grid(row=0, column=2, sticky='ew', padx=(0, 16))
    def update_notice(*_):
        message = panel.message.get().lower()
        if 'nie udało' in message or 'błąd' in message:
            background, accent, icon = '#39292f', '#ff929e', '!'
        elif ('nieaktualne' in message or 'zmieniono okres' in message
              or (panel.restored_snapshot and message.startswith('dane za okres'))):
            background, accent, icon = '#373123', '#efc778', '!'
        elif any(word in message for word in ('oczekiwanie', 'trwa', 'uruchom monitoring', 'wybierz okres')):
            background, accent, icon = '#273343', '#9ac4f4', 'ⓘ'
        elif 'dane za' in message:
            background, accent, icon = '#253a30', '#8ee2ac', '✓'
        else:
            background, accent, icon = '#273343', '#9ac4f4', 'ⓘ'
        notice.configure(bg=background)
        notice_accent.configure(bg=accent)
        notice_icon.configure(bg=background, fg=accent, text=icon)
        notice_text.configure(bg=background)
    panel.message.trace_add('write', update_notice)
    notice.bind('<Configure>', lambda event: notice_text.configure(wraplength=max(100, event.width - 76)))
    update_notice()
    def scroll_wheel(event):
        if content.winfo_reqheight() > canvas.winfo_height():
            canvas.yview_scroll(-int(event.delta / 120), 'units')
        else:
            canvas.yview_moveto(0)
        return 'break'

    canvas.bind('<MouseWheel>', scroll_wheel)
    bind_dashboard_wheel(content, scroll_wheel)
    return panel
