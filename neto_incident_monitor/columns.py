"""Column definitions shared by the picker, tables and browser reader."""
FIELDS = [
    ("number", "Numer", 125), ("short_description", "Krótki opis", 340),
    ("priority", "Priorytet", 150), ("location", "Lokalizacja", 200),
    ("created", "Utworzono", 165), ("updated", "Zaktualizowano", 165),
    ("state", "Stan", 150), ("caller", "Zgłaszający", 180),
    ("assigned_to", "Przypisane do", 180), ("description", "Opis", 420),
    ("parent_incident", "Incydent nadrzędny", 160),
    ("configuration_item", "Objęty element konfiguracji", 230),
    ("assignment_group", "Grupa przypisania", 200),
    ("filter", "Monitorowany filtr", 155), ("read", "Przeczytanie", 145),
    ("time", "Wykryto (historia)", 150),
]
DEFAULT = ["number", "state", "caller", "priority", "short_description", "location", "created"]
DATA_FIELDS = [key for key, _, _ in FIELDS if key not in ("number", "filter", "read", "time")]
LOCAL = {"number", "filter", "read", "time"}
