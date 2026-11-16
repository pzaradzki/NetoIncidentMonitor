"""Fixed read status and contextual actions below the scrollable data."""
import tkinter as tk

from neto_incident_monitor.read_status import ReadStatus
from neto_incident_monitor.theme import MUTED, SURFACE, TEXT
from neto_incident_monitor.widgets import RoundedButton, StatusPill


class ReadStatusBar(tk.Frame):
    BORDER = '#404751'
    ACTIONS = {'edit': 'Edytuj filtr', 'retry': 'Ponów odczyt'}

    def __init__(self, parent, *, date_label='Dane z'):
        super().__init__(parent, bg=SURFACE)
        self.date_label = date_label
        self.targets = {}
        self.current_action = ''
        self.columnconfigure(1, weight=1)
        tk.Frame(self, bg=self.BORDER, height=1).grid(row=0, column=0, columnspan=2, sticky='ew')
        self.edge = tk.Frame(self, bg=SURFACE, width=3)
        self.edge.grid(row=1, column=0, rowspan=2, sticky='ns')
        self.message = tk.Frame(self, bg=SURFACE)
        self.message.grid(row=1, column=1, sticky='ew', padx=9, pady=(12, 8))
        self.message.columnconfigure(1, weight=1)
        self.icon = tk.Label(self.message, text='⚠', bg=SURFACE, font=('Segoe UI Symbol', 12))
        self.icon.grid(row=0, column=0, padx=(0, 7), sticky='n')
        text = tk.Frame(self.message, bg=SURFACE)
        text.grid(row=0, column=1, sticky='ew')
        self.title = tk.Label(text, bg=SURFACE, fg=TEXT, font=('Segoe UI', 10, 'bold'), justify='left', wraplength=320)
        self.title.pack(anchor='w')
        self.detail = tk.Label(text, bg=SURFACE, fg=MUTED, font=('Segoe UI', 9), justify='left', wraplength=320)
        self.detail.pack(anchor='w')
        text.bind('<Configure>', self.fit_message)
        self.button = RoundedButton(self.message, text='Ponów odczyt', command=self.invoke_action,
                                    background=SURFACE, compact=True)
        self.button.grid(row=0, column=2, sticky='ne', padx=(10, 0))
        self.meta = tk.Frame(self, bg=SURFACE)
        self.meta.grid(row=2, column=1, sticky='ew', padx=9, pady=12)
        self.separator = tk.Frame(self.meta, bg=self.BORDER, height=1)
        self.separator.grid(row=0, column=0, columnspan=3, sticky='ew', pady=(0, 4))
        self.fields = [tk.StringVar(self) for _ in range(3)]
        field_gap = 28
        self.pill = StatusPill(self.meta, compact=True)
        self.pill.configure(bg=SURFACE)
        self.pill.grid(row=1, column=0, sticky='w', padx=(0, field_gap))
        self.labels = [self.pill]
        for column, variable in enumerate(self.fields[1:], 1):
            label = tk.Label(self.meta, textvariable=variable, bg=SURFACE, fg=MUTED, font=('Segoe UI', 9))
            label.grid(row=1, column=column, sticky='w', padx=(0, field_gap if column == 1 else 0))
            self.labels.append(label)
        self.show(ReadStatus())

    def fit_message(self, event):
        for label in (self.title, self.detail):
            label.configure(wraplength=max(1, event.width - 4))

    def set_actions(self, **targets):
        self.targets = targets
        self.sync_action()

    def sync_action(self):
        target = self.targets.get(self.current_action)
        if target is None:
            self.button.grid_remove()
            return
        self.button.grid()
        if self.button.enabled != target.enabled:
            self.button.configure(state='normal' if target.enabled else 'disabled')

    def invoke_action(self):
        target = self.targets.get(self.current_action)
        if target is not None and target.enabled:
            target.command()

    def show(self, status):
        outcome, timestamp, duration = status.labels()
        expanded = bool(status.detail or status.title or status.action)
        failed = outcome == 'Błąd odczytu' and not status.warning
        tone = '#ffadb8' if failed else '#f1c577' if expanded else '#91d3ad' if status.read_at is not None else MUTED
        self.edge.configure(bg=tone if expanded else SURFACE)
        self.icon.configure(fg=tone)
        self.title.configure(text=status.title or (outcome if outcome not in ('Odczyt udany', 'Brak odczytu')
                                                   else 'Informacja o odczycie'))
        self.detail.configure(text=status.detail)
        self.fields[0].set(outcome)
        self.fields[1].set(f'{self.date_label} {timestamp}')
        self.fields[2].set(f'Zapytanie {duration}')
        self.current_action = status.action if expanded else ''
        if self.current_action:
            self.button.text = self.ACTIONS[self.current_action]
            self.button.redraw()
        self.sync_action()
        has_date, has_duration = status.read_at is not None, status.duration_ms is not None
        for label, visible in zip(self.labels[1:], (has_date, has_duration)):
            if visible:
                label.grid()
            else:
                label.grid_remove()
        if expanded:
            self.message.grid()
            self.separator.grid()
            self.pill.grid_remove()
            if has_date or has_duration:
                self.meta.grid()
            else:
                self.meta.grid_remove()
        else:
            self.message.grid_remove()
            self.separator.grid_remove()
            self.meta.grid()
            self.pill.grid()
            pill_tone = 'success' if outcome == 'Odczyt udany' else None
            if (self.pill.status_text, self.pill.tone) != (outcome, pill_tone):
                self.pill.set_status(outcome, pill_tone)
