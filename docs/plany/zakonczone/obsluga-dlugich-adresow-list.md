# Obsługa długich adresów list ServiceNow

4 listopada 2026. Zakończono wdrożenie, odbiór źródeł i lokalnego EXE. Nie publikowano wydania ani nowego ZIP.

- [x] Potwierdzić na stronie przyjęcie długiego adresu i zamianę na skrót `__tinyId__`.
- [x] Naprawić wspólną normalizację bez surowych spacji i utraty parametrów.
- [x] Zachować warunki, widok, skróty i tożsamość istniejących adresów bezpośrednich.
- [x] Odrzucać niebezpieczne cele i sprzeczne parametry przed zapisem.
- [x] Dodać bezpieczne kategorie diagnostyki, odporne na awarię logowania.
- [x] Sprawdzić dialog, zapis/restart, znaki zarezerwowane i Unicode oraz odrzucenie bez zmiany konfiguracji.
- [x] Uruchomić 66 testów zakresowych w Windows.
- [x] Dodać i odczytać rzeczywisty adres ze źródeł na osobnych danych.
- [x] Przebudować EXE, dodać adres w jego UI, zrestartować i potwierdzić pełne odczyty.
- [x] Uzupełnić kontrakt, decyzję, architekturę i instrukcję.

Dowody i ograniczenia: [kontrakt list](../../kontrakty/kontrakt-odczytu-list.md), [decyzja 016](../../decyzje/016-normalizacja-adresow-list.md).
