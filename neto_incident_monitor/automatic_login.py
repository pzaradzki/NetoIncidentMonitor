"""One delivered submission, with bounded retries of undelivered ADEO clicks."""
import re
from time import monotonic
import logging
from urllib.parse import urlparse
from uuid import uuid4
from neto_incident_monitor.authentication import INPUT_GUARD, manual_handoff, document_generation
from neto_incident_monitor.login_diagnostics import error_facts, readiness_facts
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


ARM_DELIVERY = """(el, token) => {
    const guard = {token, activations: 0, active: true};
    window.__netoLoginDelivery = guard;
    const mark = event => {
        if (window.__netoLoginDelivery !== guard) return;
        if (guard.active && window.__netoInputGuard && window.__netoInputGuard.manual &&
            (event.type === 'click' || event.type === 'submit')) {
            event.preventDefault();
            event.stopImmediatePropagation();
            return;
        }
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
    def __init__(self, diagnostics=None, enabled=None):
        self.diagnostics = diagnostics
        self.enabled = enabled or (lambda: True)
        self.form_token = None
        self.generation = None
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

    def previous_submission_pending(self, page, now):
        if self.pending_delivery_token is None:
            return False
        try:
            delivery = page.evaluate(READ_DELIVERY, self.pending_delivery_token)
        except Exception:
            delivery = None
        if type(delivery) is int and delivery == 0:
            return False
        self.submitted = True
        self.submitted_at = now
        self.pending_delivery_token = None
        self.report('submit_retry_cancelled', delivery='observed' if type(delivery) is int else 'unknown')
        return True

    def step(self, page):
        if not self.enabled():
            return
        address = urlparse(page.url)
        host = address.hostname or ""
        if self.blocked or address.scheme != "https" or not re.fullmatch(r"idp[a-z0-9-]*\.adeo\.com", host, re.I):
            self.report("automatic_skipped", blocked=self.blocked, supported_origin=bool(address.scheme == "https" and re.fullmatch(r"idp[a-z0-9-]*\.adeo\.com", host, re.I)))
            return
        page.evaluate(INPUT_GUARD)
        if manual_handoff(page):
            self.block('wykryto ręczną obsługę formularza')
            return
        generation = document_generation(page)
        if self.generation is not None and generation != self.generation and self.form_token is not None:
            self.account_clicked = False
            if not self.submitted:
                self.block('formularz logowania został zastąpiony')
                return
        self.generation = generation
        interaction = page.evaluate("() => ({manual: window.__netoInputGuard.manual, submitted: window.__netoInputGuard.submitted})")
        if isinstance(interaction, dict) and (interaction.get('manual') or interaction.get('submitted')):
            self.block("wykryto ręczną obsługę formularza")
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
        if passwords.count() > 1:
            self.block('formularz zawiera wiele pól hasła')
            return
        if passwords.count() == 1:
            token = passwords.first.evaluate("el => { if (!el.__netoFormToken) el.__netoFormToken = crypto.randomUUID(); return el.__netoFormToken; }", timeout=1000)
            if isinstance(token, str):
                if self.form_token is not None and token != self.form_token:
                    self.account_clicked = False
                    self.block('formularz logowania został zastąpiony')
                    return
                self.form_token = token
            ready = passwords.first.evaluate("el => !!el.value && !el.disabled", timeout=1000)
            if not self.account_clicked:
                if not ready:
                    # Chromium can apply saved credentials after the first
                    # inspection of the login page.
                    self.report("waiting_password_fill")
                    self.prefill_since = None
                    return
                autofilled = passwords.first.evaluate("el => el.matches(':-webkit-autofill')", timeout=1000)
                if not autofilled:
                    self.block("pole hasła nie zostało rozpoznane jako autouzupełnione")
                    return
            # Only inspect whether autofill is present. Never retrieve the password.
            buttons = page.get_by_role("button", name=re.compile(r"^Zaloguj się$", re.I))
            adeo_button = page.locator('a#signOnButton:visible')
            if adeo_button.count() == 1:
                buttons = adeo_button
            if ready and buttons.count() == 1 and buttons.first.is_visible() and buttons.first.is_enabled(timeout=1000):
                disabled = buttons.first.evaluate("el => el.getAttribute('aria-disabled') === 'true' || el.classList.contains('disabled')", timeout=1000)
                if disabled:
                    self.report("submit_unavailable", aria_or_class_disabled=True)
                    return
                now = monotonic()
                if self.last_submit_attempt is not None and now - self.last_submit_attempt < 2:
                    return
                if self.previous_submission_pending(page, now):
                    return
                if self.submit_attempts >= 3:
                    self.block("nie udało się wykonać kliknięcia logowania po trzech próbach")
                    return
                try:
                    # A trial waits for stable, unobstructed actionability but
                    # never activates the form. Do not spend submission attempts
                    # while Chromium is minimized or the page is still loading.
                    buttons.first.click(trial=True, timeout=500)
                except PlaywrightTimeoutError as error:
                    self.report("submit_waiting_ready", **readiness_facts(error))
                    return
                # A previously undelivered activation can arrive while trial
                # actionability is being checked. Inspect its observer again.
                if self.previous_submission_pending(page, monotonic()):
                    return
                if not self.enabled():
                    return
                if manual_handoff(page) or page.evaluate(
                        "!!(window.__netoInputGuard && (window.__netoInputGuard.manual || window.__netoInputGuard.submitted))") is True:
                    self.block('wykryto ręczną obsługę formularza')
                    return
                if (document_generation(page) != self.generation or
                        (isinstance(self.form_token, str) and
                         passwords.first.evaluate('el => el.__netoFormToken', timeout=500) != self.form_token)):
                    self.block('formularz logowania został zastąpiony')
                    return
                token = uuid4().hex
                armed = buttons.first.evaluate(ARM_DELIVERY, token, timeout=1000) is True
                self.pending_delivery_token = None
                self.submit_attempts += 1
                self.last_submit_attempt = now
                self.submitted = True  # Ambiguous outcomes must never be retried.
                self.submitted_at = now
                self.report("submit_attempt", attempt=self.submit_attempts, delivery_observer=armed, timeout_ms=5000)
                try:
                    buttons.first.click(timeout=5000, no_wait_after=True)
                except Exception as error:
                    activations = None
                    if armed:
                        try:
                            activations = page.evaluate(READ_DELIVERY, token)
                        except Exception:
                            pass  # Navigation/document destruction makes delivery uncertain.
                    undelivered = type(activations) is int and activations == 0
                    self.report("submit_error", **error_facts(error),
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
                finally:
                    try:
                        page.evaluate("token => { const g = window.__netoLoginDelivery; if (g && g.token === token) g.active = false; }", token)
                    except Exception:
                        pass
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
                    self.block("wymagany wybór spośród wielu kont")
                    return
                name = accounts.first.locator('.identifier-first__account-name')
                if name.count() == 1 and name.is_visible():
                    now = monotonic()
                    if self.last_account_attempt is not None and now - self.last_account_attempt < 5:
                        return
                    if self.account_attempts >= 3:
                        self.block("wybór konta nie przeszedł do formularza po trzech próbach")
                        return
                    # Click the card at the name, never its centre (which can
                    # contain the remove-account button). The name itself may
                    # have pointer-events:none while the card is interactive.
                    card = accounts.first
                    position = card.evaluate("""el => {
                        const name = el.querySelector('.identifier-first__account-name');
                        if (!name) return null;
                        const n = name.getBoundingClientRect(), r = el.getBoundingClientRect();
                        const x = n.left + n.width / 2, y = n.top + n.height / 2;
                        const hit = document.elementFromPoint(x, y);
                        if (hit && el.contains(hit) && hit.closest('.identifier-first__remove-account')) return null;
                        return n.width && n.height ? {x: x - r.left - el.clientLeft,
                            y: y - r.top - el.clientTop} : null;
                    }""")
                    if not position:
                        self.report("account_waiting_ready", readiness_reason="unavailable")
                        return
                    try:
                        card.click(position=position, trial=True, timeout=500)
                    except Exception as error:
                        # Readiness polls do not consume actual selection
                        # attempts. Return promptly to Stop/live-settings checks.
                        self.report("account_waiting_ready", **readiness_facts(error))
                        return
                    if not self.enabled() or manual_handoff(page) or page.evaluate(
                            "!!(window.__netoInputGuard && window.__netoInputGuard.manual)") is True:
                        return
                    self.account_attempts += 1
                    self.last_account_attempt = now
                    self.report("account_click_attempt", attempt=self.account_attempts)
                    if not self.enabled():
                        return
                    try:
                        card.evaluate("el => { window.__netoAccountClick = el; }")
                        card.click(position=position, timeout=5000, no_wait_after=True)
                    except Exception as error:
                        self.report("account_click_error", attempt=self.account_attempts, **error_facts(error))
                        # Selection is safe to retry on this exact welcome
                        # screen; never retry submitting the password form.
                        logging.getLogger("servicenow").warning("Nie udało się kliknąć zapamiętanego konta; wybór zostanie ponowiony.")
                        return
                    finally:
                        try:
                            page.evaluate("window.__netoAccountClick = false")
                        except Exception:
                            pass
                    self.account_clicked = True
                    self.report("account_clicked", attempt=self.account_attempts)
                return
