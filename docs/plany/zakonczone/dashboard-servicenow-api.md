# Migracja dashboardu i Incydentów zagrożonych SLA do ServiceNow REST API

**Status planu** — zakończony w źródłach po odbiorze użytkownika i regresji Windows. Usunięto stary czytnik oraz zakres renderowania analityki. [Kontrakt](../../kontrakty/kontrakt-odczytu-dashboardu.md)

Po zakończonej serii zmian zaktualizuj checkboxy i dopisz wynik testów, pomiary i otwarte kwestie. Etap zaznacz po wykonaniu wszystkich jego kroków. Porównanie rzeczywistych wyników z ServiceNow wykonuje użytkownik. Wyniki tego odbioru zapisuj osobno od testów lokalnych.

## Stan wdrożenia do odbioru

- W źródłach podłączono oba widoki do REST na karcie `SharedSession`. Dashboard zachowuje osobne migawki trzech sekcji. Zagrożenia liczą sześć kategorii oraz budują listę z jednej kompletnej odpowiedzi lub pełnego zestawu stron. Wycofano pasek postępu z interfejsu.
- Lokalny importer `tools/import_dashboard_api.py` zweryfikował warunki wszystkich 24 zapytań z arkusza i zapisał ignorowaną przez Git konfigurację `data/dashboard-api.json`. Instalacja EXE potrzebuje własnej kopii konfiguracji w lokalnym katalogu danych użytkownika.
- Odbiór użytkownika potwierdził zgodność obu widoków z ServiceNow, także dla niepustej listy zagrożeń. Lokalna diagnostyka odnotowała trzy kompletne odczyty dashboardu po osiem zapytań i jeden odczyt zagrożeń w jednym zapytaniu. Mediana czasu żądania w ms (maksimum): miesięczne SLA 250 (860), Wstrzymane 141 (172), Wnioski 125 (156), zagrożenia 125 (125, jedna próba). Czas kolejki poza pomiarem.
- Regresja końcowa na Windows i Chromium: 539 scenariuszy w 72 modułach, 538 zaliczonych, 1 pominięty z powodu braku możliwości utworzenia dowiązania symbolicznego. Dwa zaktualizowane moduły natywne ponowiono osobno (7/7). Test transportu REST w Chromium przeszedł na kontrolowanych odpowiedziach. Wielostronicowy wynik zagrożeń sprawdzono na danych syntetycznych.

## 1. Potwierdzenie definicji kafelków

- [x] **Zamknięto kontrakt danych dla 24 liczników oraz listy zagrożeń.**
  - [x] Sprawdzono lokalny arkusz `data/dashboard-api-kafelki.xlsx`, wiersze 9–26. Wszystkie mają pełne zapytanie w komórce i nieujemną liczbę całkowitą. Pola licznika, tabeli i zapytania nie zawierają formuł. Filtry SLA mają wspólny zakres października 2026, zestaw 104 lokalizacji i wspólną bazę warunków. Kafelki P1–P5 dodają odpowiedni priorytet, a „Przekroczone” dodatkowo `has_breached=true`. Suma P1–P5 w arkuszu wynosi 3225 i zgadza się z „Liczba zgłoszeń”.
  - [x] W 18 definicjach dashboardu występuje ten sam zestaw 46 osób, także w filtrach Wstrzymanych zapisanych przez alias pola. Użytkownik potwierdził usunięcie jednej osoby względem pilotażu. Bieżącą definicją jest zestaw 46 osób. W siedmiu wierszach L1 kolumna tabeli jest pusta. Źródła ustalono wcześniej z list — `incident_metric` dla Wstrzymanych i `sc_task` dla Wniosków.
  - [x] Wiersze 27–32 zawierają sześć unikalnych filtrów zagrożeń bez formuł. Wszystkie ograniczają zakres do tej samej grupy przypisania, aktywnych incydentów i aktywnych SLA w toku, z wykluczeniem wskazanych stanów i incydentów podrzędnych. P1–P5 to SLA rozwiązania z granicami 1, 2, 4, 24 i 48 godzin. Podjęcie to SLA odpowiedzi z granicą 5 minut, bez warunku priorytetu. Każdy filtr obejmuje również wcześniejsze terminy. Kolumna tabeli jest pusta. Pola filtrów wskazują na `task_sla`. W arkuszu dla wszystkich sześciu kafelków wpisano zero.
  - [x] Użytkownik potwierdził zgodność zbiorczej listy zagrożeń dla niepustego wyniku.
  - [x] W arkuszu zapytania Wstrzymanych różnią się wyłącznie granicą `mi_start` 7 lub 14 dni.
  - [x] Dla Wniosków importer porównał wspólną bazę, progi `sys_created_on` i oba progi Smartfonów z arkuszem.
  - [x] Zachowano oba warunki „Nieprzypisanych wniosków L1”. Importer i testy sprawdzają definicję z arkusza, a użytkownik potwierdził zgodność dashboardu.
  - [x] Zapisano i sprawdzono format v1 lokalnych parametrów zapytań. Importer porównał wszystkie warunki arkusza. Rzeczywiste listy i identyfikatory pozostają w lokalnych danych. Aplikacja składa zapytania z konfiguracji.

