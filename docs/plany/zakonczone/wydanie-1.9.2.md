# Wydanie 1.9.2

Status: przygotowanie, 5 listopada 2026. Publikacja zlecona przez użytkownika.

- [x] Potwierdzono najnowsze wydanie v1.9.1 i brak tagu v1.9.2. Odrzucony eksperyment usunięty; brak jego kodu w źródłach wydania.
- [x] Numer 1.9.2, opis stabilnej poprawki odzyskiwania dashboardu i ograniczeń.
- [x] Pełna regresja finalnego kodu: 505 testów, 503 zaliczone, 2 pominięcia środowiskowe (fokus Windows i symlink), bez niezaliczonych modułów i błędów callbacków Tk. Składnia 136 plików Python/PYW, pip check i diff: OK. Raport build/release-1.9.2-tests.json.
- [x] Kontrolowane źródła, testy i dokumentacja przygotowane do commita; dwie prywatne notatki i dane wykonawcze pozostają poza Git.
- [x] Kandydat EXE istniejącym PyInstallerem 6.22.3; zgodność 55 modułów, launchera i 4 zasobów ze źródłami. Brak eksperymentalnego runtime hooka i obserwatora.
- [x] Nowy ZIP: CRC i zgodność wszystkich 1441 plików po rozpakowaniu. Offline smoke UI/Chromium/walidacji startu na osobnych danych: OK, wersja 1.9.2. Bez konfiguracji, historii, logów i profilu użytkownika w paczce (build/release-1.9.2-smoke.json).
- [ ] Publikacja commita, tagu v1.9.2 oraz wydania z załącznikiem Neto.Incident.Monitor.zip.
- [ ] Pobranie publicznego załącznika i weryfikacja SHA-256 oraz latest.
- [ ] Aktualizacja głównej lokalnej paczki i ZIP-a po weryfikacji, bez zatrzymywania działającego monitora.

Bez zmian schematów, zależności i selektorów. Nie jest to nowy odbiór ServiceNow/SSO. Poprawka odzyskiwania była wcześniej sprawdzona lokalnie jako 1.9.1; niniejszy raport opisuje osobną publikację. [Opis wersji](../../wersje/v1.9.2.md).

Paczka Neto.Incident.Monitor.zip: 269206684 bajtów. SHA-256: `a2cdc494071398056c769dca2126ee1fbb42c733a134f3687b1d2ce307deb86b`. Kandydat lokalny: build/release-1.9.2-dist; nowy ZIP: build/release-1.9.2-package.zip.
