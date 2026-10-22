"""Per-filter discovered schemas and persistent table presentation."""
import copy
import tkinter as tk
from tkinter import ttk

from neto_incident_monitor.columns import FIELDS, DEFAULT, LOCAL_FIELDS, age_minutes
from neto_incident_monitor.theme import BG, MUTED
from neto_incident_monitor.widgets import RoundedButton, PriorityDots
from neto_incident_monitor import themed_dialogs as messagebox
from neto_incident_monitor.service_now_urls import effective_list_url

LOCAL_KEYS = [key for key, _, _ in LOCAL_FIELDS]
WIDTHS = {key: width for key, _, width in FIELDS}


def normalize_schema(schema):
    result = []
    seen = set()
    if not isinstance(schema, list):
        return []
    for item in schema[:256]:
        if not isinstance(item, dict):
            continue
        key = item.get('key')
        if (not isinstance(key, str) or not key or len(key) > 512 or key in seen
                or key in LOCAL_KEYS or key.startswith('#') or any(ord(c) < 32 for c in key)):
            continue
        seen.add(key)
        result.append({'key': key, 'label': ' '.join(str(item.get('label') or key).split())[:160]})
    return result if 'number' in seen else []


def load_profiles(value):
    result = {}
    if not isinstance(value, dict):
        return result
    for url, profile in value.items():
        if not isinstance(profile, dict):
            continue
        schema = normalize_schema(profile.get('schema'))
        if not schema:
            continue
        keys = [c['key'] for c in schema] + LOCAL_KEYS
        order = profile.get('order', keys)
        order = list(dict.fromkeys(k for k in order if isinstance(k, str) and k in keys)) if isinstance(order, list) else []
        order += [k for k in keys if k not in order]
        visible = profile.get('visible', [])
        widths = profile.get('widths', {})
        result[url] = {'schema': schema, 'order': order,
                       'visible': [k for k in visible if isinstance(k, str) and k in keys] if isinstance(visible, list) else [],
                       'widths': {k: max(70, min(1500, v)) for k, v in widths.items()
                                  if k in keys and isinstance(v, int)} if isinstance(widths, dict) else {}}
    return result


def update_profile(previous, schema):
    schema = normalize_schema(schema)
    if not schema:
        return previous
    keys = [c['key'] for c in schema]
    if previous is None or set(keys) != {c['key'] for c in previous['schema']}:
        return {'schema': schema, 'visible': keys, 'order': keys + LOCAL_KEYS, 'widths': {}}
    profile = copy.deepcopy(previous)
    profile['schema'] = schema
    return profile


