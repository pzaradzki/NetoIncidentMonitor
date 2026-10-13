"""One attempt per login session, using only already filled ADEO login fields."""
import re
from time import monotonic
import logging
from urllib.parse import urlparse


class AutomaticLogin:
    def __init__(self):
        self.account_clicked = False
        self.submitted = False
        self.blocked = False
        self.account_attempts = 0
        self.last_account_attempt = None

    def step(self, page):
        host = urlparse(page.url).hostname or ""
        if self.blocked or self.submitted or not re.fullmatch(r"idp[a-z0-9-]*\.adeo\.com", host, re.I):
            return
        body = page.locator("body").inner_text(timeout=1000)
        if re.search(r"nieprawidł|błędne hasło|incorrect|invalid|authentication failed|"
                     r"kod weryfik|verification code|jednorazow|one.time|authenticator|"
                     r"zatwierdź|approve sign|captcha|zablokowan", body, re.I):
            self.blocked = True
            return
        passwords = page.locator('input[type="password"]:visible')
        if passwords.count() == 1:
            if not self.account_clicked:
                # A manually opened login form belongs to the user, even when
                # typing or autofill makes the password field nonempty.
                self.blocked = True
                return
            # Only inspect whether autofill is present. Never retrieve the password.
            ready = passwords.first.evaluate("el => !!el.value && !el.disabled")
            buttons = page.get_by_role("button", name=re.compile(r"^Zaloguj się$", re.I))
            adeo_button = page.locator('a#signOnButton:visible')
            if adeo_button.count() == 1:
                buttons = adeo_button
            if ready and buttons.count() == 1 and buttons.first.is_visible() and buttons.first.is_enabled():
                disabled = buttons.first.evaluate("el => el.getAttribute('aria-disabled') === 'true' || el.classList.contains('disabled')")
                if disabled:
                    return
                self.submitted = True  # Set before click: ambiguous failures must not retry.
                buttons.first.click(timeout=1500)
            return
        if re.search(r"WITAMY|WELCOME", body, re.I):
            accounts = page.locator('#existingAccountsSelectionList .identifier-first__account-item:visible')
            if accounts.count():
                if accounts.count() != 1:
                    return
                name = accounts.first.locator('.identifier-first__account-name')
                if name.count() == 1 and name.is_visible():
                    now = monotonic()
                    if self.last_account_attempt is not None and now - self.last_account_attempt < 5:
                        return
                    if self.account_attempts >= 3:
                        self.blocked = True
                        logging.getLogger("servicenow").warning("Automatyczny wybór konta nie przeszedł do formularza po trzech próbach; wymagane ręczne logowanie.")
                        return
                    self.account_attempts += 1
                    self.last_account_attempt = now
                    try:
                        name.click(timeout=1500)
                    except Exception:
                        # Selection is safe to retry on this exact welcome
                        # screen; never retry submitting the password form.
                        logging.getLogger("servicenow").warning("Nie udało się kliknąć zapamiętanego konta; wybór zostanie ponowiony.")
                        return
                    self.account_clicked = True
                return
