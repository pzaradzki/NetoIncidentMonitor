"""Authentication signals and input guards; never collect credential values."""
from weakref import WeakKeyDictionary, WeakSet
from threading import Lock

_manual_pages = WeakKeyDictionary()
_account_selections = WeakKeyDictionary()
_login_active = WeakSet()
_manual_password_contexts = WeakSet()
_generations = WeakKeyDictionary()
_observed_pages = WeakSet()
_manual_lock = Lock()


def manual_handoff(page):
    with _manual_lock:
        return bool(_manual_pages.get(page, False))


def clear_manual_handoff(page):
    with _manual_lock:
        _manual_pages.pop(page, None)
        _account_selections.pop(page, None)


def set_login_activity(page):
    with _manual_lock:
        _login_active.add(page)

def take_manual_password_entry(page):
    with _manual_lock:
        entered = page.context in _manual_password_contexts
        _manual_password_contexts.discard(page.context)
        return entered


def clear_login_activity(page):
    with _manual_lock:
        _manual_password_contexts.discard(page.context)
        for active in list(_login_active):
            if active is page or active.context is page.context:
                _login_active.discard(active)


def finish_authentication(page):
    clear_manual_handoff(page)
    clear_login_activity(page)
    try:
        page.evaluate("""() => {
            const state = window.__netoInputGuard;
            if (state) for (const key of Object.keys(state)) state[key] = false;
            if (window.__netoLoginDelivery) window.__netoLoginDelivery.active = false;
            window.__netoAccountClick = false;
        }""")
    except Exception:
        pass  # A confirmed session may immediately replace its document.


def document_generation(page):
    with _manual_lock:
        return _generations.get(page, 0)


INPUT_GUARD = r"""(() => {
    if (window.__netoInputGuard) return;
    const state = {manual: false, submitted: false, accountSelected: false, clickClaimed: false, submitSeen: false};
    window.__netoInputGuard = state;
    const target = event => event.composedPath ? event.composedPath()[0] : event.target;
    const active = () => window.__netoLoginDelivery && window.__netoLoginDelivery.active;
    const cancel = event => { event.preventDefault(); event.stopImmediatePropagation(); };
    const authentication = () => /^idp[a-z0-9-]*\.adeo\.com$/i.test(location.hostname) ||
            /login|sso|auth/i.test(location.pathname) ||
            [...document.querySelectorAll('input[type=password]')].some(el => el.getClientRects().length);
    const claimManual = (submitted=false) => {
        const claim = () => {
            state.manual = true;
            if (submitted) { state.submitted = true; state.userSubmitIntent = true; }
        };
        if (authentication()) {
            claim();
            if (typeof window.__netoManualAction === 'function')
                window.__netoManualAction().catch(() => {});
        } else if (typeof window.__netoManualAction === 'function') {
            window.__netoManualAction('candidate').then(active => { if (active) claim(); }).catch(() => {});
        }
    };
    window.addEventListener('pageshow', event => {
        if (!event.persisted) return;
        // Back/forward cache can restore an in-flight guard from the old page.
        if (window.__netoLoginDelivery) window.__netoLoginDelivery.active = false;
        window.__netoAccountClick = false;
        claimManual();
    });
    const edit = event => {
        const el = target(event);
        if (event.isTrusted && el && el.matches &&
            el.matches('input[type=password], input[type=text], input[type=email], input[type=tel]'))
            { if (!state.manual) claimManual(); }
    };
    document.addEventListener('beforeinput', edit, true);
    document.addEventListener('paste', edit, true);
    document.addEventListener('beforeinput', event => {
        const el = target(event);
        if (!event.isTrusted || !el?.matches?.('input[type=password], input[autocomplete=current-password]') ||
            el.matches('[autocomplete=one-time-code]') ||
            !['insertText', 'insertFromPaste', 'insertCompositionText', 'insertFromDrop'].includes(event.inputType) ||
            typeof window.__netoManualAction !== 'function') return;
        window.__netoManualAction('password').catch(() => {});
    }, true);
    document.addEventListener('keydown', event => {
        const el = target(event);
        if (event.isTrusted && event.key === 'Enter' && el && el.matches &&
            el.matches('input[type=password], input[type=text], input[type=email], input[type=tel]'))
            claimManual(true);
    }, true);
    document.addEventListener('click', event => {
        const el = target(event);
        const control = el && el.closest && el.closest('button, input[type=submit], a#signOnButton, .identifier-first__account-item');
        if (!control) return;
        if (control === window.__netoAccountClick) {
            if (state.manual) cancel(event);
            return;
        }
        // Selecting an SSO account is a narrow handoff, not ownership of the
        // subsequent password form. Never include the remove-account control.
        if (event.isTrusted && control.matches('.identifier-first__account-item') &&
            !el.closest('.identifier-first__remove-account')) {
            state.accountSelected = true;
            if (typeof window.__netoManualAction === 'function')
                window.__netoManualAction('account').catch(() => {});
            return;
        }
        const login = control.id === 'signOnButton' || control.type === 'submit' ||
            /^(zaloguj się|sign in|log in)$/i.test((control.innerText || control.value || '').trim());
        if (active() && login) {
            if (state.manual || state.clickClaimed || state.submitSeen) { cancel(event); return; }
            state.clickClaimed = true;
        } else if (event.isTrusted) {
            claimManual(login);
        }
    }, true);
    document.addEventListener('submit', event => {
        const account = window.__netoAccountClick;
        if (account && account.closest && account.closest('form') === event.target && !state.manual) return;
        if (state.accountSelected && !state.manual && !state.submitted &&
            !event.target.querySelector('input[type=password]')) return;
        if (active()) {
            if (state.manual || state.submitSeen) { cancel(event); return; }
            state.submitSeen = true;
        } else if (state.manual || state.userSubmitIntent) {
            claimManual(true);
        } else if (event.target.querySelector('input[type=password]')) {
            // A site-initiated password request is also not permission for an
            // additional automatic request. Hidden SAML relay forms are not
            // human interaction and must not acquire manual ownership.
            state.submitted = true;
        }
    }, true);
})()"""


