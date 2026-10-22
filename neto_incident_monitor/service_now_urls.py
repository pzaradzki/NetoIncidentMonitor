"""Explicit tenant policy shared by filters, record links and notifications."""
import re
from urllib.parse import urlparse, unquote

# This deployment monitors one tenant. Do not infer trust from a pasted URL.
TENANT_HOST = 'adeo.service-now.com'
LIST_PATHS = ('/incident_list.do', '/sc_task_list.do')


def trusted_url(value):
    try:
        if not isinstance(value, str) or len(value) > 32000:
            return False
        if any(ord(c) < 33 or ord(c) == 127 for c in value) or '\\' in value:
            return False
        parsed = urlparse(value)
        if any(ord(c) < 32 or ord(c) == 127 for c in unquote(value)):
            return False
        return (parsed.scheme == 'https' and parsed.hostname == TENANT_HOST
                and parsed.port in (None, 443) and parsed.username is None
                and parsed.password is None and '#' not in value and not parsed.params)
    except ValueError:
        return False


def normalize_list_url(value):
    message = 'Podaj adres listy INC lub SCTASK w https://adeo.service-now.com, bez danych logowania i fragmentu.'
    if not trusted_url(value):
        raise ValueError(message)
    parsed = urlparse(value)
    prefix = '/now/nav/ui/classic/params/target/'
    if parsed.path.startswith(prefix):
        target = urlparse(unquote(parsed.path[len(prefix):]))
        if (target.scheme or target.netloc or target.params or target.fragment
                or target.path not in ('incident_list.do', '/incident_list.do', 'sc_task_list.do', '/sc_task_list.do')):
            raise ValueError(message)
        parsed = parsed._replace(path='/' + target.path.lstrip('/'), query=target.query)
    if parsed.path not in LIST_PATHS or not trusted_url(parsed.geturl()):
        raise ValueError(message)
    return parsed._replace(netloc=TENANT_HOST).geturl()


def safe_record_url(value, number, list_url=None):
    """Invalid or mismatched links become plain record numbers, never URLs."""
    if not isinstance(number, str) or not re.fullmatch(r'(INC|SCTASK)\d{1,20}', number):
        return ''
    if not trusted_url(value):
        return ''
    parsed = urlparse(value)
    expected = '/sc_task.do' if number.startswith('SCTASK') else '/incident.do'
    if parsed.path != expected:
        return ''
    if list_url is not None:
        try:
            origin = urlparse(normalize_list_url(list_url))
        except ValueError:
            return ''
        if parsed.hostname != origin.hostname or (parsed.port or 443) != (origin.port or 443):
            return ''
    return parsed._replace(netloc=TENANT_HOST).geturl()
