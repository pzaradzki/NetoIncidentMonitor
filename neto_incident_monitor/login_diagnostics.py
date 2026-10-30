"""Bounded login diagnostics containing structural facts, never form values."""
import json
import logging
from logging.handlers import RotatingFileHandler
from threading import Lock
from time import perf_counter
from urllib.parse import urlparse
from uuid import uuid4
from contextvars import ContextVar

from neto_incident_monitor.runtime_paths import DATA

_lock = Lock()
_logger = logging.getLogger('neto.login_diagnostics')
_logger.propagate = False
_logger.setLevel(logging.INFO)
TRACE = ContextVar('authentication_trace', default=None)

SNAPSHOT = """() => {
    const visible = el => !!el.getClientRects().length;
    const passwords = [...document.querySelectorAll('input[type=password]')].filter(visible);
    const identities = [...document.querySelectorAll('input')].filter(el =>
        visible(el) && ['text', 'email', 'tel'].includes(el.type));
    const buttons = [...document.querySelectorAll('button, input[type=submit], a#signOnButton')]
        .filter(el => visible(el) && (el.id === 'signOnButton' || /^zaloguj się$/i.test((el.innerText || el.value || '').trim())));
    const text = document.body ? document.body.innerText : '';
    return {
        password_count: passwords.length,
        password_filled: passwords.some(el => !!el.value),
        password_enabled: passwords.some(el => !el.disabled),
        password_autofilled: passwords.some(el => el.matches(':-webkit-autofill')),
        password_manual_edit: !!(window.__netoInputGuard && window.__netoInputGuard.manual),
        identity_count: identities.length,
        identity_locked: identities.some(el => el.readOnly || el.disabled),
        login_button_count: buttons.length,
        login_button_enabled: buttons.some(el => !el.disabled && el.getAttribute('aria-disabled') !== 'true' && !el.classList.contains('disabled')),
        account_count: [...document.querySelectorAll('#existingAccountsSelectionList .identifier-first__account-item')].filter(visible).length,
        welcome: /WITAMY|WELCOME/i.test(text),
        intervention: /incorrect|invalid|błędne hasło|kod weryfik|verification code|authenticator|captcha|zablokowan/i.test(text),
        document_ready: document.readyState === 'complete'
    };
}"""

FIELDS = ('password_count', 'password_filled', 'password_enabled', 'password_autofilled',
          'password_manual_edit', 'identity_count', 'identity_locked', 'login_button_count',
          'login_button_enabled', 'account_count', 'welcome', 'intervention', 'document_ready')

# Only explicitly approved structural fields may reach disk. Unknown text is
# discarded rather than redacted after the fact.
NUMERIC_FIELDS = set(FIELDS) | {'auto_login', 'minimize', 'hidden', 'minimize_browser', 'hide_browser', 'elapsed_s',
    'auto_blocked', 'auto_submitted', 'account_selected', 'blocked', 'supported_origin',
    'password_ready', 'button_count', 'aria_or_class_disabled', 'attempt',
    'delivery_observer', 'timeout_ms', 'delay_s', 'automatic_blocked', 'autofilled',
    'locked_account', 'manual', 'submitted', 'frame_count', 'page_count', 'http_status', 'reused', 'loading', 'button_available', 'widget_count', 'activated_count'}
