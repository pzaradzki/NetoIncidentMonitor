# 017 — Odporność lokalnego IO po audycie

4 listopada 2026. **Status: przyjęta; wdrożona w źródłach.** Uzupełnia 004 i 011, bez zmiany schematów i stanów outbox.

**Decyzja:** zwykły log i JSONL współdzielą handler odporny na błędy zapisu, rotacji, flush i zamknięcia. Otwarcie zwykłego logu jest opóźnione; ostrzeżenie omija uszkodzony handler oraz przekierowany stderr. Kolejna próba IO następuje po 30 s.

**Powód:** pełny dysk nie może powodować rekurencji w loggerze. Błąd zadania executora nie może pozostać nieobserwowany ani uruchamiać ponownego, niepewnego POST.

**Realizacja:** każde zlecenie dostarczenia alertów obserwuje Future. Wyłącznie odczyt kolejki ma do 3 prób, z oczekiwaniem 1/5 s przerywanym Stop. Błędy przejść stanów i wyniki wysyłki są odrębnie diagnozowane, z run/read/action, etapem i stałymi kategoriami. `sending` bez wyniku nadal przechodzi przy restarcie w `uncertain`.

Przed App, executorami, migracją konfiguracji i uzgodnieniem autostartu wykonywana jest walidacja odczytanych danych. Historia SQLite jest odczytywana w trybie tylko do odczytu. Błędne dane albo brak dostępu otwierają wyłącznie ekran informacyjny z zamknięciem; bez zastępowania konfiguracji/historii domyślnymi. Diagnostyka może zapisać stałą kategorię błędu. Niedostępny DPAPI zachowuje dotychczasową obsługę szyfrogramu.

Wiadomości obu kanałów dzielone są według końcowego JSON, bez obcinania treści i przecinania wygenerowanych linków. Cała partia jest sprawdzana przed transportem. Zbyt duży nagłówek Teams daje bezpieczny błąd przed POST.

**Ograniczenia:** brak retencji outbox i zmiany ścieżek źródłowych; brak gwarancji dostarczenia przez zewnętrzny kanał. Nie zmieniono DOM/selektorów ServiceNow ani produkcyjnej paczki EXE. Wyniki etapów i granice odbioru: [AUDIT.md](../../AUDIT.md).
