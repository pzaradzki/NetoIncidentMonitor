# 006 — Wspólny odczyt i niezależna aktualność sekcji

Data: 1 listopada 2026. **Status: przyjęta; wdrożona w źródłach, bez nowego EXE.**

**Decyzja:** SLA, Wstrzymane, Wnioski i zagrożenia korzystają z tego samego obserwatora pojedynczego widżetu i jednego właściciela ponowień. Sekcja zwraca kompletny, zweryfikowany zestaw albo błąd. Nie scala się starych i nowych kafelków wewnątrz sekcji.

**Powód:** różne czytniki i zagnieżdżone ponowienia utrudniały diagnozę, a wspólny czas cache pozornie odmładzał nieodczytane sekcje. To realizacja zasady [003](003-poprawnosc-i-aktualnosc.md), nie jej zastąpienie.

**Realizacja:** `dashboard_context.py` potwierdza cel; `dashboard.py` wiąże tytuł, lokalny loader i liczbę oraz obsługuje leniwe renderowanie. `section_runner.py` zarządza najwyżej dwiema próbami we wspólnym aktywnym budżecie 60 s; pierwsza ma najwyżej 39 s. Czas ręcznego logowania jest rozliczany osobno. `read_budget.py` przekazuje pozostały czas do oczekiwań. Odzyskanie odtwarza cały kontekst sekcji.

Cache schematu 2 zapisuje osobno kompletny wynik, kontekst, czas sukcesu i ostatnią próbę każdej sekcji. Migracja nie wymyśla brakujących czasów historycznych. Błąd sekcji zachowuje jej ostatni sukces i pozwala sprawdzić pozostałe sekcje. WJRUW powstaje z jednego kompletu SLA. Zagrożenia zachowują dotychczasowy alarm i harmonogram; nie otrzymują trwałego cache ani powiadomień.

**Ograniczenia:** to walidacja UI, nie transakcyjny odczyt bazy. Nie gwarantuje dostępności ServiceNow ani stałego czasu odpowiedzi. Budżet jest kooperacyjny; nie zabija procesu przeglądarki zablokowanego poza obsługą Playwright. Zmiany definicji widżetów wymagają ponownej inspekcji. Wyniki odbioru i pozostałe sprawdzenia zawiera [raport](../verification/dashboard-stabilization-verification.md).
