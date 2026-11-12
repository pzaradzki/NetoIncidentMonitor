# Płynność listy wielu filtrów

6 listopada 2026. Poprawka źródeł po 1.9.4; bez budowania i publikacji EXE.

## Przyczyna i zmiana

`refresh_filters` usuwał wszystkie wiersze, po czym każdy insert rysował cały dotychczas dodany zestaw. Powstawał koszt kwadratowy i przejściowo pusty scrollregion resetujący pozycję. `toggle_filter` wykonywał dodatkowo dwa powiadomienia wyboru oraz powtórne odświeżenia widoków.

Pełne odświeżenie zastępuje teraz dane jednym zestawem bez pustego stanu. Przełączenie zachowuje istniejące wiersze i przewinięcie oraz powiadamia wybór raz, po unieważnieniu snapshotu. Współdzielone grafiki i etykiety eliminują ponowny rendering PIL oraz pomiary każdego napisu. Cache grafik ograniczony do ośmiu stanów przy jednej szerokości. Suwak ma odstęp 8 px.

Zachowano natychmiastowy zapis, rollback po odmowie zapisu, rewizje ochrony przed nieaktualnymi wynikami, walidację URL i budzenie harmonogramu. Brak zmian ServiceNow, schematów, zależności, diagnostyki odczytów i wersji. Nie dodajemy logowania każdego kliknięcia ani nazw i adresów filtrów.

## Weryfikacja

- Regresja 100 syntetycznych filtrów: cztery kolejne przełączenia (w tym ponowne tego samego filtra), poprawne stany i wybór, cztery zapisy, zachowane przewinięcie również po pełnym odświeżeniu, brak przebudowy danych podczas toggle, najwyżej osiem nowych grafik, odstęp suwaka.
- Testy zakresowe listy i widoków: 10/10 zaliczonych.
- Kontrola składni i pip check: zaliczone.
- Pełna regresja: 567 testów, 565 zaliczonych, 2 pominięcia środowiskowe, zero niezaliczonych modułów i błędów callbacków. Raport lokalny: `build/filter-list-full.json`. Końcowe testy zakresowe po doprecyzowaniu licznika zapisów: 10/10 (`build/filter-list-targeted.json`).
- Odmowa zapisu: stan filtra, rewizje, karta i przewinięcie zachowane. Licznik testu obejmuje wyłącznie zapis filtrów, niezależnie od timerów zapisu układu okna.
- `git diff --check`: zaliczony.

Testy dotyczą syntetycznego UI Tk. Nie stanowią pomiaru na rzeczywistym profilu użytkownika ani odbioru EXE. Wolny dysk lub zabezpieczenia systemowe nadal mogą wydłużać synchroniczny zapis konfiguracji; nie zmieniano transakcyjności zapisu na asynchroniczną.
