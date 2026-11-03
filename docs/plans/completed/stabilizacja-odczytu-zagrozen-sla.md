# Plan stabilizacji odczytu incydentów zagrożonych SLA

> Zakończony plan i historia wdrożenia, nie bieżąca lista zadań. Aktualny status, lokalny build 1.8.0 i pozostałe sprawdzenia: [indeks planów](../README.md). Zapisy o braku EXE dotyczą ówczesnego etapu.

Data planu: **1 listopada 2026**. Wersja analizowana: **1.7.17**.

Status: **etapy A–E wdrożone w źródłach i objęte testami; nowy EXE odłożony na polecenie użytkownika**. Wyniki: [raport odbioru](../../verification/dashboard-stabilization-verification.md). Poniższa analiza opisuje stan historyczny, na podstawie którego przygotowano zmiany.

## Cel

Ograniczyć błędy odczytu zagrożeń powodowane przejściami po logowaniu, nawigacją i przebudową widżetów ServiceNow. Przejściowe problemy mają być naprawiane w ramach bieżącego sprawdzenia, a utrzymujące się awarie mają mieć jednoznaczną, bezpieczną diagnostykę.

Nie możemy zagwarantować dostępności ServiceNow lub sieci. Aplikacja ma rozpoznawać takie sytuacje, zachowywać ostatni poprawny wynik i kontynuować pracę po odzyskaniu dostępu.

## 1. Ustalenia z analizy

### Potwierdzone zdarzenie

Źródło: lokalny `login-diagnostics.jsonl` działającego EXE v1.7.17. Godziny poniżej są podane w strefie **Europe/Warsaw**, 1 listopada 2026.

| Czas | Zdarzenie |
| --- | --- |
| 10:16:01 | Potwierdzono sesję ServiceNow i rozpoczęto sprawdzanie zagrożeń. |
| 10:16:02 | Etap nawigacji zakończył się błędem po około 0,5 s. Nie rozpoczął się odczyt kafelków. |
| 10:17:02 | Harmonogram rozpoczął kolejną próbę. |
| 10:17:10 | Odczytano poprawnie wszystkie sześć liczników; próba trwała około 8,1 s. |

Wniosek: to zdarzenie nie było przekroczeniem limitu oczekiwania na liczniki. Samo zwiększenie tego limitu nie usuwa wykrytej luki.

### Hipoteza wymagająca potwierdzenia

Nawigacja do zagrożeń mogła nałożyć się na kończące się przekierowanie po SSO. Obecny zapis `Error / unexpected` nie pozwala odtworzyć dokładnej przyczyny wyjątku. Nie traktujemy tej hipotezy jako ustalonej przyczyny.

### Potwierdzone słabe punkty kodu

- Potwierdzenie sesji i gotowość dokumentu do kolejnej nawigacji nie są osobnymi etapami.
- Odczyt zagrożeń ponawia próbę po wygaśnięciu sesji, ale zwykły błąd nawigacji kończy bieżące sprawdzenie. Następna próba następuje dopiero z harmonogramu.
- Klasyfikacja części błędów nawigacji jest zbyt ogólna.
- Obserwowanie zdarzeń nawigacji i sieci podczas logowania kończy się przed odczytem zagrożeń.
- Limity poszczególnych operacji nie tworzą jednego budżetu całego odczytu i jego ponowień.

### Ponowna inspekcja rzeczywistej strony — 1 listopada 2026

Analizę wykonano w oddzielnej karcie Codex z istniejącą sesją. Nie sterowano Chromium działającej aplikacji. Nie kopiowano danych tabeli, list osób ani HTML do projektu.

