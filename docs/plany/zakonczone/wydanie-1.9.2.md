# Wydanie 1.9.2

Status: publikacja zakończona, 5 listopada 2026. Publikacja zlecona przez użytkownika.

- [x] Potwierdzono najnowsze wydanie v1.9.1 i brak tagu v1.9.2. Odrzucony eksperyment usunięty; brak jego kodu w źródłach wydania.
- [x] Numer 1.9.2, opis stabilnej poprawki odzyskiwania dashboardu i ograniczeń.
- [x] Pełna regresja finalnego kodu: 505 testów, 503 zaliczone, 2 pominięcia środowiskowe (fokus Windows i symlink), bez niezaliczonych modułów i błędów callbacków Tk. Składnia 136 plików Python/PYW, pip check i diff: OK. Raport build/release-1.9.2-tests.json.
- [x] Kontrolowane źródła, testy i dokumentacja przygotowane do commita; dwie prywatne notatki i dane wykonawcze pozostają poza Git.
- [x] Kandydat EXE istniejącym PyInstallerem 6.22.3; zgodność 55 modułów, launchera i 4 zasobów ze źródłami. Brak eksperymentalnego runtime hooka i obserwatora.
- [x] Nowy ZIP: CRC i zgodność wszystkich 1441 plików po rozpakowaniu. Offline smoke UI/Chromium/walidacji startu na osobnych danych: OK, wersja 1.9.2. Bez konfiguracji, historii, logów i profilu użytkownika w paczce (build/release-1.9.2-smoke.json).
- [x] Opublikowano commit `66ff2822280d8f2296372d165a6f4ac00acdc1d2`, tag v1.9.2 oraz [wydanie](https://github.com/pzaradzki/NetoIncidentMonitor/releases/tag/v1.9.2) z załącznikiem Neto.Incident.Monitor.zip. Kod EXE porównano bezpośrednio ze źródłami tagu.
- [x] Pobrano cały publiczny załącznik: 269206684 bajty. SHA-256 zgodne z lokalnym ZIP-em i digest GitHub. API potwierdziło latest, stabilne wydanie, docelowy commit oraz opis UTF-8 (build/release-1.9.2-verified.json).
- [x] Główne lokalne EXE i ZIP zaktualizowano po potwierdzeniu braku uruchomionego monitora. Poprzednią paczkę i ZIP zachowano w build/release-1.9.2-previous. Ponowny offline smoke głównego EXE: OK, wersja 1.9.2; EXE obecny po próbie (build/release-1.9.2-main-smoke.json).

Bez zmian schematów, zależności i selektorów. Nie jest to nowy odbiór ServiceNow/SSO. Poprawka odzyskiwania była wcześniej sprawdzona lokalnie jako 1.9.1; niniejszy raport opisuje osobną publikację. [Opis wersji](../../wersje/v1.9.2.md).

Paczka Neto.Incident.Monitor.zip: 269206684 bajtów. SHA-256: `a2cdc494071398056c769dca2126ee1fbb42c733a134f3687b1d2ce307deb86b`. Kandydat lokalny: build/release-1.9.2-dist; nowy ZIP: build/release-1.9.2-package.zip.

Końcowe lokalne artefakty: dist/Neto Incident Monitor/ oraz dist/Neto Incident Monitor.zip. Dwie prywatne notatki pozostają poza commitem i wydaniem; gałąź safety/stable-2026-11-05 pozostaje zachowana.