def login_observation(page, target, **options):
    from neto_incident_monitor.login_observation import observe_login
    observed = observe_login(page, target, generation=document_generation(page), **options)
    with _manual_lock:
        observed.facts['manual_account_selections'] = _account_selections.get(page, 0)
    return observed


def authentication_required(page, target):
    return login_observation(page, target).requires_authentication


def install_input_guard(context):
    from neto_incident_monitor.login_observation import origin_kind

    def handoff(source, kind=None):
        with _manual_lock:
            if kind == 'password':
                page = source['page']
                if page not in _login_active or origin_kind(source['frame'].url) == 'other':
                    return False
                _manual_password_contexts.add(context)
                _manual_pages[page] = True
            elif kind == 'account':
                _account_selections[source['page']] = _account_selections.get(source['page'], 0) + 1
            else:
                if kind == 'candidate' and source['page'] not in _login_active:
                    return False
                _manual_pages[source['page']] = True
            return True
    context.expose_binding('__netoManualAction', handoff)
    def observe(page):
        if page in _observed_pages:
            return
        _observed_pages.add(page)
        try:
            opener = page.opener()
        except Exception:
            opener = None
        with _manual_lock:
            if opener in _login_active:
                _login_active.add(page)
        def navigated(frame):
            if frame == page.main_frame:
                with _manual_lock:
                    _generations[page] = _generations.get(page, 0) + 1
        page.on('framenavigated', navigated)
    context.on('page', observe)
    for page in context.pages:
        observe(page)
    context.add_init_script(INPUT_GUARD)


def login_surface(page, target):
    """Inspect only authentication popups opened by the monitored tab."""
    from neto_incident_monitor.login_observation import owned_pages
    for candidate in reversed(owned_pages(page)):
        if authentication_required(candidate, target):
            return candidate
    return page



def authenticated_session(page, target):
    return login_observation(page, target).session_ready
