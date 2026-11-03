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
    from neto_incident_monitor.dashboard_cache import load_snapshot, save_sections, valid_values, NAMES
    from neto_incident_monitor.dashboard import measured_record
    from pathlib import Path
    cache_path = Path(cache_path) if cache_path is not None else DATA / 'dashboard-cache.json'
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
    panel.section_snapshots = {}
    panel.cache_error = False
    panel.restored_snapshot = False
    panel.request_id = 0
    panel.active_request = None
    panel.request_period = None
    panel.period_controls = []
    panel.request_diagnostics = None
    panel.request_sections = set()
    panel.last_complete_read_at = None
    def record(event, **facts):
        try:
            if panel.request_diagnostics is None:
                from neto_incident_monitor.login_diagnostics import LoginDiagnostics
                panel.request_diagnostics = LoginDiagnostics(source='dashboard')
            measured_record(panel.request_diagnostics, event, **facts)
        except Exception:
            pass  # Diagnostic setup cannot change request ownership.
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
            if state in ('Oczekuje', 'W trakcie aktualizacji', 'Ponawianie odczytu'):
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
        panel.message.set(f'Dane SLA za okres {months[month - 1].lower()} {year}. • '
                          f'Ostatnio odczytano: {panel.last_read_text} • {description}')
    panel.set_message = set_message
    set_message('Wybierz okres i kliknij Aktualizuj. Wymagany uruchomiony monitoring.')
    def period_changed(event=None):
        if panel.active_request is not None:
            request_id, year, month = panel.active_request
            if panel.year.get() != str(year):
                panel.year.set(str(year))
            if panel.month.get() != months[month - 1]:
                panel.month.set(months[month - 1])
            record('dashboard_period_state', request_id=request_id, year=year, month=month,
                   request_state='blocked')
            return
        panel.request_id += 1
        if hasattr(app, 'dashboard_progress'):
            app.dashboard_progress.hide()
        set_section_state(panel.request_id, 'Dashboard SLA', 'Dane nieaktualne')
        year, month = int(panel.year.get()), months.index(panel.month.get()) + 1
        record('dashboard_period_state', request_id=panel.request_id, year=year, month=month,
               request_state='idle_changed')
        set_message(f'Wybrano {months[month - 1].lower()} {year} — kliknij Aktualizuj. '
                    'Kafelki SLA pokazują poprzedni odczyt.')

    for label, variable, options, width in (("Miesiąc", panel.month, months, 16),
                                ("Rok", panel.year, tuple(str(y) for y in range(2026, 2031)), 7)):
        field = tk.Frame(period, bg=BG)
        field.pack(side="left", padx=(0, 10))
        tk.Label(field, text=label, bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 5))
        combo = ttk.Combobox(field, values=options, state="readonly", width=width, textvariable=variable)
        combo.pack()
        panel.period_controls.append(combo)
        combo.bind('<<ComboboxSelected>>', period_changed)

    restoring_period = False
    def protect_period(*_):
        nonlocal restoring_period
        if panel.active_request is not None and not restoring_period:
            restoring_period = True
            try:
                period_changed()
            finally:
                restoring_period = False
    for variable in (panel.month, panel.year):
        variable.trace_add('write', protect_period)

    def set_updating(request_id, year, month, state):
        if panel.active_request != (request_id, year, month):
            record('dashboard_request_state', request_id=request_id,
                   active_request_id=panel.request_id,
                   request_state='period_mismatch' if request_id == panel.request_id else 'stale_id')
            return False
        record('dashboard_request_state', request_id=request_id, year=year, month=month,
               request_state=state)
        if state in ('finished', 'cancelled', 'queue_error'):
            panel.active_request = None
            for combo in panel.period_controls:
                combo.configure(state='readonly')
            panel.finish_pending()
            record('dashboard_period_state', request_id=request_id, year=year, month=month,
                   request_state='unlocked')
        return True
    panel.set_updating = set_updating

    def cancel_request():
        if panel.active_request is not None:
            set_updating(*panel.active_request, 'cancelled')
    panel.cancel_request = cancel_request

    def request(automatic=False, coordinated=False):
        if not automatic and not coordinated:
            return app.request_refresh('dashboard')
        if panel.active_request is not None:
            return False
        if not automatic and (not app.worker or not app.worker.is_alive()):
            set_message('Najpierw uruchom monitoring i zaloguj się w ServiceNow.')
            return False
        year, month = int(panel.year.get()), months.index(panel.month.get()) + 1
        panel.request_id += 1
        panel.active_request = (panel.request_id, year, month)
        panel.request_period = (year, month)
        panel.request_sections.clear()
        panel.request_diagnostics = None
        for combo in panel.period_controls:
            combo.configure(state='disabled')
        record('dashboard_period_state', request_id=panel.request_id, year=year, month=month,
               request_state='locked')
        if hasattr(app, 'dashboard_progress'):
            app.dashboard_progress.start(panel.request_id)
        for section in panel.section_pills:
            set_section_state(panel.request_id, section, 'Oczekuje')
        try:
            app.dashboard_requests.put(panel.active_request)
        except Exception:
            set_updating(*panel.active_request, 'queue_error')
            if hasattr(app, 'dashboard_progress'):
                app.dashboard_progress.hide()
            set_message('Nie udało się zlecić aktualizacji dashboardu. Spróbuj ponownie.')
            return False
        record('dashboard_request_state', request_id=panel.request_id, year=year, month=month,
               request_state='queued')
        set_message('Oczekiwanie na zalogowanie i odczyt dashboardu…' if automatic else
                          'Oczekiwanie na odczyt w przeglądarce… Poprzednie dane mogą być nieaktualne.')
        return True

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

    RoundedButton(period, text='Otwórz w SNOW', command=open_dashboard,
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
    def render_snapshots():
        from datetime import datetime
        panel.snapshot_values = {}
        for alias, snapshot in panel.section_snapshots.items():
            panel.snapshot_values.update(snapshot['values'])
            if alias == 'sla':
                panel.data_period = (snapshot['year'], snapshot['month'])
        panel.last_read_text = (datetime.fromisoformat(panel.last_complete_read_at).strftime('%d.%m.%Y %H:%M:%S')
                                if panel.last_complete_read_at else '—')
        for title, variable in panel.values.items():
            if title != 'WJRUW':
                variable.set(str(panel.snapshot_values[title]) if title in panel.snapshot_values else '—')
        from neto_incident_monitor.dashboard import calculate_wjruw
        sla = panel.section_snapshots.get('sla', {}).get('values', {})
        indicator = calculate_wjruw(sla)
        panel.values['WJRUW'].set('Brak danych' if indicator is None else f'{indicator:.2f}%'.replace('.', ','))
        panel.value_labels['WJRUW'].configure(font=('Segoe UI', 12 if indicator is None else 28))

    def result(payload, restored_at=None):
        from datetime import datetime
        request_id, year, month, values, error, *extra = payload
        if request_id != panel.request_id:
            record('dashboard_result_rejected', request_id=request_id,
                   active_request_id=panel.request_id, request_state='stale_id')
            return
        if panel.request_period is not None and (year, month) != panel.request_period:
            record('dashboard_result_rejected', request_id=request_id, year=year, month=month,
                   expected_year=panel.request_period[0], expected_month=panel.request_period[1],
                   request_state='period_mismatch')
            return
        if panel.request_period is not None and panel.active_request is None:
            record('dashboard_result_rejected', request_id=request_id, request_state='finished')
            return
        message = extra[0] if extra else ''
        metadata = extra[1] if len(extra) > 1 else None
        if error:
            set_message('Nie udało się odczytać danych. Zachowano ostatnie poprawne wyniki i ich daty.')
            return
        if metadata:
            alias = metadata['section']
            now = datetime.now().astimezone().isoformat(timespec='seconds')
            previous = panel.section_snapshots.get(alias)
            if metadata.get('error'):
                panel.request_sections.discard(alias)
                if previous:
                    previous.update(last_attempt_at=now, last_outcome='error')
            elif valid_values(alias, metadata['values']):
                panel.request_sections.add(alias)
                panel.section_snapshots[alias] = {'values': dict(metadata['values']),
                    'read_at': metadata['read_at'], 'last_attempt_at': now, 'last_outcome': 'success',
                    'complete': True, 'year': year if alias == 'sla' else None,
                    'month': month if alias == 'sla' else None}
            else:
                panel.request_sections.discard(alias)
                set_section_state(request_id, NAMES[alias], 'Błąd odczytu')
                return
            render_snapshots()
            diagnostics = metadata['diagnostics']
            try:
                if panel.section_snapshots:
                    save_sections(cache_path, panel.section_snapshots, panel.last_complete_read_at)
                panel.cache_error = False
                measured_record(diagnostics, 'dashboard_cache', cache_result='saved' if panel.section_snapshots else 'skipped')
            except OSError as exc:
                panel.cache_error = True
                from neto_incident_monitor.login_diagnostics import error_facts
                measured_record(diagnostics, 'dashboard_cache', cache_result='failed',
                    os_errno=exc.errno, winerror=getattr(exc, 'winerror', None), **error_facts(exc))
        if not metadata and panel.request_sections == {'sla', 'held', 'requests'}:
            # Only a completed full transaction advances the public timestamp.
            panel.last_complete_read_at = datetime.now().astimezone().isoformat(timespec='seconds')
            render_snapshots()
            record('dashboard_complete', request_id=request_id, year=year, month=month, outcome='returned')
            try:
                save_sections(cache_path, panel.section_snapshots, panel.last_complete_read_at)
                panel.cache_error = False
                record('dashboard_cache', cache_result='saved')
            except OSError as exc:
                panel.cache_error = True
                from neto_incident_monitor.login_diagnostics import error_facts
                record('dashboard_cache', cache_result='failed', **error_facts(exc))
        panel.restored_snapshot = False
        message = message or 'Dane zostały zaktualizowane. Wstrzymane L1 i Wnioski L1 przedstawiają stan bieżący.'
        if panel.cache_error:
            message += ' Nie udało się zapisać odczytu na dysku.'
        set_message(message)
    panel.apply_result = result
    cached = load_snapshot(cache_path)
    if cached or cache_path.exists():
        from neto_incident_monitor.login_diagnostics import LoginDiagnostics
        measured_record(LoginDiagnostics(source='dashboard'), 'dashboard_cache',
            cache_result='restored' if cached else 'invalid')
    if cached:
        panel.section_snapshots = cached['sections']
        panel.last_complete_read_at = cached.get('last_complete_read_at')
        sla = panel.section_snapshots.get('sla')
        if sla:
            panel.month.set(months[sla['month'] - 1])
            panel.year.set(str(sla['year']))
        render_snapshots()
        panel.restored_snapshot = True
        set_message('Zapisane dane mogą być nieaktualne. Wstrzymane L1 i Wnioski L1 przedstawiają stan z poprzedniego odczytu.')
    notice_text = tk.Label(content, textvariable=panel.message, wraplength=700,
                           bg=BG, fg=MUTED, font=('Segoe UI', 10),
                           justify='left', anchor='w')
    notice_text.grid(row=6, column=0, sticky='ew', pady=(12, 0))
    panel.notice = notice_text
    notice_text.bind('<Configure>', lambda event:
                     notice_text.configure(wraplength=max(100, event.width - 6)))
    panel.progress_host = tk.Frame(content, bg=BG)
    panel.progress_host.grid(row=7, column=0, sticky='ew', pady=(6, 0))
    def scroll_wheel(event):
        if content.winfo_reqheight() > canvas.winfo_height():
            canvas.yview_scroll(-int(event.delta / 120), 'units')
        else:
            canvas.yview_moveto(0)
        return 'break'

    canvas.bind('<MouseWheel>', scroll_wheel)
    bind_dashboard_wheel(content, scroll_wheel)
    return panel
