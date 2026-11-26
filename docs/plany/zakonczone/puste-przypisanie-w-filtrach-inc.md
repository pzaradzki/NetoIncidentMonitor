# Puste przypisanie w filtrach INC

**Status.** Zakończono. Wdrożono w źródłach oraz potwierdzono odczyt na ADEO i w regresji Windows.

## Cel i zakres

W filtrach incydentów użytkownik może skopiować adres listy, w której wybrał **„Przypisany do → jest”** i zostawił wartość pustą. Po rozkodowaniu adresu ten warunek ma postać `assigned_to=`. W wersji 1.13.3 walidacja kończy taki odczyt błędem przed wysłaniem żądania o rekordy. Celem poprawki jest odczyt nieprzypisanych incydentów przez wykonanie odpowiednika `assigned_toISEMPTY`, czyli **„Przypisany do → Jest puste”**. [Walidator](../../../neto_incident_monitor/filter_conditions.py) · [Operatory ServiceNow](https://www.servicenow.com/docs/r/platform-user-interface/r_OpAvailableFiltersQueries.html)

Reguła dotyczy wyłącznie zwykłego pola `assigned_to` w tabeli `incident`, operatora `=` i dosłownie pustego argumentu. Rozpoznaje cały warunek, również jako człon gałęzi z `OR` lub `NQ`. Pozostałe pola, tabele katalogowe, ścieżki odwołań, warianty z `GOTO`, inne operatory oraz zapis z wartością, spacją albo słowem „puste” podlegają dotychczasowym regułom.

Zapisany adres, jego oryginalne `sysparm_query`, podgląd definicji i tożsamość filtra zachowują dotychczasową postać. Spójniki, pozycja warunku, kolejność sortowania i sposób rozstrzygania remisów zachowują dotychczasowe znaczenie. [Kontrakt odczytu list](../../kontrakty/kontrakt-odczytu-list.md) · [Decyzja 038](../../decyzje/038-walidacja-warunkow-filtrow.md)

## 1. Potwierdzenie równoważności na ADEO

- [x] Ustalić odczytową próbę dla tabeli INC na zwykłym koncie. Ograniczyć ją do znanego, stabilnego zbioru zawierającego przypisane i nieprzypisane incydenty, które spełniają pozostałe warunki. Przy zapytaniu z `NQ` zawęzić każdą gałąź.
- [x] Otworzyć osobną sesję testową dla użytkownika. Logowanie wykona użytkownik. Przeprowadzić próby w tej samej zalogowanej sesji, bez ingerencji w uruchomiony monitoring, zapisywania filtrów i uruchamiania powiadomień.
- [x] Porównać klasyczną listę otwartą z oryginalnym warunkiem z klasyczną listą używającą **Jest puste**. Zachować te same pozostałe warunki i widok. Odczytać także próbkę kontrolną bez warunku przypisania i potwierdzić, że przypisany incydent jest widoczny w kontroli oraz odpada w obu wariantach.
- [x] Porównać oba wyniki z kompletnym wynikiem Table API dla `assigned_toISEMPTY`. Użyć właściwej tabeli i odczytać tylko pola potrzebne do rozstrzygnięcia. Porównać zbiory identyfikatorów w pamięci oraz sprawdzić nieprzypisanie rekordów w podstawowej próbce, kompletność i brak duplikatów. Powtórzyć na reprezentatywnym zapytaniu z `OR` oraz na ograniczonej próbce z `NQ`, uwzględniając zakres każdej gałęzi. [Kontrakt list](../../kontrakty/kontrakt-odczytu-list.md) · [Table API](https://www.servicenow.com/docs/r/api-reference/rest-apis/c_TableAPI.html)
- [x] Zapisać tylko liczebności, wynik porównania i ograniczenia prób. Rozpocząć implementację po potwierdzeniu tych samych zestawów rekordów na próbce z przypadkiem pasującym i wykluczonym. Jeżeli zmienność listy, uprawnienia lub różnica wyników uniemożliwią rozstrzygnięcie, zapisać przyczynę i pozostawić zakres otwarty.

**Wynik etapu.** W osobnym Chromium na zwykłym koncie ADEO próbka kontrolna objęła trzy przypisane i trzy nieprzypisane incydenty. Oba warianty klasycznej listy i Table API dla `ISEMPTY` zwróciły te same zestawy. Próba podstawowa zwróciła trzy nieprzypisane incydenty, a próby `OR` i `NQ` po cztery rekordy z zachowaniem zakresów gałęzi. Sprawdzono liczniki stron, unikalność oraz stabilność kontroli. Porównania wykonano w pamięci.

## 2. Jedna reguła przygotowania zapytania

- [x] W istniejącym `api_query()` przygotować warunek dla potwierdzonej tabeli. Rozpoznać dokładne człony `assigned_to=`, `ORassigned_to=` i `NQassigned_to=` po rozkodowaniu. Zamienić w nich tylko treść warunku, zachowując prefiks i pozycję. Stosować dopasowanie całego członu, żeby zapis występujący w wartości innego pola pozostał tekstem. [Przygotowanie zapytania](../../../neto_incident_monitor/filter_definition.py)
- [x] Przekazać ustaloną tabelę z odczytu adresu i metadanych do `parse_query()`. Przeprowadzić przez tę samą regułę pierwsze rozpoznanie adresu, walidację pól i przyjęcie istniejącej definicji. Walidator nadal sprawdza metadane pola, spójniki, pozostałe operatory i kompletność warunków. [Parser](../../../neto_incident_monitor/filter_conditions.py) · [Metadane i zapis definicji](../../../neto_incident_monitor/filter_metadata.py)
- [x] Użyć tej samej wersji przygotowania w `read_filter_records()`, przed przekazaniem `sysparm_query` do transportu. Zachować kontrolę sortowania, według której czytnik sprawdza ścisłą kolejność identyfikatorów. Gotowa definicja nadal korzysta z jednego zwykłego żądania po rekordy, z dotychczasowymi budżetami i zasadami ponowień. [Czytnik Table API](../../../neto_incident_monitor/filter_api.py)
- [x] Zachować surowe zapytanie w definicji i w **Konfiguruj → Zapytanie**. Powiązanie z adresem, kontem i instancją filtra nadal opiera się na zapisanych metadanych. Sprawdzić pełny adres, adres opakowany nawigatorem oraz rozwijany skrót.
- [x] Sprawdzić aktualizację dla filtra zapisanego przed poprawką. Jego adres może zostać odczytany w dotychczasowej konfiguracji. Filtr wcześniej wyłączony po błędach pozostaje w tym stanie do zmiany przełącznika przez użytkownika. **Ponów odczyt** pozwala sprawdzić poprawioną interpretację osobno. [Wyłączenie po błędach](../../decyzje/048-wylaczenie-filtra-po-bledach.md)

## 3. Diagnostyka i bezpieczeństwo wyniku

- [x] Przekazać z tego samego przebiegu przygotowania zapytania bezpieczną liczbę zastosowanych zamian. Dołączyć ją do istniejącej diagnostyki odczytu z identyfikatorem próby. Zanotować zastosowanie reguły także wtedy, gdy następująca po niej próba transportu kończy się błędem. Rozszerzyć listę dozwolonych pól o użyty licznik. [Diagnostyka](../../../neto_incident_monitor/login_diagnostics.py)
- [x] Potwierdzić, że log zawiera etap, wynik i korelację, a szczegóły filtra pozostają poza logami. Test z syntetycznymi znacznikami ma sprawdzić ochronę adresu, wartości warunków, zapytania, identyfikatorów zgłoszeń i danych sesji.
- [x] Zachować reguły zatwierdzania wyniku. Pełny odczyt przechodzi przez istniejące kontrole liczebności, aktualności i zapisu. Próby niekompletne, anulowane lub odrzucone zachowują poprzedni wynik. Zastane zgłoszenia przy tworzeniu stanu początkowego zachowują dotychczasowe zasady powiadomień. [Kolejka i trwałość](../../kontrakty/kolejka-i-trwalosc.md) · [Zapis historii](../../../neto_incident_monitor/history.py)

## 4. Testy i odbiór

- [x] Sprawdzić syntetyczne warianty warunku na początku i wewnątrz zapytania, z `OR`, `NQ`, końcowym `EQ` i jawnym sortowaniem. W zapytaniu z osobną gałęzią bez warunku przypisania zachować jej zakres. Potwierdzić identyczny wynik przygotowania po ponownym zastosowaniu reguły.
- [x] Sprawdzić zachowanie poza zakresem. Uwzględnić `assigned_toISEMPTY`, wypełnione przypisanie, `assigned_to!=`, puste inne pole, zapis zawarty w wartości tekstowej oraz `assigned_to=` dla SCTASK, REQ i RITM. Zachować obecne komunikaty o odrzuconych warunkach. [Testy walidacji](../../../tests/test_filter_metadata.py)
- [x] Przechwycić parametry wysłane przez aplikacyjny czytnik na danych syntetycznych. Potwierdzić, że dokładnie poprawiony warunek trafia do Table API przy pierwszym i kolejnym odczycie. Sprawdzić zgodność podglądu i zapisanej definicji z oryginalnym adresem, także po ponownym uruchomieniu. [Testy odczytu](../../../tests/test_filter_api.py) · [Testy sesji](../../../tests/test_shared_session.py)
- [x] Sprawdzić pełny udany odczyt, potwierdzone zero, błąd odpowiedzi i anulowanie po przygotowaniu zapytania. Zweryfikować ochronę historii, stanu obecności, licznika i kolejki alertów oraz zachowanie ręcznego odczytu filtra wyłączonego z harmonogramu. [Testy trwałości](../../../tests/test_filter_atomic_commit.py) · [Testy stanu filtrów](../../../tests/test_filter_state.py)
- [x] W osobnym środowisku testowym na ADEO przejść ścieżkę aplikacji z oryginalnym adresem. Porównać jej pełny wynik z próbą z etapu 1, sprawdzić podgląd definicji i następny odczyt z zapisanych metadanych. Użyć testowego ustawienia bez wysyłki powiadomień.
- [x] Uruchomić testy zakresowe i pełną regresję Windows. Zapisać wyniki lokalne, ograniczenia i wynik ADEO z osobna. [Runner regresji](../../../tools/run_regression.py)

**Odbiór ADEO.** Na odizolowanych danych lokalnych dwa ręczne odczyty w aplikacji zwróciły po trzy oczekiwane incydenty z oryginalnego adresu. Rozpoznanie definicji odbyło się raz. Każdy odczyt wykonał jedno żądanie po rekordy z `assigned_toISEMPTY`. Zapis i podgląd zachowały źródłowy warunek, a testowy filtr pozostał poza harmonogramem. Kolejka alertów pozostała pusta. Podsumowanie w `build/assigned-empty-adeo/app-acceptance.json`.

**Odbiór lokalny.** Zaliczone 82 testy zakresowe. Osobna próba na danych syntetycznych użyła zapisu i ponownego wczytania konfiguracji w dwóch procesach. Po restarcie podgląd zawierał źródłowy warunek, a pojedynczy odczyt użył `assigned_toISEMPTY`. Raport zakresowy w `build/assigned-empty-adeo/tests-focused.json`.

**Regresja Windows.** Uruchomiono 598 testów. Jeden test widoczności i fokusu okna przeszedł w izolowanym powtórzeniu. Łącznie potwierdzono 596 zaliczeń. Dwa testy pominięto z powodu ograniczeń środowiska Windows dotyczących fokusu pasywnego i tworzenia dowiązań symbolicznych. Raporty w `build/assigned-empty-adeo/tests-regression.json` i `build/assigned-empty-adeo/tests-focus-retry.json`.

## 5. Dokumentacja i aktualizacja planu

- [x] Po odbiorze uzupełnić kontrakt odczytu list o potwierdzoną zamianę, zakres i rozróżnienie adresu źródłowego od zapytania wysyłanego do REST. Zapisać decyzję z uzasadnieniem i dowodem z ADEO. [Kontrakt list](../../kontrakty/kontrakt-odczytu-list.md) · [Decyzja 049](../../decyzje/049-puste-przypisanie-w-inc.md)
- [x] Zaznaczać checkbox po wykonaniu i weryfikacji kroku. Zapisać przy nim wynik lub odnośnik do dowodu. Po ukończeniu przenieść plan do `zakonczone/` i uaktualnić [indeks planów](../README.md).
