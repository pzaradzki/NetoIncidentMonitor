# Wydanie 1.9.4

Status: publikacja zakończona, 5 listopada 2026. Publikacja zlecona przez użytkownika.

- Zakres: odporne zatwierdzanie okresu i filtrów dashboardu, wcześniej sprawdzone w lokalnym EXE 1.9.3. Bez zmian schematów, selektorów i zależności.
- Numer 1.9.4; osobny build istniejącym PyInstallerem, zgodność 55 modułów, launchera i 4 zasobów ze źródłami, CRC ZIP-a i porównanie wszystkich 1441 plików po rozpakowaniu: OK. Offline smoke rozpakowanego EXE na izolowanych danych: OK, wersja 1.9.4 (build/release-1.9.4-package.json, build/release-1.9.4-smoke.json). Bez instalowania i aktualizowania pakietów.
- Składnia 137 plików, pip check i diff: OK. Pełna regresja: 523 testy, 521 zaliczonych, 2 pominięcia środowiskowe (fokus Windows i niedostępny symlink), bez błędów modułów lub callbacków Tk (build/release-1.9.4-tests.json).
- Opublikowano commit af12948c8c96f6b85ca24fd550293f42e866a6b3 i tag v1.9.4. Potwierdzono zgodność kodu EXE bezpośrednio ze źródłami tagu. Utworzono szkic, przesłano Neto.Incident.Monitor.zip i sprawdzono digest przed publikacją [wydania](https://github.com/pzaradzki/NetoIncidentMonitor/releases/tag/v1.9.4).
- Ponownie pobrano cały publiczny załącznik (269206868 bajtów); SHA-256 zgodne z lokalnym plikiem i digest GitHub. API potwierdziło latest, docelowy commit i opis UTF-8 (build/release-1.9.4-verified.json).
- Dwie prywatne notatki, logi i dane użytkownika poza Git i paczką. Po potwierdzeniu braku procesu monitora zaktualizowano dist/Neto Incident Monitor i dist/Neto Incident Monitor.zip. Poprzednie lokalne EXE i ZIP zachowano w build/release-1.9.4-previous. Końcowy offline smoke głównej paczki na osobnym LOCALAPPDATA: OK, wersja 1.9.4; EXE obecny po próbie (build/release-1.9.4-main-smoke.json).

[Opis wersji](../../wersje/v1.9.4.md). [Odbiór poprawki](zatwierdzanie-kontekstu-dashboardu.md).

Nowy ZIP: build/release-1.9.4-package.zip, 269206868 bajtów, SHA-256 `e7cfaec2f784c301c42f36640e05d137717f449caef9258b4b0a8bc736bc421e`. Kandydat: build/release-1.9.4-dist. Bez konfiguracji, historii, logów i profilu użytkownika.
