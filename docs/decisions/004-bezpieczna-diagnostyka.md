# 004 — Diagnostyka jako część funkcjonalności

Data: 1 listopada 2026. **Status: przyjęta zasada; pokrycie wymaga dalszego uzupełniania.**

**Decyzja:** nowe i zmieniane operacje mają wspólną diagnostykę etapów, czasu, wyniku, prób i przyczyn błędów. Zdarzenia wiążemy identyfikatorami technicznymi. Stosujemy listy dozwolonych pól i kategorii zamiast zapisywania dowolnego tekstu.

**Powód:** log powinien wyjaśniać przebieg bez ujawniania loginów, haseł, tokenów, cookies, adresów SSO, HTML lub treści zgłoszeń. Zapisujemy zmiany stanów i podsumowania, nie każde odpytywanie.

**Realizacja:** `login_diagnostics.py` — zdarzenia, filtrowanie i rotacja; `safe_logging.py` — bezpieczne lokalizacje wyjątków. Logi dopisujemy między uruchomieniami i przechowujemy poza paczką wydania. Awaria diagnostyki nie może przerywać funkcji.

**Dashboard i zagrożenia:** dodano korelację `run_id/read_id/request_id/section/attempt`, bezpieczny kontekst, czasy etapów, stany widżetów, przyczyny odzyskiwania i końcowej awarii, rozliczenie logowania, zapis cache oraz opóźnienie harmonogramu. Błąd przywrócenia polityki okna jest odrębny od wyniku odczytu. [Kontrakt](../contracts/dashboard-read-contract.md) i [raport odbioru](../verification/dashboard-stabilization-verification.md) opisują realizację oraz granice. Nie oznacza to automatycznie kompletnego pokrycia wszystkich starszych funkcji aplikacji.

Szczegółowe wymagania ochrony danych i testów: [AGENTS.md](../../AGENTS.md). Nie tworzymy osobnego loggera dla każdej nowej funkcji.
