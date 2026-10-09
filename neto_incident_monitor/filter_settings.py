"""Notification preferences scoped to a single monitored filter."""
import tkinter as tk
from tkinter import ttk

from neto_incident_monitor.theme import SURFACE
from neto_incident_monitor.widgets import RoundedButton, Toggle
from neto_incident_monitor import themed_dialogs as messagebox


def show_filter_settings(app, index):
    entry = app.filters[index]
    window = tk.Toplevel(app.root)
    window.title("Powiadomienia filtra")
    window.configure(background=SURFACE)
    window.transient(app.root)
    window.resizable(False, False)
    panel = ttk.Frame(window, style="White.TFrame", padding=24)
    panel.pack(fill="both", expand=True)
    ttk.Label(panel, text=entry["name"], style="White.TLabel",
              font=("Segoe UI", 14, "bold"), wraplength=430).pack(anchor="w", pady=(0, 18))
    values = {}
    controls = {}
    for key, title, description, enabled in [
        ("notify_windows", "Powiadomienia Windows", "Wymagają włączonych powiadomień globalnych.", app.notify.get()),
        ("notify_teams", "Powiadomienia Microsoft Teams", "Wymagają włączonych powiadomień globalnych.", app.teams_enabled.get()),
        ("first_only", "Tylko pierwsze wystąpienie", "Nie powiadamiaj ponownie, gdy incydent wróci do filtra.", True),
    ]:
        row = ttk.Frame(panel, style="White.TFrame", padding=(0, 10))
        row.pack(fill="x")
        row.columnconfigure(0, weight=1)
        ttk.Label(row, text=title, style="White.TLabel", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(row, text=description, style="WhiteMuted.TLabel", wraplength=350).grid(row=1, column=0, sticky="w", pady=(4, 0))
        values[key] = tk.BooleanVar(value=entry.get(key, key != "first_only"))
        controls[key] = Toggle(row, values[key])
        controls[key].grid(row=0, column=1, rowspan=2, padx=(18, 0))
        controls[key].configure(state="normal" if enabled else "disabled")

    def save():
        previous = dict(entry)
        entry.update({key: value.get() for key, value in values.items()})
        try:
            app.persist_filters()
        except OSError as error:
            entry.clear()
            entry.update(previous)
            messagebox.showerror("Powiadomienia filtra", str(error), parent=window)
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
