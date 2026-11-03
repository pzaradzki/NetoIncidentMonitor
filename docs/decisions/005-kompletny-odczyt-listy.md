# 005 — Kompletny odczyt listy przed zapisem

Data: 1 listopada 2026. **Status: przyjęta; wdrożona w źródłach, odbiór nowego EXE pozostał.**

**Decyzja:** tabela, pager i metadane należą do jednego rozpoznanego kontekstu. Sprawdzamy gotowość strony, ciągłość zakresów, liczbę i unikalność rekordów oraz kompletność całego wyniku. Dopiero zakończony odczyt trafia do warstwy aktualizacji historii, obecności i powiadomień.

**Powód:** wyłączony przycisk „Dalej” lub powtarzające się numery nie dowodzą kompletności; częściowy zestaw nie może udawać pełnej listy.

**Realizacja:** `list_context.py`, `pagination.py: read_all`. Dopuszczamy jedno ponowienie całego odczytu od pierwszej strony z pustym buforem. Nie powtarzamy niepewnego kliknięcia „Dalej”. Stop, logowanie, zamknięcie przeglądarki i odmowa dużej listy mają odrębne ścieżki.

**Ograniczenie:** walidacja nie tworzy transakcyjnej kopii ServiceNow z jednej chwili. Niewykrywalne zmiany danych mogą pozostać. Liczby prób i limitów paginacji nie przenosimy automatycznie do dashboardu; jego kontrakt jest osobnym zadaniem.

Weryfikacja i granice gwarancji: [plan paginacji](../plans/completed/stabilizacja-paginacji.md).
