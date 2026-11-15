"""Read-only preview of saved ServiceNow list metadata."""
import tkinter as tk
from tkinter import ttk

from neto_incident_monitor.columns import LOCAL_FIELDS
from neto_incident_monitor.theme import BG, MUTED, SURFACE, TEXT
from neto_incident_monitor.widgets import RoundedButton
from neto_incident_monitor.window_style import apply_window_style


def show_filter_definition(parent, name, definition, *, refresh):
    dialog = tk.Toplevel(parent)
    dialog.withdraw()
    dialog.title(f'Definicja filtra – {name}')
    dialog.transient(parent)
    dialog.configure(bg=BG)
    content = tk.Frame(dialog, bg=BG, padx=20, pady=16)
    content.pack(fill='both', expand=True)

    view = definition['view'] or 'nieokreślony w adresie'
    tk.Label(content, text=f"Tabela {definition['table']}   •   Widok {view}",
             bg=BG, fg=MUTED).pack(anchor='w', pady=(0, 8))
    query = definition['query']
    query_area = tk.Frame(content, bg=BG)
    query_area.pack(fill='x')
    query_text = tk.Text(query_area, height=6, width=68, wrap='word', bg=SURFACE, fg=TEXT,
                         relief='flat', padx=8, pady=6, font=('Consolas', 10))
    query_scroll = ttk.Scrollbar(query_area, command=query_text.yview)
    query_text.configure(yscrollcommand=query_scroll.set)
    query_scroll.pack(side='right', fill='y')
    query_text.pack(fill='both', expand=True)
    query_text.insert('1.0', query or '(Puste zapytanie)')
    query_text.configure(state='disabled')

    tk.Label(content, text='Kolumny', bg=BG, fg=TEXT).pack(anchor='w', pady=(12, 6))
    columns_area = tk.Frame(content, bg=BG)
    columns_area.pack(fill='both', expand=True)
    columns = ttk.Treeview(columns_area, columns=('label', 'field'), show='headings', height=8)
    columns.heading('label', text='Nazwa')
    columns.heading('field', text='Pole ServiceNow')
    columns.column('label', width=240)
    columns.column('field', width=260)
    scroll = ttk.Scrollbar(columns_area, command=columns.yview)
    columns.configure(yscrollcommand=scroll.set)
    scroll.pack(side='right', fill='y')
    columns.pack(fill='both', expand=True)
    for column in definition['columns']:
        columns.insert('', 'end', values=(column['label'], column.get('field') or 'Nie rozpoznano pola'))
    for key, label, _ in LOCAL_FIELDS:
        if key != 'age_minutes' or definition['table'] == 'incident':
            columns.insert('', 'end', values=(label, 'Kolumna lokalna'))

    def copy_query():
        parent.clipboard_clear()
        parent.clipboard_append(query)

    actions = tk.Frame(content, bg=BG)
    actions.pack(fill='x', pady=(12, 0))
    close = RoundedButton(actions, text='Zamknij', command=dialog.destroy, background=BG)
    close.pack(side='right')
    copy = RoundedButton(actions, text='Kopiuj zapytanie', command=copy_query, background=BG)
    copy.pack(side='right', padx=(0, 8))
    if not query:
        copy.configure(state='disabled')
    def refresh_definition():
        if refresh():
            dialog.destroy()
        else:
            refresh_status.configure(text='Odświeżanie jest dostępne po zalogowaniu do ServiceNow.')

    refresh_status = tk.Label(content, bg=BG, fg=MUTED)
    refresh_status.pack(anchor='w')
    refresh_button = RoundedButton(actions, text='Odśwież definicję z SNOW',
                                   command=refresh_definition, background=BG)
    refresh_button.pack(side='left')
    dialog.bind('<Escape>', lambda _: dialog.destroy())
    dialog.update_idletasks()
    width, height = dialog.winfo_reqwidth(), dialog.winfo_reqheight()
    x = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
    y = parent.winfo_rooty() + (parent.winfo_height() - height) // 2
    dialog.geometry(f'+{max(0, x)}+{max(0, y)}')
    dialog.deiconify()
    dialog.after_idle(lambda: apply_window_style(dialog))
    dialog.grab_set()
    close.focus_set()
