"""Google Chat incoming webhooks with bounded, rate-limited background delivery."""
import json
import queue
import re
import threading
import time
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse, quote
from urllib.request import Request, build_opener

from neto_incident_monitor.teams_notifications import NoRedirect
from neto_incident_monitor.service_now_urls import safe_record_url
from neto_incident_monitor.notification_text import plain_text


class DeliveryError(RuntimeError):
    """A message constructed locally, safe to display without webhook credentials."""


def validate_webhook(value):
    message = 'Podaj pełny adres HTTPS webhooka Google Chat z parametrami key i token.'
    try:
        value = value.strip()
        parsed = urlparse(value)
        query = parse_qs(parsed.query)
        if (parsed.scheme != 'https' or parsed.hostname != 'chat.googleapis.com'
                or parsed.port not in (None, 443) or parsed.username or parsed.password or parsed.fragment
                or not re.fullmatch(r'/v1/spaces/[A-Za-z0-9_-]+/messages', parsed.path)
                or any(len(query.get(key, [])) != 1 or not query[key][0].strip() for key in ('key', 'token'))):
            raise ValueError(message)
        return value
    except (ValueError, AttributeError):
        raise ValueError(message) from None


def plain(value):
    # Prevent record descriptions from introducing Google Chat mentions or link markup.
    return plain_text(value).translate(str.maketrans({'<': '‹', '>': '›', '*': '＊', '_': '＿', '~': '～', '`': 'ˋ'}))


def payloads(title, message, links=None):
    from neto_incident_monitor.notification_templates import linked_parts, slices
    header = plain(title[:300])
    current = header
    result = []
    for line in (part for line in message.split('\n') for part in slices(line, 3000)):
        parts = []
        for value, url in linked_parts(line, links):
            if url and len(url) <= 4000:
                url = quote(url, safe=":/?#[]@!$&'()*+,;=%~-._")
                parts.append(f'<{url}|{value}>' if len(url) <= 8000 else plain(value))
            else:
                parts.append(plain(value))
        text = ''.join(parts)
        if len(text.encode('utf-8')) > 26000:
            text = text.encode('utf-8')[:26000].decode('utf-8', errors='ignore') + '…'
        candidate = current + ('\n' if current else '') + text
        if (len(candidate.encode('utf-8')) > 28000
                or len(json.dumps({'text': candidate}, ensure_ascii=False).encode('utf-8')) > 30000):
            result.append({'text': current})
            current = header
        current += ('\n' if current else '') + text
    result.append({'text': current})
    return result


def send(webhook, content):
    webhook = validate_webhook(webhook)
    request = Request(webhook, data=json.dumps(content, ensure_ascii=False).encode('utf-8'),
                      headers={'Content-Type': 'application/json; charset=utf-8'}, method='POST')
    try:
        with build_opener(NoRedirect).open(request, timeout=15) as response:
            if not 200 <= response.status < 300:
                raise DeliveryError('Google Chat nie przyjął wiadomości.')
    except HTTPError as error:
        raise DeliveryError(f'Google Chat odrzucił wiadomość (HTTP {error.code}). Sprawdź webhook i uprawnienia.') from None
    except Exception:
        raise DeliveryError('Nie udało się wysłać wiadomości do Google Chat. Sprawdź połączenie i webhook.') from None


class Sender:
    def __init__(self, events):
        self.events = events
        self.jobs = queue.Queue(maxsize=20)
        self.next_send = 0
        threading.Thread(target=self.run, daemon=True).start()

    def submit(self, webhook, title, message, test=False, links=None):
        try:
            self.jobs.put_nowait((webhook, title, message, test, links))
        except queue.Full:
            self.events.put(('google_chat_result', (False, test, 'Kolejka Google Chat jest pełna. Zgłoszenia pozostają w historii.')))

    def deliver(self, job):
        webhook, title, message, test, links = job
        try:
            for content in payloads(title, message, links):
                delay = self.next_send - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
                try:
                    send(webhook, content)
                finally:
                    self.next_send = time.monotonic() + 1.1
            result = True, test, 'Google Chat przyjął wiadomość. Sprawdź wybraną przestrzeń.'
        except DeliveryError as error:
            result = False, test, str(error)
        except Exception:
            result = False, test, 'Nie udało się wysłać powiadomienia do Google Chat. Sprawdź webhook, połączenie i uprawnienia.'
        self.events.put(('google_chat_result', result))

    def run(self):
        while True:
            self.deliver(self.jobs.get())
