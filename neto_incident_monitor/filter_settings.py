"""Notification preferences scoped to a single monitored filter."""
import tkinter as tk
from tkinter import ttk

from neto_incident_monitor.theme import SURFACE
from neto_incident_monitor.widgets import RoundedButton, Toggle
from neto_incident_monitor import themed_dialogs as messagebox


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
        controls[key].grid(row=0, column=1, rowspan=2, padx=(18, 0))
        controls[key].configure(state="normal" if enabled else "disabled")
        if key in ('notify_teams', 'notify_google_chat'):
            webhook_key = key.removeprefix('notify_') + '_webhook'
            ttk.Label(row, text='Webhook filtra (opcjonalnie)', style='WhiteMuted.TLabel').grid(
                row=2, column=0, columnspan=2, sticky='w', pady=(10, 4))
            webhooks[webhook_key] = tk.StringVar(value=entry.get(webhook_key, ''))
            ttk.Entry(row, textvariable=webhooks[webhook_key], show='•', width=48).grid(
                row=3, column=0, columnspan=2, sticky='ew')
            ttk.Label(row, text='Puste pole używa webhooka globalnego.', style='WhiteMuted.TLabel').grid(
                row=4, column=0, columnspan=2, sticky='w', pady=(4, 0))

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
    window.geometry(f"+{max(0, (window.winfo_screenwidth()-window.winfo_reqwidth())//2)}+{max(0, (window.winfo_screenheight()-window.winfo_reqheight())//2)}")
    window.grab_set()
