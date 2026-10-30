"""Progress from completed browser steps; UI timers stay on the Tk thread."""
from contextlib import contextmanager
from contextvars import ContextVar
import tkinter as tk
from neto_incident_monitor.theme import BG, SURFACE, MUTED

STEPS = {
    'Dashboard SLA': ('navigate', 'open_period', 'fill_start', 'fill_end', 'commit_period',
                      'status', 'location', 'assigned', 'scores'),
    'Wstrzymane L1': ('open_tab', 'agent', 'scores'),
    'Wnioski L1': ('open_tab', 'agent', 'scores'),
}
_current = ContextVar('dashboard_progress', default=None)


@contextmanager
def progress_steps(progress, section):
    token = _current.set((progress, section))
    try:
        yield
    finally:
        _current.reset(token)


def completed_step(step):
    current = _current.get()
    if current:
        current[0].advance(current[1], step)


class DashboardProgress:
    def __init__(self, emit):
        self.emit = emit
        self.completed = set()
        self.percent = 0
        self.emit(0, 'Oczekiwanie na odczyt dashboardu', 'running')

    def advance(self, section, step):
        key = (section, step)
        if step not in STEPS.get(section, ()) or key in self.completed:
            return
        self.completed.add(key)
        self.percent = min(99, len(self.completed) * 100 // sum(map(len, STEPS.values())))
        self.emit(self.percent, section, 'running')

    def section_done(self, section):
        for step in STEPS[section]:
            self.advance(section, step)

    def waiting(self):
        self.emit(self.percent, 'Oczekiwanie na logowanie', 'running')

    def finish(self, success):
        if success:
            self.percent = 100
        self.emit(self.percent, 'Dane zostały zaktualizowane.' if success else
                  'Odczyt nie został zakończony w całości.', 'complete' if success else 'warning')


class DashboardProgressBar(tk.Frame):
    def __init__(self, parent, **pack_options):
        super().__init__(parent, bg=BG)
        self.pack_options = {'fill': 'x', **pack_options}
        self.request_id = None
        self.percent = 0
        self.description = ''
        self.hide_timer = None
        self.view_active = True
        self.display_pending = False
        self.color = '#69dc9e'
        self.label = tk.Label(self, bg=BG, fg=MUTED, font=('Segoe UI', 9), width=5, anchor='e')
        self.label.pack(side='right', padx=(8, 0))
        self.canvas = tk.Canvas(self, bg=BG, height=4, highlightthickness=0, borderwidth=0)
        self.canvas.pack(side='left', fill='x', expand=True)
        self.canvas.bind('<Configure>', lambda event: self.redraw())

    def cancel_hide(self):
        if self.hide_timer is not None:
            self.after_cancel(self.hide_timer)
            self.hide_timer = None

    def start(self, request_id):
        self.cancel_hide()
        self.request_id, self.percent = request_id, 0
        self.apply(request_id, 0, 'Oczekiwanie na odczyt dashboardu', 'running')

    def set_view_active(self, active):
        self.view_active = bool(active)
        if self.view_active and self.display_pending:
            self.pack(**self.pack_options)
        else:
            self.pack_forget()

    def apply(self, request_id, percent, description, state):
        if request_id != self.request_id:
            return
        self.cancel_hide()
        self.percent = max(self.percent, min(100, percent))
        self.description = description
        self.color = '#f6bd60' if state == 'warning' else '#69dc9e'
        self.label.configure(text=f'{self.percent} %', fg=self.color if state == 'warning' else MUTED)
        self.display_pending = True
        self.set_view_active(self.view_active)
        self.redraw()
        if state == 'complete' and self.percent == 100:
            def dismiss():
                if self.request_id == request_id and self.percent == 100:
                    self.hide_timer = None
                    self.display_pending = False
                    self.pack_forget()
            self.hide_timer = self.after(3000, dismiss)

    def hide(self):
        self.cancel_hide()
        self.request_id = None
        self.display_pending = False
        self.pack_forget()

    def redraw(self):
        self.canvas.delete('all')
        width = max(1, self.canvas.winfo_width())
        self.canvas.create_rectangle(0, 0, width, 4, fill=SURFACE, outline='')
        self.canvas.create_rectangle(0, 0, width * self.percent / 100, 4, fill=self.color, outline='')

    def destroy(self):
        self.cancel_hide()
        super().destroy()
