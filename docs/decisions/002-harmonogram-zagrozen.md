# 002 — Harmonogram zagrożeń SLA

Data: 1 listopada 2026. **Status: przyjęta; stosowana.**

**Decyzja:** pierwsze sprawdzenie zagrożeń odbywa się po logowaniu, przed dashboardem i filtrami. Następny termin wyznaczamy zegarem monotonicznym na 60 s od zakończenia próby, także błędnej. Ręczna aktualizacja ustawia ten sam termin od nowa.

**Powód:** zachowujemy sekwencyjną obsługę przeglądarki, a zagrożenia nie muszą czekać na cały długi zestaw filtrów.

**Realizacja:** `app.py: read_threatened_request/read_due_threatened`, punkty kontroli w `monitor`, testy `test_refresh_requests.py`. Zaległe sprawdzenie wtrącamy między całymi filtrami i po dashboardzie; nie przerywamy paginacji jednego filtra i nie odtwarzamy kolejki zaległych minut.

**Ograniczenie:** to termin najwcześniejszego następnego sprawdzenia, nie gwarancja stałej częstotliwości. Długi filtr, dashboard lub logowanie mogą go opóźnić. Równoległość pozostaje poza obecną decyzją.
