"""Credential-free authentication observation shared by readers and diagnostics.

Unknown observations never prove a session. This module observes, but neither
clicks nor navigates; action ownership and visibility remain with their callers.
"""
from dataclasses import dataclass
import re
from urllib.parse import urlsplit


def origin_kind(url, target='https://adeo.service-now.com/'):
    try:
        actual, expected = urlsplit(url), urlsplit(target)
        if (actual.scheme != 'https' or actual.username is not None or
                actual.password is not None or actual.port not in (None, 443)):
            return 'other'
        if actual.hostname == expected.hostname and expected.scheme == 'https':
            return 'servicenow'
        if re.fullmatch(r'idp[a-z0-9-]*\.adeo\.com', actual.hostname or '', re.I):
            return 'adeo_identity'
    except (ValueError, TypeError, AttributeError):
        pass
    return 'other'


# No text or input values cross the browser boundary. The selectors below are
# the controls observed in the ADEO audit, plus standard accessibility signals.
SIGNALS = r"""() => {
    const visible = el => !!el.getClientRects().length;
    const passwords = [...document.querySelectorAll('input[type=password]')].filter(visible);
    const identities = [...document.querySelectorAll('input')].filter(el =>
        visible(el) && ['text', 'email', 'tel'].includes(el.type));
    const buttons = [...document.querySelectorAll('button, input[type=submit], a#signOnButton')]
        .filter(el => visible(el) && (el.id === 'signOnButton' ||
            /^(zaloguj się|sign in|log in)$/i.test((el.innerText || el.value || '').trim())));
    const accounts = [...document.querySelectorAll('#existingAccountsSelectionList .identifier-first__account-item')].filter(visible);
    const scopes = new Set(passwords.map(el => el.closest('form')).filter(Boolean));
    const notices = [...document.querySelectorAll('[role=alert], [aria-live=assertive]')]
        .filter(el => visible(el) && [...scopes].some(scope => scope.contains(el)));
    const challenge = [...document.querySelectorAll('input[autocomplete="one-time-code"], iframe[src*="captcha"]')].some(visible);
    const pingid = location.protocol === 'https:' && !passwords.length &&
        [...document.querySelectorAll('input[maxlength="6"]')].some(visible) &&
        /podaj otrzymany kod dostępu/i.test(document.body?.innerText || '') &&
        /wyślij kod dostępu ponownie/i.test(document.body?.innerText || '');
    const intervention = challenge || pingid || notices.some(el =>
        /incorrect|invalid|błędne|nieprawidł|verification|weryfik|captcha|zablokowan/i.test(el.innerText || ''));
    const user = window.g_user || (window.NOW && window.NOW.user);
    const id = user && (user.userID || user.user_id);
    // SOW can render the authenticated header without the legacy user global.
    // Read only the structure of the known main workspace, never its profile data.
    let sowSession = false;
    if (window === window.top && location.pathname === '/now/sow/home') {
        const unique = (root, selector) => {
            const matches = root?.querySelectorAll(selector);
            return matches?.length === 1 ? matches[0] : null;
        };
        const shell = unique(document, 'macroponent-f51912f4c700201072b211d4d8c26010');
        const layout = unique(shell?.shadowRoot, 'sn-polaris-layout');
        const header = unique(layout?.shadowRoot, 'sn-polaris-header');
        const menu = unique(header?.shadowRoot, 'sn-contextual-menu#userMenu');
        const avatar = unique(header?.shadowRoot, 'now-avatar');
        sowSession = !!menu && !!avatar && visible(avatar);
    }
    return {
        password_count: passwords.length,
        password_filled: passwords.some(el => !!el.value),
        password_enabled: passwords.some(el => !el.disabled && !el.readOnly),
        password_autofilled: passwords.some(el => el.matches(':-webkit-autofill')),
        password_manual_edit: !!(window.__netoInputGuard && window.__netoInputGuard.manual),
        identity_count: identities.length,
        identity_locked: identities.some(el => el.readOnly || el.disabled),
        login_button_count: buttons.length,
        login_button_enabled: buttons.some(el => !el.disabled && el.getAttribute('aria-disabled') !== 'true' && !el.classList.contains('disabled')),
        account_count: accounts.length, welcome: accounts.length > 0,
        intervention, session_signal: (!!id && id !== 'guest') || sowSession,
        logout_signal: /\/(?:external_logout_complete|logout|logout_complete)\.do$/i.test(location.pathname),
        authentication_path: /login|sso|auth/i.test(location.pathname),
        document_ready: document.readyState === 'complete'
    };
}"""

