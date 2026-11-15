# 015 — Potwierdzona równoważność zapisu daty filtra

Data: 4 listopada 2026. Status: przyjęta, wdrożona w źródłach.

## Decyzja i powód

W porównaniach warunków listy normalizujemy kompletną wartość `javascript:gs.daysAgoStart(7)` do `javascript:gs.beginningOfLast7Days()` w warunku pola `sys_updated_on`. Na rzeczywistym filtrze „Dyżur 1L” ServiceNow zmieniało wyłącznie tę wartość między adresem żądania a atrybutem `query` tabeli. Oba warianty pokazały tę samą granicę daty. Dotychczasowa walidacja EXE 1.8.1 i źródeł odrzucała wynik jako `query_mismatch`; zarejestrowano 11 błędów w analizowanym uruchomieniu.

## Realizacja i ograniczenia

Wspólna funkcja `list_conditions` porównuje warunki adresu z metadanymi tabeli przy ustalaniu definicji REST. Zachowuje pole, operator, prefiksy i kolejność OR/NQ. Zdarzenie `filter_query_comparison` odróżnia `exact`, `known_alias` i `mismatch` oraz używa kodu `last_7_days` dla potwierdzonego aliasu. Diagnostyka pomija treść zapytań i zgłoszeń.

Zachowujemy zasadę [005](005-kompletny-odczyt-listy.md): kompletność przed zapisem i odrzucenie nieznanych różnic. Nie zmieniamy URL ani tożsamości filtra i nie wykonujemy JavaScript z zapytania. Inne funkcje daty oraz inne pola wymagają osobnego potwierdzenia. [Kontrakt i odbiór](../kontrakty/kontrakt-odczytu-list.md).
