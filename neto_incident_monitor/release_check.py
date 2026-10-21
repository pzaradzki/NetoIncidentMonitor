"""Manual release lookup. Opens a release page, never downloads or installs files."""
import json
import logging
import queue
import re
import ssl
import threading
import tkinter as tk
import webbrowser
from tkinter import ttk
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, unquote

from neto_incident_monitor import __version__
from neto_incident_monitor.theme import BG
from neto_incident_monitor.widgets import RoundedButton

API = 'https://api.github.com/repos/pzaradzki/NetoIncidentMonitor/releases/latest'
RELEASES = 'https://github.com/pzaradzki/NetoIncidentMonitor/releases/tag/'
LOG = logging.getLogger(__name__)


def release_page_tag():
    request = Request('https://github.com/pzaradzki/NetoIncidentMonitor/releases/latest',
                      headers={'User-Agent': f'NetoIncidentMonitor/{__version__}'}, method='HEAD')
    with urlopen(request, timeout=15) as response:
        address = urlparse(response.geturl())
    prefix = '/pzaradzki/NetoIncidentMonitor/releases/tag/'
    if address.scheme != 'https' or address.netloc != 'github.com' or not address.path.startswith(prefix):
        raise ValueError('Nieprawidłowy adres wydania GitHub.')
    tag = unquote(address.path[len(prefix):])
    version(tag)
    return version(tag) > version(__version__), RELEASES + tag


def failure_message(error):
    if isinstance(error, HTTPError):
        if error.code == 429 or (error.code == 403 and error.headers.get('X-RateLimit-Remaining') == '0'):
            return 'GitHub ograniczył dostęp do sprawdzania wydań. Spróbuj ponownie później.'
        if error.code == 403:
            return 'Dostęp do informacji o wydaniu został odrzucony (HTTP 403). Szczegóły zapisano w logu.'
        if error.code == 404:
            return 'Nie znaleziono opublikowanego wydania aplikacji na GitHubie.'
        return f'GitHub zwrócił błąd HTTP {error.code}. Spróbuj ponownie później.'
    reason = error.reason if isinstance(error, URLError) else error
    if isinstance(reason, ssl.SSLError):
        return 'Nie udało się zweryfikować bezpiecznego połączenia z GitHubem. Szczegóły zapisano w logu.'
    if isinstance(reason, (TimeoutError, OSError)):
        return 'Nie udało się połączyć z GitHubem. Sprawdź połączenie internetowe lub dostęp przez sieć firmową.'
    return 'Nie udało się odczytać informacji o wydaniu GitHub. Szczegóły zapisano w logu.'


def version(value):
    if not isinstance(value, str) or not re.fullmatch(r'v?\d+\.\d+\.\d+', value):
        raise ValueError('Nieprawidłowa wersja wydania.')
    return tuple(int(part) for part in value.removeprefix('v').split('.'))


def latest_release():
    request = Request(API, headers={'Accept': 'application/vnd.github+json',
                                  'User-Agent': f'NetoIncidentMonitor/{__version__}'})
    try:
        with urlopen(request, timeout=15) as response:
            content = response.read(1_000_001)
    except HTTPError as error:
        LOG.warning('GitHub HTTP %s, remaining=%s, reset=%s, retry_after=%s',
                    error.code, error.headers.get('X-RateLimit-Remaining'),
                    error.headers.get('X-RateLimit-Reset'), error.headers.get('Retry-After'))
        if error.code == 429 or (error.code == 403 and error.headers.get('X-RateLimit-Remaining') == '0'):
            return release_page_tag()
        raise
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
    text = ((error if isinstance(error, str) else 'Nie udało się sprawdzić aktualizacji. Spróbuj ponownie później.') if error else
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
        except Exception as error:
            LOG.exception('Nie udało się sprawdzić najnowszego wydania GitHub')
            results.put(failure_message(error))

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
        if isinstance(result, str):
            show_result(owner, False, error=result)
        else:
            show_result(owner, *result)

    threading.Thread(target=work, daemon=True).start()
    owner.after(100, poll)
