"""Thread-safe preferences; Playwright actions stay in the worker."""
from queue import Queue, Empty
from threading import Lock


class BrowserOptions:
    KEYS = ('auto_login', 'minimize_browser', 'hide_browser')

    def __init__(self, settings):
        self.lock = Lock()
        self.values = {key: bool(settings.get(key, False)) for key in self.KEYS}

    def update(self, **values):
        with self.lock:
            self.values.update({key: bool(value) for key, value in values.items() if key in self.KEYS})

    def snapshot(self):
        with self.lock:
            return dict(self.values)

    def background(self):
        values = self.snapshot()
        return values['hide_browser'] or values['minimize_browser']


class BrowserRuntime:
    def __init__(self, page, options, window_factory, set_state, diagnostics, window_changed):
        self.page, self.options = page, options
        self.window_factory, self.set_state = window_factory, set_state
        self.diagnostics, self.window_changed = diagnostics, window_changed
        self.window = None
        self.manual_required = False
        self.previous = None
        self.applied_visibility = None
        self.override = None
        self.commands = Queue()
        self.activity = 'filters'

    def set_activity(self, activity):
        if activity not in ('login', 'dashboard', 'filters'):
            raise ValueError('Unknown browser activity')
        if activity != self.activity:
            self.activity = activity
            self.override = None
            self.diagnostics.record('browser_activity', activity=activity)
        self.tick()

    def show_window(self, activate=False):
        if self.window is None:
            self.window = self.window_factory()
            self.window_changed(self.window)
        self.window.show(activate=activate)
        if activate:
            self.page.bring_to_front()

    def request_show(self):
        self.commands.put('show')
        # This only posts a Win32 message to an already identified browser PID.
        # The worker later applies the persistent override and tab focus.
        if self.window is not None:
            self.window.reveal()

    def tick(self, force=False):
        from neto_incident_monitor.authentication import manual_handoff
        if self.window is not None:
            self.window.is_visible()
        if manual_handoff(self.page):
            self.manual_required = True
        options = self.options.snapshot()
        if options != self.previous:
            self.diagnostics.record('browser_options_changed', **options)
            if self.previous and any(options[k] != self.previous[k] for k in ('hide_browser', 'minimize_browser')):
                self.override = None
            self.previous = options
        while True:
            try:
                command = self.commands.get_nowait()
            except Empty:
                break
            if (self.manual_required or self.activity != 'filters') and command == 'hide':
                self.diagnostics.record('visibility_deferred')
            elif self.manual_required and command == 'show':
                self.show_window(activate=True)
            else:
                self.override = command
                force = True
        # Login and dashboard reads need a rendered, non-minimized page even when
        # filter monitoring is configured to hide/minimize Chromium. Apply once
        # per phase/page, so polling does not repeatedly steal keyboard focus.
        if self.activity != 'filters':
            visibility = (self.activity, self.page)
            if force or visibility != self.applied_visibility:
                self.show_window(activate=self.override == 'show')
                self.applied_visibility = visibility
            return options
        if self.manual_required:
            if self.applied_visibility != (options['hide_browser'], options['minimize_browser'], self.override):
                self.diagnostics.record('visibility_deferred')
            return options
        visibility = (options['hide_browser'], options['minimize_browser'], self.override)
        if force or visibility != self.applied_visibility:
            if self.override == 'hide' or (self.override is None and options['hide_browser']):
                if self.window is None:
                    self.window = self.window_factory()
                    self.window_changed(self.window)
                self.window.hide()
            else:
                state = 'minimized' if self.override is None and options['minimize_browser'] else 'normal'
                if self.window:
                    if state == 'minimized':
                        self.window.minimize()
                    else:
                        self.show_window(activate=self.override == 'show')
                else:
                    self.set_state(self.page, state)
            self.applied_visibility = visibility
        return options

    def complete_login(self):
        from neto_incident_monitor.authentication import clear_manual_handoff
        clear_manual_handoff(self.page)
        self.manual_required = False
        self.override = None
        self.tick(force=True)