## 2. Najmniejsza potwierdzona liczba zapytań

- [x] **Wybrać wariant na podstawie zgodności i pomiaru obciążenia.**
  - [x] **SLA:** 1 agregacja grupowana po priorytecie i przekroczeniu. Podsumowanie, WJRUW oraz pusty okres sprawdzone syntetycznie. Zgodność dashboardu potwierdzona przez użytkownika.
  - [x] **Wstrzymane:** 2 agregacje `incident_metric` dla 7 i 14 dni. Obie zwróciły wyniki na koncie użytkownika.
  - [x] **Wnioski:** 5 agregacji `sc_task` z warunkami arkusza, w tym zmienna katalogowa i pusty przydział. Zachowano agregacje o potwierdzonej zgodności.
  - [x] **Zagrożenia:** 1 zapytanie `task_sla` dla pierwszej strony. Próg wyliczany względem wspólnego czasu UTC dla wszystkich stron. Granice i przekroczenia sprawdzono syntetycznie.
  - [x] **Dane zagrożeń:** liczniki liczą rekordy SLA, a lista grupuje je według INC. Zgodność niepustej listy potwierdzona przez użytkownika.
  - [x] **Paginacja zagrożeń:** stały filtr czasu i porządek po ID, limity stron i czasu, kontrola total i kolejnej strony. Testy sprawdzają wielostronicowy wynik, duplikat, ucięcie, pusty wynik i ponowny start po wygaśnięciu sesji.
  - [x] **Punkt odniesienia:** 8 agregacji dla dashboardu (1 SLA + 2 Wstrzymane + 5 Wnioski) oraz docelowo 1 żądanie na pierwszą stronę zagrożeń. Pełne **Sprawdź teraz** oznacza w tej konfiguracji 9 operacji ServiceNow w tych dwóch widokach przed ponowieniami. Większa lista zwiększa liczbę stron. Samodzielny odczyt zagrożeń nie pobiera dashboardu.
  - [x] Wybrano niezależne GET. Batch ograniczałby liczbę żądań HTTP przy tej samej liczbie operacji po stronie ServiceNow. Przy zaobserwowanych czasach osobną ocenę Batch odłożono.
  - [x] Liczbę żądań i zaobserwowane czasy zapisano w wynikach. Dla analityki przyjęto 8+1 wywołań bez Batch.

## 3. Odczyt, sesja i zapis

