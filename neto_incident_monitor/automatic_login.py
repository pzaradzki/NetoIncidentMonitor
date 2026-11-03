"""One delivered submission, with bounded retries of undelivered ADEO clicks."""
import re
from time import monotonic
import logging
from urllib.parse import urlparse
from uuid import uuid4
from neto_incident_monitor.authentication import INPUT_GUARD, manual_handoff, document_generation
from neto_incident_monitor.login_diagnostics import error_facts, readiness_facts, safe_facts
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


ARM_DELIVERY = """(el, token) => {
    const guard = {token, activations: 0, active: true};
    window.__netoLoginDelivery = guard;
    const mark = event => {
        if (window.__netoLoginDelivery !== guard) return;
        if (guard.active && el.matches('.identifier-first__account-item') &&
            event.target.closest && event.target.closest('.identifier-first__remove-account')) {
            event.preventDefault();
            event.stopImmediatePropagation();
            return;
        }
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
        self.autofill_wait_expired = False
        self.submit_attempts = 0
        self.last_submit_attempt = None
        self.pending_delivery_token = None
        self.needs_user = False
        self.account_token = None
        self.account_delivery = None
        self.action_id = uuid4().hex

    def autofilled(self, control):
        """Boolean browser evidence only; selecting an account is not evidence."""
        return control.evaluate("el => el.matches(':-webkit-autofill')", timeout=500) is True

    def pause(self, reason):
        reason = safe_facts({'reason': reason}).get('reason', 'strona wymaga interwencji użytkownika lub zgłasza błąd')
        self.needs_user = True
        self.reason = reason
        self.report('login_user_required', reason=reason)

    def report(self, event, **facts):
        if self.diagnostics:
            try:
                self.diagnostics.record(event, action_id=self.action_id, document_generation=self.generation or 0, **facts)
            except Exception:
                pass  # Diagnostics never changes delivery or manual ownership.

    def block(self, reason):
        reason = safe_facts({'reason': reason}).get('reason', 'strona wymaga interwencji użytkownika lub zgłasza błąd')
        if not self.blocked:
            self.blocked = True
            self.needs_user = True
            self.reason = reason
            self.report("blocked", reason=reason)
            try:
                logging.getLogger("servicenow").warning("Automatyczne logowanie: %s; wymagane ręczne logowanie.", reason)
            except Exception:
                pass

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
        self.needs_user = self.blocked
        self.autofill_wait_expired = False
        if not self.enabled():
            return
        try:
            address = urlparse(page.url)
            supported = (address.scheme == 'https' and address.hostname == 'idpb2e.adeo.com'
                         and address.port in (None, 443) and address.username is None and address.password is None)
        except ValueError:
            supported = False
            address = urlparse('about:blank')
        if self.blocked or not supported:
            if not self.blocked and (self.submitted or self.pending_delivery_token is not None):
                # SSO can leave the IdP between the snapshot and this step.
                # A different address after delivery is not itself a handoff.
                self.submitted = True
                self.pending_delivery_token = None
                if self.submitted_at is None:
                    self.submitted_at = self.last_submit_attempt if self.last_submit_attempt is not None else monotonic()
                self.report('awaiting_submission_result')
                if monotonic() - self.submitted_at >= 30:
                    self.pause('brak zakończenia logowania przez 30 sekund po zatwierdzeniu')
            else:
                self.needs_user = True
            self.report("automatic_skipped", blocked=self.blocked, supported_origin=supported)
            return
        page.evaluate(INPUT_GUARD)
        if manual_handoff(page):
            self.block('wykryto ręczną obsługę formularza')
            return
        generation = document_generation(page)
        if self.generation is not None and generation != self.generation and self.form_token is not None:
            self.account_clicked = False
            if not self.submitted and self.pending_delivery_token is None:
                self.form_token = None
                self.prefill_since = None
        self.generation = generation
        interaction = page.evaluate("() => ({manual: window.__netoInputGuard.manual, submitted: window.__netoInputGuard.submitted})")
        if isinstance(interaction, dict) and (interaction.get('manual') or interaction.get('submitted')):
            self.block("wykryto ręczną obsługę formularza")
            return
        from neto_incident_monitor.login_observation import SIGNALS
        signals = page.evaluate(SIGNALS)
        if not isinstance(signals, dict):
            self.report('inspection_error')
            return
        if signals.get('intervention') is True:
            self.block("strona wymaga interwencji użytkownika lub zgłasza błąd")
            return
        if self.submitted:
            self.report("awaiting_submission_result")
            # Lack of progress is a safety bound, never evidence to resend.
            if self.submitted_at is not None and monotonic() - self.submitted_at >= 30:
                self.pause("brak zakończenia logowania przez 30 sekund po zatwierdzeniu")
            return
        passwords = page.locator('input[type="password"]:visible')
        if passwords.count() != 1:
            self.prefill_since = None
        if passwords.count() > 1:
            self.block('formularz zawiera wiele pól hasła')
            return
        if passwords.count() == 1:
            token = passwords.first.evaluate("el => { if (!el.__netoFormToken) el.__netoFormToken = crypto.randomUUID(); return el.__netoFormToken; }", timeout=1000)
            if isinstance(token, str):
                if self.form_token is not None and token != self.form_token:
                    self.account_clicked = False
                    if self.pending_delivery_token is not None:
                        if not self.previous_submission_pending(page, monotonic()):
                            self.pause('formularz logowania został zastąpiony')
                        return
                    self.prefill_since = None
                    self.report('login_form_changed')
                self.form_token = token
            ready = passwords.first.evaluate("el => !!el.value && !el.disabled", timeout=1000)
            if not ready:
                # Start the grace period on the usable field, not during SSO
                # navigation; selecting a saved account follows the same path.
                try:
                    if not passwords.first.is_editable(timeout=500):
                        self.prefill_since = None
                        return
                except PlaywrightTimeoutError:
                    return
                now = monotonic()
                if self.prefill_since is None:
                    self.prefill_since = now
                self.autofill_wait_expired = now - self.prefill_since >= 5
                self.needs_user = self.autofill_wait_expired
                self.report('waiting_password_fill')
                return
            self.prefill_since = None
            if not self.autofilled(passwords.first):
                self.pause("pole hasła nie zostało rozpoznane jako autouzupełnione")
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
                current = page.evaluate(SIGNALS)
                if (not isinstance(current, dict) or current.get('intervention') or
                        current.get('password_manual_edit') or not self.autofilled(passwords.first) or
                        not passwords.first.evaluate('el => !!el.value && !el.disabled && !el.readOnly', timeout=500)):
                    self.pause('strona wymaga interwencji użytkownika lub zgłasza błąd')
                    return
                token = uuid4().hex
                armed = buttons.first.evaluate(ARM_DELIVERY, token, timeout=1000) is True
                self.pending_delivery_token = None
                self.action_id = uuid4().hex
                self.submit_attempts += 1
                self.last_submit_attempt = now
                self.submitted = True  # Ambiguous outcomes must never be retried.
                self.submitted_at = now
                self.report("submit_attempt", attempt=self.submit_attempts, delivery_observer=armed, timeout_ms=500)
                try:
                    buttons.first.click(timeout=500, no_wait_after=True)
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
        if signals.get('welcome') is True:
            accounts = page.locator('#existingAccountsSelectionList .identifier-first__account-item:visible')
            if accounts.count():
                if accounts.count() != 1:
                    self.report("account_selection_ambiguous", account_count=accounts.count())
                    self.pause("wymagany wybór spośród wielu kont")
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
                    component = card.evaluate("el => { if (!el.__netoAccountToken) el.__netoAccountToken = crypto.randomUUID(); return el.__netoAccountToken; }")
                    if self.account_delivery is not None:
                        delivered = page.evaluate(READ_DELIVERY, self.account_delivery)
                        if component == self.account_token or delivered is None or delivered > 0:
                            self.report('account_awaiting_result')
                            if now - self.last_account_attempt >= 30:
                                self.pause('wybór konta nie spowodował przejścia do formularza')
                            return
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
                    if (document_generation(page) != self.generation or
                            card.evaluate('el => el.__netoAccountToken') != component):
                        self.report('login_form_changed')
                        return
                    self.account_attempts += 1
                    self.action_id = uuid4().hex
                    self.last_account_attempt = now
                    self.report("account_click_attempt", attempt=self.account_attempts)
                    if not self.enabled():
                        return
                    try:
                        card.evaluate("el => { window.__netoAccountClick = el; }")
                        self.account_token = component
                        self.account_delivery = uuid4().hex
                        card.evaluate(ARM_DELIVERY, self.account_delivery)
                        card.click(position=position, timeout=500, no_wait_after=True)
                    except Exception as error:
                        self.report("account_click_error", attempt=self.account_attempts, **error_facts(error))
                        # Unknown or observed selection must not be repeated.
                        try:
                            if page.evaluate(READ_DELIVERY, self.account_delivery) == 0:
                                self.account_delivery = None
                        except Exception:
                            pass
                        return
                    finally:
                        try:
                            page.evaluate("window.__netoAccountClick = false")
                            page.evaluate("token => { const g=window.__netoLoginDelivery; if(g && g.token===token) g.active=false; }", self.account_delivery)
                        except Exception:
                            pass
                    self.account_clicked = True
                    self.report("account_clicked", attempt=self.account_attempts)
                return
        if signals.get('identity_count', 0) and not signals.get('identity_locked'):
            self.pause('strona wymaga interwencji użytkownika lub zgłasza błąd')
        elif signals.get('document_ready') is True:
            self.pause('nierozpoznany krok logowania wymaga obsługi użytkownika')
