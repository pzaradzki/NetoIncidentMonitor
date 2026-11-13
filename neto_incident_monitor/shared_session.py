"""One Chromium owner and serial ServiceNow work for the desktop application."""

from collections import deque
from threading import Event, Lock, Thread
from time import monotonic
from uuid import uuid4

from playwright._impl._errors import TargetClosedError
from playwright.sync_api import sync_playwright

from neto_incident_monitor.authentication import authentication_required
from neto_incident_monitor.browser_actions import ACTION_TICK, checkpoint
from neto_incident_monitor.browser_session import close_session, create_runtime, open_context
from neto_incident_monitor.favorites import HOME
from neto_incident_monitor.login_diagnostics import LoginDiagnostics, TRACE, error_facts
from neto_incident_monitor.monitoring import Health, ReadPart, ReadQueue
from neto_incident_monitor.pagination import Cancelled


class StopSignal:
    def __init__(self, *events, invalidated=None):
        self.events = events
        self.invalidated = invalidated

    def is_set(self):
        return any(event.is_set() for event in self.events) or bool(self.invalidated and self.invalidated())


class MonitorCycle:
    def __init__(self, initial, intervals):
        self.stop = Event()
        self.initial = deque(initial)
        self.intervals = dict(intervals)
        self.deadlines = dict.fromkeys(intervals, 0.0)
        self.last_finished = {}
        self.filters = deque()
        self.filter_kinds = set()
        self._interval_lock = Lock()
        self._pending_intervals = None

    def request_intervals(self, intervals):
        with self._interval_lock:
            self._pending_intervals = dict(intervals)

    def apply_interval_changes(self):
        """Consume the latest saved settings in the session thread."""
        with self._interval_lock:
            pending = self._pending_intervals
            self._pending_intervals = None
        if pending is None:
            return ()
        changes = []
        for kind, previous in self.intervals.items():
            interval = pending[kind]
            if interval == previous:
                continue
            active = kind in self.filter_kinds
            if not active and kind in self.last_finished:
                self.deadlines[kind] = self.last_finished[kind] + interval
            self.intervals[kind] = interval
            changes.append((kind, previous, interval, active))
        return changes

    def next_filter(self, parts):
        if not self.filters:
            due = {kind for kind, deadline in self.deadlines.items() if deadline <= monotonic()}
            self.filters.extend(part for part in parts if part.data['kind'] in due)
            self.filter_kinds = due
            if not self.filters:
                self.finish_filter_batch()
        return self.filters[0] if self.filters else None

    def finish_filter_batch(self):
        now = monotonic()
        for kind in self.filter_kinds:
            self.schedule_next(kind, now)
        self.filter_kinds.clear()

    def schedule_next(self, kind, finished):
        self.last_finished[kind] = finished
        self.deadlines[kind] = finished + self.intervals[kind]

    def finish_full_read(self, requested, current):
        now = monotonic()
        for kind in self.intervals:
            enabled = {part for part in current if part.data['kind'] == kind}
            if enabled and enabled.issubset(requested):
                self.schedule_next(kind, now)
                self.filter_kinds.discard(kind)
                self.filters = deque(part for part in self.filters if part.data['kind'] != kind)


