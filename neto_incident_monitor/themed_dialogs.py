"""Themed information/error dialogs with the messagebox call interface."""
import tkinter as tk
from tkinter import ttk
from neto_incident_monitor.theme import BG, TEXT, MUTED, ACCENT
from neto_incident_monitor.widgets import RoundedButton
from neto_incident_monitor.window_style import apply_window_style


def _show(title, message, parent=None, error=False, **kwargs):
    owner = parent or tk._default_root
    temporary = owner is None
    if temporary:
        owner = tk.Tk()
        owner.withdraw()
    previous_grab = owner.grab_current()
    dialog = tk.Toplevel(owner)
    dialog.title(title)
    dialog.configure(background=BG)
    dialog.transient(owner)
    dialog.resizable(False, False)
    frame = tk.Frame(dialog, background=BG, padx=24, pady=24)
    frame.pack(fill="both", expand=True)
    tk.Label(frame, text=title, background=BG, foreground=ACCENT if error else TEXT,
             font=("Segoe UI", 14, "bold"), anchor="w").pack(fill="x", pady=(0, 14))
    tk.Label(frame, text=message, background=BG, foreground=MUTED, wraplength=460,
             justify="left", font=("Segoe UI", 10)).pack(anchor="w")
    button = RoundedButton(frame, text="OK", command=dialog.destroy, background=BG)
    button.pack(anchor="e", pady=(22, 0))
    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
    dialog.bind("<Escape>", lambda _: dialog.destroy())
    dialog.bind("<Return>", lambda _: dialog.destroy())
    dialog.update_idletasks()
    if not temporary:
        x = owner.winfo_rootx() + (owner.winfo_width() - dialog.winfo_reqwidth()) // 2
        y = owner.winfo_rooty() + (owner.winfo_height() - dialog.winfo_reqheight()) // 2
        dialog.geometry(f"+{max(0, x)}+{max(0, y)}")
    apply_window_style(dialog)
    dialog.grab_set()
    button.focus_set()
    owner.wait_window(dialog)
    if previous_grab is not None and previous_grab.winfo_exists():
        previous_grab.grab_set()
    if temporary:
        owner.destroy()
    return "ok"


def showinfo(title, message, **kwargs):
    return _show(title, message, **kwargs)


def showerror(title, message, **kwargs):
    return _show(title, message, error=True, **kwargs)
