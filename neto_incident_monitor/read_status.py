"""Presentation metadata for the last attempt and last complete read."""
from dataclasses import dataclass, replace
from datetime import datetime


@dataclass(frozen=True)
class ReadStatus:
    outcome: str = 'Brak odczytu'
    read_at: float | None = None
    duration_ms: int | None = None
    detail: str = ''
    title: str = ''
    action: str = ''
    warning: bool = False

    def accepted(self, read_at, duration_ms):
        return ReadStatus('Odczyt udany', read_at, duration_ms)

    def failed(self, detail='', *, partial=False, title='', action='retry', warning=False):
        return replace(self, outcome='Odczyt częściowy' if partial else 'Błąd odczytu', detail=detail,
                       title=title, action=action, warning=warning or partial)

    def labels(self):
        date = '—'
        if self.read_at is not None:
            timestamp = datetime.fromtimestamp(self.read_at)
            date = timestamp.strftime('%H:%M:%S' if timestamp.date() == datetime.now().date() else '%d.%m.%Y %H:%M:%S')
        duration = f'{self.duration_ms / 1000:.2f}'.replace('.', ',') + ' s' if self.duration_ms is not None else '—'
        return self.outcome, date, duration
