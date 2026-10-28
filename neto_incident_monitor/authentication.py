"""Authentication signals and input guards; never collect credential values."""
from urllib.parse import urlparse
from weakref import WeakKeyDictionary, WeakSet
from threading import Lock

_manual_pages = WeakKeyDictionary()
_generations = WeakKeyDictionary()
_observed_pages = WeakSet()
_manual_lock = Lock()


def manual_handoff(page):
    with _manual_lock:
        return bool(_manual_pages.get(page, False))


def clear_manual_handoff(page):
    with _manual_lock:
        _manual_pages.pop(page, None)


def document_generation(page):
    with _manual_lock:
        return _generations.get(page, 0)


INPUT_GUARD = r"""(() => {
    if (window.__netoInputGuard) return;
    const state = {manual: false, submitted: false, clickClaimed: false, submitSeen: false};
    window.__netoInputGuard = state;
    const target = event => event.composedPath ? event.composedPath()[0] : event.target;
    const active = () => window.__netoLoginDelivery && window.__netoLoginDelivery.active;
    const cancel = event => { event.preventDefault(); event.stopImmediatePropagation(); };
    const handoff = () => {
        const auth = /^idp[a-z0-9-]*\.adeo\.com$/i.test(location.hostname) ||
            /login|sso|auth/i.test(location.pathname) ||
            [...document.querySelectorAll('input[type=password]')].some(el => el.getClientRects().length);
        if (auth && typeof window.__netoManualAction === 'function')
            window.__netoManualAction().catch(() => {});
    };
    window.addEventListener('pageshow', event => {
        if (!event.persisted) return;
        // Back/forward cache can restore an in-flight guard from the old page.
        if (window.__netoLoginDelivery) window.__netoLoginDelivery.active = false;
        window.__netoAccountClick = false;
        state.manual = true;
        handoff();
    });
    const edit = event => {
        const el = target(event);
        if (event.isTrusted && el && el.matches &&
            el.matches('input[type=password], input[type=text], input[type=email], input[type=tel]'))
            { if (!state.manual) handoff(); state.manual = true; }
    };
    document.addEventListener('beforeinput', edit, true);
    document.addEventListener('paste', edit, true);
    document.addEventListener('click', event => {
        const el = target(event);
        const control = el && el.closest && el.closest('button, input[type=submit], a#signOnButton, .identifier-first__account-item');
        if (!control) return;
        if (control === window.__netoAccountClick) {
            if (state.manual) cancel(event);
            return;
        }
        const login = control.id === 'signOnButton' || control.type === 'submit' ||
            /^(zaloguj się|sign in|log in)$/i.test((control.innerText || control.value || '').trim());
        if (active() && login) {
            if (state.manual || state.clickClaimed || state.submitSeen) { cancel(event); return; }
            state.clickClaimed = true;
        } else if (event.isTrusted) {
            if (!state.manual) handoff();
            state.manual = true;
            if (login) state.submitted = true;
        }
    }, true);
    document.addEventListener('submit', event => {
        const account = window.__netoAccountClick;
        if (account && account.closest && account.closest('form') === event.target && !state.manual) return;
        if (active()) {
            if (state.manual || state.submitSeen) { cancel(event); return; }
            state.submitSeen = true;
        } else {
            handoff();
            state.submitted = true;
        }
    }, true);
})()"""


def authentication_required(page, target):
    if not isinstance(page.url, str):
        return False
    actual = urlparse(page.url)
    if actual.hostname != urlparse(target).hostname or any(
            part in actual.path.lower() for part in ('login', 'sso', 'auth')):
        return True
    # Inline forms can keep the original list URL. Inspect frames as well.
    try:
        return any(frame.locator('input[type="password"]:visible').count() > 0
                   for frame in page.frames)
    except Exception:
        # Navigation will be inspected again on the next iteration.
        return False


def install_input_guard(context):
    def handoff(source):
        with _manual_lock:
            _manual_pages[source['page']] = True
    context.expose_binding('__netoManualAction', handoff)
    def observe(page):
        if page in _observed_pages:
            return
        _observed_pages.add(page)
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
    pages = page.context.pages
    if isinstance(pages, (list, tuple)):
        for candidate in pages:
            if candidate != page and not candidate.is_closed() and candidate.opener() == page:
                if authentication_required(candidate, target):
                    return candidate
    return page



SESSION_READY = """() => {
    const user = window.g_user || (window.NOW && window.NOW.user);
    const id = user && (user.userID || user.user_id);
    return !!id && id !== 'guest';
}"""


def authenticated_session(page, target):
    expected = urlparse(target).hostname
    for frame in page.frames:
        if not isinstance(frame.url, str) or urlparse(frame.url).hostname != expected:
            continue
        try:
            if frame.locator('input[type=password]:visible').count() == 0 and frame.evaluate(SESSION_READY) is True:
                return True
        except Exception:
            continue
    return False