| Obszar | Potwierdzona obserwacja | Wniosek |
| --- | --- | --- |
| Właściwa zakładka | Wybrana była `L1 – Incydenty zagrożone SLA`, w tym samym dashboardzie co SLA i pozostałe sekcje. | Potwierdzać tożsamość dashboardu i zakładki, nie tylko obecność sześciu tytułów. |
| Kafelki | Potwierdzono tytuły P1–P5 i Podjęcie, z progami 1 h, 2 h, 4 h, 1 dzień, 2 dni i 5 min oraz dopiskiem „po terminie”. Każdy miał jedną wartość w `now-score-basic .now-score-value`. Wystąpiły prawidłowe zera i wartości dodatnie. | Obecne dopasowanie kategorii i lokalny odczyt wartości odpowiadają zaobserwowanej strukturze. Tytuł zawiera także znaczenie progu, którego obecny kod nie waliduje. |
| Dodatkowa zawartość | Poniżej sześciu liczników jest osobny widżet tabeli zagrożeń. Nie znaleziono widocznych kontenerów `sn-component-filter` na tej zakładce. | Nie czekać na tabelę ani nie przenosić tu wymogu „Agent L1 — wszystko” z innych sekcji. Ponownie sprawdzić układ, jeżeli strona zostanie zmieniona. |
| Odświeżenie | Kontrolka `Odśwież bieżącą kartę` była dostępna. Bezpośrednio po kliknięciu widoczne były sześć komunikatów ładowania i brak wyrenderowanych wartości; następnie pojawiło się sześć liczników, bez tych komunikatów. | Rozróżniać ładowanie od zera i braku kafelka. Zbadać tę kontrolkę jako alternatywę pełnej nawigacji, zanim zmienimy istniejącą politykę odczytu. |
| Kliknięcie kafelka | Przyciski liczników nie miały zwykłego `href`. Kliknięcie P2 otworzyło listę `task_sla_list.do`; po zdekodowaniu nawigacji `sysparm_query` zgadzał się z filtrem P2 w `threatened_ui.py`. Wrócono do dashboardu. | Potwierdzono jeden z sześciu statycznych linków. Pozostałych pięciu nie uznawać za ponownie zweryfikowane. Nie dodawać kosztownego otwierania wszystkich list do cyklicznego odczytu. |

Kontrolka odświeżenia nie zmieniała dat ani kategorii. Nie edytowano rekordów, nie zmieniano konfiguracji dashboardu i nie wysyłano powiadomień.

**Granice inspekcji:** nie wymuszano wygaśnięcia sesji, awarii sieci ani zamknięcia działającej przeglądarki użytkownika. Nie przeprowadzono kontrolowanego porównania renderowania z przewijaniem i bez przewijania. Nie potwierdzono na rzeczywistym koncie sytuacji podmiany kafelka ani starej liczby utrzymującej się po odświeżeniu. To przypadki do testów, a nie odtworzone obecnie awarie.

### Uzupełnienie audytu kodu

- `read_threatened_dashboard` wykonuje pełną nawigację przy każdym sprawdzeniu, a potem korzysta z lokalnego obserwatora `_request_tile` współdzielonego z Wnioskami L1. To rozwiązanie jest już dokładniejsze od globalnego odczytu SLA/Wstrzymanych; nie trzeba projektować go od zera.
- Czytnik wymaga kompletu sześciu stabilnych wartości i nie przewija dodatkowej tabeli, gdy liczniki są gotowe. Przy brakach wywołuje jednak przygotowanie wszystkich widocznych kart. Budżet 45 s zaczyna się dopiero po nawigacji, która ma własny limit; operacje przygotowujące także nie dostają wspólnego pozostałego czasu.
- Rozpoznawanie nagłówka sprawdza kategorię i separator przed `<`, ale nie poprawność progu oraz znaczenia „po terminie”. Zmiana definicji kafelka może więc pozostawić poprawny technicznie odczyt z nieaktualnym opisem i linkiem w aplikacji.
- W trakcie zbierania i przed zwrotem wyniku nie ma osobnego potwierdzenia tożsamości właściwego dashboardu i wybranej zakładki. `check_session` potwierdza potrzebę logowania, nie pełny kontekst odczytu zagrożeń.
- Orkiestrator ponawia po odzyskaniu sesji, lecz zwykły błąd nawigacji lub inny wyjątek kończy sprawdzenie. Nie ma jeszcze wspólnej polityki ograniczonego odzyskiwania z czytnikiem.
- UI waliduje komplet sześciu nieujemnych liczb całkowitych, zachowuje wynik i czas ostatniego sukcesu po błędzie, nie wygasza aktywnego alarmu i ignoruje stare identyfikatory żądań. Te zabezpieczenia zachowujemy.
- Przed pierwszym poprawnym odczytem przycisk nie jest potwierdzony jako zdrowy. Po błędzie sześciu wcześniejszych zer również traci potwierdzenie „wszystko w porządku”. To właściwe rozróżnienie nieznanego stanu i poprawnego zera.
- Odczyty okresowe wykorzystują ponownie identyfikator ostatniego żądania UI. Do diagnostyki potrzebny jest dodatkowo unikalny identyfikator każdego faktycznego sprawdzenia. Konstruktor `LoginDiagnostics` zapisuje `source` i `section` w zdarzeniu startowym, ale nie dołącza ich automatycznie do każdego następnego zdarzenia; korelację zapewniają obecnie `session`/`trace`.
- Błąd przywracania polityki okna w `finally` może zostać zapisany jako `section_read_error` także po prawidłowym odczycie. Należy oddzielić błąd porządkowania stanu przeglądarki od błędu pobrania danych.
- Zagrożenia nie mają własnego trwałego cache między uruchomieniami. Nie dodajemy go przy okazji stabilizacji bez uzgodnienia; po restarcie nie wolno przedstawiać nieodczytanego stanu jako sześciu zer.

