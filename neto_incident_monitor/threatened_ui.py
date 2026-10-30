"""Manual SLA-risk refresh and presentation on the Tk thread."""
import time
import random
import tkinter as tk
import webbrowser
from urllib.parse import urlencode
from tkinter import ttk
from time import monotonic
from neto_incident_monitor.theme import BG, SURFACE, TEXT, MUTED
from neto_incident_monitor.widgets import StatusPill, PriorityDots, RoundedButton

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


class RiskTile(tk.Frame):
    def __init__(self, parent, title, description, accent):
        super().__init__(parent, bg=SURFACE, highlightthickness=1, highlightbackground='#3c424d', cursor='hand2')
        self.accent = accent
        self.url = TILE_URLS[title]
        self.hovered = self.pressed = False
        self.timer = None
        self.current_color = SURFACE
        self.color_from = SURFACE
        self.color_to = SURFACE
        self.labels = []
        heading = tk.Label(self, text=f'●  {title}', fg=accent, font=('Segoe UI', 12, 'bold'), anchor='w')
        heading.pack(fill='x', padx=20, pady=(18, 0))
        self.value_label = tk.Label(self, text='—', fg=TEXT, font=('Segoe UI', 34), anchor='w')
        self.value_label.pack(fill='x', padx=20, pady=(18, 10))
        self.description = tk.Label(self, text=description, fg=MUTED, font=('Segoe UI', 10), anchor='w', justify='left')
        self.description.pack(fill='x', padx=20, pady=(0, 18))
        self.labels = [heading, self.value_label, self.description]
        for widget in (self, *self.labels):
            widget.configure(bg=SURFACE, cursor='hand2')
            widget.bind('<Enter>', self.enter)
            widget.bind('<Leave>', self.leave)
            widget.bind('<ButtonPress-1>', self.press)
            widget.bind('<ButtonRelease-1>', self.release)
        self.configure(takefocus=True)
        self.bind('<FocusIn>', self.enter)
        self.bind('<FocusOut>', lambda event: self.set_state(False, False))
        self.bind('<KeyPress-space>', self.press)
        self.bind('<KeyRelease-space>', self.release)
        self.bind('<KeyPress-Return>', self.press)
        self.bind('<KeyRelease-Return>', self.release)
        self.bind('<Configure>', lambda event: self.description.configure(wraplength=max(80, event.width - 40)))
        self.bind('<Destroy>', self.close, add='+')

    def enter(self, event=None):
        self.set_state(True, self.pressed)

    def leave(self, event):
        # Moving from the tile to a child label is still inside the same tile.
        if not (self.winfo_rootx() <= event.x_root < self.winfo_rootx() + self.winfo_width()
                and self.winfo_rooty() <= event.y_root < self.winfo_rooty() + self.winfo_height()):
            self.set_state(False, False)

    def press(self, event=None):
        self.focus_set()
        self.set_state(True, True)

    def release(self, event=None):
        activate = self.pressed and self.hovered
        self.set_state(self.hovered, False)
        if activate:
            webbrowser.open(self.url)

    def set_state(self, hovered, pressed):
        self.hovered, self.pressed = hovered, pressed
        target = '#424b5b' if pressed else '#303947' if hovered else SURFACE
        self.configure(highlightbackground=self.accent if hovered or pressed else '#3c424d')
        self.color_from, self.color_to = self.current_color, target
        self.started = monotonic()
        if self.timer is not None:
            self.after_cancel(self.timer)
            self.timer = None
        self.animate()

    def animate(self):
        self.timer = None
        fraction = min(1, (monotonic() - self.started) / 0.14)
        start = self.winfo_rgb(self.color_from)
        end = self.winfo_rgb(self.color_to)
        color = '#' + ''.join(f'{round((a + (b - a) * fraction) / 257):02x}' for a, b in zip(start, end))
        self.current_color = color
        for widget in (self, *self.labels):
            widget.configure(bg=color)
        if fraction < 1:
            self.timer = self.after(16, self.animate)

    def close(self, event):
        if event.widget is self and self.timer is not None:
            self.after_cancel(self.timer)
            self.timer = None


def build_threatened_view(parent, app):
    panel = tk.Frame(parent, bg=BG)
    panel.request_id = 0
    panel.pending = False
    panel.monitoring = False
    panel.values = {}
    panel.last_read = None
    panel.simulated = False
    canvas = tk.Canvas(panel, bg=BG, highlightthickness=0)
    scroll = ttk.Scrollbar(panel, orient='vertical', command=canvas.yview)
    canvas.pack(side='left', fill='both', expand=True)
    content = tk.Frame(canvas, bg=BG)
    window = canvas.create_window((0, 0), window=content, anchor='nw')
    def layout(event=None):
        canvas.itemconfigure(window, width=canvas.winfo_width())
        needed = content.winfo_reqheight()
        canvas.configure(scrollregion=(0, 0, canvas.winfo_width(), max(needed, canvas.winfo_height())))
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
            panel.message.set('Oczekiwanie na zalogowanie. Zagrożenia zostaną sprawdzone przed dashboardem i filtrami.')
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
    tk.Label(content, textvariable=panel.message, wraplength=700, justify='left',
             bg=BG, fg=MUTED, font=('Segoe UI', 10), anchor='w').pack(fill='x', pady=(6, 0))
    def set_state(request_id, state):
        if request_id != panel.request_id:
            return
        if state in ('Oczekuje', 'W trakcie aktualizacji'):
            panel.pending = True
            update_button()
        if state in ('Błąd odczytu', 'Dane nieaktualne'):
            button = app.threatened_incidents_button
            button.set_alert(button.alert, confirmed=False)
        pill.set_status(state)
        timestamp = time.strftime('%d.%m.%Y %H:%M:%S', time.localtime(panel.last_read)) if panel.last_read else '—'
        descriptions = {'Oczekuje': 'Oczekiwanie na zakończenie bieżącej pracy przeglądarki.',
                        'W trakcie aktualizacji': 'Trwa odczyt sześciu liczników z ServiceNow.',
                        'Zaktualizowany': 'Dane zostały zaktualizowane.',
                        'Błąd odczytu': 'Nie udało się odczytać kompletu danych. Zachowano ostatni poprawny wynik.',
                        'Dane nieaktualne': 'Odczyt nie jest aktualny. Uruchom monitoring i kliknij Aktualizuj.'}
        description = descriptions[state]
        if panel.simulated:
            description = ('Nie udało się odczytać danych z ServiceNow.' if state == 'Błąd odczytu' else description)
            description += ' Wyświetlane dane testowe — zastąpi je następny poprawny odczyt.'
        panel.message.set(f'Ostatnio odczytano: {timestamp} • {description}')
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
        set_state(request_id, 'Zaktualizowany' if values is not None else 'Błąd odczytu')
        update_button()
    panel.apply_result = apply_result
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