- [x] **Podłączyć wspólny transport API do osobnych operacji dashboardu i zagrożeń.**
  - [x] Przenieść sprawdzony transport z pilotażu do właściwej ścieżki. Wykonać żądania z tej samej karty i originu ServiceNow. Chromium dołącza cookies, a JavaScript przekazuje bieżący token sesji. Używać stałych tras i dozwolonych tabel. Kolejną stronę wyznaczać na podstawie zwalidowanych parametrów tej samej trasy. Jeśli dokument nie dostarcza tokenu, wrócić do potwierdzonej strony sesji SOW. Zapytania powstają z lokalnej konfiguracji.
  - [x] Związać zapisany okres SLA i dane konfiguracji z ID operacji. Zachować kolejkę `SharedSession` dla **Aktualizuj**, **Sprawdź teraz** i automatycznego startu, gdy jest włączony. Nie dublować oczekującej pracy. Zmiana wybranego miesiąca wpływa na kolejne żądanie; kontrolki pozostają zablokowane do końca pasującej operacji.
  - [x] Korzystać z istniejącej koordynacji i budżetu `section_runner`/`read_budget`. Zachować kolejność dashboard → zagrożenia → filtry, niezależne aktualizacje ręczne oraz termin zagrożeń 60 s od zakończenia próby ręcznej lub okresowej, również nieudanej. Zaległy odczyt wykonać raz.
  - [x] Działa wspólny budżet sekcji 60 s oraz limit pojedynczego żądania 5 s. Ponowienia i sesja mają jednego właściciela. HTTP 403 i 429 kończą próbę bez pętli logowania, a dla 401 i przekierowania działa odzyskanie sesji.
  - [x] Walidacja HTTP, schematu i kompletności poprzedza publikację migawki. Test sprawdza także poprawne HTTP 200 z terminem wykraczającym poza warunek zagrożeń. Błędy sekcji dashboardu zachowują jej poprzednią migawkę.
  - [x] Zachować kompatybilność `dashboard_cache.py`. Dane z API zapisywać transakcyjnie jako komplet sekcji. Cache po restarcie to ostatni zapisany odczyt i pokazuje datę oraz okres. Oddzielić czas każdej sekcji od czasu ostatniego pełnego sukcesu. Błąd dysku zgłosić osobno od wyniku odczytu; uwzględnić, że dane mogą pozostać tylko w pamięci.
  - [x] Grupować zagrożenia do jednego wiersza na INC, z kategoriami ze wszystkich jego SLA. Zachować rekord z najwcześniejszym terminem, remis według ID SLA, czas i procent z tej samej umowy, sortowanie i sprawdzony link do incydentu.
  - [x] Przy kompletnym wyniku użyć `History.commit_threatened` i istniejącej kolejki SQLite. Zachować historię, alert przy pierwszym wykryciu i po potwierdzonym powrocie. Poprawny pusty wynik potwierdza zniknięcie. Częściowy odczyt, błąd, anulowanie lub spóźnione zdarzenie zachowują dotychczasową obecność i historię. Sprawdzić zachowanie przy błędzie zapisu oraz brak odesłania wcześniejszych alertów po migracji i restarcie.
  - [x] Użyć obecnej diagnostyki. Rejestrować start, koniec, ID uruchomienia/operacji/próby, okres dla SLA, alias sekcji, oczekiwany i zaobserwowany stan, liczbę żądań, stron i rekordów, czasy kolejki i sieci, kody HTTP, przyczyny ponowień i anulowań oraz wynik zapisu migawki i alertów. Używać dozwolonych pól bez treści zapytań, odpowiedzi, danych rekordów i poświadczeń. Awaria zapisu logów nie przerywa odczytu. [Decyzja 004](../../decyzje/004-bezpieczna-diagnostyka.md)

## 4. Statusy i interfejs bez paska postępu

