"""Google Chat configuration, using the same interaction as Teams settings."""
import tkinter as tk
from tkinter import ttk
import webbrowser

from neto_incident_monitor import themed_dialogs as messagebox
from neto_incident_monitor.google_chat_notifications import validate_webhook
from neto_incident_monitor.theme import BG
from neto_incident_monitor.widgets import RoundedButton


def persist(app):
    from neto_incident_monitor.app import CONFIG, read_json, save_json
    try:
        settings = read_json(CONFIG, {})
        settings.update(google_chat_enabled=app.google_chat_enabled.get(), google_chat_webhook=app.google_chat_webhook)
        save_json(CONFIG, settings)
        app.saved_google_chat = app.google_chat_enabled.get(), app.google_chat_webhook
        return True
    except (OSError, ValueError):
        app.saving_google_chat = True
        enabled, app.google_chat_webhook = app.saved_google_chat
        app.google_chat_enabled.set(enabled)
        app.saving_google_chat = False
        app.status.set('Nie udało się zapisać konfiguracji Google Chat.')
        return False


def changed(app):
    if app.saving_google_chat:
        return
    if app.google_chat_enabled.get() and not app.google_chat_webhook:
        show_config(app)
        if not app.google_chat_webhook:
            app.google_chat_enabled.set(False)
            return
    persist(app)


def show_config(app):
    dialog = tk.Toplevel(app.root)
    dialog.configure(background=BG)
    dialog.title('Powiadomienia Google Chat')
    dialog.transient(app.root)
    dialog.resizable(False, False)
    panel = ttk.Frame(dialog, padding=20)
    panel.pack(fill='both', expand=True)
    ttk.Label(panel, text='Adres Webhook').pack(anchor='w')
    address = tk.StringVar(value=app.google_chat_webhook)
    field = ttk.Entry(panel, textvariable=address, show='•', width=65)
    field.pack(fill='x', pady=8)
    shown = tk.BooleanVar(value=False)
    ttk.Checkbutton(panel, text='Pokaż adres', variable=shown, style='App.TCheckbutton',
                    command=lambda: field.configure(show='' if shown.get() else '•')).pack(anchor='w')
    buttons = ttk.Frame(panel)
    buttons.pack(fill='x', pady=(16, 0))

    def accepted():
        try:
            return validate_webhook(address.get())
        except ValueError as error:
            messagebox.showerror('Google Chat', str(error), parent=dialog)

    def save():
        value = accepted()
        if value:
            app.google_chat_webhook = value
            if persist(app):
                dialog.destroy()
            else:
                messagebox.showerror('Google Chat', 'Nie udało się zapisać konfiguracji.', parent=dialog)

    def test():
        value = accepted()
        if value:
            app.google_chat_sender.submit(value, 'Test powiadomień ServiceNow', 'Połączenie z aplikacją działa.', True)

    def instruction():
        try:
            if webbrowser.open('https://developers.google.com/workspace/chat/quickstart/webhooks'):
                return
        except Exception:
            pass
        messagebox.showerror('Google Chat', 'Nie udało się otworzyć instrukcji w przeglądarce.', parent=dialog)

    RoundedButton(buttons, background=BG, text='Wyślij test', command=test).pack(side='left')
    RoundedButton(buttons, background=BG, text='Instrukcja', command=instruction).pack(side='left', padx=8)
    RoundedButton(buttons, background=BG, text='Zapisz', command=save).pack(side='right')
    RoundedButton(buttons, background=BG, text='Anuluj', command=dialog.destroy).pack(side='right', padx=8)
    dialog.bind('<Escape>', lambda event: dialog.destroy())
    dialog.update_idletasks()
    dialog.geometry(f'+{max(0, (dialog.winfo_screenwidth()-dialog.winfo_reqwidth())//2)}+{max(0, (dialog.winfo_screenheight()-dialog.winfo_reqheight())//2)}')
    dialog.grab_set()
    field.focus_set()
    app.root.wait_window(dialog)
