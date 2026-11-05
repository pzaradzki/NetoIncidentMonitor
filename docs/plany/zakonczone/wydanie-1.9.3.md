# Wydanie 1.9.3

Status: publikacja zakończona, 5 listopada 2026. Publikacja zlecona przez użytkownika.

- [x] Potwierdzono najnowsze wydanie 1.9.2 i brak tagu v1.9.3. Zakres: stabilna synchronizacja statusów UI, bez odrzuconego eksperymentu.
- [x] Numer 1.9.3 i opis zmian oraz ograniczeń na wzór poprzedniego wydania.
- [x] Pełna regresja: 514 testów, 512 zaliczonych, 2 pominięcia środowiskowe (fokus Windows i symlink), bez niezaliczonych modułów i błędów callbacków Tk. Składnia 136 plików Python/PYW, pip check i diff OK (build/release-1.9.3-tests.json).
- [x] Kontrolowane źródła, testy i dokumentacja przygotowane do commita; dwie prywatne notatki i dane wykonawcze pozostają poza Git.
- [x] Kandydat EXE istniejącym PyInstallerem 6.22.3; zgodność 55 modułów, launchera i 4 zasobów ze źródłami, bez eksperymentalnego obserwatora i runtime hooka.
- [x] Nowy ZIP: CRC i zgodność wszystkich 1441 plików po rozpakowaniu. Offline smoke UI/Chromium/walidacji startu na osobnych danych: OK, wersja 1.9.3. Paczka bez konfiguracji, historii, logów i profilu użytkownika (build/release-1.9.3-smoke.json).
- [x] Opublikowano commit `b34a91aaf5b52f87325b59307a7932b36a5454ce`, tag v1.9.3 i [wydanie](https://github.com/pzaradzki/NetoIncidentMonitor/releases/tag/v1.9.3) z załącznikiem Neto.Incident.Monitor.zip. Kod EXE porównano bezpośrednio ze źródłami tagu.
- [x] Ponownie pobrano cały publiczny załącznik: 269208697 bajtów. SHA-256 zgodne z lokalnym ZIP-em i digest GitHub. API potwierdziło latest, docelowy commit i opis UTF-8 (build/release-1.9.3-verified.json).
- [x] Po potwierdzeniu braku procesu monitora zaktualizowano dist/Neto Incident Monitor i dist/Neto Incident Monitor.zip. Poprzednią paczkę i ZIP zachowano w build/release-1.9.3-previous. Ponowny offline smoke głównego EXE: OK, wersja 1.9.3; EXE obecny po próbie (build/release-1.9.3-main-smoke.json).

Bez zmian schematów, selektorów i zależności. Poprawka prezentacji była wcześniej sprawdzona lokalnie jako 1.9.2; niniejszy raport opisuje osobną publikację. Bez nowego odbioru rzeczywistego ServiceNow/SSO. [Opis wersji](../../wersje/v1.9.3.md).

Załącznik Neto.Incident.Monitor.zip: 269208697 bajtów, SHA-256 `f1a8b6852abdcbe8a88aa208e76f3c7b8e0b26d093f291a22dc65053b9845d60`. Kandydat: build/release-1.9.3-dist; nowy ZIP: build/release-1.9.3-package.zip.

Dwie lokalne prywatne notatki pozostają poza commitem i wydaniem. Gałąź safety/stable-2026-11-05 jest zachowana.