### Semantyka liczników i linków

Zaobserwowany cel P2 to rekordy SLA powiązane z incydentami, a nie zwykła tabela incydentów. Nie potwierdzono, czy konfiguracja raportów liczy unikalne incydenty czy rekordy SLA. Nie zakładamy też rozłączności Podjęcia i P1–P5. Alarm „występuje dodatnia wartość” jest możliwy bez sumowania kategorii, ale przyszłe powiadomienia nie powinny nazywać ich sumy liczbą unikalnych incydentów bez weryfikacji definicji. Sprawdzenie definicji raportu i pięciu pozostałych linków jest zadaniem odbiorczym; nie musi być wykonywane co minutę.

## 2. Zasady, które zachowujemy

- Pierwsze sprawdzenie zagrożeń następuje po logowaniu, przed dashboardem i filtrami.
- Kolejne sprawdzenie jest planowane 60 s od zakończenia poprzedniego, także nieudanego.
- Zaległe sprawdzenie może zostać wtrącone między całymi filtrami. Nie przerywamy paginacji pojedynczego filtra i nie kumulujemy zaległych uruchomień.
- Jeden wątek jest właścicielem operacji Playwright. Nie wprowadzamy teraz równoległości.
- Podczas odczytu dashboardu Chromium jest pokazane zgodnie z obecną polityką widoczności i fokusu.
- Błąd lub brak danych nigdy nie oznacza zera i nie wygasza istniejącego alarmu.
- Użytkownik może zatrzymać monitoring również podczas oczekiwania i ponawiania.
- Nie nadpisujemy formularza ręcznego logowania nawigacją ani dodatkowymi próbami wysłania danych.

## 3. Docelowy przebieg sprawdzenia

1. **Potwierdzenie sesji** — rozpoznanie zalogowania lub przekazanie sterowania obecnej obsłudze logowania.
2. **Gotowość po logowaniu** — potwierdzenie zakończenia nawigacji głównego dokumentu i jego gotowości, bez czekania na rekordy pierwszego filtra.
3. **Otwarcie zagrożeń** — nawigacja do właściwego dashboardu i zakładki.
4. **Weryfikacja celu** — sprawdzenie dashboardu, wybranej zakładki oraz braku strony logowania lub strony błędu.
5. **Przygotowanie widżetów** — uruchomienie leniwego renderowania potrzebnych kafelków.
6. **Odczyt i walidacja** — sześć jednoznacznych, gotowych liczników, poprawne liczby całkowite nieujemne i stabilny wynik.
7. **Publikacja wyniku w UI** — aktualizacja całego zestawu oraz znacznika ostatniego poprawnego odczytu.
8. **Zakończenie** — przywrócenie polityki widoczności i wyznaczenie kolejnego terminu od zakończenia operacji.

W razie błędu najpierw klasyfikujemy sytuację. Przejściowa awaria przechodzi do ograniczonego odzyskiwania; wygaśnięcie sesji do logowania; zatrzymanie do anulowania; zamknięcie przeglądarki do istniejącej obsługi jej odzyskiwania.

## 4. Kolejność prac

### Etap A — diagnostyka i odtworzenie problemu

