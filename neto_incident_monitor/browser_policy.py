"""Thread-safe preferences; Playwright actions stay in the worker."""
from queue import Queue, Empty
from threading import Lock
from contextlib import contextmanager
from time import monotonic


class BrowserOptions:
    KEYS = ('auto_login', 'minimize_browser', 'hide_browser')

    def __init__(self, settings):
        self.lock = Lock()
        self.values = {key: bool(settings.get(key, False)) for key in self.KEYS}
        self.values['debug_show_browser'] = False

    def update(self, **values):
        with self.lock:
            self.values.update({key: bool(value) for key, value in values.items() if key in self.KEYS})

    def snapshot(self):
        with self.lock:
            return dict(self.values)

    def toggle_debug_browser(self):
        with self.lock:
            enabled = not self.values['debug_show_browser']
            self.values['debug_show_browser'] = enabled
            return enabled

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
        from neto_incident_monitor.browser_rendering import HiddenRendering
        self.login_rendering = HiddenRendering(diagnostics, scope='login')
        self.favorites_rendering = HiddenRendering(diagnostics, scope='favorites')
        self.favorites_page = None
        self.debug_show_browser = False
        self.rendering_failed = False
        self.manual_key = None
        self.manual_attempts = 0
        self.manual_due = 0
        self.manual_confirmed = False
        self.visibility_failure = False
        self.visible_login = False
        self.session_visibility = False
        self.restore_main_focus = False

    def record(self, event, **facts):
        try:
            self.diagnostics.record(event, **facts)
        except Exception:
            pass

    def close(self):
        from neto_incident_monitor.authentication import clear_login_activity
        clear_login_activity(self.page)
        self.login_rendering.close('runtime_closed')
        self.favorites_rendering.close('runtime_closed')

    @contextmanager
    def favorites_read(self, page, diagnostics):
        renderer = self.favorites_rendering
        renderer.diagnostics = diagnostics
        self.favorites_page = page
        try:
            renderer.sync(page, self.options.snapshot()['hide_browser'] and not self.debug_show_browser)
            yield
        finally:
            self.favorites_page = None
            renderer.close()
            renderer.diagnostics = self.diagnostics

    def set_activity(self, activity):
        if activity not in ('login', 'filters'):
            raise ValueError('Unknown browser activity')
        from neto_incident_monitor.authentication import set_login_activity, clear_login_activity
        if activity == 'login':
            set_login_activity(self.page)
        else:
            clear_login_activity(self.page)
        if activity != self.activity:
            self.activity = activity
            if activity == 'login':
                self.override = None
                self.rendering_failed = False
                self.manual_key = None
            else:
                self.login_rendering.close('not_needed')
            self.record('browser_activity', activity=activity)
        self.tick()

    def show_window(self, activate=False):
        if self.window is None:
            self.window = self.window_factory()
            self.window_changed(self.window)
        shown = self.window.show(activate=activate)
        if activate:
            self.page.bring_to_front()
        return shown

    def show_manual(self):
        key = self.page
        if key is not self.manual_key:
            self.manual_key = key
            self.manual_attempts = 0
            self.manual_due = 0
            self.manual_confirmed = self.visibility_failure = False
        if self.manual_confirmed:
            return  # Respect a subsequent user minimize/hide.
        if self.manual_attempts and self.window and self.window.is_visible() is True:
            self.manual_confirmed = True
            self.record('manual_login_shown', attempt=self.manual_attempts, window_visible=True)
            return
        now = monotonic()
        if now < self.manual_due:
            return
        if self.manual_attempts >= 3:
            self.visibility_failure = True
            return
        self.manual_attempts += 1
        self.manual_due = now + 2
        self.record('manual_login_show_attempt', attempt=self.manual_attempts)
        self.manual_confirmed = self.show_window(activate=True) is not False
        foreground = None
        try:
            foreground = self.window.is_foreground()
        except Exception:
            pass
        self.record('manual_login_shown' if self.manual_confirmed else 'manual_login_show_retry',
                    attempt=self.manual_attempts, window_visible=self.manual_confirmed,
                    foreground_confirmed=foreground)

    def request_show(self):
        self.commands.put('show')
        # This only posts a Win32 message to an already identified browser PID.
        # The worker later applies the persistent override and tab focus.
        if self.window is not None:
            self.window.reveal()

    def tick(self, force=False):
        from neto_incident_monitor.authentication import manual_handoff
        visible = self.window.is_visible() if self.window is not None else False
        if (not self.session_visibility or self.activity == 'login') and manual_handoff(self.page):
            self.manual_required = True
        options = self.options.snapshot()
        debug = options['debug_show_browser']
        debug_changed = debug != self.debug_show_browser
        self.debug_show_browser = debug
        if debug_changed:
            self.override = None
            force = True
        show_debug = debug and (debug_changed or self.window is None or
                                (not visible and self.window.is_hidden()))
        if options != self.previous:
            self.record('browser_options_changed', **options)
            if self.previous and any(options[k] != self.previous[k] for k in ('hide_browser', 'minimize_browser')):
                self.override = None
            self.previous = options
        while True:
            try:
                command = self.commands.get_nowait()
            except Empty:
                break
            if (self.manual_required or (self.activity == 'login' and not options['auto_login'])) and command == 'hide':
                self.record('visibility_deferred')
            else:
                self.override = command
                if command == 'show':
                    self.manual_key = None
                force = True
        if self.activity == 'login' or (self.manual_required and not self.session_visibility):
            manual = self.manual_required or not options['auto_login'] or self.rendering_failed
            hidden = (not debug and not self.visible_login and not manual and self.override != 'show' and
                      (self.override == 'hide' or options['hide_browser']))
            visibility = (self.activity, self.page, manual, hidden, self.override)
            if not hidden:
                self.login_rendering.sync(self.page, False)
            if manual:
                self.show_manual()
            else:
                self.manual_key = None
            native_mismatch = hidden and self.window is not None and self.window.is_hidden() is False
            if native_mismatch:
                self.record('browser_visibility_repaired', activity=self.activity)
            if force or native_mismatch or visibility != self.applied_visibility:
                if hidden:
                    if self.window is None:
                        self.window = self.window_factory()
                        self.window_changed(self.window)
                    self.window.hide()
                elif not manual and not debug:
                    self.show_window(activate=self.visible_login or self.override == 'show')
                self.applied_visibility = visibility
            if show_debug and not manual:
                self.show_window(activate=debug_changed)
            try:
                self.login_rendering.sync(self.page, hidden)
            except Exception:
                self.rendering_failed = self.manual_required = True
                self.login_rendering.close('not_needed')
                self.show_manual()
                self.applied_visibility = (self.activity, self.page, True, False, self.override)
            self.finish_debug_toggle(options, debug_changed, hidden and not self.rendering_failed)
            return options
        hidden = not debug and (self.override == 'hide' or (self.override is None and options['hide_browser']))
        visibility = (self.activity, self.page, hidden, options['minimize_browser'], self.override)
        native_mismatch = hidden and self.window is not None and self.window.is_hidden() is False
        if native_mismatch:
            self.record('browser_visibility_repaired', activity=self.activity)
        if force or native_mismatch or visibility != self.applied_visibility:
            if hidden:
                if self.window is None:
                    self.window = self.window_factory()
                    self.window_changed(self.window)
                self.window.hide()
            elif not debug:
                state = 'minimized' if self.override is None and options['minimize_browser'] else 'normal'
                if self.window:
                    if state == 'minimized':
                        self.window.minimize()
                    else:
                        self.show_window(activate=self.override == 'show')
                else:
                    self.set_state(self.page, state)
            self.applied_visibility = visibility
        if show_debug:
            self.show_window(activate=debug_changed)
        self.finish_debug_toggle(options, debug_changed, hidden)
        return options

    def finish_debug_toggle(self, options, changed, hidden):
        if not changed:
            return
        visible = self.window.is_visible() if self.window is not None else None
        self.record('session_visibility', visibility_reason='debug_browser_toggled', activity=self.activity,
                    debug_show_browser=self.debug_show_browser, hide_browser=hidden, window_visible=visible)
        if self.favorites_page is not None:
            self.favorites_rendering.sync(self.favorites_page, options['hide_browser'] and not self.debug_show_browser)

    def complete_login(self):
        from neto_incident_monitor.authentication import finish_authentication
        if self.session_visibility:
            from neto_incident_monitor.login_observation import owned_pages
            try:
                if self.window and self.window.is_foreground():
                    self.restore_main_focus = True
            except OSError:
                pass
            for owned in reversed(owned_pages(self.page)):
                owned.close()
        finish_authentication(self.page)
        self.manual_required = False
        self.override = None
        self.visible_login = False
        self.login_rendering.close('not_needed')
        self.rendering_failed = False
        self.manual_key = None
        self.activity = 'filters'
        self.tick(force=True)
