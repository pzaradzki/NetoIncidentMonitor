# 015 — Potwierdzona równoważność zapisu daty filtra

Data: 4 listopada 2026. Status: przyjęta, wdrożona w źródłach.

## Decyzja i powód

W porównaniach warunków listy normalizujemy kompletną wartość `javascript:gs.daysAgoStart(7)` do `javascript:gs.beginningOfLast7Days()` w warunku pola `sys_updated_on`. Na rzeczywistym filtrze „Dyżur 1L” ServiceNow zmieniało wyłącznie tę wartość między adresem żądania a atrybutem `query` tabeli. Oba warianty pokazały tę samą granicę daty. Dotychczasowa walidacja EXE 1.8.1 i źródeł odrzucała wynik jako `query_mismatch`; zarejestrowano 11 błędów w analizowanym uruchomieniu.

## Realizacja i ograniczenia

Wspólna funkcja `list_conditions` normalizuje zarówno warunek żądany, jak i tożsamość tabeli w paginacji. Zachowuje pole, operator, prefiksy i kolejność OR/NQ. Surowe zapytanie w `ListState` służy jedynie klasyfikacji zgodności i nie wpływa na równość stanu. Diagnostyka odróżnia `exact`, `known_alias` i `mismatch`, z kodem `last_7_days`, najwyżej raz dla każdej klasy na próbę. Nie zapisuje zapytań ani danych zgłoszeń.

Zachowujemy zasadę [005](005-kompletny-odczyt-listy.md): kompletność przed zapisem i odrzucenie nieznanych różnic. Nie zmieniamy URL ani tożsamości filtra i nie wykonujemy JavaScript z zapytania. Inne funkcje daty oraz inne pola wymagają osobnego potwierdzenia. [Kontrakt i odbiór](../kontrakty/kontrakt-odczytu-list.md).