- [x] **Pokazać stan rzeczywisty bez procentów.**
  - [x] Pigułki obu widoków pokazują stan od kolejki po wynik, bez paska procentowego.

  | Zdarzenie | Pigułka sekcji | Kafelki i opis |
  | --- | --- | --- |
  | Brak odczytu i brak cache | Brak danych | Kreski do pierwszego wyniku. |
  | Odczyt z cache przy starcie lub wybrany inny miesiąc SLA | Dane nieaktualne | Zachowany prawdziwy okres i czas starej migawki. Zmiana miesiąca oznacza tylko sekcję SLA. |
  | Przyjęcie pracy / rozpoczęcie odczytu | W kolejce / Aktualizuje | Ostatnie poprawne wartości pozostają widoczne. Pigułka **Dashboard** na pasku bocznym wskazuje aktywny odczyt. |
  | Potwierdzona utrata sesji albo dozwolone ponowienie | Oczekuje na logowanie / Ponawia | Tylko sekcje bez rozstrzygnięcia. Pigułka sesji opisuje logowanie. |
  | Kompletna odpowiedź | Dane aktualne | Podmiana całej sekcji. SLA pokazuje okres, wszystkie sekcje mogą podać czas odczytu. |
  | Błąd / anulowanie | Błąd odczytu / powrót do stanu ostatniej migawki | Zachowane liczby. Przy błędzie krótka przyczyna, a po anulowaniu komunikat „Aktualizacja przerwana”. Brak migawki nadal oznacza kreski. |

  - [x] Rozdzielić stany ogólne od pigułek sekcji. Pasek boczny kończy animację natychmiast po zakończeniu żądania. Stopka: okres faktycznie wyświetlanego SLA • ostatnia pełna aktualizacja dashboardu • wynik (dane aktualne, aktualizacja częściowa, błąd lub przerwanie). Przy częściowym sukcesie wskazać nieodświeżone sekcje. Nie przypisywać daty ostatniego pełnego sukcesu do nowszej, częściowej migawki.
  - [x] W zagrożeniach użyć tej samej mapy stanów. Pigułka boczna **Aktualizuje** kończy się z własnym żądaniem. **Dane aktualne** oznaczają komplet liczników i zapis bieżącej listy. Jeżeli poprawne liczniki mają niezależne potwierdzenie, przy błędzie listy pokazać **Aktualizacja częściowa** i zachować poprzednią listę. Pełny pusty odczyt daje sześć zer i pustą zakładkę bieżącą. Po restarcie oznaczyć odtworzoną listę jako zapisaną. Stopka zagrożeń pokazuje czas i stan odczytu, bez okresu dashboardu.
  - [x] Zapewnić, że stare zdarzenia, Stop, zamknięcie i zmiana widoku nie pozostawiają blokady miesiąca, aktywnej animacji ani starego błędu po nowym sukcesie. Stop monitoringu zachowuje uzgodnione zachowanie żądań ręcznych, zamknięcie kończy całą pracę.

## 5. Przełączenie i usunięcie starego odczytu

- [x] **Przełączyć oba widoki w jednym zestawie zmian.**
  - [x] Podłączono oba wejścia koordynatora do API i sprawdzono je po usunięciu czytników DOM.
  - [x] Po odbiorze usunięto wybieranie okresu i kategorii, czytniki DOM i ich testy. Zachowano **Otwórz w SNOW**, logowanie oraz renderowanie importu.
  - [x] Po usunięciu starego kodu uruchomić ponownie testy obu widoków, sesji i zwykłych odczytów. Sprawdzić, czy żadne wejście do migracji nie wywołuje czytnika DOM.
  - [x] Usunięto pasek dashboardu, zdarzenia i moduł `dashboard_progress`. Kontrole okresu i statusy przeszły testy zakresowe po przestawieniu ich na API.
  - [x] Przyciskiem do API jest zwykłe odświeżenie. Usunięto zbędne mechanizmy i ich diagnostykę. Zaktualizowano architekturę, kontrakt, decyzje, instrukcję, plan diagnostyki i status dawnej paginacji DOM.

## 6. Odbiór

- [x] **Odebrać pełny odczyt oraz brak regresji.**
  - [x] Przetestować syntetycznie okres, progi L1, brak grupy, pusty okres, niepełną odpowiedź, ponowienie i anulowanie. Sprawdzić WJRUW, ochronę cache, pigułki, spóźnione zdarzenia, usunięcie procentów i bezpieczne logi, w tym awarię zapisu.
  - [x] Przetestować zagrożenia na pustej, niepustej i wielostronicowej odpowiedzi. Uwzględnić granice czasu, SLA po terminie, wiele SLA jednego INC, brak uprawnień, uszkodzone dane, duplikaty, zmiany w trakcie paginacji i utratę sesji. Sprawdzić historię i alerty dla obecności, zniknięcia i powrotu, przy awarii zapisu oraz restarcie.
  - [x] Regresja Windows i Chromium sprawdziła transport na jednej karcie, sesję, widoczność, Start/Stop, kolejkę, terminy, ręczne odświeżanie, import i ustawienia.
  - [x] Zapisano instrukcję uruchomienia oraz porównania okresów, liczników i listy zagrożeń w [dokumencie API](../../servicenow-api-sesja-przegladarki.md#uruchomienie-odczytów-api).
  - [x] Potwierdzenie użytkownika i testy lokalne zapisano osobno. Kompletność w rzeczywistej instancji potwierdzono dla niepustej listy, a przypadek wielostronicowy sprawdzono syntetycznie. Build i publikacja pozostają osobnym zadaniem.
