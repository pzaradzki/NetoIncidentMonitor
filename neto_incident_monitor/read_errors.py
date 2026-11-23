"""Control flow shared by ServiceNow readers and the browser session."""


class AuthenticationRequired(Exception):
    """The operation needs a confirmed ServiceNow session."""


class Cancelled(Exception):
    """The operation was stopped or invalidated."""


class LoginTargetUnavailable(RuntimeError):
    """Login finished but the requested list could not be verified."""


class LoginPopupClosed(LoginTargetUnavailable):
    """The user dismissed the authentication popup before session confirmation."""


class BrowserClosedError(RuntimeError):
    """The monitored browser was closed and can be started again."""
