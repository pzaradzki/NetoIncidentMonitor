"""Manual release lookup. Opens a release page, never downloads or installs files."""
import json
import queue
import re
import threading
import tkinter as tk
import webbrowser
from tkinter import ttk
from urllib.request import Request, urlopen

from neto_incident_monitor import __version__
from neto_incident_monitor.theme import BG
from neto_incident_monitor.widgets import RoundedButton

API = 'https://api.github.com/repos/pzaradzki/NetoIncidentMonitor/releases/latest'
RELEASES = 'https://github.com/pzaradzki/NetoIncidentMonitor/releases/tag/'


def version(value):
    if not isinstance(value, str) or not re.fullmatch(r'v?\d+\.\d+\.\d+', value):
        raise ValueError('Nieprawidłowa wersja wydania.')
    return tuple(int(part) for part in value.removeprefix('v').split('.'))


def latest_release():
    request = Request(API, headers={'Accept': 'application/vnd.github+json',
                                  'User-Agent': f'NetoIncidentMonitor/{__version__}'})
    with urlopen(request, timeout=15) as response:
        content = response.read(1_000_001)
    if len(content) > 1_000_000:
        raise ValueError('Nieprawidłowa odpowiedź GitHub.')
    data = json.loads(content)
    if not isinstance(data, dict) or data.get('draft') or data.get('prerelease'):
        raise ValueError('Nieprawidłowe wydanie GitHub.')
    tag = data.get('tag_name')
    newer = version(tag) > version(__version__)
    return newer, RELEASES + tag


def show_result(owner, newer, url=None, error=False):
    dialog = tk.Toplevel(owner)
    dialog.title('Aktualizacje')
    dialog.configure(background=BG)
    dialog.transient(owner)
    dialog.resizable(False, False)
    panel = ttk.Frame(dialog, padding=24)
    panel.pack(fill='both', expand=True)
    text = ('Nie udało się sprawdzić aktualizacji. Spróbuj ponownie później.' if error else
            'Nowa wersja aplikacji jest dostępna' if newer else
            'Najnowsza wersja aplikacji jest zainstalowana')
    message = ttk.Label(panel, text=text, wraplength=420)
    message.pack(anchor='w')
    footer = ttk.Frame(panel)
    footer.pack(fill='x', pady=(22, 0))

    def open_release():
        try:
            if webbrowser.open(url):
                dialog.destroy()
                return
        except Exception:
            pass
        message.configure(text='Nie udało się otworzyć przeglądarki. Spróbuj ponownie.')

    if newer and not error:
        RoundedButton(footer, text='Otwórz Github', command=open_release,
                      primary=True, background=BG).pack(side='right')
        RoundedButton(footer, text='Anuluj', command=dialog.destroy,
                      background=BG).pack(side='right', padx=8)
    else:
        RoundedButton(footer, text='Ok', command=dialog.destroy,
                      background=BG).pack(side='right')
    dialog.bind('<Escape>', lambda _: dialog.destroy())
    dialog.update_idletasks()
    dialog.geometry(f'+{max(0, (dialog.winfo_screenwidth()-dialog.winfo_reqwidth())//2)}+{max(0, (dialog.winfo_screenheight()-dialog.winfo_reqheight())//2)}')
    dialog.grab_set()


def check_updates(owner, button):
    if not button.enabled:
        return
    button.configure(state='disabled')
    results = queue.Queue()

    def work():
        try:
            results.put(latest_release())
        except Exception:
            results.put(None)

    def poll():
        if not owner.winfo_exists():
            return
        try:
            result = results.get_nowait()
        except queue.Empty:
            owner.after(100, poll)
            return
        button.configure(state='normal')
        if owner.state() == 'withdrawn':
            return
        if result is None:
            show_result(owner, False, error=True)
        else:
            show_result(owner, *result)

    threading.Thread(target=work, daemon=True).start()
    owner.after(100, poll)