COUNTS = ('password_count', 'identity_count', 'login_button_count', 'account_count')
FLAGS = ('password_filled', 'password_enabled', 'password_autofilled',
         'password_manual_edit', 'identity_locked', 'login_button_enabled',
         'welcome', 'intervention', 'session_signal', 'logout_signal',
         'authentication_path', 'document_ready')


def owned_pages(page):
    """Follow browser-reported opener ancestry, never a page-provided URL."""
    pages = list(page.context.pages)
    result = []
    for candidate in pages:
        if candidate == page or candidate.is_closed():
            continue
        ancestor = candidate.opener()
        visited = set()
        while ancestor is not None:
            if ancestor == page:
                result.append(candidate)
                break
            if ancestor in visited or len(visited) >= 32:
                raise RuntimeError('Popup ownership could not be confirmed')
            visited.add(ancestor)
            ancestor = ancestor.opener()
    return result


@dataclass(frozen=True)
class LoginObservation:
    state: str
    evidence: str
    origin: str
    surface: str
    generation: int
    frame_count: int
    facts: dict

    @property
    def session_ready(self):
        return self.state == 'session'

    @property
    def requires_authentication(self):
        # A failed inspection is not permission to consume stale page data.
        return self.state not in ('session', 'target')


def observe_login(page, target, *, surface='main', generation=0, include_popups=True):
    origin = origin_kind(getattr(page, 'url', None), target)
    frames = getattr(page, 'frames', ())
    facts = {key: 0 for key in COUNTS}
    facts.update({key: False for key in FLAGS})
    try:
        facts['logout_signal'] = bool(re.search(
            r'/(?:external_logout_complete|logout|logout_complete)\.do$',
            urlsplit(page.url).path, re.I))
    except (ValueError, TypeError, AttributeError):
        pass
    failed = False
    frame_count = 0
    auth = origin == 'adeo_identity'
    session = False
    def observation_error(error):
        # Classification only; exception messages can contain SSO parameters.
        from neto_incident_monitor.login_diagnostics import error_facts, safe_facts
        if 'error_category' not in facts:
            facts.update(safe_facts(error_facts(error)))
    try:
        frames = list(frames)
        frame_count = len(frames)
        if not frames:
            failed = True
        for frame in frames:
            try:
                raw = frame.evaluate(SIGNALS)
                if (not isinstance(raw, dict) or
                        any(type(raw.get(key)) is not int or raw[key] < 0 for key in COUNTS) or
                        any(type(raw.get(key)) is not bool for key in FLAGS)):
                    failed = True
                    continue
                for key in COUNTS:
                    facts[key] += raw[key]
                for key in FLAGS:
                    facts[key] |= raw[key]
                frame_origin = origin_kind(frame.url, target)
                auth |= bool(raw['password_count'] or raw['account_count'] or
                             raw['intervention'] or raw['authentication_path'])
                session |= frame_origin == 'servicenow' and raw['session_signal']
            except Exception as error:
                failed = True
                observation_error(error)
        # Only a popup owned by this monitored page can veto its stale session.
        if include_popups:
            for candidate in owned_pages(page):
                popup = observe_login(candidate, target, surface='owned_popup', include_popups=False)
                if popup.state != 'session':
                    auth = True
    except Exception as error:
        failed = True
        observation_error(error)
    if facts['logout_signal']:
        state, evidence = 'logout', 'logout_document'
    elif auth:
        state, evidence = 'authentication', 'authentication_surface'
    elif failed:
        state, evidence = 'unknown', 'observation_failed'
    elif session and origin == 'servicenow':
        state, evidence = 'session', 'session_confirmed'
    elif origin != 'servicenow':
        state, evidence = 'unknown', 'context_unconfirmed'
    else:
        state, evidence = 'target', 'session_unconfirmed'
    return LoginObservation(state, evidence, origin, surface, generation, frame_count, facts)
