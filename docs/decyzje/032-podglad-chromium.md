# 032 — Podgląd Chromium

**Status.** Przyjęta i wdrożona w źródłach po 1.11.2. Uzupełnia [decyzję 025](025-wspolna-sesja-servicenow.md).

**Decyzja.** `Ctrl+Shift+F11` w oknie monitora przełącza widoczność roboczego Chromium na czas diagnostyki. Stan trwa do ponownego użycia skrótu lub zamknięcia monitora.

**Powód.** Obserwacja odczytu wymaga ciągłej widoczności tej samej karty także przy zmianie zadania i odzyskiwaniu sesji.

**Realizacja.** `BrowserOptions` przechowuje stan w pamięci procesu. `BrowserRuntime` odczytuje go na wątku sesji i uzgadnia widoczność oraz renderowanie. Potwierdzenie sesji przy włączonym podglądzie dopuszcza widoczne Chromium. Diagnostyka zapisuje zmianę trybu, aktywność oraz oczekiwaną i zaobserwowaną widoczność.

**Ograniczenia.** Skrót działa w głównym oknie monitora. Wyłączenie podglądu przywraca zwykłą politykę, w tym widoczne okno potrzebne do ręcznego logowania i potwierdzenia zapisu hasła.