class SharedSession:
    def __init__(self, app, profile):
        self.app, self.profile = app, profile
        self.closed = Event()
        self.reconnect = Event()
        self.reconnect.set()
        self.work = ReadQueue()
        self.cycle = None
        self.filter_parts = ()
        self.manual_filter_parts = {}
        self.connected = False
        self.manual_login = False
        self.ready_once = False
        self.active_job = None
        self.active_job_success = True
        self.after_manual = False
        self.last_idle = None
        self.runtime = None
        self.health = Health()
        self.legacy_membership = None
        self.thread = Thread(target=self.run, name='ServiceNow-session', daemon=True)

    def emit(self, kind, value=None):
        self.app.events.put((kind, value))

    def submit(self, scope, parts):
        job_id, merged = self.work.submit(scope, parts)
        LoginDiagnostics(source='monitor', request_id=job_id).record(
            'refresh_queue', queue_scope=scope, queue_state='merged' if merged else 'queued')
        self.app.schedule.request()
        return job_id, merged

    def cancel_pending(self, part):
        job_id = self.work.cancel_pending(part)
        if job_id is None:
            return False
        LoginDiagnostics(source='monitor', request_id=job_id).record(
            'refresh_queue', queue_scope=part.scope, queue_state='cancelled', outcome='cancelled')
        return True

    def update_filters(self, parts):
        invalidated = {part for url, part in self.manual_filter_parts.items() if parts.get(url) != part}
        self.manual_filter_parts = parts
        self.filter_parts = tuple(part for part in parts.values() if part.data['scheduled'])
        if invalidated:
            for job, skipped in self.work.discard_pending_filters(invalidated):
                LoginDiagnostics(source='monitor', request_id=job.id).record('refresh_queue',
                    queue_scope=job.scope, queue_state='filter_changed', item_count=skipped)

    def filter_is_current(self, part):
        return self.manual_filter_parts.get(part.target[0]) == part

    def start_cycle(self, initial, intervals):
        self.cycle = MonitorCycle(initial, intervals)
        self.app.schedule.request()

    def update_intervals(self, intervals):
        cycle = self.cycle
        if cycle is not None and not cycle.stop.is_set():
            cycle.request_intervals(intervals)
            self.app.schedule.request()

    def apply_interval_changes(self, cycle):
        for kind, previous, interval, active in cycle.apply_interval_changes():
            self.log.record('schedule_interval_change', interval_stage='applied', schedule_kind=kind,
                            previous_interval_s=previous, interval_s=interval, batch_active=active)

    def stop_cycle(self):
        if self.cycle:
            self.cycle.stop.set()
        self.app.schedule.request()

    def retry(self):
        self.reconnect.set()

    def shutdown(self):
        self.closed.set()
        self.reconnect.set()
        self.app.schedule.request()

    def confirm_password_save(self, page, diagnostics):
        from neto_incident_monitor.app import BrowserClosedError

        request = {'done': Event(), 'choice': None, 'save_failed': False}
        started = monotonic()
        self.runtime.manual_required = True
        if not self.runtime.window or not self.runtime.window.is_visible():
            self.runtime.show_window(activate=False)
        # Finish the browser's initial activation before the Tk prompt takes focus.
        self.runtime.tick()
        diagnostics.record('password_save_prompt', password_save_choice='waiting',
                           window_visible=bool(self.runtime.window and self.runtime.window.is_visible()))
        self.emit('session_password_save', request)
        try:
            while not self.closed.is_set():
                if page.is_closed():
                    raise BrowserClosedError('Chromium zamknięto podczas oczekiwania na zapis hasła.')
                if request['done'].is_set():
                    self.runtime.restore_main_focus = request.get('restore_main_focus', False)
                    return request['choice'] in ('saved', 'disabled')
                if self.runtime.page.is_closed():
                    self.runtime.page = page
                self.runtime.tick()
                page.wait_for_timeout(100)
            return False
        finally:
            request['done'].set()
            self.emit('session_password_save_finished', request)
            if request['save_failed']:
                diagnostics.record('password_save_prompt', password_save_choice='save_error')
            diagnostics.record('password_save_prompt', password_save_choice=request['choice'] or 'cancelled',
                               foreground_confirmed=request.get('foreground_confirmed'),
                               duration_ms=round((monotonic() - started) * 1000))

    def authenticate(self, page, stop, *, visible=False):
        from neto_incident_monitor.app import BrowserClosedError, open_login_target, wait_for_login

        self.connected = False
        self.runtime.visible_login = visible
        self.runtime.restore_main_focus = False
        self.emit('session_waiting')
        if self.active_job is not None:
            self.record_job(self.active_job, 'waiting_login')

        def activity(message, tone):
            manual = message == 'Wymagane ręczne logowanie'
            if manual and not self.manual_login and not visible:
                window = self.runtime.window
                self.log.record('session_visibility', visibility_reason='login_required',
                                window_visible=bool(window and window.is_visible()))
            self.manual_login = manual
            self.emit('session_activity', (message, tone, self.manual_login))

        try:
            self.runtime.set_activity('login')
            if visible:
                self.log.record('session_visibility', visibility_reason='reconnect' if self.ready_once else 'initial_login',
                                window_visible=self.runtime.window.is_visible())
                if not open_login_target(page, HOME, stop, on_error=self.navigation_error):
                    return False
            elif not authentication_required(page, HOME):
                # A reader may have lost its frame during navigation. Confirm a
                # fresh session on the known landing page before repeating it.
                if not open_login_target(page, HOME, stop, on_error=self.navigation_error):
                    return False
            if not wait_for_login(page, HOME, stop, runtime=self.runtime,
                                  on_activity=activity, fail_unavailable=visible,
                                  on_password_save=self.confirm_password_save):
                return False
            for _ in range(20):
                checkpoint(stop)
                if self.runtime.debug_show_browser or self.runtime.window.is_hidden():
                    break
                page.wait_for_timeout(50)
            hidden = self.runtime.window.is_hidden()
            debug = self.runtime.debug_show_browser
            restore_focus = self.runtime.restore_main_focus and not debug
            self.log.record('session_visibility', visibility_reason='session_confirmed', hidden=hidden,
                                focus_handoff=restore_focus, debug_show_browser=debug)
            if not hidden and not debug:
                raise BrowserClosedError('Nie udało się ukryć okna Chromium.')
            self.connected = self.ready_once = True
            self.emit('session_ready', restore_focus)
            return True
        finally:
            self.manual_login = False
            self.runtime.visible_login = False
            self.runtime.manual_required = False
            if not page.is_closed():
                self.runtime.set_activity('filters')

    def navigation_error(self, facts):
        self.runtime.navigation_error = facts['error_category']

    def run(self):
        while not self.closed.is_set():
            self.reconnect.wait()
            self.reconnect.clear()
            if self.closed.is_set():
                break
            trace = TRACE.set(uuid4().hex)
            self.log = LoginDiagnostics(source='monitor')
            try:
                with sync_playwright() as playwright:
                    self.open_and_serve(playwright)
            except Cancelled:
                continue
            except Exception as error:
                facts = error_facts(error)
                if self.active_job is not None:
                    facts['request_id'] = self.active_job.id
                self.log.record('session_connection_error', **facts)
                if not self.closed.is_set():
                    self.emit('session_problem')
            finally:
                self.connected = self.manual_login = False
                TRACE.reset(trace)
        for job in self.work.abort_all():
            self.record_job(job, 'cancelled', outcome='cancelled')

    def open_and_serve(self, playwright):
        from neto_incident_monitor.app import BrowserClosedError, set_chromium_window_state

        context = open_context(playwright, self.profile, self.log, visible=True, offer_password_save=True)
        tick_token = None
        try:
            pages = context.pages
            page = pages[0] if pages else context.new_page()
            for surplus in pages[1:]:
                surplus.close()
            self.app.browser_runtime = self.runtime = create_runtime(
                page, self.app.browser_options, self.log, self.app.events, set_chromium_window_state,
                lambda window: setattr(self.app, 'browser_window', window))
            self.runtime.session_visibility = True
            tick_token = ACTION_TICK.set(self.runtime.tick)
            if self.authenticate(page, self.closed, visible=True):
                self.serve(page)
            if not self.closed.is_set():
                raise BrowserClosedError('Sesja Chromium została zamknięta.')
        finally:
            if tick_token is not None:
                ACTION_TICK.reset(tick_token)
            close_session(context, self.runtime, self.log)
            self.app.browser_runtime = self.app.browser_window = self.runtime = None

    def record_job(self, job, state, **fields):
        self.log.record('refresh_queue', request_id=job.id, queue_scope=job.scope, queue_state=state,
                        duration_ms=round((monotonic() - job.submitted_at) * 1000), **fields)

    def serve(self, page):
        from neto_incident_monitor.app import BrowserClosedError, wait_for_browser_cycle

        while not self.closed.is_set():
            if page.is_closed():
                raise BrowserClosedError('Karta robocza została zamknięta.')
            cycle = self.cycle
            if cycle is not None and cycle.stop.is_set():
                cycle = None
            selected = self.next_part(cycle)
            if selected is None:
                deadlines = tuple(cycle.deadlines.values()) if cycle else ()
                if cycle and self.app.threatened_next_read is not None:
                    deadlines += (self.app.threatened_next_read,)
                next_read = min(deadlines, default=monotonic() + 1)
                idle = (cycle is not None, next_read if cycle else None, dict(cycle.deadlines) if cycle else {})
                if idle != self.last_idle:
                    self.emit('session_idle', idle)
                    self.last_idle = idle
                wait_for_browser_cycle(page, self.app.schedule, max(0, next_read - monotonic()), self.closed)
                continue
            part, source = selected
            self.last_idle = None
            self.app.threatened_delay_reason = {'filter': 'filter', 'dashboard': 'dashboard'}.get(part.scope, 'idle')
            stop = StopSignal(self.closed, cycle.stop) if source != 'manual' else self.closed
            if part.scope == 'favorites':
                stop = StopSignal(self.closed, part.data['stop'])
            elif part.scope == 'filter':
                stop = StopSignal(stop, invalidated=lambda part=part: not self.filter_is_current(part))
            try:
                checkpoint(stop)
                if not self.connected or authentication_required(page, HOME):
                    if not self.authenticate(page, stop):
                        raise Cancelled()
                success = self.app.execute_session_part(page, part, stop, source)
            except Cancelled:
                if part.scope == 'favorites':
                    part.data['events'].put((part.target, 'result', ('cancelled', 'Import anulowany.')))
                success = False
            skipped = part.scope == 'filter' and not self.filter_is_current(part)
            self.work.complete_part(part, manual=source == 'manual', success=success)
            if source == 'initial':
                cycle.initial.popleft()
            if source == 'filter':
                cycle.filters.popleft()
                if not cycle.filters:
                    self.apply_interval_changes(cycle)
                    cycle.finish_filter_batch()
                if skipped:
                    self.log.record('refresh_queue', queue_scope='filter', queue_state='filter_changed', item_count=1)
            if source == 'manual':
                if skipped:
                    self.active_job.skipped_filters += 1
                    self.record_job(self.active_job, 'filter_changed', item_count=1)
                else:
                    self.active_job_success &= bool(success)
            self.emit('refresh_state')

    def next_part(self, cycle):
        if cycle is not None:
            self.apply_interval_changes(cycle)
        job = self.active_job
        deadline = self.app.threatened_next_read
        threats_due = cycle is not None and (deadline is None or deadline <= monotonic())
        if job is not None:
            if job.parts:
                if (job.scope == 'all' and threats_due and job.parts[0].scope == 'filter' and
                        not any(part.scope == 'threatened' for part in job.parts)):
                    return ReadPart('threatened'), 'threatened'
                return job.parts[0], 'manual'
            outcome = 'error' if not self.active_job_success else 'partial' if job.skipped_filters else 'returned'
            self.record_job(job, 'finished', outcome=outcome, item_count=job.skipped_filters)
            if cycle and job.scope == 'all':
                cycle.finish_full_read(job.requested, self.filter_parts)
            self.work.finish()
            self.active_job = None
            self.after_manual = True
            self.emit('session_job_finished', (job.scope, self.active_job_success, job.skipped_filters))
        if cycle and cycle.initial:
            return cycle.initial[0], 'initial'
        if threats_due:
            if self.work.next_scope() not in ('all', 'threatened'):
                return ReadPart('threatened'), 'threatened'
        if cycle and self.after_manual:
            self.after_manual = False
            part = cycle.next_filter(self.filter_parts)
            if part:
                return part, 'filter'
        job = self.work.take()
        if job is not None:
            self.active_job = job
            self.active_job_success = True
            self.record_job(job, 'running')
            self.emit('session_job_running', job.scope)
            return job.parts[0], 'manual'
        if cycle:
            part = cycle.next_filter(self.filter_parts)
            if part:
                return part, 'filter'
        return None
