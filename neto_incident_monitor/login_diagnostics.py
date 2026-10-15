"""Bounded login diagnostics containing structural facts, never form values."""
import json
import logging
from logging.handlers import RotatingFileHandler
from threading import Lock
from time import perf_counter
from urllib.parse import urlparse
from uuid import uuid4

from neto_incident_monitor.runtime_paths import DATA

_lock = Lock()
_logger = logging.getLogger('neto.login_diagnostics')
_logger.propagate = False
_logger.setLevel(logging.INFO)

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
        password_manual_edit: passwords.some(el => !!el.__netoManualEdit),
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


class LoginDiagnostics:
    def __init__(self, **options):
        self.session = uuid4().hex[:12]
        self.started = perf_counter()
        self.previous = {}
        from neto_incident_monitor import __version__
        self.record('start', app_version=__version__, **options)

    def record(self, event, **facts):
        try:
            # Callers supply fixed event codes and booleans/counts, never DOM text.
            now = perf_counter()
            signature = json.dumps(facts, sort_keys=True)
            previous = self.previous.get(event)
            if previous and previous[0] == signature and now - previous[1] < 10:
                return
            self.previous[event] = (signature, now)
            with _lock:
                if not _logger.handlers:
                    DATA.mkdir(parents=True, exist_ok=True)
                    handler = RotatingFileHandler(DATA / 'login-diagnostics.jsonl',
                                                  maxBytes=2_000_000, backupCount=3, encoding='utf-8')
                    handler.setFormatter(logging.Formatter('%(message)s'))
                    _logger.addHandler(handler)
            from datetime import datetime, timezone
            _logger.info(json.dumps({'time': datetime.now(timezone.utc).isoformat(),
                                    'session': self.session, 'elapsed_s': round(now - self.started, 1),
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
                        auto_blocked=bool(automatic and automatic.blocked),
                        auto_submitted=bool(automatic and automatic.submitted),
                        account_selected=bool(automatic and automatic.account_clicked))
            if perf_counter() - self.started >= 30:
                self.record('login_still_waiting')
        except Exception as error:
            self.record('inspection_error', error_type=type(error).__name__)
