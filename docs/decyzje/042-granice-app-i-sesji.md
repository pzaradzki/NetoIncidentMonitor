# 042 — Granice App i wspólnej sesji

**Status.** Podział wdrożono w źródłach i zweryfikowano na Windows oraz na ADEO w zakresie logowania. Uzupełnia decyzje o [właścicielach wątków](001-watki-i-kolejki.md) i [wspólnej sesji](025-wspolna-sesja-servicenow.md). [Zakończony plan](../plany/zakonczone/zaleznosci-od-app.md)

**Decyzja.** `App` składa interfejs, sesję i zapis. Moduły konfiguracji, logowania i odczytów mogą być importowane bez `App` i Tk. `config_io` zarządza ścieżką konfiguracji, odczytem starszych ustawień oraz zapisem z użyciem dotychczasowej ochrony DPAPI. Ładowanie i wstępna walidacja mają zachować dotychczasowe reguły zapisu. [Konfiguracja](../../neto_incident_monitor/config_io.py) · [Kontrola startowa](../../neto_incident_monitor/data_validation.py)

**Uzasadnienie.** Moduły wykonujące pracę w tle pobierały funkcje i typy błędów z modułu interfejsu. Oddzielne moduły dają możliwość testowania konfiguracji, logowania i czytników bez ładowania Tk, a położenie funkcji wskazuje właściciela operacji.

**Realizacja.** `SharedSession` wywołuje `browser_login` i `browser_actions` na swoim wątku. Ten sam wątek czeka na przygotowanie żądania analitycznego przez Tk i ustala termin kolejnego odczytu zagrożeń. `dashboard_read` i `threatened_read` otrzymują żądanie oraz zależności potrzebne do odczytu, odzyskania sesji i zapisu. Wyniki przechodzą przez istniejące zdarzenia do `dashboard_ui` i `threatened_ui`. [Sesja](../../neto_incident_monitor/shared_session.py) · [Dashboard](../../neto_incident_monitor/dashboard_read.py) · [Zagrożenia](../../neto_incident_monitor/threatened_read.py)

**Granice.** Przygotowanie żądania, zmiany kontrolek i przyjęcie zdarzeń należą do Tk. Odczyty, budżety i kooperacyjne anulowanie należą do właściciela karty. `History` nadal zatwierdza dane i alerty w tej samej transakcji. [Kontrakt kolejki](../kontrakty/kolejka-i-trwalosc.md)
