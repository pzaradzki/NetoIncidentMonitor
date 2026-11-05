# Synchronizacja statusów monitoringu i dashboardu

Status: zakończone w źródłach i głównej paczce lokalnej, 5 listopada 2026. Bez nowej publikacji.

- [x] Przed poprawką odtworzono niespójność odczyt → logowanie → ogólne Oczekiwanie → ponowienie SLA. Nowe regresje wykazały błędy starego kodu.
- [x] Wspólne mapowanie czytania, ponawiania, oczekiwania na logowanie i błędu dla SLA, Wstrzymanych i Wniosków. Opis korzysta z istniejącego formattera okresu i timestampu.
- [x] Guard aktywnego request_id oraz ochrona odebranego końcowego wyniku; zachowanie błędu częściowego po pracy kolejnej sekcji. Bez zmian faz i kontroli przycisków przez sam status sekcji.
- [x] Diagnostyka zmian UI: allowlistowane kody, korelacja, deduplikacja i brak syntetycznych sekretów.
- [x] Zakresowe testy: 40 testów w pierwszym przebiegu, po rozszerzeniu 12/12 testów aktywności. Liczby częściowo się nakładają. Scenariusze obejmują Stop, restart, sukces, błąd, wynik częściowy, stare/zakończone żądania, cache, timestamp, okres, tooltip i stan przycisków.
- [x] Pełna regresja: 514 testów, 512 zaliczonych i 2 pominięcia środowiskowe (fokus Windows i symlink), bez niezaliczonych modułów i błędów callbacków. Składnia 136 plików Python/PYW, pip check i diff: OK (build/status-ui-full.json).
- [x] Osobny kandydat PyInstaller 6.22.3; zgodność 55 modułów, launchera i 4 zasobów ze źródłami. Offline smoke UI/Chromium/walidacji startu na tymczasowym LOCALAPPDATA: OK, wersja 1.9.2 (build/status-ui-candidate-smoke.json).
- [x] Potwierdzono brak procesu monitora i podmieniono główną paczkę dist/Neto Incident Monitor. Poprzednia paczka zachowana w build/status-ui-previous/Neto Incident Monitor. SHA-256 przeniesionego EXE zgodne z kandydatem; ponowny offline smoke OK, EXE obecny po próbie (build/status-ui-main-smoke.json). Sprawdzono niezmienność HEAD, tagu v1.9.2 i SHA-256 ZIP-a wydania.

Wersja pozostaje 1.9.2. Tag, ZIP lokalnego wydania oraz publikacja GitHub nie są zmieniane. Dwie prywatne notatki pozostają nietknięte. Bez zmian selektorów lub interakcji ServiceNow; nie wykonywano nowego odbioru rzeczywistego ServiceNow/SSO. [Decyzja 020](../../decyzje/020-spojne-statusy-dashboardu.md).

Późniejsze zlecenie publikacji tej poprawki opisuje [wydanie 1.9.3](wydanie-1.9.3.md). Wzmianki o braku publikacji powyżej dotyczą pierwotnego etapu lokalnego.
