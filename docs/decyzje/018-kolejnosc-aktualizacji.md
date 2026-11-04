# 018 — Dashboard przed zagrożeniami SLA

4 listopada 2026. **Status: przyjęta; wdrożona w źródłach.** Zastępuje [002](002-harmonogram-zagrozen.md), zachowując zasady terminów i sekwencyjnej obsługi przeglądarki.

**Decyzja:** po logowaniu przy starcie oraz przy pełnej ręcznej aktualizacji kolejność to dashboard → incydenty zagrożone → filtry. Przy wyłączonym automatycznym dashboardzie start pomija tę sekcję. Samodzielne aktualizacje sekcji nie wymuszają dashboardu.

**Powód:** użytkownik chce otrzymać dashboard jako pierwszy wynik wspólnej aktualizacji. Zmiana priorytetu nie wymaga drugiego workera, nowego harmonogramu ani interakcji z DOM.

**Realizacja:** istniejący worker obsługuje żądanie dashboardu przed kolejką zagrożeń. Kontroluje Stop przed przejściem dalej. Zachowane są rezerwacja całego zakresu, blokada okresu dashboardu i odzyskiwanie sesji. Obsłużony błąd sekcji dashboardu pozwala kontynuować pozostałe odczyty. Komunikaty startowe uwzględniają rzeczywiście zakolejkowany dashboard.

Następny odczyt zagrożeń nadal przypada 60 s od końca próby, również błędnej. Ręczne odświeżenie ustawia ten sam termin. Zaległe sprawdzenia odbywają się po dashboardzie i między całymi filtrami, bez kolejki zaległych minut. Obsłużenie oczekującego żądania zagrożeń ustawia nowy termin, co zapobiega natychmiastowej powtórce.

**Ograniczenia:** pierwszy odczyt zagrożeń może czekać na dashboard, jego ponowienia i ręczne logowanie. 60 s jest najwcześniejszym terminem, nie gwarancją częstotliwości. Bez zmian selektorów, danych, zależności, wersji i publikacji. Wyniki w [zakończonym planie](../plany/zakonczone/kolejnosc-aktualizacji.md): 493 testy (2 pominięcia), osobny build i próba offline; bez nowego odbioru rzeczywistego ServiceNow.
