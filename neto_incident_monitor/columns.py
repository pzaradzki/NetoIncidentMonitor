"""Column definitions shared by the picker, tables and browser reader."""
from datetime import datetime


def age_minutes(created, number, now=None):
    """Whole elapsed minutes, using the local timezone of ServiceNow display."""
    if not str(number).startswith("INC") or not created:
        return "—"
    value = str(created).strip()
    parsed = None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        for pattern in ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M"):
            try:
                parsed = datetime.strptime(value, pattern)
                break
            except ValueError:
                pass
    if parsed is None:
        return "—"
    current = now or (datetime.now().astimezone() if parsed.tzinfo else datetime.now())
    if current.tzinfo and not parsed.tzinfo:
        current = current.astimezone().replace(tzinfo=None)
    elif parsed.tzinfo and not current.tzinfo:
        current = current.astimezone()
    return str(max(0, int((current - parsed).total_seconds() // 60)))


FIELDS = [
    ("number", "Numer", 125), ("short_description", "Krótki opis", 340),
    ("priority", "Priorytet", 150), ("location", "Lokalizacja", 200),
    ("created", "Utworzono", 165), ("updated", "Zaktualizowano", 165),
    ("age_minutes", "Wiek (min)", 185),
    ("state", "Stan", 150), ("caller", "Zgłaszający", 180),
    ("assigned_to", "Przypisane do", 180), ("description", "Opis", 420),
    ("parent_incident", "Incydent nadrzędny", 160),
    ("configuration_item", "Objęty element konfiguracji", 230),
    ("assignment_group", "Grupa przypisania", 200),
    ("requested_for", "Wnioskowane dla", 180),
    ("opened_by", "Otwarte przez", 180),
    ("time", "Wykryto (historia)", 150),
]
DEFAULT = ["number", "state", "caller", "priority", "short_description", "location", "created"]
DATA_FIELDS = [key for key, _, _ in FIELDS if key not in ("number", "time", "age_minutes")]
LOCAL = {"number", "time"}

LOCAL_FIELDS = [
    ('age_minutes', 'Wiek (min)', 185),
    ('time', 'Wykryto (historia)', 150),
]


class ColumnDiscovery(set):
    """Columns accepted only after a complete, consistent list traversal."""
    def __init__(self):
        super().__init__()
        self.schema = None

    def discover(self, schema):
        if self.schema is not None and {c['key']: c['label'] for c in self.schema} != {c['key']: c['label'] for c in schema}:
            from neto_incident_monitor.list_context import ListStateError
            raise ListStateError("schema_changed")
        if self.schema is None:
            self.schema = schema
