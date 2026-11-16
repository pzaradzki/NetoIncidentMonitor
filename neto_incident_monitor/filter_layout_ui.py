"""Preview and refresh the default ServiceNow list layouts."""
import tkinter as tk
from tkinter.font import Font
from tkinter import ttk
from time import monotonic

from neto_incident_monitor.dashboard import measured_record
from neto_incident_monitor.filter_layouts import DEFAULT_LAYOUT_PREFIXES
from neto_incident_monitor.login_diagnostics import LoginDiagnostics
from neto_incident_monitor.template_library_ui import fit_and_center
from neto_incident_monitor.theme import SURFACE
from neto_incident_monitor.widgets import RoundedButton
from neto_incident_monitor.window_style import apply_window_style


def show_saved_layouts(app, parent):
    window = tk.Toplevel(parent, background=SURFACE)
    window.withdraw()
    window.title('Układy kolumn list ServiceNow')
    window.transient(parent)
    window.minsize(640, 440)
    panel = ttk.Frame(window, style='White.TFrame', padding=20)
    panel.pack(fill='both', expand=True)
    ttk.Label(panel, text='Układy kolumn list ServiceNow', style='White.TLabel',
              font=('Segoe UI', 14, 'bold')).pack(anchor='w')
    subtitle = tk.StringVar(window, value='Domyślne widoki zapisane dla aktualnego konta.')
    ttk.Label(panel, textvariable=subtitle, style='WhiteMuted.TLabel').pack(anchor='w', pady=(4, 14))
    sections = ttk.Frame(panel, style='White.TFrame')
    sections.pack(fill='both', expand=True)
    sections.columnconfigure((0, 1), weight=1, uniform='layouts')
    sections.rowconfigure((0, 1), weight=1, uniform='layouts')
    font = Font(window, font=('Segoe UI', 10))
    section_ui = {}
    for position, prefix in enumerate(DEFAULT_LAYOUT_PREFIXES):
        section = ttk.Frame(sections, style='White.TFrame')
        section.grid(row=position // 2, column=position % 2, sticky='nsew', padx=(0, 10), pady=(0, 12))
        section.columnconfigure(0, weight=1)
        section.rowconfigure(1, weight=1)
        ttk.Label(section, text=prefix, style='White.TLabel', font=('Segoe UI', 11, 'bold')).grid(
            row=0, column=0, sticky='w', pady=(0, 6))
        table = ttk.Treeview(section, columns=('label', 'field'), show='headings', height=5, selectmode='browse')
        table.heading('label', text='Nazwa w ServiceNow', anchor='w')
        table.heading('field', text='Identyfikator pola', anchor='w')
        table.column('label', width=170, minwidth=135)
        table.column('field', width=180, minwidth=125)
        table.grid(row=1, column=0, sticky='nsew')
        vertical = ttk.Scrollbar(section, orient='vertical', command=table.yview)
        vertical.grid(row=1, column=1, sticky='ns')
        horizontal = ttk.Scrollbar(section, orient='horizontal', command=table.xview)
        horizontal.grid(row=2, column=0, sticky='ew')
        table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        empty = ttk.Label(section, text='Brak zapisanego układu', style='WhiteMuted.TLabel')
        empty.grid(row=1, column=0, sticky='nw', padx=8, pady=8)
        section_ui[prefix] = table, vertical, horizontal, empty

    previous = object()
    footer = ttk.Frame(panel, style='White.TFrame')
    footer.pack(fill='x')
    status = tk.StringVar(window)
    ttk.Label(footer, textvariable=status, style='WhiteMuted.TLabel', wraplength=370,
              justify='left').pack(side='left', fill='x', expand=True)
    close = RoundedButton(footer, text='Zamknij', command=window.destroy)
    close.pack(side='right')

    def request_refresh():
        app.request_default_layout_refresh()
        refresh()

    update = RoundedButton(footer, text='Aktualizuj', icon='refresh', command=request_refresh)
    update.pack(side='right', padx=(6, 8))

    def refresh():
        nonlocal previous
        session = getattr(app, 'session', None)
        layouts = session.saved_default_layouts() if session is not None and app.session_state == 'ready' else None
        request_id, phase, completed = app.default_layout_refresh
        missing = ', '.join(prefix for prefix in DEFAULT_LAYOUT_PREFIXES if prefix not in completed)
        messages = {
            'queued': 'W kolejce',
            'running': 'Aktualizowanie układów…',
            'returned': 'Zaktualizowano wszystkie cztery układy.',
            'partial': f'Nie udało się odświeżyć układów: {missing}.',
            'error': f'Nie udało się odświeżyć układów: {missing}.',
            'cancelled': f'Przerwano aktualizację. Pominięte układy: {missing}.',
        }
        if request_id is not None and app.session_state in ('waiting', 'failed'):
            status.set('Oczekiwanie na połączenie z ServiceNow.')
        else:
            status.set(messages.get(phase, ''))
        update.configure(state='normal' if app.can_refresh_default_layouts() else 'disabled')
        if layouts == previous:
            return layouts
        previous = layouts
        subtitle.set('Domyślne widoki zapisane dla aktualnego konta.' if layouts is not None else
                     'Układy będą dostępne po potwierdzeniu konta ServiceNow.')
        for prefix, (table, vertical, horizontal, empty) in section_ui.items():
            rows = layouts.get(prefix, ()) if layouts is not None else ()
            existing = table.get_children()
            if existing:
                table.delete(*existing)
            for row in rows:
                table.insert('', 'end', values=row)
            if rows:
                for index, (column, base) in enumerate((('label', 170), ('field', 180))):
                    width = max(base, max(font.measure(row[index]) for row in rows) + 18)
                    table.column(column, width=width, minwidth=width, stretch=False)
                empty.grid_remove()
                table.grid()
                vertical.grid()
                horizontal.grid()
            else:
                table.grid_remove()
                vertical.grid_remove()
                horizontal.grid_remove()
                empty.grid()
        return layouts

    def clear_refresh(event):
        if event.widget is window and app.refresh_saved_layout_preview is refresh:
            app.refresh_saved_layout_preview = None

    diagnostics = LoginDiagnostics(source='configuration')
    started = monotonic()
    measured_record(diagnostics, 'filter_layout_preview', outcome='started')
    app.refresh_saved_layout_preview = refresh
    window.bind('<Destroy>', clear_refresh, add='+')
    layouts = refresh()
    ready = sum(bool(rows) for rows in (layouts or {}).values())
    measured_record(diagnostics, 'filter_layout_preview',
                    outcome='authentication' if layouts is None else 'returned' if ready == len(section_ui) else 'partial',
                    ready_count=ready, duration_ms=round((monotonic() - started) * 1000))
    window.bind('<Escape>', lambda _: window.destroy())
    fit_and_center(window)
    window.deiconify()
    apply_window_style(window)
    window.grab_set()
    close.focus_set()
    return window