TEXT_FIELDS = {
    'risk_tile': {'P1', 'P2', 'P3', 'P4', 'P5', 'Podjęcie'},
    'tile': {'Otwarte wnioski L1', 'Wnioski L1 >7 dni', 'Wnioski L1 >14 dni', 'Nieprzypisane wnioski L1'},
    'tile_state': {'ready', 'missing', 'ambiguous', 'invalid', 'unavailable', 'loading'},
    'score_source': {'widget_value', 'button', 'none'},
    'activity': {'login', 'dashboard', 'filters'},
    'readiness_reason': {'covered', 'unstable', 'disabled', 'hidden', 'detached', 'outside_viewport', 'unavailable'},
    'origin': {'adeo_identity', 'servicenow', 'other'},
    'source': {'dashboard', 'monitor'},
    'section': {'sla', 'held', 'requests', 'threatened'},
    'category': {'status', 'location', 'assigned', 'agent', 'other'},
    'operation': {'navigate', 'open_tab', 'open_period', 'fill_start', 'fill_end', 'commit_period', 'category_select', 'category_apply', 'prepare_widgets', 'read_scores'},
    'network_error': {'aborted', 'timeout', 'dns', 'connection', 'certificate', 'other'},
    'error_category': {'timeout', 'browser_closed', 'profile_locked', 'browser_missing',
        'access_denied', 'network_dns', 'network_connection', 'network_tls',
        'document_changed', 'ambiguous_locator', 'element_unavailable', 'file_access', 'unexpected'},
    'delivery': {'observed', 'not_observed', 'unknown'},
    'error_type': {'Error', 'TimeoutError', 'TargetClosedError', 'RuntimeError',
                   'ValueError', 'OSError', 'PermissionError', 'LoginTargetUnavailable'},
    'reason': {'wykryto ręczną obsługę formularza', 'wymagany wybór spośród wielu kont',
        'logowanie w osobnym oknie wymaga obsługi użytkownika',
        'formularz zawiera wiele pól hasła', 'formularz logowania został zastąpiony',
        'pole hasła nie zostało rozpoznane jako autouzupełnione',
        'strona wymaga interwencji użytkownika lub zgłasza błąd',
        'brak zakończenia logowania przez 30 sekund po zatwierdzeniu',
        'nie udało się wykonać kliknięcia logowania po trzech próbach',
        'wybór konta nie przeszedł do formularza po trzech próbach'},
}
EVENTS = set('''start blocked automatic_skipped awaiting_submission_result dashboard_widgets_retry
waiting_password_fill waiting_remembered_form submit_unavailable submit_retry_cancelled
submit_attempt submit_error submit_retry_scheduled submit_clicked account_selection_ambiguous
account_click_attempt account_click_error account_waiting_ready submit_waiting_ready account_clicked browser_closed automatic_login_step_error
manual_login_show_attempt manual_login_shown manual_login_show_retry manual_login_show_failed
target_unavailable login_complete reopen_requested_list login_loop_error login_cancelled
page_state login_still_waiting inspection_error section_read_attempt section_read_complete section_read_partial
dashboard_scores_attempt dashboard_scores_error dashboard_scores_retry dashboard_tile_state dashboard_tile_missing dashboard_widgets_activated
session_expired navigation document_response document_failed initial_navigation_attempt initial_navigation_error
authentication_popup dashboard_operation dashboard_navigation section_read_error browser_options_changed browser_activity visibility_deferred authentication_popup_closed session_confirmed browser_launch_attempt browser_launched monitor_error monitor_finished browser_restart_limited browser_restart_delay'''.split())


def readiness_facts(error):
    """Return fixed actionability codes; never retain the Playwright call log."""
    message = str(error).lower()
    reason = next((code for marker, code in (
        ('intercepts pointer events', 'covered'), ('not stable', 'unstable'),
        ('not enabled', 'disabled'), ('not visible', 'hidden'),
        ('not attached', 'detached'), ('outside of the viewport', 'outside_viewport'),
    ) if marker in message), 'unavailable')
    return {'readiness_reason': reason, **error_facts(error)}


def error_facts(error):
    """Classify in memory, retaining neither the message nor URL/form values."""
    message = str(error).lower()
    category = next((code for markers, code in (
        (('targetclosed', 'target page, context or browser has been closed'), 'browser_closed'),
        (('processsingleton', 'profile in use', 'user data directory is already in use'), 'profile_locked'),
        (("executable doesn't exist", 'executable not found'), 'browser_missing'),
        (('err_name_not_resolved',), 'network_dns'),
        (('err_cert_',), 'network_tls'),
        (('err_connection_', 'err_internet_disconnected'), 'network_connection'),
        (('execution context was destroyed', 'cannot find context'), 'document_changed'),
        (('strict mode violation',), 'ambiguous_locator'),
        (('not attached to the dom', 'element is not visible', 'element is not enabled'), 'element_unavailable'),
        (('access denied', 'permission denied'), 'access_denied'),
        (('timeout', 'timed out'), 'timeout'),
    ) if any(marker in message for marker in markers)), None)
    if category is None:
        category = 'timeout' if type(error).__name__ == 'TimeoutError' else 'file_access' if isinstance(error, OSError) else 'unexpected'
    return {'error_type': type(error).__name__, 'error_category': category}