- [x] Rozszerzyć bezpieczne kategorie błędów o przerwanie/anulowanie nawigacji, podmianę dokumentu i odłączenie ramki.
- [x] Rozróżnić zdarzenie odzyskiwalne od końcowego niepowodzenia odczytu.
- [x] Objąć obserwacją nawigację i odczyt zagrożeń; zawsze odłączać obserwatorów po zakończeniu próby.
- [x] Dodać identyfikator sprawdzenia, numer próby, etap, czas etapu i powód ponowienia.
- [x] Rozróżnić identyfikator uruchomienia aplikacji, żądania UI i pojedynczego sprawdzenia okresowego. Zapewnić trwały bezpieczny kontekst zdarzeń, również po rozpoczęciu sekcji.
- [x] Mierzyć opóźnienie względem zaplanowanego terminu oraz jego przyczynę: długi filtr, dashboard, logowanie lub odtwarzanie przeglądarki. Nie oznaczać takiego opóźnienia jako błędu sieci.
- [x] Odtworzyć przejście po SSO w kontrolowanym teście z opóźnionym przekierowaniem.

**Kryterium zakończenia:** podobny incydent daje się przypisać do konkretnego etapu i kategorii przyczyny bez zapisywania treści wyjątku lub danych uwierzytelniających.

### Etap B — gotowość po SSO i kontrolowana nawigacja

- [x] Oddzielić aktywną sesję od gotowości dokumentu do następnej nawigacji.
- [x] Wykorzystać stan dokumentu i zdarzenia nawigacji; nie zastępować ich stałym kilkusekundowym opóźnieniem.
- [x] Po przerwaniu nawigacji sprawdzić aktualny stan strony: jeśli cel został osiągnięty, kontynuować bez kolejnego `goto`.
- [x] Potwierdzać właściwy dashboard i wybraną zakładkę, z uwzględnieniem normalizacji adresów przez ServiceNow.
- [x] Nie uzależniać gotowości od `networkidle`, ponieważ aplikacja może utrzymywać połączenia w tle.
- [x] Nie czekać na dane pierwszego filtra, aby rozpocząć sprawdzanie zagrożeń.

**Kryterium zakończenia:** opóźnione przekierowanie po logowaniu nie kończy sprawdzenia natychmiastowym błędem i nie powoduje nawigacji nad formularzem logowania.

### Etap C — ograniczone odzyskiwanie w bieżącym sprawdzeniu

- [x] Zdefiniować jawne reguły ponawiania dla rozpoznanych błędów przejściowych.
- [x] Kolejność odzyskiwania: obserwacja aktualnego stanu → ponowienie potrzebnej nawigacji → kontrolowane przeładowanie, gdy jest uzasadnione.
- [x] Przyjąć wstępnie najwyżej jedno kontrolowane ponowienie po pierwszej próbie, zgodnie z planem dashboardu, bez zagnieżdżonych, mnożących się pętli retry. Poprzednia propozycja dwóch ponowień zostaje zastąpiona tym wspólnym punktem wyjścia; ostateczny budżet ustalić po pomiarach.
- [x] Wprowadzić wspólny budżet aktywnego odczytu i ponowień; **60 s to wartość wstępna do zweryfikowania pomiarami**.
- [x] Oczekiwanie na ręczne logowanie rozliczać osobno, zamiast zużywać nim budżet odczytu.
- [x] Zachować częste punkty anulowania oraz obsługę zamknięcia Chromium.
- [x] Po zakończeniu nadal odliczać 60 s do następnego zaplanowanego sprawdzenia.

**Kryterium zakończenia:** pojedynczy przejściowy błąd może zostać naprawiony bez czekania na następny cykl; utrzymujący się błąd kończy próbę w przewidywalnym czasie.

### Etap D — odporny odczyt sześciu kafelków