class DynamicColumns:
    def column_profile(self):
        return getattr(self, 'column_profiles', {}).get(self.selected_filter_url())

    def save_column_profiles(self, profiles):
        from neto_incident_monitor.app import read_json, save_json, CONFIG
        settings = read_json(CONFIG, {})
        settings['filter_column_profiles'] = profiles
        save_json(CONFIG, settings)
        self.column_profiles = profiles

    def accept_column_schema(self, url, schema):
        old = self.column_profiles.get(url)
        profile = update_profile(old, schema)
        if profile is None:
            return
        if profile != old:
            profiles = dict(self.column_profiles)
            profiles[url] = profile
            try:
                self.save_column_profiles(profiles)
            except (OSError, ValueError):
                self.status.set('Nie udało się zapisać kolumn filtra. Ponowię próbę po kolejnym odczycie.')
                return
        if url == self.selected_filter_url():
            self.columns_filter_url = None
            self.filter_selected()

    def prepare_dynamic_tables(self):
        profile = self.column_profile()
        self.visible_columns = list(profile['visible']) if profile else []
        self.columns_button.configure(state='normal' if profile else 'disabled')
        schema = profile['schema'] if profile else []
        for table in (self.current_table, self.table):
            base = [('read', 'Przeczytane', 145)] + [c for c in FIELDS if c[0] not in ('read', 'time')]
            if table.history_view:
                base.insert(0, ('time', 'Wykryto (historia)', 150))
            keys = [c[0] for c in base]
            definitions = base + [(c['key'], c['label'], WIDTHS.get(c['key'], 180)) for c in schema if c['key'] not in keys]
            titles = {key: label for key, label, _ in definitions}
            titles.update({c['key']: c['label'] for c in schema})
            if tuple(table['columns']) != tuple(key for key, _, _ in definitions):
                self.clear_table(table)
                table.configure(displaycolumns=(), columns=[key for key, _, _ in definitions])
                table.default_order = ()
                if table.sort_column not in table['columns']:
                    table.sort_column = None
                table.column_drag = None
                self.hide_column_drop_marker(table)
            table.heading_titles = titles
            widths = profile.get('widths', {}) if profile else {}
            for key, _, width in definitions:
                table.heading(key, text=titles[key], anchor='w', command=lambda column=key, t=table: self.toggle_sort(t, column))
                table.column(key, width=max(70, min(1500, int(widths.get(key, width)))), minwidth=70, stretch=False)

    def table_values(self, table, incident, read_label, detected=''):
        values = dict(incident)
        values.update(incident.get('_values', {}))
        values['number'] = incident['number']
        priority = str(values.get('priority') or '').strip()
        if priority[:1] in PriorityDots.COLORS:
            values['priority'] = '\u2003\u2002' + priority
        values['read'] = read_label
        values['time'] = detected
        values['age_minutes'] = age_minutes(incident.get('created'), incident['number'])
        return [values.get(key) or '—' for key in table['columns']]

    def column_order(self, table):
        if not hasattr(self, 'column_profiles'):
            # Tables used independently, outside the filter UI.
            keys = list(table['columns'])
            return [k for k in DEFAULT if k in keys] + [k for k in keys if k not in DEFAULT]
        profile = self.column_profile()
        return [k for k in profile['order'] if k in table['columns']] if profile else []

    def applicable_columns(self):
        profile = self.column_profile()
        keys = [c['key'] for c in profile['schema']] if profile else []
        if self.unread_highlighting_enabled():
            keys.append('read')
        if not effective_list_url(self.selected_filter_url(), self.filters).split('?', 1)[0].endswith('/sc_task_list.do'):
            keys.append('age_minutes')
        return keys + ['time']

    def default_filter_columns(self):
        profile = self.column_profile()
        return [c['key'] for c in profile['schema']] if profile else []

    def available_columns(self, history=False):
        return set(self.default_filter_columns()) | set(LOCAL_KEYS)

    def apply_visible_columns(self):
        if not hasattr(self, 'column_profiles'):
            return
        profile = self.column_profile()
        for table in (self.current_table, self.table):
            visible = [k for k in self.column_order(table)
                       if k in self.visible_columns and k in self.applicable_columns()]
            table.configure(displaycolumns=visible)
            if table.sort_column and table.sort_column not in visible:
                table.sort_column = None
                self.apply_sort(table)
        self.columns_button.configure(state='normal' if profile else 'disabled')

    def update_column_warnings(self):
        pass

    def reorder_column(self, table, source, target):
        profile = self.column_profile()
        visible = list(table['displaycolumns'])
        if not profile or source not in visible or target not in visible or source == target:
            return
        original = list(visible)
        position = visible.index(target)
        visible.remove(source)
        visible.insert(position, source)
        iterator = iter(visible)
        profiles = copy.deepcopy(self.column_profiles)
        profiles[self.selected_filter_url()]['order'] = [next(iterator) if k in original else k for k in profile['order']]
        try:
            self.save_column_profiles(profiles)
        except (OSError, ValueError):
            messagebox.showerror('Kolumny', 'Nie udało się zapisać kolejności kolumn.', parent=self.root)
            return
        self.apply_visible_columns()

    def sync_column_widths(self, source):
        if not self.column_profile():
            return
        profiles = copy.deepcopy(self.column_profiles)
        widths = profiles[self.selected_filter_url()].setdefault('widths', {})
        widths.update({key: source.column(key, 'width') for key in source['displaycolumns']})
        try:
            self.save_column_profiles(profiles)
        except (OSError, ValueError):
            messagebox.showerror('Kolumny', 'Nie udało się zapisać szerokości kolumn.', parent=self.root)
            return
        for table in (self.current_table, self.table):
            for key, width in widths.items():
                if key in table['columns']:
                    table.column(key, width=width)

    def configure_columns(self):
        profile = self.column_profile()
        if not profile:
            return
        url = self.selected_filter_url()
        schema_keys = {c['key'] for c in profile['schema']}
        dialog = tk.Toplevel(self.root)
        dialog.title('Widoczne kolumny')
        dialog.configure(background=BG)
        dialog.transient(self.root)
        dialog.geometry(f'580x{min(650, dialog.winfo_screenheight()-100)}')
        dialog.minsize(480, 350)
        header = ttk.Frame(dialog, padding=20)
        header.pack(fill='x')
        ttk.Label(header, text='Wybierz kolumny', font=('Segoe UI', 14, 'bold')).pack(anchor='w')
        ttk.Label(header, text='Ustawienia dotyczą bieżącej listy i historii tego filtra.', foreground=MUTED).pack(anchor='w', pady=(8, 0))
        footer = ttk.Frame(dialog, padding=20)
        footer.pack(side='bottom', fill='x')
        viewport = ttk.Frame(dialog)
        viewport.pack(fill='both', expand=True)
        canvas = tk.Canvas(viewport, background=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(viewport, command=canvas.yview)
        scroll.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        canvas.configure(yscrollcommand=scroll.set)
        panel = ttk.Frame(canvas, padding=(20, 0))
        content = canvas.create_window(0, 0, window=panel, anchor='nw')
        canvas.bind('<Configure>', lambda event: canvas.itemconfigure(content, width=event.width))
        panel.bind('<Configure>', lambda _: canvas.configure(scrollregion=canvas.bbox('all')))
        dialog.bind('<MouseWheel>', lambda event: canvas.yview_scroll(-int(event.delta/120), 'units'))
        choices = {}
        def checkbox(key, label, row, column):
            import textwrap
            value = tk.BooleanVar(value=key in profile['visible'])
            choices[key] = value
            ttk.Checkbutton(panel, text='\n'.join(textwrap.wrap(label, 31)), variable=value,
                            style='App.TCheckbutton').grid(row=row, column=column, sticky='w', pady=4, padx=(0, 12))
        labels = {c['key']: c['label'] for c in profile['schema']}
        ordered = [k for k in profile['order'] if k in schema_keys]
        for i, key in enumerate(ordered):
            checkbox(key, labels[key], i//2, i%2)
        offset = (len(ordered)+1)//2
        ttk.Separator(panel).grid(row=offset, column=0, columnspan=2, sticky='ew', pady=(16, 10))
        ttk.Label(panel, text='Kolumny dodatkowe', foreground=MUTED).grid(row=offset+1, column=0, columnspan=2, sticky='w', pady=(0, 6))
        for i, (key, label, _) in enumerate(c for c in LOCAL_FIELDS if c[0] in self.applicable_columns()):
            checkbox(key, label, offset+2+i, 0)
        reset_order = False
        def restore():
            nonlocal reset_order
            reset_order = True
            for key, value in choices.items():
                value.set(key in schema_keys)
        def save():
            live = self.column_profiles.get(url)
            if live is None or {c['key'] for c in live['schema']} != schema_keys:
                messagebox.showerror('Kolumny', 'Zestaw kolumn uległ zmianie. Otwórz konfigurację ponownie.', parent=dialog)
                return
            profiles = copy.deepcopy(self.column_profiles)
            updated = profiles[url]
            # Options hidden by global preferences retain their previous state.
            selected = [k for k in live['visible'] if k not in choices]
            selected += [k for k, value in choices.items() if value.get()]
            updated['visible'] = selected
            if reset_order:
                updated['visible'] = [k for k, value in choices.items() if value.get()]
                updated['order'] = [c['key'] for c in live['schema']] + LOCAL_KEYS
                updated['widths'] = {}
            try:
                self.save_column_profiles(profiles)
            except (OSError, ValueError):
                messagebox.showerror('Kolumny', 'Nie udało się zapisać ustawień kolumn.', parent=dialog)
                return
            if self.selected_filter_url() == url:
                self.columns_filter_url = None
                self.filter_selected()
            dialog.destroy()
        RoundedButton(footer, text='Przywróć domyślne', command=restore, background=BG).pack(side='left')
        RoundedButton(footer, text='Zapisz', command=save, primary=True, background=BG).pack(side='right')
        RoundedButton(footer, text='Anuluj', command=dialog.destroy, background=BG).pack(side='right', padx=8)
        dialog.bind('<Escape>', lambda _: dialog.destroy())
        dialog.update_idletasks()
        dialog.geometry(f'+{max(0, (dialog.winfo_screenwidth()-dialog.winfo_width())//2)}+{max(0, (dialog.winfo_screenheight()-dialog.winfo_height())//2)}')
        dialog.grab_set()
