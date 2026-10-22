"""Notification preferences scoped to a single monitored filter."""
import tkinter as tk
from tkinter import ttk

from neto_incident_monitor.theme import SURFACE
from neto_incident_monitor.widgets import RoundedButton, Toggle
from neto_incident_monitor import themed_dialogs as messagebox


def show_channel_settings(parent, title, key, value):
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.configure(background=SURFACE)
    dialog.transient(parent)
    dialog.resizable(False, False)
    panel = ttk.Frame(dialog, style='White.TFrame', padding=24)
    panel.pack(fill='both', expand=True)
    ttk.Label(panel, text='Webhook filtra (opcjonalnie)', style='White.TLabel').pack(anchor='w')
    draft = tk.StringVar(value=value.get())
    address = ttk.Entry(panel, textvariable=draft, show='•', width=48)
    address.pack(fill='x', pady=(8, 6))
    ttk.Label(panel, text='Puste pole używa webhooka globalnego.', style='WhiteMuted.TLabel').pack(anchor='w')

    def close():
        dialog.destroy()
        if parent.winfo_exists():
            parent.grab_set()

    def apply():
        from neto_incident_monitor.teams_notifications import validate_webhook as teams_validate
        from neto_incident_monitor.google_chat_notifications import validate_webhook as chat_validate
        text = draft.get().strip()
        try:
            if text:
                text = (teams_validate if key == 'teams_webhook' else chat_validate)(text)
        except ValueError as error:
            messagebox.showerror(title, str(error), parent=dialog)
            dialog.grab_set()
            return
        value.set(text)
        close()

    footer = ttk.Frame(panel, style='White.TFrame')
    footer.pack(fill='x', pady=(20, 0))
    RoundedButton(footer, text='Zastosuj', command=apply, primary=True).pack(side='right')
    RoundedButton(footer, text='Anuluj', command=close).pack(side='right', padx=8)
    dialog.protocol('WM_DELETE_WINDOW', close)
    dialog.bind('<Escape>', lambda _: close())
    dialog.update_idletasks()
    dialog.geometry(f'+{max(0, (dialog.winfo_screenwidth()-dialog.winfo_reqwidth())//2)}+{max(0, (dialog.winfo_screenheight()-dialog.winfo_reqheight())//2)}')
    dialog.grab_set()
    address.focus_set()


def show_filter_settings(app, index):
    entry = app.filters[index]
    window = tk.Toplevel(app.root)
    window.title("Ustawienia filtra")
    window.configure(background=SURFACE)
    window.transient(app.root)
    window.resizable(False, False)
    panel = ttk.Frame(window, style="White.TFrame", padding=24)
    panel.pack(fill="both", expand=True)
    ttk.Label(panel, text=entry["name"], style="White.TLabel",
              font=("Segoe UI", 14, "bold"), wraplength=430).pack(anchor="w", pady=(0, 18))
    values = {}
    controls = {}
    webhooks = {}
    for key, title, description, enabled in [
        ("notify_windows", "Powiadomienia Windows", "Wymagają włączonych powiadomień globalnych.", app.notify.get()),
        ("notify_teams", "Powiadomienia Microsoft Teams", "Wymagają włączonych powiadomień globalnych.", app.teams_enabled.get()),
        ("notify_google_chat", "Powiadomienia Google Chat", "Wymagają włączonych powiadomień globalnych.", app.google_chat_enabled.get()),
        ("first_only", "Tylko pierwsze wystąpienie", "Nie powiadamiaj ponownie, gdy incydent wróci do filtra.", True),
        ("allow_large_list", "Pobieraj duże listy bez pytania", "Dotyczy list zawierających ponad 1000 wpisów.", True),
    ]:
        if not enabled:
            continue
        row = ttk.Frame(panel, style="White.TFrame", padding=(0, 10))
        row.pack(fill="x")
        row.columnconfigure(0, weight=1)
        ttk.Label(row, text=title, style="White.TLabel", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(row, text=description, style="WhiteMuted.TLabel", wraplength=350).grid(row=1, column=0, sticky="w", pady=(4, 0))
        values[key] = tk.BooleanVar(value=entry.get(key, key in ("notify_windows", "notify_teams", "notify_google_chat")))
        controls[key] = Toggle(row, values[key])
        controls[key].grid(row=0, column=2, rowspan=2, padx=(10, 0))
        controls[key].configure(state="normal" if enabled else "disabled")
        if key in ('notify_teams', 'notify_google_chat'):
            webhook_key = key.removeprefix('notify_') + '_webhook'
            webhooks[webhook_key] = tk.StringVar(value=entry.get(webhook_key, ''))
            gear = RoundedButton(row, text='', icon='gear', command=lambda k=webhook_key, t=title:
                                 show_channel_settings(window, t, k, webhooks[k]))
            gear.grid(row=0, column=1, rowspan=2, padx=(18, 0))

    def save():
        from neto_incident_monitor.teams_notifications import validate_webhook as teams_validate
        from neto_incident_monitor.google_chat_notifications import validate_webhook as chat_validate
        addresses = {}
        try:
            for key, variable in webhooks.items():
                value = variable.get().strip()
                # Preserve unreadable protected values on unrelated edits.
                original = entry.get(key, '')
                addresses[key] = original if value == original else value
                if value:
                    addresses[key] = (teams_validate if key == 'teams_webhook' else chat_validate)(value)
        except ValueError as error:
            messagebox.showerror('Ustawienia filtra', str(error), parent=window)
            return
        previous = dict(entry)
        entry.update({key: value.get() for key, value in values.items()})
        entry.update(addresses)
        try:
            app.persist_filters()
        except (OSError, ValueError):
            entry.clear()
            entry.update(previous)
            messagebox.showerror("Ustawienia filtra", 'Nie udało się zapisać ustawień filtra.', parent=window)
            return
        window.destroy()

    footer = ttk.Frame(panel, style="White.TFrame")
    footer.pack(fill="x", pady=(18, 0))
    RoundedButton(footer, text="Zapisz", command=save, primary=True).pack(side="right")
    RoundedButton(footer, text="Anuluj", command=window.destroy).pack(side="right", padx=8)
    window.bind("<Escape>", lambda event: window.destroy())
    window.update_idletasks()
    width = max(520, window.winfo_reqwidth())
    height = window.winfo_reqheight()
    window.geometry(f"{width}x{height}+{max(0, (window.winfo_screenwidth()-width)//2)}+{max(0, (window.winfo_screenheight()-height)//2)}")
    window.grab_set()
