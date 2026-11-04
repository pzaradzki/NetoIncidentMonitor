"""Manual SLA-risk refresh and presentation on the Tk thread."""
import time
import random
import re
import sqlite3
import tkinter as tk
import webbrowser
from urllib.parse import urlencode
from tkinter import ttk
from neto_incident_monitor.theme import BG, SURFACE, TEXT, MUTED
from neto_incident_monitor.widgets import IncidentMenu, StatusPill, PriorityDots, RoundedButton, AnimatedMetricTile
from neto_incident_monitor.service_now_urls import safe_record_url

CATEGORIES = (
    ('P1', 'Mniej niż 1 godz. do terminu lub po terminie', PriorityDots.COLORS['1']),
    ('P2', 'Mniej niż 2 godz. do terminu lub po terminie', PriorityDots.COLORS['2']),
    ('P3', 'Mniej niż 4 godz. do terminu lub po terminie', PriorityDots.COLORS['3']),
    ('P4', 'Mniej niż 1 dzień do terminu lub po terminie', PriorityDots.COLORS['4']),
    ('P5', 'Mniej niż 2 dni do terminu lub po terminie', PriorityDots.COLORS['5']),
    ('Podjęcie', 'Mniej niż 5 min do terminu lub po terminie', '#d0a1ff'),
)

# Same filters as the six ServiceNow tiles; only the navigation wrapper is removed.
_COMMON_QUERY = (
    'task.sys_class_name=incident^task.assignment_group=36e1263edb64b7408033459d3b9619e0'
    '^task.active=true^task.stateNOT IN3,6,7,8^active=true^stage=in_progress'
)
TILE_URLS = {
    f'P{priority}': 'https://adeo.service-now.com/task_sla_list.do?' + urlencode({'sysparm_query':
        _COMMON_QUERY + f'^sla.target=resolution^task.priority={priority}'
        + f'^planned_end_timeRELATIVELT@hour@ahead@{hours}'
        + '^task.ref_incident.parent_incidentISEMPTY'})
    for priority, hours in enumerate((1, 2, 4, 24, 48), 1)
}
TILE_URLS['Podjęcie'] = 'https://adeo.service-now.com/task_sla_list.do?' + urlencode({'sysparm_query':
    _COMMON_QUERY + '^sla.target=response^planned_end_timeRELATIVELT@minute@ahead@5'
    + '^task.ref_incident.parent_incidentISEMPTY'})


class RiskTile(AnimatedMetricTile):
    def __init__(self, parent, title, description, accent):
        self.url = TILE_URLS[title]
        super().__init__(parent, accent, command=lambda: webbrowser.open(self.url))
        heading = tk.Label(self, text=f'●  {title}', fg=accent, font=('Segoe UI', 12, 'bold'), anchor='w')
        heading.pack(fill='x', padx=20, pady=(18, 0))
        self.value_label = tk.Label(self, text='—', fg=TEXT, font=('Segoe UI', 34), anchor='w')
        self.value_label.pack(fill='x', padx=20, pady=(18, 10))
        self.description = tk.Label(self, text=description, fg=MUTED, font=('Segoe UI', 10), anchor='w', justify='left')
        self.description.pack(fill='x', padx=20, pady=(0, 18))
        self.bind_content(heading, self.value_label, self.description)
        self.bind('<Configure>', lambda event: self.description.configure(wraplength=max(80, event.width - 40)))


def remaining_seconds(value):
    units = {'d': 86400, 'g': 3600, 'h': 3600, 'm': 60, 's': 1}
    pattern = r'(\d+)\s*(dni|dzień|godziny|godzin|godzina|godz\.?|h|minuty|minuta|minut|min|sekund[ay]?|sek\.?|s)'
    parts = re.findall(pattern, value, re.I)
    if not parts or re.sub(pattern, '', value.removeprefix('-'), flags=re.I).strip():
        return None
    return (-1 if value.startswith('-') else 1) * sum(
        int(count) * units[unit[0].lower()] for count, unit in parts)


