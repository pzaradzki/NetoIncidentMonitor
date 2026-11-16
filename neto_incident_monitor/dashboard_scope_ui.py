"""Saved identifier lists used to scope the Dashboard SLA queries."""
import tkinter as tk
from tkinter import ttk

from neto_incident_monitor.analytics_config import dashboard_scope, load_config
from neto_incident_monitor.dashboard_context import DashboardReadError
from neto_incident_monitor.template_library_ui import fit_and_center
from neto_incident_monitor.theme import SURFACE
from neto_incident_monitor.widgets import RoundedButton
from neto_incident_monitor.window_style import apply_window_style


def show_dashboard_scope(app, parent):
    window = tk.Toplevel(parent, background=SURFACE)
    window.withdraw()
    window.title('Agenci i lokalizacje Dashboardu SLA')
    window.transient(parent)
    window.minsize(640, 390)
    panel = ttk.Frame(window, style='White.TFrame', padding=20)
    panel.pack(fill='both', expand=True)
    ttk.Label(panel, text='Agenci i lokalizacje Dashboardu SLA', style='White.TLabel',
              font=('Segoe UI', 14, 'bold')).pack(anchor='w')
    ttk.Label(panel, text='Identyfikatory używane w zapytaniach dashboardu.',
              style='WhiteMuted.TLabel').pack(anchor='w', pady=(4, 14))
    lists = ttk.Frame(panel, style='White.TFrame')
    lists.pack(fill='both', expand=True)
    lists.columnconfigure((0, 1), weight=1, uniform='scope')
    lists.rowconfigure(0, weight=1)
    tables = {}
    for column, (key, title) in enumerate((('assignees', 'Agenci'), ('locations', 'Lokalizacje'))):
        section = ttk.Frame(lists, style='White.TFrame')
        section.grid(row=0, column=column, sticky='nsew', padx=(0, 6) if column == 0 else (6, 0))
        section.columnconfigure(0, weight=1)
        section.rowconfigure(1, weight=1)
        heading = ttk.Label(section, text=title, style='White.TLabel', font=('Segoe UI', 11, 'bold'))
        heading.grid(row=0, column=0, sticky='w', pady=(0, 6))
        table = ttk.Treeview(section, columns=('id',), show='headings', height=9, selectmode='browse')
        table.heading('id', text='Identyfikator ServiceNow', anchor='w')
        table.column('id', width=260)
        table.grid(row=1, column=0, sticky='nsew')
        vertical = ttk.Scrollbar(section, orient='vertical', command=table.yview)
        vertical.grid(row=1, column=1, sticky='ns')
        table.configure(yscrollcommand=vertical.set)
        tables[key] = title, heading, table

    footer = ttk.Frame(panel, style='White.TFrame')
    footer.pack(fill='x', pady=(14, 0))
    status = tk.StringVar(window)
    ttk.Label(footer, textvariable=status, style='WhiteMuted.TLabel', wraplength=380,
              justify='left').pack(side='left', fill='x', expand=True)
    close = RoundedButton(footer, text='Zamknij', command=window.destroy)
    close.pack(side='right')

    def request():
        app.request_dashboard_scope_refresh()
        refresh()

    update = RoundedButton(footer, text='Aktualizuj', icon='refresh', command=request)
    update.pack(side='right', padx=(6, 8))
    snapshot = None
    config_available = False
    version = object()

    def refresh():
        nonlocal snapshot, config_available, version
        request_id, phase = app.dashboard_scope_refresh
        if version != phase:
            version = phase
            config_available = False
            try:
                config = load_config()
                config_available = True
                snapshot = dashboard_scope(config)
            except DashboardReadError:
                snapshot = None
            for key, (title, heading, table) in tables.items():
                rows = snapshot.get(key, ()) if snapshot else ()
                heading.configure(text=f'{title} · {len(rows)}' if snapshot else title)
                previous = table.get_children()
                if previous:
                    table.delete(*previous)
                for identifier in rows:
                    table.insert('', 'end', values=(identifier,))
        messages = {
            'queued': 'W kolejce',
            'running': 'Odczytywanie zakresu dashboardu…',
            'returned': 'Zaktualizowano obie listy.',
            'dashboard_scope_query': 'Nie potwierdzono obu list w zapytaniu P1. Zachowano poprzedni zakres.',
            'dashboard_scope_save': 'Nie udało się zapisać zakresu dashboardu. Zachowano poprzedni zakres.',
            'dashboard_scope_filter': 'Nie potwierdzono pełnego wyboru agentów i lokalizacji.',
            'rendering_unavailable': 'Nie udało się odczytać dashboardu w tle. Zachowano poprzednie listy.',
            'error': 'Nie udało się odczytać zakresu dashboardu. Zachowano poprzednie listy.',
            'cancelled': 'Odświeżanie zakresu zostało przerwane.',
        }
        if request_id is not None and app.session_state in ('waiting', 'failed'):
            status.set('Oczekiwanie na połączenie z ServiceNow.')
        else:
            status.set(messages.get(phase, 'Nie udało się odczytać zakresu dashboardu.' if phase else
                                    '' if snapshot else 'Brak poprawnego zapisu zakresu dashboardu.'))
        update.configure(state='normal' if config_available and app.can_refresh_dashboard_scope() else 'disabled')

    def clear(event):
        if event.widget is window and app.refresh_dashboard_scope_preview is refresh:
            app.refresh_dashboard_scope_preview = None

    app.refresh_dashboard_scope_preview = refresh
    window.bind('<Destroy>', clear, add='+')
    window.bind('<Escape>', lambda _: window.destroy())
    refresh()
    fit_and_center(window)
    window.deiconify()
    apply_window_style(window)
    window.grab_set()
    close.focus_set()
    return window
