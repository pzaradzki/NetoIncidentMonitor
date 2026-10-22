"""Named template selection and nested draft editor."""
import copy
import tkinter as tk
from tkinter import ttk
from neto_incident_monitor import themed_dialogs as confirmation

from neto_incident_monitor import themed_dialogs as messagebox
from neto_incident_monitor.theme import SURFACE
from neto_incident_monitor.widgets import RoundedButton
from neto_incident_monitor.template_library import put, resolve
from neto_incident_monitor.notification_templates import render, standard, validate


def fit_and_center(window, large=False):
    window.update_idletasks()
    width = max(640 if large else 620, window.winfo_reqwidth())
    height = window.winfo_reqheight()
    width = min(width, window.winfo_screenwidth() - 40)
    height = min(height, window.winfo_screenheight() - 80)
    x = max(0, (window.winfo_screenwidth() - width) // 2)
    y = max(0, (window.winfo_screenheight() - height) // 2)
    window.geometry(f'{width}x{height}+{x}+{y}')


def modal(parent, title, large=False):
    window = tk.Toplevel(parent)
    window.title(title)
    window.configure(background=SURFACE)
    window.transient(parent)
    window.resizable(True, True)
    footer = ttk.Frame(window, style='White.TFrame', padding=(24, 12))
    footer.pack(side='bottom', fill='x')
    panel = ttk.Frame(window, style='White.TFrame', padding=24)
    panel.pack(fill='both', expand=True)

    def close():
        window.destroy()
        if parent.winfo_exists():
            parent.grab_set()
    window.protocol('WM_DELETE_WINDOW', close)
    window.bind('<Escape>', lambda _: close())
    window.minsize(520, 280)
    window.grab_set()
    return window, panel, footer, close


def show_channel_settings(parent, title, key, value, template=None, schema=None, name='', app=None, library=None,
                          save_library=None, save_channel=None):
    from neto_incident_monitor.teams_notifications import validate_webhook as teams_validate
    from neto_incident_monitor.google_chat_notifications import validate_webhook as chat_validate
    validator = teams_validate if key == 'teams_webhook' else chat_validate
    library = library if library is not None else {}
    working = copy.deepcopy(library)
    template = template if template is not None else {}
    schema = schema or []
    window, panel, footer, close = modal(parent, title)
    ttk.Label(panel, text='Adres webhooka (opcjonalnie)', style='White.TLabel').pack(anchor='w')
    address = tk.StringVar(value=value.get())
    ttk.Entry(panel, textvariable=address, show='•').pack(fill='x', pady=(8, 6))
    ttk.Label(panel, text='Pozostaw puste, aby użyć ustawień globalnych.', style='WhiteMuted.TLabel').pack(anchor='w')
    ttk.Label(panel, text='Szablon powiadomienia', style='White.TLabel').pack(anchor='w', pady=(20, 6))
    selected = template.get('template_id', '')
    choice = ttk.Combobox(panel, state='readonly')
    choice.pack(fill='x')
    tools = ttk.Frame(panel, style='White.TFrame')
    tools.pack(fill='x', pady=(10, 0))
    note = tk.StringVar()
    ttk.Label(panel, textvariable=note, wraplength=560, style='WhiteMuted.TLabel').pack(anchor='w', pady=(10, 0))
    identities = []

    def refresh():
        nonlocal selected, identities
        identities = [''] + sorted(working, key=lambda identity: working[identity]['name'].casefold())
        if selected not in identities:
            selected = ''
        choice.configure(values=['Standardowy'] + [working[i]['name'] for i in identities[1:]])
        choice.current(identities.index(selected))
        edit_button.configure(state='normal' if selected else 'disabled')
        delete_button.configure(state='normal' if selected else 'disabled')
        note.set('')
        if selected:
            config = working[selected]
            try:
                missing = validate(config['message'], config['item'], schema, config.get('bindings'))
                if missing:
                    note.set('Nie udało się odczytać pól: ' + ', '.join(missing))
            except ValueError as error:
                note.set(str(error))

    def choose(_=None):
        nonlocal selected
        selected = identities[choice.current()] if choice.current() >= 0 else ''
        refresh()

    def edit(adding=False):
        if not adding and not selected:
            return
        identity = None if adding else selected
        config = working.get(identity, {})
        editor, body, buttons, cancel = modal(window, 'Dodaj szablon' if adding else 'Edytuj szablon', large=True)
        ttk.Label(body, text='Nazwa szablonu', style='White.TLabel').pack(anchor='w')
        template_name = tk.StringVar(value=config.get('name', ''))
        field = ttk.Entry(body, textvariable=template_name)
        field.pack(fill='x', pady=(6, 10))
        from neto_incident_monitor.notification_template_ui import build_editor
        get_draft, _ = build_editor(body, config, schema, name, named=True)

        def save():
            nonlocal selected
            draft = get_draft()
            try:
                validate(draft['message'], draft['item'], schema, draft.get('bindings'))
                candidate = copy.deepcopy(working)
                new_identity = put(candidate, template_name.get(), draft['message'], draft['item'], identity, draft.get('bindings'))
                if save_library is not None:
                    save_library(candidate)
                working.clear()
                working.update(candidate)
                selected = new_identity
            except (OSError, ValueError) as error:
                messagebox.showerror('Szablon', str(error) if isinstance(error, ValueError)
                                     else 'Nie udało się zapisać szablonu. Spróbuj ponownie.', parent=editor)
                editor.grab_set()
                return
            cancel()
            refresh()
        RoundedButton(buttons, text='Zapisz szablon', command=save, primary=True).pack(side='right')
        RoundedButton(buttons, text='Anuluj', command=cancel).pack(side='right', padx=8)
        field.focus_set()
        fit_and_center(editor, large=True)

    def delete():
        nonlocal selected
        if not selected:
            return
        if confirmation.askyesno('Usuń szablon',
                f'Usunąć szablon „{working[selected]["name"]}”?\nFiltry używające go wrócą do szablonu Standardowy.',
                parent=window, default='no'):
            candidate = copy.deepcopy(working)
            del candidate[selected]
            try:
                if save_library is not None:
                    save_library(candidate)
            except (OSError, ValueError):
                messagebox.showerror('Usuń szablon', 'Nie udało się zapisać usunięcia szablonu.', parent=window)
                window.grab_set()
                return
            working.clear()
            working.update(candidate)
            selected = ''
            refresh()
        window.grab_set()

    RoundedButton(tools, text='Dodaj', command=lambda: edit(True)).pack(side='left')
    edit_button = RoundedButton(tools, text='Edytuj', command=edit)
    edit_button.pack(side='left', padx=8)
    delete_button = RoundedButton(tools, text='Usuń', command=delete)
    delete_button.pack(side='left')
    choice.bind('<<ComboboxSelected>>', choose)

    def apply():
        try:
            text = validator(address.get()) if address.get().strip() else ''
            if save_channel is not None:
                save_channel(key, text, {'template_id': selected})
        except (OSError, ValueError) as error:
            messagebox.showerror(title, str(error) if isinstance(error, ValueError)
                                 else 'Nie udało się zapisać ustawień kanału. Spróbuj ponownie.', parent=window)
            window.grab_set()
            return
        value.set(text)
        template.clear()
        template['template_id'] = selected
        library.clear()
        library.update(working)
        close()

    def test():
        try:
            destination = validator(address.get().strip() or getattr(app, key, ''))
            sample = [{'number': 'INC0012345', 'short_description': 'Przykładowe zgłoszenie',
                       '_values': {c['key']: f"Przykład: {c['label']}" for c in schema}}]
            config = resolve({'template_id': selected}, working)
            header, message = ('', render(config, name, sample)) if config else standard(name, sample)
            sender = app.teams_sender if key == 'teams_webhook' else app.google_chat_sender
            sender.submit(destination, header, message, test=True)
        except ValueError as error:
            messagebox.showerror(title, str(error), parent=window)
        window.grab_set()
    if app is not None:
        RoundedButton(footer, text='Wyślij test', command=test).pack(side='left')
    RoundedButton(footer, text='Zastosuj', command=apply, primary=True).pack(side='right')
    RoundedButton(footer, text='Anuluj', command=close).pack(side='right', padx=8)
    refresh()
    fit_and_center(window)