def add_cell_decorations(table, snapshot, open_record, context_menu):
    stops = ((50, (63, 211, 145)), (70, (244, 216, 75)),
             (90, (255, 155, 55)), (100, (245, 77, 99)))
    bars = []
    badges = []
    category_colors = {key: color for key, _, color in CATEGORIES}
    pending = None

    def paint():
        nonlocal pending
        pending = None
        visible = dict.fromkeys(table.identify_row(y) for y in range(0, table.winfo_height(), 10))
        used = 0
        badge_count = 0
        for number in visible:
            category_bounds = table.bbox(number, 'categories') if number in snapshot else ()
            if category_bounds:
                x, y, width, height = category_bounds
                available = min(width, table.winfo_width() - x) - 12
                if available > 0 and y + height <= table.winfo_height():
                    if badge_count == len(badges):
                        cell = tk.Canvas(table, highlightthickness=0, cursor='hand2')
                        cell.bind('<Button-1>', lambda event: table.selection_set(event.widget.number))
                        cell.bind('<Double-1>', lambda event: open_record(event.widget.number))
                        cell.bind('<Button-3>', lambda event: context_menu(table, event.widget.number, event))
                        cell.bind('<MouseWheel>', lambda event: table.yview_scroll(-int(event.delta / 120), 'units'))
                        badges.append(cell)
                    cell = badges[badge_count]
                    badge_count += 1
                    cell.number = number
                    background = '#513039' if number in table.selection() else SURFACE
                    cell.configure(bg=background)
                    cell.delete('all')
                    offset = 0
                    for category in snapshot[number]['categories']:
                        label = cell.create_text(offset + 5, 10, anchor='w', text=category,
                                                 fill=category_colors.get(category, TEXT),
                                                 font=('Segoe UI', 9, 'bold'))
                        right = cell.bbox(label)[2] + 4
                        pill = cell.create_polygon(
                            offset + 3, 1, right - 3, 1, right, 4, right, 16,
                            right - 3, 19, offset + 3, 19, offset, 16, offset, 4,
                            fill='#343943')
                        cell.tag_lower(pill, label)
                        offset = right + 5
                    cell.place(x=x + 1, y=y, width=available + 5, height=height)
                    cell.move('all', 5, (height - 20) // 2)
            bounds = table.bbox(number, 'percent') if number in snapshot and 'percent' in table['columns'] else ()
            if not bounds:
                continue
            x, y, width, height = bounds
            width = min(width - 16, table.winfo_width() - x - 16)
            if width < 12 or y < 0 or y + height > table.winfo_height():
                continue
            if used == len(bars):
                bar = tk.Canvas(table, height=3, bg='#3c414b', highlightthickness=0, cursor='hand2')
                bar.bind('<Button-1>', lambda event: table.selection_set(event.widget.number))
                bar.bind('<Double-1>', lambda event: open_record(event.widget.number))
                bar.bind('<Button-3>', lambda event: context_menu(table, event.widget.number, event))
                bar.bind('<MouseWheel>', lambda event: table.yview_scroll(-int(event.delta / 120), 'units'))
                bars.append(bar)
            bar = bars[used]
            used += 1
            bar.number = number
            percent = max(0, min(100, snapshot[number]['percent']))
            low, start = 0, stops[0][1]
            for high, end in stops:
                if percent <= high:
                    ratio = (percent - low) / (high - low)
                    color = '#%02x%02x%02x' % tuple(round(a + (b - a) * ratio) for a, b in zip(start, end))
                    break
                low, start = high, end
            bar.delete('all')
            bar.create_rectangle(0, 0, width * percent / 100, 3, fill=color, width=0)
            bar.place(x=x + 8, y=y + height - 7, width=width)
        for bar in bars[used:]:
            bar.place_forget()
        for cell in badges[badge_count:]:
            cell.place_forget()

    def refresh(event=None):
        nonlocal pending
        if pending is None:
            pending = table.after_idle(paint)

    def close(event):
        if pending is not None:
            table.after_cancel(pending)

    table.usage_bars = refresh
    for sequence in ('<Configure>', '<Map>', '<B1-Motion>', '<ButtonRelease-1>', '<<TreeviewSelect>>'):
        table.bind(sequence, refresh, add='+')
    table.bind('<Destroy>', close, add='+')


def add_threatened_tables(content, app):
    notebook = ttk.Notebook(content, style='Clean.TNotebook')
    notebook.pack(fill='both', expand=True, pady=(12, 0))
    snapshot = {}
    tables = []
    render_generation = 0
    columns = {'number': 'Numer INC', 'categories': 'Kategorie SLA', 'remaining': 'Pozostały czas roboczy',
               'percent': 'Wykorzystany czas', 'first_seen': 'Pierwsze wykrycie',
               'last_seen': 'Ostatnie wykrycie', 'present': 'Zagrożenie SLA'}
    sort_keys = {
        'number': lambda row: int(row['number'][3:]),
        'categories': lambda row: tuple(index for index, (key, _, _) in enumerate(CATEGORIES)
                                       if key in row['categories']),
        'remaining': lambda row: remaining_seconds(row['remaining']),
    }

    def draw():
        nonlocal render_generation
        render_generation += 1
        for table, state, current in tables:
            selected = table.selection() or getattr(table, 'pending_selection', ())
            table.pending_selection = selected
            children = table.get_children()
            if children:
                table.delete(*children)
            key, descending = state
            sort_key = sort_keys.get(key, lambda row: row.get(key))
            rows = [row for row in snapshot.values() if not current or row['present']]
            title = 'Bieżące zgłoszenia' if current else 'Historia zgłoszeń'
            notebook.tab(table.master.master, text=f'{title}   {len(rows)}')
            rows.sort(key=sort_keys['number'])
            known = [row for row in rows if sort_key(row) is not None]
            known.sort(key=sort_key, reverse=descending)
            ordered = known + [row for row in rows if sort_key(row) is None]
            insert_rows(table, ordered, selected, render_generation)
            for column, label in columns.items():
                if column in table['columns']:
                    suffix = (' ▼' if descending else ' ▲') if column == key else ''
                    table.heading(column, text=label + suffix)

    def insert_rows(table, rows, selected, generation, start=0):
        if generation != render_generation or not table.winfo_exists():
            return
        end = start + 100
        for row in rows[start:end]:
            values = dict(row, categories=' · '.join(row['categories']),
                          percent=f'{row["percent"]:g}%'.replace('.', ','),
                          present='Aktualne' if row['present'] else 'Nieaktualne')
            for key in ('first_seen', 'last_seen'):
                values[key] = time.strftime('%d.%m.%Y %H:%M', time.localtime(row[key]))
            table.insert('', 'end', iid=row['number'], values=[values[key] for key in table['columns']])
        if hasattr(table, 'usage_bars'):
            table.after_idle(table.usage_bars)
        if end < len(rows):
            table.after_idle(insert_rows, table, rows, selected, generation, end)
        else:
            if selected and table.exists(selected[0]) and not table.selection():
                table.selection_set(selected[0])
            table.pending_selection = ()

    def sort(state, column):
        state[:] = [column, not state[1] if state[0] == column else False]
        draw()

    def open_record(number):
        row = snapshot.get(number)
        if row and (url := safe_record_url(row['url'], number)):
            webbrowser.open(url)

    def context_menu(table, number, event):
        row = snapshot.get(number)
        if not row or not table.exists(number):
            return
        table.selection_set(number)
        table.focus(number)
        url = safe_record_url(row['url'], number)
        menu = IncidentMenu(table)

        def copy(value):
            table.clipboard_clear()
            table.clipboard_append(value)

        if url:
            menu.add_command('Otwórz incydent', lambda: open_record(number))
            menu.add_separator()
        menu.add_command('Kopiuj numer', lambda: copy(number))
        if url:
            menu.add_command('Kopiuj link', lambda: copy(url))
        menu.show(event.x_root, event.y_root)
        return 'break'

    for current, title in ((True, 'Bieżące zgłoszenia'), (False, 'Historia zgłoszeń')):
        frame = tk.Frame(notebook, bg=BG)
        notebook.add(frame, text=title)
        keys = tuple(columns)[:4] if current else ('number', 'categories', 'first_seen', 'last_seen', 'present')
        border = tk.Frame(frame, bg=SURFACE, highlightthickness=0, borderwidth=0)
        border.pack(fill='both', expand=True)
        table = ttk.Treeview(border, columns=keys, show='headings', height=1)
        scroll = ttk.Scrollbar(border, orient='vertical', command=table.yview)
        def scroll_changed(first, last, widget=table, scrollbar=scroll):
            scrollbar.set(first, last)
            if float(first) == 0 and float(last) == 1:
                scrollbar.pack_forget()
            elif not scrollbar.winfo_manager():
                scrollbar.pack(side='right', fill='y', before=widget)
            if hasattr(widget, 'usage_bars'):
                widget.after_idle(widget.usage_bars)
        table.configure(yscrollcommand=scroll_changed)
        table.pack(fill='both', expand=True)
        add_cell_decorations(table, snapshot, open_record, context_menu)
        state = ['deadline', False] if current else ['last_seen', True]
        tables.append((table, state, current))
        for index, column in enumerate(keys, 1):
            table.column(column, width=145, minwidth=70)
            table.heading(column, anchor='w', command=lambda key=column, target=state: sort(target, key))
            def keyboard_sort(event, key=column, target=state):
                sort(target, key)
                return 'break'
            table.bind(f'<Alt-Key-{index}>', keyboard_sort)
        table.bind('<Double-1>', lambda event: open_record(event.widget.identify_row(event.y)))
        table.bind('<Button-3>', lambda event: context_menu(
            event.widget, event.widget.identify_row(event.y), event))

    def render_details(rows):
        snapshot.clear()
        snapshot.update(rows)
        draw()

    if hasattr(app, 'history'):
        try:
            render_details(app.history.threatened_snapshot())
        except (OSError, ValueError, sqlite3.Error):
            return render_details, True
    return render_details, False


def build_threatened_view(parent, app):
    panel = tk.Frame(parent, bg=BG)
    panel.request_id = 0
    panel.pending = False
    panel.monitoring = False
    panel.values = {}
    panel.last_read = None
    panel.last_full_read = None
    panel.simulated = False
    canvas = tk.Canvas(panel, bg=BG, highlightthickness=0)
    scroll = ttk.Scrollbar(panel, orient='vertical', command=canvas.yview)
    canvas.pack(side='left', fill='both', expand=True)
    content = tk.Frame(canvas, bg=BG)
    window = canvas.create_window((0, 0), window=content, anchor='nw')
    def layout(event=None):
        needed = content.winfo_reqheight()
        height = max(needed, canvas.winfo_height())
        canvas.itemconfigure(window, width=canvas.winfo_width(), height=height)
        canvas.configure(scrollregion=(0, 0, canvas.winfo_width(), height))
        if needed > canvas.winfo_height():
            scroll.pack(side='right', fill='y', padx=(6, 0))
        else:
            scroll.pack_forget()
            canvas.yview_moveto(0)
    canvas.configure(yscrollcommand=scroll.set)
    canvas.bind('<Configure>', layout)
    content.bind('<Configure>', layout)
    header = tk.Frame(content, bg=BG)
    header.pack(fill='x', pady=(0, 18))
    tk.Label(header, text='Incydenty zagrożone SLA', bg=BG, fg=TEXT, font=('Segoe UI', 12, 'bold')).pack(side='left')
    pill = StatusPill(header, compact=True)
    pill.set_status('Dane nieaktualne')
    pill.pack(side='left', padx=(12, 0))
    panel.status_pill = pill
    def update_button():
        busy = hasattr(app, 'refresh_control') and app.refresh_control.busy
        panel.refresh_button.configure(state='normal' if panel.monitoring and not panel.pending and not busy else 'disabled')
    def request(automatic=False, coordinated=False):
        if not automatic and not coordinated:
            return app.request_refresh('threatened')
        if panel.pending or app.stop.is_set():
            return
        if not automatic and (not app.worker or not app.worker.is_alive()):
            return
        panel.request_id += 1
        panel.pending = True
        set_state(panel.request_id, 'Oczekuje')
        app.threatened_requests.put(panel.request_id)
        if automatic:
            dashboard_pending = getattr(getattr(app, 'dashboard_view', None), 'active_request', None) is not None
            panel.message.set('Oczekiwanie na zalogowanie. Zagrożenia zostaną sprawdzone '
                              + ('po dashboardzie i przed filtrami.' if dashboard_pending else 'przed filtrami.'))
            if panel.simulated:
                panel.message.set(panel.message.get() + ' Wyświetlane dane testowe.')
        update_button()
    panel.request_refresh = request
    from neto_incident_monitor.threatened import THREATENED_URL
    panel.open_snow_button = RoundedButton(header, text='Otwórz w SNOW',
        command=lambda: webbrowser.open(THREATENED_URL), background=BG)
    panel.open_snow_button.pack(side='right', padx=(8, 0))
    panel.refresh_button = RoundedButton(header, text='Aktualizuj', icon='refresh', command=request, background=BG)
    panel.refresh_button.pack(side='right')
    panel.refresh_button.configure(state='disabled')
    tiles = tk.Frame(content, bg=BG)
    tiles.pack(fill='x')
    tiles.columnconfigure((0, 1, 2), weight=1, uniform='risk')
    panel.tiles = []
    for index, (title, description, accent) in enumerate(CATEGORIES):
        tile = RiskTile(tiles, title, description, accent)
        tile.grid(row=index // 3, column=index % 3, sticky='nsew', padx=(0, 12 if index % 3 != 2 else 0), pady=(0, 12))
        panel.tiles.append(tile)
    panel.message = tk.StringVar(value='Uruchom monitoring i kliknij Aktualizuj. Kafelki otwierają listy w ServiceNow.')
    render_details, history_error = add_threatened_tables(content, app)
    if history_error:
        panel.message.set('Nie udało się odczytać zapisanej historii zagrożeń.')
    tk.Label(content, textvariable=panel.message, wraplength=700, justify='left',
             bg=BG, fg=MUTED, font=('Segoe UI', 10), anchor='w').pack(side='bottom', fill='x', pady=(6, 0))
    def set_state(request_id, state):
        if request_id != panel.request_id:
            return
        if state in ('Oczekuje', 'W trakcie aktualizacji', 'Ponawianie odczytu'):
            panel.pending = True
            update_button()
        if state in ('Błąd odczytu', 'Dane nieaktualne'):
            button = app.threatened_incidents_button
            button.set_alert(button.alert, confirmed=False)
        pill.set_status(state)
        timestamp = time.strftime('%d.%m.%Y %H:%M:%S', time.localtime(panel.last_full_read)) if panel.last_full_read else '—'
        descriptions = {'Ponawianie odczytu': 'Ponawianie odczytu po przejściowym problemie.', 'Oczekuje': 'Oczekiwanie na zakończenie bieżącej pracy przeglądarki.',
                        'W trakcie aktualizacji': 'Trwa odczyt zagrożeń z ServiceNow.',
                        'Zaktualizowany': 'Odczytano liczniki i listę zagrożeń.',
                        'Niepełny odczyt': 'Odczytano liczniki. Zachowano ostatnią poprawną listę.',
                        'Błąd odczytu': 'Nie udało się odczytać kompletu danych. Zachowano ostatni poprawny wynik.',
                        'Dane nieaktualne': 'Odczyt nie jest aktualny. Uruchom monitoring i kliknij Aktualizuj.'}
        description = descriptions[state]
        if panel.simulated:
            description = ('Nie udało się odczytać danych z ServiceNow.' if state == 'Błąd odczytu' else description)
            description += ' Wyświetlane dane testowe — zastąpi je następny poprawny odczyt.'
        panel.message.set(f'Ostatni pełny odczyt: {timestamp} • {description}')
    panel.set_state = set_state
    def apply_result(request_id, values, timestamp):
        if request_id != panel.request_id:
            return
        from neto_incident_monitor.threatened import KEYS
        if values is not None and (set(values) != set(KEYS) or
                any(type(value) is not int or value < 0 for value in values.values())):
            values = None
        if values is not None:
            panel.simulated = False
            panel.values = dict(values)
            panel.last_read = timestamp
            for tile, (key, _, _) in zip(panel.tiles, CATEGORIES):
                tile.value_label.configure(text=str(values[key]))
            app.threatened_incidents_button.set_alert(any(values.values()))
        panel.pending = False
        if values is None:
            set_state(request_id, 'Błąd odczytu')
        update_button()
    panel.apply_result = apply_result

    def apply_details(request_id, rows):
        if request_id != panel.request_id:
            return
        if rows is not None:
            render_details(rows)
            panel.last_full_read = panel.last_read
            set_state(request_id, 'Zaktualizowany')
        else:
            set_state(request_id, 'Niepełny odczyt')

    panel.apply_details = apply_details
    def simulate_read():
        from neto_incident_monitor.threatened import KEYS
        category = random.choice(KEYS)
        panel.values = dict.fromkeys(KEYS, 0)
        panel.values[category] = 1
        panel.simulated = True
        for tile, (key, _, _) in zip(panel.tiles, CATEGORIES):
            tile.value_label.configure(text=str(panel.values[key]))
        app.threatened_incidents_button.set_alert(True)
        pill.set_status('Dane testowe', 'waiting')
        panel.message.set(f'Symulacja: {category} — 1 zagrożony incydent. '
                          'To dane testowe; następny poprawny odczyt z ServiceNow je zastąpi.')
        # Keep the in-flight request, its ID, timestamp and button state intact.
        return 'break'
    panel.simulate_read = simulate_read
    def finish_request(request_id):
        if request_id == panel.request_id:
            panel.pending = False
            update_button()
    panel.finish_request = finish_request
    def set_monitoring(active):
        panel.monitoring = bool(active)
        if not active:
            panel.request_id += 1
            panel.pending = False
            set_state(panel.request_id, 'Dane nieaktualne')
        update_button()
    panel.set_monitoring = set_monitoring
    def wheel(event):
        if content.winfo_reqheight() > canvas.winfo_height():
            canvas.yview_scroll(-int(event.delta / 120), 'units')
    def bind_wheel(widget):
        widget.bind('<MouseWheel>', wheel)
        for child in widget.winfo_children():
            bind_wheel(child)
    bind_wheel(content)
    canvas.bind('<MouseWheel>', wheel)
    return panel
