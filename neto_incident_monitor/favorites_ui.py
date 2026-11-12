"""Tk-only preview; browser results cross a private queue with an import ID."""
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from uuid import uuid4

from neto_incident_monitor.favorites import classify, commit_selection
from neto_incident_monitor.login_diagnostics import LoginDiagnostics
from neto_incident_monitor.widgets import RoundedButton, checkbox_images
from neto_incident_monitor.theme import BG


class FavoritesImport:
    def __init__(self, app):
        self.app = app
        self.session = getattr(app, 'session', None)
        self.import_id = uuid4().hex
        self.log = LoginDiagnostics(source='favorites', import_id=self.import_id)
        self.events = queue.Queue()
        self.cancelled = False
        self.result = None
        self.items, self.rows, self.chosen = [], [], set()
        self.window = tk.Toplevel(app.root)
        self.window.withdraw()
        self.window.title('Importuj z ServiceNow')
        self.window.configure(background=BG)
        self.window.transient(app.root)
        self.window.protocol('WM_DELETE_WINDOW', self.cancel)
        self.checkbox_images = checkbox_images(self.window, background=None)
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(3, weight=1)
        self.status = tk.StringVar(value='Otwieranie ServiceNow…')
        self.status_label = ttk.Label(self.window, textvariable=self.status, wraplength=900)
        self.status_label.grid(row=0, column=0, sticky='ew', padx=12, pady=12)
        self.search = tk.StringVar()
        search_label = ttk.Label(self.window, text='Szukaj w odczytanych pozycjach:')
        search_label.grid(row=1, column=0, sticky='w', padx=12)
        search_entry = ttk.Entry(self.window, textvariable=self.search)
        search_entry.grid(row=2, column=0, sticky='ew', padx=12, pady=6)
        self.search.trace_add('write', lambda *_: self.render())
        body = ttk.Frame(self.window)
        body.grid(row=3, column=0, sticky='nsew', padx=12)
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)
        self.sort_column, self.sort_descending = None, False
        self.heading_titles = {'#0':'Wybór', 'name':'Nazwa', 'group':'Grupa', 'kind':'Typ', 'status':'Status'}
        self.table = ttk.Treeview(body, columns=('name','group','kind','status'), show='tree headings', selectmode='browse')
        self.table.column('#0', width=65, minwidth=65, stretch=False, anchor='center')
        for key, width in (('name',260),('group',140),('kind',65),('status',310)):
            self.table.column(key, width=width, minwidth=45)
        for key, title in self.heading_titles.items():
            self.table.heading(key, text=title, command=lambda column=key: self.sort_by(column))
        scroll = ttk.Scrollbar(body, orient='vertical', command=self.table.yview)
        horizontal = ttk.Scrollbar(body, orient='horizontal', command=self.table.xview)
        self.table.configure(yscrollcommand=scroll.set, xscrollcommand=horizontal.set)
        self.table.grid(row=0, column=0, sticky='nsew')
        scroll.grid(row=0, column=1, sticky='ns')
        horizontal.grid(row=1, column=0, sticky='ew')
        self.table.bind('<Button-1>', self.click_row)
        self.table.bind('<space>', self.space_row)
        self.actions = ttk.Frame(self.window)
        self.actions.grid(row=4, column=0, sticky='ew', padx=12, pady=12)
        self.actions.columnconfigure(2, weight=1)
        RoundedButton(self.actions, text='Zaznacz dostępne', command=lambda: self.select_all(True)).grid(row=0, column=0)
        RoundedButton(self.actions, text='Odznacz wszystkie', command=lambda: self.select_all(False)).grid(row=0, column=1, padx=8)
        self.cancel_button = RoundedButton(self.actions, text='Anuluj', command=self.cancel)
        self.cancel_button.grid(row=0, column=3, padx=8)
        self.add = RoundedButton(self.actions, text='Dodaj wybrane', command=self.accept)
        self.add.configure(state='disabled')
        self.add.grid(row=0, column=4)
        self.window.bind('<Configure>', self.resize)
        self.window.update_idletasks()
        # Reserve the fixed controls; only the table gives up height on resize.
        fixed_height = sum(w.winfo_reqheight() for w in
            (self.status_label, search_label, search_entry, self.actions, horizontal)) + 68
        min_width = max(650, self.actions.winfo_reqwidth() + 24)
        min_height = fixed_height + 80
        self.window.minsize(min_width, min_height)
        width, height = max(950, min_width), max(580, min_height)
        x = max(0, (self.window.winfo_screenwidth() - width) // 2)
        y = max(0, (self.window.winfo_screenheight() - height) // 2)
        self.window.geometry(f'{width}x{height}+{x}+{y}')
        self.window.deiconify()
        if self.session:
            from neto_incident_monitor.monitoring import ReadPart
            self.stop = threading.Event()
            self.part = ReadPart('favorites', self.import_id,
                                 {'id': self.import_id, 'events': self.events, 'stop': self.stop})
            self.status.set('Import oczekuje w kolejce…')
            self.session.submit('favorites', [self.part])
        else:
            self.window.grab_set()
            self.lock_controls()
            app.stop.clear()
            self.stop = app.stop
            settings = {'auto_login': bool(app.auto_login.get())}
            from neto_incident_monitor.favorites_worker import run_import
            from neto_incident_monitor.runtime_paths import DATA
            self.worker = threading.Thread(target=run_import,
                args=(self.events, app.stop, settings, DATA/'browser-profile', self.import_id), daemon=True)
            app.worker = self.worker
            try:
                self.worker.start()
            except RuntimeError:
                self.result = ('error', 'Nie udało się uruchomić importu.')
        self.timer = self.window.after(100, self.poll)

    def lock_controls(self):
        self.app.start_button.configure(state='disabled')
        for button in self.app.filter_buttons:
            button.configure(state='disabled')

    def poll(self):
        self.timer = None
        if self.app.quitting:
            self.cancelled = True
            self.stop.set()
        try:
            while True:
                token, kind, value = self.events.get_nowait()
                if token != self.import_id or self.result is not None:
                    continue
                if kind == 'status' and not self.cancelled:
                    self.status.set(value)
                elif kind == 'result':
                    self.result = value
        except queue.Empty:
            pass
        if self.is_reading():
            self.timer = self.window.after(100, self.poll)
            return
        if self.cancelled or self.app.quitting:
            self.finish()
            return
        if self.result is None:
            self.result = ('error', 'Import zakończył się bez kompletnego wyniku.')
        outcome, value = self.result
        if outcome == 'success':
            self.items = value
            self.rows = classify(self.items, self.app.filters)
            self.status.set(f'Odczytano pozycji: {len(self.rows)}. Wybierz filtry do dodania. Nowe filtry i powiadomienia będą wyłączone.')
            self.log.record('favorites_preview', item_count=len(self.rows),
                ready_count=sum(r['status']=='ready' for r in self.rows),
                duplicate_count=sum(r['status']=='existing' for r in self.rows),
                rejected_count=sum(r['status'] in ('invalid','unsupported') for r in self.rows))
            self.render()
        else:
            self.status.set(value)
        self.cancel_button.text = 'Zamknij'
        self.cancel_button.redraw()

    def resize(self, event):
        if event.widget is self.window:
            self.status_label.configure(wraplength=max(250, event.width-24))

    def sort_by(self, column):
        if self.sort_column != column:
            self.sort_column, self.sort_descending = column, False
        elif not self.sort_descending:
            self.sort_descending = True
        else:
            self.sort_column, self.sort_descending = None, False
        self.render()

    def render(self):
        focus = self.table.focus()
        selected = self.table.selection()
        position = self.table.yview()[0]
        self.table.delete(*self.table.get_children())
        needle = self.search.get().casefold().strip()
        visible = []
        for index, row in enumerate(self.rows):
            group = ' / '.join(row.get('groups', []))
            if not needle or needle in (row['name']+' '+group+' '+row['kind']).casefold():
                visible.append(index)
        def key(index):
            row = self.rows[index]
            if self.sort_column == '#0':
                return (index in self.chosen, row['status']=='ready')
            value = {'name':row['name'], 'group':' / '.join(row.get('groups', [])),
                     'kind':row['kind'], 'status':row['detail']}[self.sort_column]
            return value.casefold()
        if self.sort_column:
            visible.sort(key=key, reverse=self.sort_descending)
        for column, title in self.heading_titles.items():
            arrow = (' ▼' if self.sort_descending else ' ▲') if column==self.sort_column else ''
            self.table.heading(column, text=title+arrow)
        for index in visible:
            row = self.rows[index]
            image = self.checkbox_images[int(index in self.chosen)] if row['status']=='ready' else ''
            self.table.insert('', 'end', iid=str(index), image=image, values=(
                row['name'], ' / '.join(row.get('groups', [])), row['kind'], row['detail']))
        if focus and self.table.exists(focus):
            self.table.focus(focus)
        self.table.selection_set([i for i in selected if self.table.exists(i)])
        self.table.yview_moveto(position)
        self.add.configure(state='normal' if self.chosen else 'disabled')

    def toggle(self, item):
        if item and self.rows[int(item)]['status'] == 'ready':
            index = int(item)
            self.chosen.symmetric_difference_update({index})
            self.render()
            if self.table.exists(item):
                self.table.selection_set(item)
                self.table.focus(item)

    def click_row(self, event):
        if self.table.identify_region(event.x, event.y) in ('tree', 'cell'):
            item = self.table.identify_row(event.y)
            if item:
                self.table.focus_set()
                self.toggle(item)
                if self.table.exists(item):
                    self.table.focus(item)
                    self.table.selection_set(item)
                # The checked row may have moved after sorting by selection.
                # Do not let the class binding select a different row at y.
                return 'break'

    def space_row(self, event):
        self.toggle(self.table.focus())
        return 'break'

    def select_all(self, selected):
        if selected:
            self.chosen.update(int(i) for i in self.table.get_children() if self.rows[int(i)]['status']=='ready')
        else:
            self.chosen.clear()
        self.render()

    def accept(self):
        if self.is_reading() or self.cancelled or self.app.quitting or not self.result or self.result[0] != 'success':
            return
        try:
            count = commit_selection(self.app, self.items, self.chosen)
        except (ValueError, OSError):
            self.log.record('favorites_save_error', outcome='error')
            messagebox.showerror('Import filtrów', 'Nie udało się zapisać wybranych filtrów. Konfiguracja mogła się zmienić lub zapis jest niedostępny. Spróbuj ponownie albo otwórz import od nowa.', parent=self.window)
            return
        self.log.record('favorites_saved', item_count=count, outcome='returned')
        self.app.refresh_filters()
        self.finish()

    def cancel(self):
        self.cancelled = True
        self.stop.set()
        if self.session and self.session.cancel_pending(self.part):
            self.finish()
            return
        self.status.set('Anulowanie odczytu Ulubionych…')
        if not self.is_reading():
            self.finish()

    def is_reading(self):
        return self.result is None if self.session else self.worker.is_alive()

    def finish(self):
        if self.timer is not None:
            self.window.after_cancel(self.timer)
            self.timer = None
        self.log.record('favorites_dialog_end', outcome='cancelled' if self.cancelled else 'returned')
        self.app.favorites_import = None
        if self.session and not self.app.quitting:
            self.app.update_refresh_controls()
        if not self.app.quitting and not self.session:
            self.app.start_button.configure(state='normal')
            for button in self.app.filter_buttons:
                button.configure(state='normal')
        self.window.destroy()
