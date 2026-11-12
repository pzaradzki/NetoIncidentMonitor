"""Bounded rendering support for hidden analytics pages, owned by the worker."""
from time import monotonic
from urllib.parse import urlparse

from neto_incident_monitor.dashboard_context import DASHBOARD_ID, DashboardReadError


class LoginRenderingUnavailable(RuntimeError):
    """A safe code, never the raw DevTools exception or its payload."""
    pass


def dashboard_target(url):
    if not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url)
        return (parsed.scheme == 'https' and parsed.hostname == 'adeo.service-now.com'
                and parsed.port in (None, 443) and not parsed.username and not parsed.password
                and parsed.path.startswith('/now/platform-analytics-workspace/dashboards/')
                and '/sys-id/' + DASHBOARD_ID + '/' in parsed.path + '/')
    except ValueError:
        return False


class HiddenRendering:
    def __init__(self, diagnostics, scope='dashboard'):
        if scope not in ('dashboard', 'login', 'favorites'):
            raise ValueError('Unknown rendering scope')
        self.scope = scope
        self.diagnostics = diagnostics
        self.page = self.client = None
        self.failed = False
        self.frames = self.acks = self.payload_bytes = 0
        self.started = None

    def record(self, event, **facts):
        try:
            self.diagnostics.record(event, **({'rendering_scope': self.scope} if self.scope != 'dashboard' else {}), **facts)
        except Exception:
            pass  # Diagnostics must never change browser behavior.

    def sync(self, page, enabled):
        if page is not self.page:
            self.close('page_changed')
            self.page = page
        if not enabled:
            self.close('not_needed')
            return
        if page.is_closed():
            self.stop('page_closed')
            return  # Let the existing reader report/recover the closed browser.
        if self.failed:
            self.unavailable()
        if not self.target(page.url):
            self.stop('context_left')
            return
        from neto_incident_monitor.authentication import authentication_required, authenticated_session
        if self.scope == 'login':
            from neto_incident_monitor.authentication import login_observation
            observed = login_observation(page, 'https://adeo.service-now.com/', include_popups=False)
            if (observed.state != 'authentication' or observed.facts.get('intervention') or
                    observed.facts.get('password_manual_edit')):
                self.stop('authentication')
                return
        elif authentication_required(page, 'https://adeo.service-now.com/'):
            self.stop('authentication')
            return
        if self.client:
            return
        if self.scope != 'login' and not authenticated_session(page, 'https://adeo.service-now.com/'):
            self.record('rendering_deferred', rendering_reason='session_unconfirmed')
            return
        self.frames = self.acks = self.payload_bytes = 0
        self.started = monotonic()
        self.record('rendering_start')
        try:
            self.client = page.context.new_cdp_session(page)
            self.client.on('Page.screencastFrame', self.frame)
            page.on('framenavigated', self.navigation)
            page.on('close', self.closed)
            self.client.send('Page.startScreencast', {
                'format': 'jpeg', 'quality': 0, 'maxWidth': 1,
                'maxHeight': 1, 'everyNthFrame': 60})
        except Exception as error:
            closed = page.is_closed()
            self.failed = True
            from neto_incident_monitor.login_diagnostics import error_facts
            self.record('rendering_error', rendering_reason='start_failed', **error_facts(error))
            self.stop('start_failed')
            if closed:
                raise
            self.unavailable()

    def unavailable(self):
        if self.scope == 'login':
            raise LoginRenderingUnavailable('rendering_unavailable') from None
        raise DashboardReadError('rendering_unavailable', retryable=False) from None

    def frame(self, event):
        client = self.client
        if not client:
            return
        # Discard payload without decoding or retaining it. No per-frame log.
        self.frames += 1
        # Authentication payloads are never even inspected for byte length.
        if self.scope == 'dashboard':
            self.payload_bytes += len(event.get('data', ''))
        try:
            client.send('Page.screencastFrameAck', {'sessionId': event['sessionId']})
            self.acks += 1
        except Exception as error:
            self.failed = True
            from neto_incident_monitor.login_diagnostics import error_facts
            self.record('rendering_error', rendering_reason='ack_failed', **error_facts(error))
            self.stop('ack_failed')

    def navigation(self, frame):
        if self.page and frame == self.page.main_frame and (self.scope == 'login' or not self.target(frame.url)):
            self.stop('context_left')

    def target(self, url):
        if not isinstance(url, str):
            return False
        if self.scope == 'dashboard':
            return dashboard_target(url)
        if self.scope == 'favorites':
            from neto_incident_monitor.favorites import HOME
            return url == HOME
        try:
            address = urlparse(url)
            return (address.scheme == 'https' and address.hostname == 'idpb2e.adeo.com'
                    and address.port in (None, 443) and address.username is None and address.password is None)
        except (TypeError, ValueError):
            return False

    def closed(self, *_):
        self.stop('page_closed')

    def stop(self, reason):
        client, self.client = self.client, None
        started, self.started = self.started, None
        if self.page:
            for name, handler in (('framenavigated', self.navigation), ('close', self.closed)):
                try:
                    self.page.remove_listener(name, handler)
                except Exception:
                    pass
        if client:
            errors = 0
            try:
                client.remove_listener('Page.screencastFrame', self.frame)
            except Exception:
                errors += 1
            for action in (lambda: client.send('Page.stopScreencast'), client.detach):
                try:
                    action()
                except Exception:
                    errors += 1
            self.record('rendering_stop', rendering_reason=reason,
                        duration_ms=round((monotonic() - started) * 1000) if started is not None else 0,
                        frame_count=self.frames, ack_count=self.acks,
                        **({'payload_bytes': self.payload_bytes} if self.scope == 'dashboard' else {}),
                        cleanup_errors=errors)

    def close(self, reason='read_finished'):
        self.stop(reason)
        self.page = None
        self.failed = False
