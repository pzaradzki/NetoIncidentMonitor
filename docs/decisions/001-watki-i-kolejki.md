# 001 — Właściciele wątków i komunikacja

Data: 1 listopada 2026. **Status: przyjęta; stosowana.**

**Decyzja:** jeden worker monitoringu wykonuje operacje Playwright. Główny wątek obsługuje Tk. Żądania, wyniki i polecenia okna przekazujemy kolejkami; zadania pomocnicze nie sięgają samodzielnie do Tk ani obiektów Playwright.

**Powód:** unikamy kolizji nawigacji, utraty kontekstu strony i błędów wątków interfejsu. Równoległość wysyłek lub przygotowania tabel nie oznacza równoległego sterowania przeglądarką.

**Realizacja:** `app.py: monitor/drain`, `browser_policy.py: BrowserRuntime`, `table_loading.py`, kolejki nadawców Teams/Chat. Stan aktualizacji współdzieli `monitoring.py: RefreshControl`.

**Ograniczenie:** długi odczyt blokuje inne operacje przeglądarki. Wielokartowa równoległość wymaga osobnej decyzji i projektu sesji, nawigacji oraz anulowania; nie dodajemy jej jako lokalnej optymalizacji.
