"""Tk orchestration; network and helper startup run outside the UI thread."""
import json
import logging
from pathlib import Path
import subprocess
import sys
import threading
import time
from tkinter import messagebox

from neto_incident_monitor import __version__
from neto_incident_monitor.runtime_paths import DATA, FROZEN
from neto_incident_monitor import updates


class UpdateController:
    def __init__(self, app, settings, apply_startup):
        self.app = app
        self.busy = False
        self.prepared = None
        self.saved_enabled = app.check_updates.get()
        self.saving = False
        app.check_updates.trace_add('write', self.save_preference)
        if apply_startup and FROZEN and self.saved_enabled:
            app.root.after(4000, lambda: self.check(manual=False))

    def save_preference(self, *_):
        if self.saving:
            return
        from neto_incident_monitor.app import CONFIG, read_json, save_json
        try:
            settings = read_json(CONFIG, {})
            settings['check_updates'] = self.app.check_updates.get()
            save_json(CONFIG, settings)
            self.saved_enabled = self.app.check_updates.get()
        except (OSError, ValueError):
            self.saving = True
            self.app.check_updates.set(self.saved_enabled)
            self.saving = False
            messagebox.showerror('Aktualizacje', 'Nie udało się zapisać ustawienia.', parent=self.app.settings_window)

    def background(self, operation, event, manual=True):
        def run():
            try:
                self.app.events.put((event, (operation(), manual)))
            except Exception as error:
                logging.getLogger('servicenow').warning('Aktualizacja: %s (%s)', event, type(error).__name__)
                message = str(error) if isinstance(error, updates.UpdateError) else 'Nie udało się wykonać operacji. Sprawdź połączenie i uprawnienia do folderu aplikacji.'
                self.app.events.put(('update_error', (message, manual)))
        threading.Thread(target=run, daemon=True).start()

    def check(self, manual=True):
        if self.busy or self.app.quitting:
            return
        if not manual and not self.app.check_updates.get():
            return
        self.busy = True
        self.app.update_status.set('Sprawdzanie aktualizacji…')
        self.background(lambda: updates.check_release(__version__), 'update_checked', manual)

    def start_helper(self, job, resume_monitoring=False):
        job = Path(job)
        work = job.parent
        details = json.loads(job.read_text(encoding='utf-8'))
        details['resume_monitoring'] = resume_monitoring
        job.write_text(json.dumps(details), encoding='utf-8')
        process = subprocess.Popen([str(work / updates.HELPER), str(job)], cwd=work,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            if self.app.quitting:
                (work / 'cancelled').touch()
                raise updates.UpdateError('Aktualizacja anulowana podczas zamykania aplikacji.')
            if (work / 'ready').is_file():
                return str(job)
            if process.poll() is not None:
                break
            time.sleep(0.1)
        (work / 'cancelled').touch()
        raise updates.UpdateError('Nie udało się uruchomić aktualizatora. Aplikacja pozostaje otwarta.')

    def handle(self, kind, value):
        if self.app.quitting:
            return
        result, manual = value
        parent = self.app.root
        if kind == 'update_error':
            self.busy = False
            self.prepared = None
            self.app.update_status.set(result)
            if manual:
                messagebox.showerror('Aktualizacje', result, parent=parent)
        elif kind == 'update_checked':
            self.busy = False
            if result is None:
                self.app.update_status.set(f'Wersja {__version__} jest aktualna.')
                if manual:
                    messagebox.showinfo('Aktualizacje', 'Korzystasz z najnowszej wersji.', parent=parent)
                return
            self.app.update_status.set(f'Dostępna wersja {result["version"]}.')
            if not FROZEN:
                messagebox.showinfo('Aktualizacje', f'Dostępna wersja {result["version"]}. Automatyczna instalacja jest dostępna w wersji EXE.', parent=parent)
                return
            if self.prepared:
                try:
                    prepared = json.loads(Path(self.prepared).read_text(encoding='utf-8'))
                    if prepared['version'] == result['version'] and Path(prepared['payload']).is_dir():
                        self.busy = True
                        self.handle('update_prepared', (self.prepared, manual))
                        return
                except (OSError, ValueError, KeyError):
                    self.prepared = None
            if not messagebox.askyesno('Aktualizacje', f'Dostępna wersja {result["version"]}. Pobrać aktualizację?', parent=parent):
                return
            self.busy = True
            self.app.update_status.set('Pobieranie i weryfikacja paczki…')
            target = Path(sys.executable).resolve().parent
            self.background(lambda: updates.prepare_update(result, target, DATA, target / updates.HELPER), 'update_prepared')
        elif kind == 'update_prepared':
            self.prepared = result
            self.app.update_status.set('Aktualizacja jest gotowa do instalacji.')
            if not messagebox.askyesno('Aktualizacje', 'Zainstalować aktualizację teraz? Monitoring i Chromium zostaną zamknięte. Aplikacja uruchomi się ponownie.', parent=parent):
                self.busy = False
                # Retain the verified staging package; no installation occurs without consent.
                return
            self.app.update_status.set('Uruchamianie aktualizatora…')
            resume = bool(self.app.worker and self.app.worker.is_alive())
            self.background(lambda: self.start_helper(result, resume), 'update_helper_ready')
        elif kind == 'update_helper_ready':
            self.app.quit_app()
