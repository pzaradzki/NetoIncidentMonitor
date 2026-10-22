"""Teams webhook transport: bounded background delivery, no URL in errors."""
import html
import json
import queue
import threading
from urllib.parse import urlparse, parse_qs
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError
from urllib.parse import quote
from neto_incident_monitor.service_now_urls import safe_record_url
from neto_incident_monitor.notification_text import card_text, plain_text


def validate_webhook(value):
    value = value.strip()
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.fragment
            or parsed.port not in (None, 443)
            or not any(host.endswith(suffix) for suffix in (".api.powerplatform.com", ".logic.azure.com"))
            or not parsed.path.endswith("/invoke") or not parse_qs(parsed.query).get("sig")):
        raise ValueError("Podaj pełny adres HTTPS webhooka wygenerowany przez Power Automate.")
    return value


def incident_text(incidents):
    unique = {incident["number"]: incident for incident in incidents}
    if not unique:
        return None
    title = ("Nowe incydent" if len(unique) == 1
             else f"Nowe incydenty: {len(unique)}")
    lines = []
    for number, incident in sorted(unique.items()):
        location = (incident.get("location") or "").strip()
        if location in ("", "—", "-"):
            location = "Brak lokalizacji"
        description = incident.get("short_description") or incident.get("summary") or "Brak opisu"
        location = " ".join(location.split())
        description = " ".join(description.split()) or "Brak opisu"
        if number.startswith("SCTASK"):
            requested_for = " ".join((incident.get("requested_for") or "").split())
            if requested_for in ("", "—", "-"):
                requested_for = "Brak osoby wnioskującej"
            lines.append(f"{number} - {description} - {requested_for}")
        else:
            lines.append(f"{number} - {location} - {description}")
    return title, "\n".join(lines)


def payload(title, message, links=None):
    from neto_incident_monitor.notification_templates import linked_parts
    lines, card_lines = [], []
    for line in message.split("\n"):
        rich, card = [], []
        for text, url in linked_parts(line, links):
            if url:
                url = quote(url, safe=":/?#@!$&'*,;=%~-._")
                rich.append(f'<a href="{html.escape(url, quote=True)}">{text}</a>')
                card.append(f'[{text}]({url})')
            else:
                rich.append(html.escape(plain_text(text)))
                card.append(card_text(text))
        lines.append(''.join(rich))
        card_lines.append(''.join(card))
    title = ' '.join(title.splitlines())
    text = (html.escape(plain_text(title)) + "<br>" if title else '') + "<br>".join(lines)
    return {"type": "message", "text": text, "attachments": [{
        "contentType": "application/vnd.microsoft.card.adaptive", "contentUrl": None,
        "content": {"type": "AdaptiveCard", "version": "1.2", "body": [
            *([{"type": "TextBlock", "text": card_text(title), "weight": "Bolder", "wrap": True}] if title else []),
            {"type": "TextBlock", "text": "\n".join(card_lines), "wrap": True}]}}]}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def message_chunks(title, message, links=None):
    """Bound the actual escaped payload, retaining every character."""
    from neto_incident_monitor.notification_templates import slices
    current = ''
    for line in message.splitlines(keepends=True):
        for part in slices(line, 1000):
            candidate = current + part
            if current and len(json.dumps(payload(title, candidate, links)).encode('utf-8')) > 25000:
                yield current
                current = ''
            current += part
    if current or not message:
        yield current


def send(webhook, title, message, links=None):
    webhook = validate_webhook(webhook)
    request = Request(webhook, data=json.dumps(payload(title, message, links)).encode("utf-8"),
                      headers={"Content-Type": "application/json"}, method="POST")
    try:
        with build_opener(NoRedirect).open(request, timeout=15) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError("Teams nie przyjął powiadomienia.")
    except HTTPError as error:
        raise RuntimeError(f"Teams odrzucił żądanie (HTTP {error.code}). Sprawdź przepływ i uprawnienia.") from None
    except Exception:
        raise RuntimeError("Nie udało się połączyć z Teams. Sprawdź sieć i adres webhooka.") from None


class Sender:
    def __init__(self, events):
        self.events = events
        self.jobs = queue.Queue(maxsize=20)
        threading.Thread(target=self.run, daemon=True).start()

    def submit(self, webhook, title, message, test=False, links=None):
        try:
            self.jobs.put_nowait((webhook, title, message, test, links))
        except queue.Full:
            self.events.put(("teams_result", (False, test, "Kolejka Teams jest pełna. Alerty zachowano w historii.")))

    def run(self):
        while True:
            webhook, title, message, test, links = self.jobs.get()
            try:
                for chunk in message_chunks(title, message, links):
                    send(webhook, title, chunk, links)
                result = True, test, "Teams przyjął żądanie. Sprawdź wiadomość i historię uruchomień przepływu."
            except Exception as error:
                result = False, test, str(error)
            self.events.put(("teams_result", result))