- [x] Zachować rozpoznawanie kategorii po znaczeniu, bez polegania na kolejności kafelków.
- [x] Ponownie wyszukiwać elementy po przebudowie DOM, zamiast korzystać ze starego odwołania.
- [x] Aktywować potrzebne leniwie renderowane widżety i odróżniać ładowanie od braku kafelka.
- [x] Sprawdzać stan bieżącego dokumentu i zakładki podczas odczytu, aby odrzucić wynik z innego widoku.
- [x] Utrzymać walidację kompletu sześciu wartości; sprawdzić, że wartości zastępcze i stary DOM nie są uznawane za świeży wynik.
- [x] Współdzielić z dashboardem lokalny obserwator widżetu i jego stany. Nie tworzyć drugiego, rozbieżnego parsera. Osobno potwierdzać tożsamość zakładki zagrożeń.
- [x] Opisać oczekiwaną kategorię, próg i znaczenie kafelka. Zmianę semantyki tytułu sygnalizować zamiast odczytywać nowe dane pod starym opisem.
- [x] Po niepewnym odświeżeniu wymagać potwierdzenia gotowości nowej próby; nie wymagać zmiany liczby, ponieważ wartości mogą prawidłowo pozostać takie same.
- [x] Przed ewentualnym zastąpieniem pełnej nawigacji odświeżaniem bieżącej karty sprawdzić świeżość, zera, powrót po SSO i zachowanie po zmianie zakładki. To optymalizacja po stabilizacji, nie założony skrót.
- [x] Zmianę nazw lub struktury widżetów raportować jako rozpoznany problem struktury strony, zamiast bez końca ponawiać odczyt.

**Kryterium zakończenia:** leniwe renderowanie i chwilowa podmiana kafelków nie powodują fałszywych zer, częściowego sukcesu ani odczytu z niewłaściwej zakładki.

### Etap E — statusy i zachowanie po błędzie

- [x] Podczas odzyskiwania wyświetlać informację „Ponawianie odczytu”, z zachowaniem blokady przycisków aktualizacji.
- [x] Pokazywać „Błąd odczytu” dopiero po zakończeniu dostępnych prób.
- [x] Zachowywać ostatnie wartości, ich znacznik czasu i istniejący alarm podczas wszystkich prób oraz po niepowodzeniu.
- [x] Rozróżniać anulowanie przez użytkownika, oczekiwanie na logowanie i błąd odczytu.
- [x] Po sukcesie aktualizować cały wynik i przywracać normalne statusy.
- [x] Oddzielić czas ostatniego sukcesu od czasu nieudanej próby, opóźnienia harmonogramu i trybu symulacji. Nie odmładzać poprzednich wartości ani nie oznaczać nieznanego stanu jako bezpiecznego.
- [x] Testować, że symulacja Ctrl+Shift+F12 nie uruchamia w przyszłości prawdziwych powiadomień i nie zmienia terminu zaplanowanego sprawdzenia. Następny poprawny odczyt ma ją zastąpić.
- [x] Oddzielić wynik odczytu od wyniku przywracania widoczności/fokusu okna; awaria tej drugiej operacji nie może zostać opisana jako brak kompletu danych.

**Kryterium zakończenia:** status opisuje rzeczywisty etap pracy, a chwilowy problem nie sugeruje zakończonej awarii ani braku zagrożeń.

## 5. Zakres bezpiecznej diagnostyki

Dozwolone informacje:

- wersja aplikacji, identyfikator uruchomienia i sprawdzenia;
- etap, numer próby, czas trwania, przyczyna i wynik odzyskiwania;
- sklasyfikowany stan nawigacji i dokumentu;
- alias celu, np. `threatened`, zamiast pełnego adresu;
- kategoria błędu sieci i kod HTTP, jeśli dostępny;
- stan każdej kategorii: brak, ładowanie, niejednoznaczność, niepoprawna wartość, gotowość;
- liczba znalezionych i aktywowanych widżetów;
- końcowy wynik: sukces, błąd, anulowanie lub oczekiwanie na logowanie.

Nie zapisujemy loginów, haseł, tokenów, cookies, nagłówków uwierzytelniania, parametrów SSO, treści formularzy, odpowiedzi serwera ani pełnego HTML strony. Nie dodajemy automatycznych zrzutów ekranu logowania.

Nowe pola i zdarzenia trzeba dodać do istniejącej listy dozwolonych wartości diagnostyki. Samo wywołanie `record()` z nieznanym polem nie wystarczy — obecna filtracja może je pominąć. Zachowujemy rotację i ograniczenie rozmiaru logów.

## 6. Plan testów i odbioru

