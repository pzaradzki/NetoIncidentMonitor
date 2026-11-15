"""Control flow shared by ServiceNow readers and the browser session."""


class AuthenticationRequired(Exception):
    """The operation needs a confirmed ServiceNow session."""


class Cancelled(Exception):
    """The operation was stopped or invalidated."""
