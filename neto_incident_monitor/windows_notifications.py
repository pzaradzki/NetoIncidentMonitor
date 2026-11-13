"""Fit plain text in the Windows Shell notification buffers used by Plyer."""
from neto_incident_monitor.login_diagnostics import LoginDiagnostics


# NOTIFYICONDATAW reserves one UTF-16 unit in each buffer for the terminator.
TITLE_LIMIT = 63
MESSAGE_LIMIT = 255


def _fit(text, limit):
    encoded = text.encode('utf-16-le', errors='surrogatepass')
    units = len(encoded) // 2
    if units <= limit:
        return text, units
    # Keep room for the ellipsis and drop a trailing half of a surrogate pair.
    prefix = encoded[:2 * (limit - 1)].decode('utf-16-le', errors='ignore')
    return prefix.rstrip() + '…', units


def notify(title, message, *, timeout=10, diagnostics=None, action_id=None):
    from plyer import notification

    title, title_units = _fit(title, TITLE_LIMIT)
    message, message_units = _fit(message, MESSAGE_LIMIT)
    if title_units > TITLE_LIMIT or message_units > MESSAGE_LIMIT:
        diagnostics = diagnostics or LoginDiagnostics(source='monitor')
        diagnostics.record('windows_notification_truncated', channel='windows', action_id=action_id,
                           title_units=title_units, message_units=message_units,
                           title_limit=TITLE_LIMIT, message_limit=MESSAGE_LIMIT)
    notification.notify(title=title, message=message, app_name='Neto Incident Monitor', timeout=timeout)
