"""Explicit tenant policy shared by filters, record links and notifications."""
import re
from urllib.parse import urlparse, unquote

# This deployment monitors one tenant. Do not infer trust from a pasted URL.
TENANT_HOST = 'adeo.service-now.com'
RECORD_TABLES = {'INC': 'incident', 'SCTASK': 'sc_task', 'REQ': 'sc_request', 'RITM': 'sc_req_item'}
LIST_PATHS = tuple('/' + table + '_list.do' for table in RECORD_TABLES.values())


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


def is_short_url(value):
    return (trusted_url(value) and not urlparse(value).query and
            bool(re.fullmatch(r'/now/nav/ui/classic/__tinyId__/[A-Za-z0-9_-]{16,128}', urlparse(value).path)))


def normalize_list_url(value, allow_short=True):
    message = 'Podaj adres listy INC, SCTASK, REQ lub RITM w https://adeo.service-now.com, bez danych logowania i fragmentu.'
    if not trusted_url(value):
        raise ValueError(message)
    parsed = urlparse(value)
    if allow_short and is_short_url(value):
        return parsed._replace(netloc=TENANT_HOST).geturl()
    prefix = '/now/nav/ui/classic/params/target/'
    if parsed.path.startswith(prefix):
        target = urlparse(unquote(parsed.path[len(prefix):]))
        if (target.scheme or target.netloc or target.params or target.fragment
                or '/' + target.path.lstrip('/') not in LIST_PATHS):
            raise ValueError(message)
        parsed = parsed._replace(path='/' + target.path.lstrip('/'), query=target.query)
    if parsed.path not in LIST_PATHS or not trusted_url(parsed.geturl()):
        raise ValueError(message)
    return parsed._replace(netloc=TENANT_HOST).geturl()


def resolved_list_url(page, requested):
    """Resolve a short link from a loaded, visible list frame, never foreign content."""
    if not is_short_url(requested):
        return normalize_list_url(requested, allow_short=False)
    candidates = set()
    for frame in page.frames:
        try:
            direct = normalize_list_url(frame.url, allow_short=False)
        except ValueError:
            continue
        if frame.locator('body').is_visible():
            candidates.add(direct)
    if len(candidates) > 1:
        raise ValueError('Skrót wskazuje więcej niż jedną listę. Użyj bezpośredniego adresu filtra.')
    return next(iter(candidates), None)


def effective_list_url(url, filters):
    if is_short_url(url):
        for entry in filters:
            if entry.get('url') == url:
                try:
                    return normalize_list_url(entry.get('resolved_list_url'), allow_short=False)
                except ValueError:
                    break
    return url


def safe_record_url(value, number, list_url=None):
    """Invalid or mismatched links become plain record numbers, never URLs."""
    if not isinstance(number, str) or not re.fullmatch(r'(INC|SCTASK|REQ|RITM)\d{1,20}', number):
        return ''
    if not trusted_url(value):
        return ''
    parsed = urlparse(value)
    prefix = re.match(r'[A-Z]+', number)[0]
    expected = '/' + RECORD_TABLES[prefix] + '.do'
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
