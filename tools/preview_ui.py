"""Render the actual Tk interface using disposable synthetic runtime data."""
import ctypes
from ctypes import wintypes
from contextlib import ExitStack
import tempfile
import time
import tkinter as tk
from pathlib import Path
from unittest.mock import patch
from PIL import ImageGrab
from neto_incident_monitor import app as app_module, runtime_paths, login_diagnostics
from neto_incident_monitor.columns import FIELDS

OUTPUT = Path(__file__).resolve().parents[1] / 'build' / 'ui-preview.png'


def main():
    with tempfile.TemporaryDirectory(prefix='neto-ui-preview-') as temporary, ExitStack() as stack:
        folder = Path(temporary)
        stack.enter_context(patch.multiple(app_module, DATA=folder, CONFIG=folder/'config.json', STATE=folder/'seen.json'))
        stack.enter_context(patch.object(runtime_paths, 'DATA', folder))
        stack.enter_context(patch.object(login_diagnostics, 'DATA', folder))
        stack.enter_context(patch.object(login_diagnostics._logger, 'handlers', []))
        url = 'https://adeo.service-now.com/incident_list.do'
        settings = {'filters': [{'name': 'Przykładowe incydenty', 'url': url},
                               {'name': 'Drugi filtr demonstracyjny', 'url': url+'?sysparm_query=active%3Dtrue'}]}
        root = tk.Tk()
        app = None
        try:
            with patch.object(app_module, 'read_json', return_value=settings):
                app = app_module.App(root, history_path=folder/'history.json', enable_tray=False, apply_startup=False)
            app.persist_filters()
            keys = {'number', 'short_description', 'priority', 'location', 'created'}
            app.accept_column_schema(url, [{'key': k, 'label': label} for k, label, _ in FIELDS if k in keys])
            descriptions = ['Przykładowa płatność', 'Przykładowy dostęp', 'Przykładowa drukarka',
                            'Przykładowa cena', 'Przykładowa lista', 'Przykładowe przypisanie']
            incidents = {}
            for index, description in enumerate(descriptions):
                number = f'INC716{1100 + index}'
                incident = dict(number=number, short_description=description,
                    priority='2 — wysokie' if index < 2 else '3 — umiarkowane',
                    location='Lokalizacja demonstracyjna', created='2026-10-07 13:04:15',
                    url='https://adeo.service-now.com/incident.do?sys_id='+f'{index+1:032x}')
                incidents[number] = incident
                app.history.add(incident, settings['filters'][0]['name'], url)
            app.events.put(('snapshot', (1, incidents)))
            app.events.put(('read', (time.time(), settings['filters'][0]['name'])))
            app.events.put(('waiting', (time.monotonic()+51, False)))
            app.events.put(('status', 'Podgląd interfejsu — wyłącznie dane przykładowe.'))
            app.drain()
            app.show_incident_view()
            root.geometry('1440x850+30+30')
            root.update()
            app.tabs.select(1)
            root.update()
            assert len(app.table.get_children()) == len(incidents)
            app.tabs.select(0)
            root.update()
            api = ctypes.WinDLL('user32')
            api.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
            api.GetAncestor.restype = wintypes.HWND
            hwnd = api.GetAncestor(root.winfo_id(), 2)
            if not hwnd:
                raise RuntimeError('Nie rozpoznano okna podglądu.')
            OUTPUT.parent.mkdir(parents=True, exist_ok=True)
            ImageGrab.grab(window=hwnd).save(OUTPUT)
            root.geometry('1120x680+30+30')
            root.update()
            for widget in (app.start_button, app.check_button):
                assert widget.winfo_rootx()+widget.winfo_width() <= root.winfo_rootx()+root.winfo_width()
            print(str(OUTPUT.resolve()))
        finally:
            if app is not None:
                app.teams_sender.stop()
                app.google_chat_sender.stop()
                for sender in (app.teams_sender, app.google_chat_sender):
                    sender.thread.join(timeout=2)
                app.quit_app()
                root.mainloop()
            else:
                root.destroy()
            login_diagnostics.close_diagnostics()


if __name__ == '__main__':
    main()
