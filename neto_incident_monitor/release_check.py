"""Look up and present the latest stable release from either entry point."""
import json
import queue
import re
import ssl
import threading
import tkinter as tk
import webbrowser
from time import monotonic
from tkinter import ttk
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, unquote

from neto_incident_monitor import __version__
from neto_incident_monitor.login_diagnostics import LoginDiagnostics
from neto_incident_monitor.theme import BG
from neto_incident_monitor.widgets import RoundedButton
from neto_incident_monitor.window_style import current_grab_path

API = 'https://api.github.com/repos/pzaradzki/NetoIncidentMonitor/releases/latest'
RELEASES = 'https://github.com/pzaradzki/NetoIncidentMonitor/releases/tag/'


def release_page_tag():
    request = Request('https://github.com/pzaradzki/NetoIncidentMonitor/releases/latest',
                      headers={'User-Agent': f'NetoIncidentMonitor/{__version__}'}, method='HEAD')
    with urlopen(request, timeout=15) as response:
        address = urlparse(response.geturl())
    prefix = '/pzaradzki/NetoIncidentMonitor/releases/tag/'
    if address.scheme != 'https' or address.netloc != 'github.com' or not address.path.startswith(prefix):
        raise ValueError('Nieprawidłowy adres wydania GitHub.')
    tag = unquote(address.path[len(prefix):])
    return version(tag) > version(__version__, allow_experimental=True), RELEASES + tag


def rate_limited(error):
    return error.code == 429 or (error.code == 403 and error.headers.get('X-RateLimit-Remaining') == '0')


def failure_message(error, *, facts=None):
    if isinstance(error, HTTPError):
        category = 'http'
        if facts is not None:
            facts['http_status'] = error.code
        if rate_limited(error):
            category = 'rate_limit'
            message = 'GitHub ograniczył dostęp do sprawdzania wydań. Spróbuj ponownie później.'
        elif error.code == 403:
            message = 'Dostęp do informacji o wydaniu został odrzucony (HTTP 403). Szczegóły zapisano w logu.'
        elif error.code == 404:
            message = 'Nie znaleziono opublikowanego wydania aplikacji na GitHubie.'
        else:
            message = f'GitHub zwrócił błąd HTTP {error.code}. Spróbuj ponownie później.'
    else:
        reason = error.reason if isinstance(error, URLError) else error
        if isinstance(reason, ssl.SSLError):
            category = 'tls'
            message = 'Nie udało się zweryfikować bezpiecznego połączenia z GitHubem. Szczegóły zapisano w logu.'
        elif isinstance(reason, OSError):
            category = 'timeout' if isinstance(reason, TimeoutError) else 'network'
            message = 'Nie udało się połączyć z GitHubem. Sprawdź połączenie internetowe lub dostęp przez sieć firmową.'
        else:
            category = 'invalid_response' if isinstance(error, ValueError) else 'unexpected'
            message = 'Nie udało się odczytać informacji o wydaniu GitHub. Szczegóły zapisano w logu.'
    if facts is not None:
        facts['release_error'] = category
    return message


def version(value, *, allow_experimental=False):
    suffix = r'(?:-experimental\.([1-9][0-9]*))?' if allow_experimental else ''
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)' + suffix, value) if isinstance(value, str) else None
    if not match:
        raise ValueError('Nieprawidłowa wersja wydania.')
    major, minor, patch = map(int, match.groups()[:3])
    experiment = match[4] if allow_experimental else None
    return major, minor, patch, experiment is None, int(experiment or 0)


def latest_release(*, facts=None):
    request = Request(API, headers={'Accept': 'application/vnd.github+json',
                                  'User-Agent': f'NetoIncidentMonitor/{__version__}'})
    try:
        with urlopen(request, timeout=15) as response:
            content = response.read(1_000_001)
    except HTTPError as error:
        if rate_limited(error):
            if facts is not None:
                facts['release_fallback_status'] = error.code
            return release_page_tag()
        raise
    if len(content) > 1_000_000:
        raise ValueError('Nieprawidłowa odpowiedź GitHub.')
    data = json.loads(content)
    if not isinstance(data, dict) or data.get('draft') or data.get('prerelease'):
        raise ValueError('Nieprawidłowe wydanie GitHub.')
    tag = data.get('tag_name')
    newer = version(tag) > version(__version__, allow_experimental=True)
    return newer, RELEASES + tag


