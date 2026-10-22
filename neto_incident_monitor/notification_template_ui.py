"""Draft-only editor shared by Teams and Google Chat filter settings."""
import tkinter as tk
from tkinter import ttk

from neto_incident_monitor.notification_templates import DEFAULT_MESSAGE, DEFAULT_ITEM, render, validate, standard
from neto_incident_monitor.theme import SURFACE, MUTED, TEXT
from neto_incident_monitor.widgets import RoundedButton


def auto_scrollbar(frame, text):
    scroll = ttk.Scrollbar(frame, orient='vertical', command=text.yview)

    def update(first, last):
        scroll.set(first, last)
        if float(first) <= 0 and float(last) >= 1:
            scroll.pack_forget()
        elif not scroll.winfo_manager():
            scroll.pack(side='right', fill='y', before=text)

    text.configure(yscrollcommand=update)
    return scroll


def build_editor(panel, config, schema, name, named=False):
    from neto_incident_monitor.notification_templates import TOKEN, MESSAGE_ALIASES
    bindings = dict(config.get('bindings', {}))
    labels = []
    for column in schema:
        base = column['label'].replace('{', '(').replace('}', ')')
        label = base
        suffix = 2
        while label in labels or (label in bindings and bindings[label] != column['key']):
            label = f'{base} ({suffix})'
            suffix += 1
        labels.append(label)
        bindings[label] = column['key']
    friendly = {c['key']: label for c, label in zip(schema, labels)}
    initial_item = TOKEN.sub(lambda m: '{' + friendly.get(m[1], m[1]) + '}', config.get('item', DEFAULT_ITEM))
    enabled = tk.BooleanVar(value=config.get('enabled', False))
    ttk.Style(panel).configure('White.TCheckbutton', background=SURFACE, foreground=TEXT)
    if named:
        enabled.set(True)
    else:
        ttk.Checkbutton(panel, text='Własny szablon dla tego filtra', variable=enabled,
                        style='White.TCheckbutton').pack(anchor='w', pady=(16, 8))
    editors = ttk.Frame(panel, style='White.TFrame')
    editors.pack(fill='both', expand=True)

    def textbox(label, value, height):
        ttk.Label(editors, text=label, style='White.TLabel').pack(anchor='w', pady=(10, 5))
        frame = ttk.Frame(editors, style='White.TFrame')
        frame.pack(fill='both', expand=True)
        text = tk.Text(frame, height=height, width=64, wrap='word', bg=SURFACE, fg=TEXT,
                       insertbackground=TEXT, font=('Segoe UI', 10), undo=True,
                       relief='flat', borderwidth=0, highlightthickness=1,
                       highlightbackground='#484e58', highlightcolor='#929dab',
                       padx=10, pady=8, selectbackground='#513039', selectforeground='#ffe3e6')
        text.pack(side='left', fill='both', expand=True)
        auto_scrollbar(frame, text)
        text.insert('1.0', value)
        return text

    initial_message = TOKEN.sub(lambda m: '{' + MESSAGE_ALIASES.get(m[1], m[1]) + '}',
                                config.get('message', DEFAULT_MESSAGE))
    message = textbox('Szablon wiadomości', initial_message, 6)
    tools = ttk.Frame(editors, style='White.TFrame')
    tools.pack(fill='x', pady=5)

    def insert(text, token):
        text.insert('insert', '{' + token + '}')
        text.focus_set()
        refresh()

    for token, label in ((label, label) for label in ('nazwa filtra', 'liczba elementów', 'lista elementów')):
        RoundedButton(tools, text=label, compact=True,
                      command=lambda t=token: insert(message, t)).pack(side='left', padx=(0, 5))
    item = textbox('Szablon elementu listy',
                   initial_item, 6)
    picker = ttk.Frame(editors, style='White.TFrame')
    picker.pack(fill='x', pady=(8, 0))
    choice = ttk.Combobox(picker, values=labels, state='readonly')
    choice.pack(side='left', fill='x', expand=True)
    if labels:
        choice.current(0)
    RoundedButton(picker, text='Wstaw', command=lambda: insert(item, labels[choice.current()])
                  if choice.current() >= 0 else None).pack(side='right', padx=(8, 0))
    if not schema:
        ttk.Label(editors, text='Uruchom monitoring filtra, aby odczytać dostępne kolumny.',
                  style='WhiteMuted.TLabel').pack(anchor='w', pady=5)
    preview_label = ttk.Label(panel, text='Podgląd (dane przykładowe)', style='WhiteMuted.TLabel')
    preview_label.pack(anchor='w', pady=(12, 5))
    preview_frame = ttk.Frame(panel, style='White.TFrame')
    preview_frame.pack(fill='both', expand=True)
    preview = tk.Text(preview_frame, height=8, width=64, wrap='word', bg=SURFACE, fg=MUTED,
                      font=('Segoe UI', 10), state='disabled', relief='flat', borderwidth=0,
                      highlightthickness=1, highlightbackground='#484e58', highlightcolor='#929dab',
                      padx=10, pady=8, selectbackground='#513039', selectforeground='#ffe3e6')
    preview.pack(side='left', fill='both', expand=True)
    auto_scrollbar(preview_frame, preview)
    warning = tk.StringVar()
    ttk.Label(panel, textvariable=warning, wraplength=560, style='WhiteMuted.TLabel').pack(anchor='w')
    # Do not include actual record data in a configuration preview or test.
    sample = [{'number': 'INC0012345', 'short_description': 'Przykładowe zgłoszenie',
               '_values': {c['key']: f"Przykład: {c['label']}" for c in schema}},
              {'number': 'INC0012346', 'short_description': 'Drugie zgłoszenie'}]
    for row in sample:
        row.setdefault('_values', {}).update(number=row['number'], short_description=row['short_description'])

    def draft():
        return {'enabled': enabled.get(), 'message': message.get('1.0', 'end-1c'),
                'item': item.get('1.0', 'end-1c'), 'bindings': dict(bindings)}

    def refresh(*_):
        settings = draft()
        try:
            missing = validate(settings['message'], settings['item'], schema, settings['bindings'])
            warning.set('Niedostępne kolumny (puste przy wysyłce): ' + ', '.join(missing) if missing else '')
        except ValueError as error:
            warning.set(str(error))
        preview.configure(state='normal')
        preview.delete('1.0', 'end')
        preview.insert('1.0', render(settings, name, sample) if enabled.get() else '\n'.join(standard(name, sample)))
        preview.configure(state='disabled')
        if enabled.get():
            if not editors.winfo_manager():
                editors.pack(fill='both', expand=True, before=preview_label)
        else:
            editors.pack_forget()

    for text in (message, item):
        text.bind('<KeyRelease>', refresh)
        text.bind('<<Paste>>', lambda _: panel.after_idle(refresh))
    enabled.trace_add('write', refresh)
    refresh()
    return draft, lambda: render(draft(), name, sample) if enabled.get() else '\n'.join(standard(name, sample))
