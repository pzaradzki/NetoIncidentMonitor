# 020 — Spójna aktywność dashboardu

Data: 5 listopada 2026. **Status: przyjęta; wdrożona w źródłach i lokalnym EXE; testy automatyczne oraz offline zakończone.** Rozszerza [010](010-cykl-zycia-zadania-dashboardu.md).

**Decyzja:** zdarzenia sekcji bieżącego aktywnego żądania sterują wspólnie pigułką sekcji, główną aktywnością i opisem pod dashboardem. Obejmuje to czytanie, ponawianie, oczekiwanie na logowanie i błąd. Aktualizowanie aktywności używa istniejącego set_activity i nie zmienia fazy monitoringu, flag logowania ani dostępności przycisków.

**Powód:** po odzyskaniu logowania faza ustawiała główną pigułkę na Oczekiwanie. Obsługa sekcji nie uwzględniała Ponawianie odczytu, a opis pod dashboardem pozostawał tekstem z kolejkowania. UI prezentował sprzeczne etapy tej samej operacji.

**Realizacja:** panel dashboardu mapuje stan i sprawdza aktywne request_id; stare, zakończone i nieznane zdarzenia nie zmieniają UI. Odebrany wynik końcowy chroni końcowy opis przed późnym statusem sekcji. Zakończenie całego żądania zachowuje błąd także po aktywności późniejszej sekcji. Okres, timestamp, wartości i schemat cache pozostają bez zmian. Szczegółowy stan logowania zachowuje dotychczasowy mechanizm; rozpoczęcie ponowienia przywraca opis pracy.

**Diagnostyka:** dashboard_ui_state z request_id, aliasem section i stałym ui_state reading/retrying/waiting_login/error. Powtarzające się identyczne stany nie generują nowych wpisów. Bez wartości kafelków i danych formularzy.

**Ograniczenia:** wyłącznie lokalna poprawka prezentacji. Bez zmian logiki czytnika, sesji, limitów, harmonogramu, zależności i wersji 1.9.2; bez nowej publikacji GitHub. Testy syntetyczne i offline nie stanowią nowego odbioru ServiceNow/SSO. [Plan i odbiór](../plany/zakonczone/synchronizacja-statusow-dashboardu.md).

Późniejsze zlecenie publikacji tej poprawki opisuje [wydanie 1.9.3](../plany/zakonczone/wydanie-1.9.3.md). Wzmianki o braku publikacji powyżej dotyczą pierwotnego etapu lokalnego.