def window_visible(window):
    return window.winfo_exists() and window.state() in ('normal', 'zoomed') and window.winfo_viewable()


def show_result(owner, newer, url=None, error=False, *, modal=True):
    dialog = tk.Toplevel(owner)
    dialog.withdraw()
    dialog.title('Aktualizacje')
    dialog.configure(background=BG)
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
    if window_visible(owner):
        dialog.transient(owner)
    dialog.deiconify()
    dialog.lift()
    if modal and not current_grab_path(owner):
        dialog.grab_set()
    return dialog


class ReleaseCheck:
    """Own one in-flight lookup and its presentation on the Tk thread."""

    def __init__(self, root):
        self.root = root
        self.startup_timer = None
        self.poll_timer = None
        self.results = None
        self.manual = None
        self.deferred = None
        self.dialog = None
        self.closed = False
        root.bind('<Map>', self._mapped, add='+')
        root.bind('<Destroy>', self._destroyed, add='+')

    def schedule_startup(self):
        self.startup_timer = self.root.after_idle(self._startup)

    def _startup(self):
        self.startup_timer = None
        self.check_updates()

    def check_updates(self, owner=None, button=None):
        if self.closed or (button is not None and not button.enabled):
            return
        if button is not None:
            self.deferred = None
            button.configure(state='disabled')
            self.manual = owner, button
        if self.results is not None:
            return

        self.automatic = button is None
        self.started = monotonic()
        self.diagnostics = LoginDiagnostics(source='release_check', release_trigger='startup' if self.automatic else 'manual')
        self.diagnostics.record('release_check', outcome='started')
        results = self.results = queue.Queue()

        def work():
            facts = {}
            try:
                result = latest_release(facts=facts)
            except Exception as error:
                result = failure_message(error, facts=facts)
            results.put((result, facts))

        try:
            threading.Thread(target=work, daemon=True).start()
        except RuntimeError as error:
            facts = {}
            results.put((failure_message(error, facts=facts), facts))
        self.poll_timer = self.root.after(100, self._poll)

    def _release_button(self):
        if self.manual is None:
            return None
        owner, button = self.manual
        self.manual = None
        if button.winfo_exists():
            button.configure(state='normal')
        return owner

    def detach(self, owner):
        if self.manual is not None and self.manual[0] is owner:
            self._release_button()

    def _poll(self):
        self.poll_timer = None
        try:
            result, facts = self.results.get_nowait()
        except queue.Empty:
            self.poll_timer = self.root.after(100, self._poll)
            return
        self.results = None
        if isinstance(result, str):
            self._finished('error', **facts)
            newer, url, error = False, None, result
        else:
            newer, url = result
            self._finished('returned', release_newer=newer, **facts)
            error = False
        owner = self._release_button()
        if owner is not None and window_visible(owner):
            self._present(owner, newer, url, error, modal=True)
        elif self.automatic and (newer or error):
            if newer or window_visible(self.root):
                self._present(self.root, newer, url, error, modal=False)
            else:
                self.deferred = newer, url, error

    def _finished(self, outcome, **facts):
        self.diagnostics.record('release_check', outcome=outcome,
                                duration_ms=round((monotonic() - self.started) * 1000), **facts)

    def _present(self, owner, newer, url, error, *, modal):
        if self.dialog is not None and self.dialog.winfo_exists():
            self.dialog.destroy()
        self.dialog = show_result(owner, newer, url, error=error, modal=modal)

    def _mapped(self, event):
        if event.widget is not self.root:
            return
        if self.deferred is not None:
            result, self.deferred = self.deferred, None
            self._present(self.root, *result, modal=False)
        elif (self.dialog is not None and self.dialog.master is self.root
              and self.dialog.winfo_exists() and not self.dialog.transient()):
            self.dialog.transient(self.root)

    def _destroyed(self, event):
        if event.widget is self.root:
            self.close()

    def close(self):
        if self.closed:
            return
        self.closed = True
        for timer in (self.startup_timer, self.poll_timer):
            if timer is not None:
                self.root.after_cancel(timer)
        if self.results is not None:
            self._finished('cancelled')
        self.results = self.manual = self.deferred = None
        if self.dialog is not None and self.dialog.winfo_exists():
            self.dialog.destroy()
