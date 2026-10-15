"""One delivered submission, with bounded retries of undelivered ADEO clicks."""
import re
from time import monotonic
import logging
from urllib.parse import urlparse
from uuid import uuid4
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


ARM_DELIVERY = """(el, token) => {
    const guard = {token, activations: 0};
    window.__netoLoginDelivery = guard;
    const mark = event => {
        if (window.__netoLoginDelivery !== guard) return;
        if (el === event.target || el.contains(event.target) ||
            (event.type === 'submit' && (!el.form || event.target === el.form)) ||
            (event.type === 'beforeinput' && event.target.type === 'password')) guard.activations++;
    };
    for (const type of ['pointerdown', 'mousedown', 'click', 'submit', 'keydown', 'beforeinput'])
        document.addEventListener(type, mark, true);
    return true;
}"""

READ_DELIVERY = """token => {
    const guard = window.__netoLoginDelivery;
    return guard && guard.token === token ? guard.activations : null;
}"""


class AutomaticLogin:
    def __init__(self, diagnostics=None):
        self.diagnostics = diagnostics
        self.account_clicked = False
        self.submitted = False
        self.blocked = False
        self.account_attempts = 0
        self.last_account_attempt = None
        self.submitted_at = None
        self.reason = None
        self.prefill_since = None
        self.submit_attempts = 0
        self.last_submit_attempt = None
        self.pending_delivery_token = None

    def report(self, event, **facts):
        if self.diagnostics:
            self.diagnostics.record(event, **facts)

    def block(self, reason):
        if not self.blocked:
            self.blocked = True
            self.reason = reason
            self.report("blocked", reason=reason)
            logging.getLogger("servicenow").warning("Automatyczne logowanie: %s; wymagane ręczne logowanie.", reason)

    def step(self, page):
        address = urlparse(page.url)
        host = address.hostname or ""
        if self.blocked or address.scheme != "https" or not re.fullmatch(r"idp[a-z0-9-]*\.adeo\.com", host, re.I):
            self.report("automatic_skipped", blocked=self.blocked, supported_origin=bool(address.scheme == "https" and re.fullmatch(r"idp[a-z0-9-]*\.adeo\.com", host, re.I)))
            return
        body = page.locator("body").inner_text(timeout=1000)
        if re.search(r"nieprawidł|błędne hasło|incorrect|invalid|authentication failed|"
                     r"kod weryfik|verification code|jednorazow|one.time|authenticator|"
                     r"zatwierdź (?:logowanie|żądanie)|approve sign|captcha|zablokowan", body, re.I):
            self.block("strona wymaga interwencji użytkownika lub zgłasza błąd")
            return
        if self.submitted:
            self.report("awaiting_submission_result")
            if self.submitted_at is not None and monotonic() - self.submitted_at >= 30:
                self.block("brak zakończenia logowania przez 30 sekund po zatwierdzeniu")
            return
        passwords = page.locator('input[type="password"]:visible')
        if passwords.count() == 1:
            ready = passwords.first.evaluate("el => !!el.value && !el.disabled")
            if not self.account_clicked:
                if not ready:
                    # Chromium can apply saved credentials after the first
                    # inspection of the login page.
                    self.report("waiting_password_fill")
                    self.prefill_since = None
                    return
                autofilled = passwords.first.evaluate("el => el.matches(':-webkit-autofill')")
                if not autofilled:
                    remembered_form = passwords.first.evaluate("""el => {
                        if (!el.__netoEditGuard) {
                            el.__netoEditGuard = true;
                            const edited = event => { if (event.isTrusted) el.__netoManualEdit = true; };
                            el.addEventListener('beforeinput', edited);
                            el.addEventListener('paste', edited);
                        }
                        const form = el.form || document;
                        const identities = [...form.querySelectorAll('input:not([type=password]):not([type=hidden])')]
                            .filter(input => input.getClientRects().length && input.value &&
                                ['text', 'email', 'tel'].includes(input.type));
                        return !el.__netoManualEdit && identities.length === 1 &&
                            (identities[0].readOnly || identities[0].disabled);
                    }""")
                    if not remembered_form:
                        self.block("pole hasła nie zostało rozpoznane jako autouzupełnione")
                        return
                    # Some ADEO resume pages lose the Chromium autofill marker.
                    # Allow one submission only for a locked remembered account,
                    # after a quiet period with no observed manual editing.
                    now = monotonic()
                    if self.prefill_since is None:
                        self.prefill_since = now
                    if now - self.prefill_since < 5:
                        self.report("waiting_remembered_form", autofilled=False, locked_account=True)
                        return
                    logging.getLogger("servicenow").info("Automatyczne logowanie: formularz zapamiętanego konta bez znacznika autouzupełnienia.")
            # Only inspect whether autofill is present. Never retrieve the password.
            buttons = page.get_by_role("button", name=re.compile(r"^Zaloguj się$", re.I))
            adeo_button = page.locator('a#signOnButton:visible')
            if adeo_button.count() == 1:
                buttons = adeo_button
            if ready and buttons.count() == 1 and buttons.first.is_visible() and buttons.first.is_enabled():
                disabled = buttons.first.evaluate("el => el.getAttribute('aria-disabled') === 'true' || el.classList.contains('disabled')")
                if disabled:
                    self.report("submit_unavailable", aria_or_class_disabled=True)
                    return
                now = monotonic()
                if self.last_submit_attempt is not None and now - self.last_submit_attempt < 2:
                    return
                if self.pending_delivery_token is not None:
                    try:
                        previous_delivery = page.evaluate(READ_DELIVERY, self.pending_delivery_token)
                    except Exception:
                        previous_delivery = None
                    if type(previous_delivery) is not int or previous_delivery != 0:
                        self.submitted = True
                        self.submitted_at = now
                        self.pending_delivery_token = None
                        self.report("submit_retry_cancelled", delivery='observed' if type(previous_delivery) is int else 'unknown')
                        return
                if self.submit_attempts >= 3:
                    self.block("nie udało się wykonać kliknięcia logowania po trzech próbach")
                    return
                token = uuid4().hex
                armed = buttons.first.evaluate(ARM_DELIVERY, token) is True
                self.pending_delivery_token = None
                self.submit_attempts += 1
                self.last_submit_attempt = now
                self.submitted = True  # Ambiguous outcomes must never be retried.
                self.submitted_at = now
                self.report("submit_attempt", attempt=self.submit_attempts, delivery_observer=armed, timeout_ms=5000)
                try:
                    buttons.first.click(timeout=5000)
                except Exception as error:
                    activations = None
                    if armed:
                        try:
                            activations = page.evaluate(READ_DELIVERY, token)
                        except Exception:
                            pass  # Navigation/document destruction makes delivery uncertain.
                    undelivered = type(activations) is int and activations == 0
                    self.report("submit_error", error_type=type(error).__name__,
                                delivery='not_observed' if undelivered else 'observed' if type(activations) is int else 'unknown',
                                attempt=self.submit_attempts)
                    if isinstance(error, PlaywrightTimeoutError) and undelivered:
                        self.submitted = False
                        self.submitted_at = None
                        self.pending_delivery_token = token
                        self.last_submit_attempt = monotonic()
                        self.report("submit_retry_scheduled", attempt=self.submit_attempts, delay_s=2)
                        if self.submit_attempts >= 3:
                            self.block("nie udało się wykonać kliknięcia logowania po trzech próbach")
                        return
                    raise
                self.submitted_at = monotonic()
                self.report("submit_clicked")
            else:
                self.report("submit_unavailable", password_ready=bool(ready), button_count=buttons.count())
            return
        if re.search(r"WITAMY|WELCOME", body, re.I):
            accounts = page.locator('#existingAccountsSelectionList .identifier-first__account-item:visible')
            if accounts.count():
                if accounts.count() != 1:
                    self.report("account_selection_ambiguous", account_count=accounts.count())
                    return
                name = accounts.first.locator('.identifier-first__account-name')
                if name.count() == 1 and name.is_visible():
                    now = monotonic()
                    if self.last_account_attempt is not None and now - self.last_account_attempt < 5:
                        return
                    if self.account_attempts >= 3:
                        self.block("wybór konta nie przeszedł do formularza po trzech próbach")
                        return
                    self.account_attempts += 1
                    self.last_account_attempt = now
                    self.report("account_click_attempt", attempt=self.account_attempts)
                    try:
                        name.click(timeout=1500)
                    except Exception as error:
                        self.report("account_click_error", error_type=type(error).__name__)
                        # Selection is safe to retry on this exact welcome
                        # screen; never retry submitting the password form.
                        logging.getLogger("servicenow").warning("Nie udało się kliknąć zapamiętanego konta; wybór zostanie ponowiony.")
                        return
                    self.account_clicked = True
                    self.report("account_clicked", attempt=self.account_attempts)
                return
