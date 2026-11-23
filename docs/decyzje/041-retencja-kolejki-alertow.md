# 041 — Retencja kolejki powiadomień

**Status.** Polityka 30 i 90 dni przyjęta i wdrożona w źródłach. [Wyniki weryfikacji](../plany/zakonczone/retencja-kolejki-powiadomien.md)

**Decyzja.** Pełną treść `accepted` i `cancelled` usuwamy wraz z wpisem po 30 dniach. W `uncertain` po 30 dniach zostają identyfikator alertu, stan, czas z podstawą naliczenia i kanał z listy dozwolonych wartości, jeśli był rozpoznany. Po 90 dniach usuwamy cały wpis. Okresy liczymy od przejścia do stanu końcowego, przy odzyskanym `sending` od przejścia do `uncertain`, a dla starszych wpisów bez daty od pierwszego rozpoznania przez retencję. `pending` i `sending` pozostają chronione. Odzyskany `uncertain` pozostaje poza automatyczną wysyłką. [Dotychczasowy kontrakt dostarczania](017-odpornosc-lokalnego-io.md)

**Powód.** Zakończone wpisy kopiują treść zgłoszeń, choć obsługa wysyłki pobiera tylko `pending`. Czas i identyfikator pozwalają skorelować niepewną wysyłkę z diagnostyką także po usunięciu jej treści. Dla starszego wpisu brak daty uzasadnia rozpoczęcie pełnego okresu od rozpoznania.

**Realizacja.** Czas UTC w sekundach i podstawa naliczenia trafiają do klucza `_retention` pola JSON `payload` w tej samej transakcji co zmiana stanu. Trzy kolumny `alert_outbox` i znaczenie `user_version` pozostają zgodne ze starszą paczką. Starsze wpisy otrzymują datę porcjami. Czyszczenie działa poza Tk na istniejącym wykonawcy zapisów historii i wybiera wyłącznie zakończone wpisy. [SQLite](../../neto_incident_monitor/history.py) · [Czyszczenie](../../neto_incident_monitor/alert_retention.py)

**Ograniczenia.** Usunięcie wpisów zwalnia miejsce do ponownego użycia wewnątrz SQLite. Rozmiar pliku zależy od pozostałych danych i sposobu zarządzania stronami. Możliwość otwarcia bazy w starszej wersji dotyczy zgodności zapisu. Usunięte dane pozostają usunięte po zmianie wersji aplikacji.
