# Wydanie 1.9.4

Status: przygotowanie publikacji zleconej przez użytkownika, 5 listopada 2026.

- Zakres: odporne zatwierdzanie okresu i filtrów dashboardu, wcześniej sprawdzone w lokalnym EXE 1.9.3. Bez zmian schematów, selektorów i zależności.
- Numer 1.9.4; osobny build istniejącym PyInstallerem, zgodność 55 modułów, launchera i 4 zasobów ze źródłami, CRC ZIP-a i porównanie wszystkich 1441 plików po rozpakowaniu: OK. Offline smoke rozpakowanego EXE na izolowanych danych: OK, wersja 1.9.4 (build/release-1.9.4-package.json, build/release-1.9.4-smoke.json). Bez instalowania i aktualizowania pakietów.
- Składnia 137 plików, pip check i diff: OK. Pełna regresja: 523 testy, 521 zaliczonych, 2 pominięcia środowiskowe (fokus Windows i niedostępny symlink), bez błędów modułów lub callbacków Tk (build/release-1.9.4-tests.json).
- Publikacja: nowy commit i tag, szkic wydania, załącznik Neto.Incident.Monitor.zip, weryfikacja digest, publikacja i ponowne pobranie publicznego ZIP-a.
- Dwie prywatne notatki, logi i dane użytkownika poza Git i paczką. Poprzednie lokalne EXE i ZIP zostaną zachowane przed aktualizacją dist przy zamkniętym monitorze.

[Opis wersji](../../wersje/v1.9.4.md). [Odbiór poprawki](zatwierdzanie-kontekstu-dashboardu.md).

Nowy ZIP: build/release-1.9.4-package.zip, 269206868 bajtów, SHA-256 `e7cfaec2f784c301c42f36640e05d137717f449caef9258b4b0a8bc736bc421e`. Kandydat: build/release-1.9.4-dist. Bez konfiguracji, historii, logów i profilu użytkownika.
