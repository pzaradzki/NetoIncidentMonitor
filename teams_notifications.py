"""Teams webhook transport: bounded background delivery, no URL in errors."""
import html
import json
import queue
import threading
from urllib.parse import urlparse, parse_qs
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError


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
        lines.append(f"{number} - {location} - {description}")
    return title, "\n".join(lines)


def payload(title, message):
    text = html.escape(title) + "<br>" + html.escape(message).replace("\n", "<br>")
    return {"type": "message", "text": text, "attachments": [{
        "contentType": "application/vnd.microsoft.card.adaptive", "contentUrl": None,
        "content": {"type": "AdaptiveCard", "version": "1.2", "body": [
            {"type": "TextBlock", "text": title, "weight": "Bolder", "wrap": True},
            {"type": "TextBlock", "text": message, "wrap": True}]}}]}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def send(webhook, title, message):
    webhook = validate_webhook(webhook)
    request = Request(webhook, data=json.dumps(payload(title, message)).encode("utf-8"),
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

    def submit(self, webhook, title, message, test=False):
        try:
            self.jobs.put_nowait((webhook, title, message, test))
        except queue.Full:
            self.events.put(("teams_result", (False, test, "Kolejka Teams jest pełna. Alerty zachowano w historii.")))

    def run(self):
        while True:
            webhook, title, message, test = self.jobs.get()
            try:
                send(webhook, title, message)
                result = True, test, "Teams przyjął żądanie. Sprawdź wiadomość i historię uruchomień przepływu."
            except Exception as error:
                result = False, test, str(error)
            self.events.put(("teams_result", result))