| Scenariusz | Oczekiwany rezultat |
| --- | --- |
| Sesja jest potwierdzona, ale końcowe przekierowanie SSO jeszcze trwa | Oczekiwanie na właściwy dokument; brak kolizji nawigacji. |
| Nawigacja zgłasza przerwanie, ale strona docelowa została otwarta | Kontynuacja odczytu bez zbędnego przeładowania. |
| Przejściowy błąd nawigacji przed dotarciem do celu | Ograniczone odzyskiwanie w tej samej operacji. |
| Trwała awaria sieci lub brak dostępu | Zakończenie w budżecie czasu, czytelny status i kategoria błędu. |
| Sesja wygasa podczas nawigacji lub odczytu | Powrót do istniejącej obsługi logowania i ponowne sprawdzenie po odzyskaniu sesji. |
| Użytkownik wpisuje dane logowania ręcznie | Brak nawigacji nad formularzem i brak dodatkowego wysłania danych. |
| Kafelki są poza widocznym obszarem i renderują się leniwie | Aktywacja widżetów i odczyt kompletu danych. |
| ServiceNow podmienia kafelek w czasie odczytu | Ponowne znalezienie elementu i kontynuacja w budżecie czasu. |
| Brakuje kafelka, jest duplikat lub wartość zastępcza | Brak częściowego sukcesu i brak sztucznego zera. |
| Pozostał stary DOM lub wybrano inną zakładkę | Odrzucenie wyniku jako niepotwierdzonego. |
| Poprawny wynik to sześć zer | Uznanie wyniku za poprawny i wygaszenie alarmu dopiero po walidacji. |
| Po odświeżeniu wyniki są identyczne jak wcześniej | Poprawny nowy odczyt po potwierdzeniu gotowości; bez wymagania zmiany liczby. |
| Nazwa P2 nadal pasuje do prefiksu, ale próg na stronie się zmienił | Zgłoszenie zmiany znaczenia kafelka; brak cichego sukcesu pod starym opisem. |
| Długi dashboard lub filtr opóźnia termin zagrożeń | Jedno zaległe sprawdzenie w najbliższym dozwolonym punkcie; zapis rzeczywistego opóźnienia, bez kolejki zaległych minut. |
| Błąd loggera lub rotacji | Podstawowy odczyt nadal działa; bezpieczna, ograniczona sygnalizacja awarii diagnostyki. |
| Wynik został przyjęty, ale przywrócenie polityki okna nie powiodło się | Zachowanie poprawnego wyniku i osobny błąd obsługi okna. |
| Przed błędem był aktywny alarm | Alarm i ostatnie wartości pozostają. |
| Stop lub zamknięcie Chromium podczas ponowienia | Szybkie anulowanie lub właściwa obsługa odzyskiwania przeglądarki; brak zaległego wyniku w UI. |
| Błąd zawiera przykładowe hasło, login, token lub adres SSO | Żaden z tych ciągów nie trafia do logów. |
| Próba zakończyła się sukcesem lub błędem | Kolejny termin przypada 60 s po jej zakończeniu; brak kumulacji. |

Po testach celowanych: pełny zestaw testów aplikacji, test gotowego EXE z dołączonym Chromium i kontrolowana seria rzeczywistych odczytów po świeżym logowaniu oraz na istniejącej sesji. Odbiór wymaga zapisania liczby prób, ich wyników i czasów — bez deklarowania niezawodności na podstawie jednego sukcesu.

## 7. Punkty wejścia w kodzie

| Plik | Zakres |
| --- | --- |
| `neto_incident_monitor/authentication.py` | Rozpoznawanie sesji i przejść logowania. |
| `neto_incident_monitor/browser_actions.py` | Nawigacja, krótkie oczekiwania i anulowanie. |
| `neto_incident_monitor/threatened.py` | Odczyt sześciu liczników zagrożeń. |
| `neto_incident_monitor/dashboard.py` | Wspólne rozpoznawanie i przygotowanie widżetów. |
| `neto_incident_monitor/app.py` | Orkiestracja, ponowienia, harmonogram i zdarzenia UI. |
| `neto_incident_monitor/login_diagnostics.py` | Bezpieczne pola, zdarzenia, klasyfikacja błędów i rotacja. |
| `neto_incident_monitor/threatened_ui.py` | Statusy, zachowanie wyniku i alarmu. |
| `tests/test_threatened.py`, `tests/test_login_transitions.py`, `tests/test_dashboard_navigation.py`, `tests/test_login_diagnostics.py` | Główne testy do rozszerzenia. |

## 8. Poza zakresem tej poprawy

