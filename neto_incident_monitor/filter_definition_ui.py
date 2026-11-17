"""Read-only preview of saved ServiceNow list metadata."""
import tkinter as tk
from tkinter import ttk

from neto_incident_monitor.theme import BG, MUTED, SURFACE, TEXT
from neto_incident_monitor.widgets import RoundedButton
from neto_incident_monitor.window_style import current_grab_path


def show_filter_definition(parent, name, definition, *, refresh):
    parent_had_grab = str(current_grab_path(parent)) == str(parent)
    dialog = tk.Toplevel(parent)
    dialog.withdraw()
    dialog.title(f'Definicja filtra – {name}')
    dialog.transient(parent)
    dialog.configure(bg=BG)
    content = tk.Frame(dialog, bg=BG, padx=20, pady=16)
    content.pack(fill='both', expand=True)

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

    def copy_query():
        parent.clipboard_clear()
        parent.clipboard_append(query)

    def close_preview():
        dialog.destroy()
        if parent_had_grab and parent.winfo_viewable() and not current_grab_path(parent):
            parent.grab_set()

    actions = tk.Frame(content, bg=BG)
    actions.pack(fill='x', pady=(12, 0))
    close = RoundedButton(actions, text='Zamknij', command=close_preview, background=BG)
    close.pack(side='right')
    copy = RoundedButton(actions, text='Kopiuj zapytanie', command=copy_query, background=BG)
    copy.pack(side='right', padx=(0, 8))
    if not query:
        copy.configure(state='disabled')
    def refresh_definition():
        if refresh():
            close_preview()
        else:
            refresh_status.configure(text='Odświeżanie jest dostępne po zalogowaniu do ServiceNow.')

    refresh_status = tk.Label(content, bg=BG, fg=MUTED)
    refresh_status.pack(anchor='w')
    refresh_button = RoundedButton(actions, text='Odśwież zapytanie z SNOW',
                                   command=refresh_definition, background=BG)
    refresh_button.pack(side='left')
    dialog.protocol('WM_DELETE_WINDOW', close_preview)
    dialog.bind('<Escape>', lambda _: close_preview())
    dialog.update_idletasks()
    width, height = dialog.winfo_reqwidth(), dialog.winfo_reqheight()
    x = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
    y = parent.winfo_rooty() + (parent.winfo_height() - height) // 2
    dialog.geometry(f'+{max(0, x)}+{max(0, y)}')
    dialog.deiconify()
    dialog.grab_set()
    close.focus_set()
