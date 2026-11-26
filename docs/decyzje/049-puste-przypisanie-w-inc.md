# 049 — Puste przypisanie w filtrach INC

**Status.** Przyjęta i wdrożona w źródłach.

**Decyzja.** Przygotowanie do walidacji i Table API w tabeli `incident` interpretuje `assigned_to=` jako `assigned_toISEMPTY`. Zachowuje pozycję warunku i prefiks `OR` lub `NQ`. Zapis adresu źródłowego, tożsamość filtra i podgląd korzystają z oryginalnej definicji.

**Powód.** Klasyczna lista ADEO zwróciła te same identyfikatory dla obu zapisów. Wyniki potwierdziło Table API z `ISEMPTY`. Próba podstawowa objęła trzy nieprzypisane incydenty. Próby z `OR` i `NQ` zwróciły po cztery rekordy i zachowały zakres poszczególnych gałęzi. Próba kontrolna zawierała także trzy przypisane incydenty.

**Realizacja.** Wspólne `api_query()` dopasowuje cały warunek. Walidator i czytnik otrzymują tabelę z definicji filtra. `filter_query_prepared` zapisuje bezpieczny licznik `assigned_to_empty_aliases` i korelację odczytu. [Przygotowanie zapytania](../../neto_incident_monitor/filter_definition.py) · [Kontrakt list](../kontrakty/kontrakt-odczytu-list.md)

**Ograniczenia.** Reguła obejmuje dokładnie pusty argument `=` w polu `assigned_to` tabeli INC. Inne operatory, wartości, ścieżki pól, warianty z `GOTO` i tabele podlegają dotychczasowej walidacji. Powrót wcześniej wyłączonego filtra do harmonogramu wymaga użycia przełącznika. [Decyzja 048](048-wylaczenie-filtra-po-bledach.md)