- Powiadomienia o zagrożeniach przez Windows, Teams i Google Chat — osobne zadanie po ustabilizowaniu odczytu.
- Równoległe pobieranie danych w wielu kartach lub wątkach.
- Przebudowa wyglądu dashboardu i przeglądarki.
- Nowy build EXE, ZIP, commit, push lub publikacja wydania — wymagają kolejnego polecenia; ten dokument służy najpierw uzgodnieniu prac.

## 9. Sugerowana realizacja

1. Uzgodnić ten plan i wstępny budżet czasu.
2. Wykonać etap A oraz test odtwarzający przejście po SSO.
3. Wykonać etapy B–C, następnie testy celowane.
4. Wykonać etapy D–E i testy zachowania danych oraz alarmu.
5. Przeprowadzić pełną weryfikację i podsumować wyniki przed przygotowaniem nowego EXE.

Przy rozpoczęciu implementacji aktualizować checkboxy oraz dopisywać wyniki weryfikacji. Nie oznaczać etapu jako zakończonego wyłącznie dlatego, że kod został napisany.

## 10. Zależności od pozostałych planów

- Wspólne z `stabilizacja-dashboardu.md`: obserwator konkretnego widżetu, tożsamość dashboardu/zakładki, klasyfikacja nawigacji, budżet czasu i korelacja diagnostyki. Zaprojektować i wdrożyć te części raz; zachować różne kontrakty oczekiwanych kafelków.
- Specyficzne dla zagrożeń: komplet sześciu kategorii, miganie i zachowanie alarmu, kolejność po logowaniu, odliczanie 60 s od zakończenia i bezpieczne wtrącenie między filtrami.
- Specyficzne dla zwykłego dashboardu: miesiąc, kategorie, WJRUW, trzy sekcje oraz wersjonowany cache. Ich ukończenie nie jest wymagane do poprawy alarmu zagrożeń.
- Nie przerywać paginacji filtra, aby wtrącić zagrożenia. Integrację z nową paginacją zweryfikować testem harmonogramu, bez przebudowywania gotowego mechanizmu.
- Powiadomienia o zagrożeniach pozostają późniejszym osobnym planem. Historyczne uzgodnienia odstępów nie oznaczają, że wysyłanie jest już wdrożone lub ma zostać dołączone do stabilizacji.

## 11. Stan weryfikacji po aktualizacji planu

- [x] Ponowna inspekcja aktualnej zakładki zagrożeń i sześciu widżetów w Codex.
- [x] Obserwacja odświeżenia i lokalnych stanów ładowania.
- [x] Ponowne porównanie rzeczywistego filtra P2 z linkiem aplikacji; pięć pozostałych linków nadal wymaga ponownej kontroli przed odbiorem.
- [x] Audyt czytnika, orkiestratora, harmonogramu, statusów, migania i trybu symulacji.
- [x] Istniejące testy `test_threatened` i `test_refresh_requests`: **17 testów, wszystkie zaliczone**, 23,493 s. Zapis lokalny: `data/threatened-audit-tests.log`. Są to testy syntetyczne i UI, nie test EXE na rzeczywistym koncie.
- [x] Kontrolowane testy awarii, odzyskiwania, budżetu, kompletności i bezpiecznej diagnostyki.
- [x] Implementacja etapów A–E oraz odbiór źródeł na rzeczywistej stronie.
- [ ] Weryfikacja nowego EXE — poza bieżącym zakresem, wymaga osobnego polecenia budowania.

Przed wdrażaniem odległym w czasie ponownie sprawdzić aktualny DOM i definicje kafelków. Plan dokumentuje stan z dnia analizy, nie gwarantuje niezmienności ServiceNow.

## 12. Wynik realizacji

Czytnik zagrożeń korzysta ze wspólnej nawigacji, kontekstu, lokalnego obserwatora i jednego budżetu odzyskiwania. Zachowano pełną nawigację dla świeżego odczytu — nie wdrażano opcjonalnego zastąpienia jej kliknięciem odświeżenia. Wszystkie sześć linków porównano z rzeczywistymi filtrami `task_sla_list.do`; nie potwierdzono unikalności incydentów w definicji raportu, więc nie sumujemy kategorii. Harmonogram i alarm pozostały bez zmian, powiadomień nie dodano. Szczegóły testów i ograniczenia: [raport](../../verification/dashboard-stabilization-verification.md).