def safe_facts(facts):
    from neto_incident_monitor import __version__
    clean = {}
    for key, value in facts.items():
        if key in NUMERIC_FIELDS and type(value) in (bool, int, float):
            clean[key] = value
        elif key in TEXT_FIELDS and isinstance(value, str) and value in TEXT_FIELDS[key]:
            clean[key] = value
        elif key == 'error_type':
            clean[key] = 'Error'
        elif key == 'app_version' and value == __version__:
            clean[key] = value
    return clean


class LoginDiagnostics:
    def __init__(self, **options):
        self.session = uuid4().hex[:12]
        self.started = perf_counter()
        self.previous = {}
        self.sequence = 0
        self.trace = TRACE.get() or uuid4().hex
        from neto_incident_monitor import __version__
        self.record('start', app_version=__version__, **options)

    def attach(self, page):
        def navigation(frame):
            if frame == page.main_frame:
                host = urlparse(frame.url).hostname or ''
                origin = 'adeo_identity' if host.endswith('.adeo.com') else 'servicenow' if host.endswith('.service-now.com') else 'other'
                self.record('navigation', origin=origin)
        def response(result):
            if result.request.resource_type == 'document':
                self.record('document_response', http_status=result.status)
        def failed(request):
            if request.resource_type == 'document':
                failure = request.failure or ''
                # Convert the browser's message to a fixed category; never store it.
                category = next((code for marker, code in (
                    ('ABORTED', 'aborted'), ('TIMED_OUT', 'timeout'),
                    ('NAME_NOT_RESOLVED', 'dns'), ('CERT_', 'certificate'),
                    ('CONNECTION_', 'connection')) if marker in failure), 'other')
                self.record('document_failed', network_error=category)
        listeners = [('framenavigated', navigation), ('response', response), ('requestfailed', failed)]
        for event, callback in listeners:
            page.on(event, callback)
        def detach():
            for event, callback in listeners:
                try:
                    page.remove_listener(event, callback)
                except Exception:
                    pass  # Browser shutdown must not mask the original outcome.
        return detach

    def record(self, event, **facts):
        try:
            if event not in EVENTS:
                return
            facts = safe_facts(facts)
            # Callers supply fixed event codes and booleans/counts, never DOM text.
            now = perf_counter()
            signature = json.dumps(facts, sort_keys=True)
            previous = self.previous.get(event)
            if previous and previous[0] == signature and now - previous[1] < 10:
                return
            self.previous[event] = (signature, now)
            self.sequence += 1
            with _lock:
                if not _logger.handlers:
                    DATA.mkdir(parents=True, exist_ok=True)
                    handler = RotatingFileHandler(DATA / 'login-diagnostics.jsonl',
                                                  maxBytes=2_000_000, backupCount=3, encoding='utf-8')
                    handler.setFormatter(logging.Formatter('%(message)s'))
                    _logger.addHandler(handler)
            from datetime import datetime, timezone
            _logger.info(json.dumps({'time': datetime.now(timezone.utc).isoformat(),
                                    'session': self.session, 'trace': self.trace, 'sequence': self.sequence,
                                    'elapsed_s': round(now - self.started, 1),
                                    'event': event, **facts}, ensure_ascii=False))
        except Exception:
            # Diagnostics must never interrupt authentication or print unsafe exceptions.
            logging.getLogger('servicenow').warning('Nie udało się zapisać diagnostyki logowania.')

    def inspect(self, page, automatic):
        try:
            host = urlparse(page.url).hostname or ''
            origin = 'adeo_identity' if host.endswith('.adeo.com') else 'servicenow' if host.endswith('.service-now.com') else 'other'
            raw = page.evaluate(SNAPSHOT)
            facts = {key: raw[key] for key in FIELDS
                     if isinstance(raw, dict) and type(raw.get(key)) in (bool, int)}
            self.record('page_state', origin=origin, **facts,
                        frame_count=len(page.frames), page_count=len(page.context.pages),
                        auto_blocked=bool(automatic and automatic.blocked),
                        auto_submitted=bool(automatic and automatic.submitted),
                        account_selected=bool(automatic and automatic.account_clicked))
            if perf_counter() - self.started >= 30:
                self.record('login_still_waiting')
        except Exception as error:
            self.record('inspection_error', **error_facts(error))
