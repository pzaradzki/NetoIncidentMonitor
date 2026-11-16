# Kontrakt odczytu list ServiceNow

## Table API w bieżących źródłach

Belka filtra pokazuje wynik próby, godzinę ostatniego zatwierdzenia pełnej listy i czas odpowiedzi REST po rekordy. Te same metadane są widoczne przy przełączaniu na historię. Odczyt definicji i układu jest poza tym pomiarem. Zmiana adresu lub usunięcie filtra unieważnia informacje dla poprzedniego widoku, a błąd odczytu zachowuje metadane ostatniego udanego wyniku. [Decyzja 039](../decyzje/039-statusy-widokow-i-kolejki.md).

Zapytanie, tabela i widok mają trwały zapis przy filtrze. Zapytanie zachowuje `sysparm_query` wraz z sortowaniem. Gdy zapis jest nieaktualny lub go brakuje, wątek `SharedSession` czyta warunki z pełnego adresu. Skrót `__tinyId__` rozwija jednym GET i czyta dane startowe nawigatora. Weryfikuje nowe pola i odwołania za pomocą metadanych tabel. Brak ograniczenia, samo sortowanie, nierozpoznane pole i kontekstowe warunki przerywają operację przed Table API. Zmiana adresu unieważnia zapis oraz żądania starej rewizji. Starsze definicje są ponownie ustalane przy pierwszym użyciu.

Układ zawiera techniczne nazwy, etykiety i kolejność. Należy do konta, tabeli i widoku. SOW udostępnia identyfikator zalogowanego konta oraz język dokumentu. Zapis używa lokalnego klucza pochodnego i przy wczytywaniu sprawdza język etykiet. Po logowaniu `SharedSession` odświeża domyślne układy czterech tabel. Nazwany widok odczytuje przy pierwszym użyciu. Brak świeżego układu po błędzie pozwala użyć ostatniego poprawnego zapisu tego samego klucza i języka. Przy braku zapisu błąd dotyczy zależnego filtra. HTTP 200 bez potwierdzenia nazwanego widoku nie stanowi podstawy zapisu.

**Ustawienia → Dane aplikacji → Układy kolumn list ServiceNow** pokazują cztery domyślne układy bieżącego konta. Podgląd zachowuje kolejność etykiet i techniczne identyfikatory pól z lokalnego zapisu. Odświeża zawartość po zapisaniu układu przez sesję i czyści poprzednie dane na czas ponownego potwierdzenia konta. Otwarcie okna nie zleca odczytu ServiceNow.

**Aktualizuj** w podglądzie zleca jedno zadanie w `SharedSession`, dostępne także podczas monitoringu. Po zakończeniu bieżącej pracy zadanie odczytuje domyślne układy INC, REQ, RITM i SCTASK istniejącym czytnikiem. Każdy udany układ zapisuje osobno. Błąd tabeli zachowuje jej wcześniejszy układ i wskazuje ją w wyniku. Zlecenie pozostaje przypisane do konta, dla którego je przyjęto. Diagnostyka kolejki wiąże je z odczytami tabel i zapisuje liczbę zakończonych odczytów.

**Konfiguruj → Zapytanie** otwiera podgląd zapisanego zapytania z możliwością kopiowania. Akcja **Odśwież zapytanie z SNOW** powtarza rozpoznanie bez pobierania rekordów. **Kolumny → Odśwież układ z SNOW** aktualizuje wspólny układ używany przez zależne filtry przy następnym odczycie. Obie operacje wykonuje ta sama kolejka. Nieudane odświeżenie zachowuje dotychczasowy zapis. Lokalne ustawienia widoczności, kolejności i szerokości nadal należą do filtra.

Czytnik pobiera pola z zapisanego widoku ServiceNow, również ukryte lokalnie i dostępne dla historii i szablonów powiadomień. Pobiera także numer, identyfikator i surową datę utworzenia INC dla wieku zgłoszenia. Brak pola w odpowiedzi i pusta wartość są odrębnymi przypadkami. RITM może pominąć `cat_item.workflow`, mimo że układ pokazuje tę kolumnę. Aplikacja zachowuje kolumnę i pokazuje brak wartości, a pole nie może być użyte do ustalenia zakresu. Brak pozostałych wymaganych pól odrzuca wynik.

Żądanie REST zachowuje warunki i jawne dyrektywy sortowania z adresu. Dodaje `sys_id` do rozstrzygania remisów i pomija końcowe `EQ`. Dozwolony kontekst to samodzielna lista, a widok z adresu określa układ, także wtedy, gdy klasyczny klient może nadpisać go preferencją. Odrzucane są m.in. listy zależne i stały filtr w osobnym parametrze URL. W ADEO Table API pominęło błędne pole i zwróciło rekordy, dlatego sama odpowiedź HTTP 200 nie potwierdza poprawności zapytania. [ServiceNow Table API](https://www.servicenow.com/docs/r/api-reference/rest-apis/c_TableAPI.html) · [Dokumentacja widoków](https://www.servicenow.com/docs/r/platform-user-interface/view-management-overview.html)

Dla SCTASK i RITM odczytujemy aktywną definicję zmiennej z `item_option_new` po dokładnym identyfikatorze. Dla daty obsługujemy `RELATIVELT` w dniach wstecz z dodatnim progiem, a dla tekstu jednowierszowego `ISEMPTY` i `ISNOTEMPTY`. Jeżeli gałąź łączy warunki spójnikiem AND i wskazuje jedną konkretną pozycję katalogową, potwierdzamy powiązanie bezpośrednie lub członkostwo zestawu w `io_set_item`. Zmienna poza obsługiwaną tabelą, niepotwierdzona definicja, niedopasowany typ, wartość lub relacja blokują odczyt rekordów. Sortowanie po zmiennej katalogowej, wyszukiwanie tekstowe i zapytania relacyjne pozostają poza tym zakresem. [Decyzja 038](../decyzje/038-walidacja-warunkow-filtrow.md) · [Zmienne katalogowe w ServiceNow](https://www.servicenow.com/docs/r/now-intelligence/reporting/use-service-catalog-variables-in-report.html)

`SAMEAS` i `NSAMEAS` wymagają potwierdzenia obu pól oraz zgodnych typów. Przy odwołaniach oba pola muszą wskazywać tę samą tabelę. Zapis zapytania kontroluje ważność metadanych użytych do sprawdzenia zmiennej, porównania pól i daty względnej. Potwierdzenie jest ważne najwyżej dobę. Przy braku aktualnego potwierdzenia aplikacja odczytuje metadane przed pobraniem rekordów. Poprzednie zapytanie pozostaje widoczne w **Konfiguruj → Zapytanie**. Przejściowa awaria metadanych wstrzymuje ponowne próby tego samego odczytu na minutę. [Operatory ServiceNow](https://www.servicenow.com/docs/r/platform-user-interface/r_OpAvailableFiltersQueries.html)

Czytnik żąda do 1000 rekordów w jednej odpowiedzi. Wymaga `X-Total-Count`, zgodnej liczby wierszy, braku sygnału kolejnej strony oraz unikalnych identyfikatorów i numerów. Przy wyniku powyżej 1000 aplikacja wyłącza filtr z harmonogramu, zapisuje konfigurację i pokazuje monit. Stopka podaje nazwę filtra, liczebność i limit. Jeśli filtr był wyłączony, aplikacja pokazuje stopkę bez ponownego monitu o wyłączeniu. Nieudany zapis wyłączenia wyświetla komunikat o błędzie. Wynik ze starej rewizji nie zmienia konfiguracji. Błąd, wygaśnięcie sesji i anulowanie odrzucają bufor. Utrata sesji i przejściowe błędy transportu korzystają z dotychczasowych budżetów ponowień. Przekroczenie limitu i niespójna odpowiedź kończą bieżące zlecenie. [Decyzja 035](../decyzje/035-limit-odczytu-filtrow.md)

Diagnostyka łączy rozpoznanie adresu, zapis zapytania, układ, żądanie API, walidację, ponowienia i transakcję historii. Zapisuje rodzaj adresu, alias tabeli, wynik, czasy, liczebność, limit, sygnał kolejnej strony, liczbę dopuszczonych braków wartości oraz kategorię nieudanej kontroli. Pomija zapytania, pełne adresy, identyfikatory kont i zgłoszeń, treść odpowiedzi oraz dane sesji. Wyniki odczytu metadanych opisuje [analiza i odbiór](../analizy/definicja-filtrow-servicenow-bez-dom.md).

## Historia wycofanego czytnika klasycznych list

Czytnik wiąże widoczną tabelę, pager, typ rekordu i metadane z jedną listą. Jawne zapytanie i widok muszą odpowiadać żądaniu. Kolejność warunków i grupowanie OR/NQ pozostają istotne. Ignorowane są jedynie końcowe dyrektywy `EQ` i sortowania oraz potwierdzona równoważność z [decyzji 015](../decyzje/015-rownowaznosc-dat-filtrow.md).

W warunku pola `sys_updated_on` kompletne wartości `javascript:gs.daysAgoStart(7)` i `javascript:gs.beginningOfLast7Days()` są traktowane jednakowo dla operatorów `=`, `!=`, `<`, `<=`, `>` i `>=`. Pole, operator, prefiksy i inne fragmenty pozostają bez zmian. Tekst w opisach, inne argumenty i dodatkowy kod nie korzystają z reguły. Zapytanie nie jest wykonywane jako JavaScript w aplikacji ani przepisywane w konfiguracji.

Na każdej stronie wymagane są spójne zakresy, liczebność, unikalność i stała tożsamość listy. Rzeczywista zmiana warunków powoduje `query_mismatch` na pierwszej stronie lub `list_changed` podczas przejścia. Możliwe jest jedno ponowienie całego odczytu z nowym buforem, w dotychczasowym budżecie. Stop i utrata sesji zachowują odrębne ścieżki. Wynik częściowy nie trafia do historii, obecności ani kolejki alertów.

Dla klasycznych list INC, REQ, RITM i SCTASK czytnik sprawdza `rows_per_page` w metadanych właściwej tabeli przed pobraniem rekordów. Przy 100 wierszach od razu rozpoczyna odczyt. Przy innej potwierdzonej wartości próbuje wybrać **Czynności → Pokaż → 100 wiersz./str.** na tej samej karcie. Po akcji wiąże tabelę ponownie i sprawdza kontekst oraz pierwszą stronę. Niedostępna opcja lub brak potwierdzenia pozwalają użyć zaobserwowanego rozmiaru, jeśli kontekst i kompletność można potwierdzić. Ponowienie całego odczytu wykorzystuje zaobserwowany rozmiar po pierwszej próbie zmiany.

ServiceNow zapisuje wybór jako preferencję użytkownika i stosuje ją na klasycznych listach dostępnych dla tego konta. [Dokumentacja ServiceNow](https://www.servicenow.com/docs/r/platform-user-interface/configure-use-list-functions.html).

### Podgląd definicji przed migracją

Pierwsza wersja przycisku **ⓘ** pokazywała definicję z metadanych zebranych podczas pełnego odczytu klasycznej listy. Zapis obejmował tabelę, warunki, widok, etykiety i techniczne nazwy kolumn. Migracja uzupełnia ten zapis o wersję, pochodzenie i stabilne klucze używane podczas odczytu przez REST.

### Diagnostyka poprzedniego czytnika i walidacja adresu

Zdarzenie `pagination_page_size` zapisuje wynik sprawdzenia menu lub potwierdzenia zmiany, numer strony oraz poprzedni i odczytany rozmiar. Przy 100 wierszach istniejące `pagination_bound` podaje rozmiar bez dodatkowych zdarzeń menu.

Przy dodawaniu filtra `validate_urls` normalizuje adres opakowany do bezpośredniej listy. Warstwa opakowania jest dekodowana raz, parametry celu parsowane i ponownie kodowane; dołączone parametry są zachowane, a sprzeczne powtórzenia `sysparm_*` odrzucane. Istniejące bezpośrednie adresy nie są przepisywane. Reguły hosta, listy i bezpiecznych znaków nadal obowiązują. [Decyzja 016](../decyzje/016-normalizacja-adresow-list.md).

`filter_url_validation` używa źródła `configuration` i pól: `url_kind` (`direct/wrapper/short`), `validation_result` (`accepted/rejected`) oraz `validation_reason` (`none/unsafe/unsupported_target/conflicting_parameters`). Osobna korelacja wiąże zdarzenia jednej walidacji. Bez pełnych adresów i treści warunków. Nieudana walidacja nie zapisuje konfiguracji; awaria diagnostyki nie wpływa na wynik walidacji.

### Odbiór długich adresów — 4 listopada 2026

Przeszło 66 testów zakresowych adresów, dialogu filtra, bezpieczeństwa, skrótów, aliasu daty, paginacji, stanu i transakcji filtrów oraz diagnostyki. Testy objęły znaki zarezerwowane i Unicode, dwa układy parametrów, sprzeczne powtórzenia, niezmienność adresów bezpośrednich, zapis/restart i zachowanie konfiguracji po odrzuceniu.

Sonda źródeł w osobnym profilu dodała rzeczywisty długi adres przez dialog aplikacji, zapisała go i ponownie wczytała. Warunki oraz widok `default` pozostały zgodne. Dwa odczyty zakończyły się po 21 rekordów na 2 stronach w 4,64 i 4,70 s; kontrolny pusty filtr zakończył się na 1 stronie w 1,34 s. Sonda nie wysyłała powiadomień ani nie zmieniała bieżących danych użytkownika. Pierwsze uruchomienie samej sondy zakończyło się przed odczytem wskutek zbyt wczesnej inspekcji ramki po logowaniu; po dodaniu oczekiwania na gotową listę ponowiono ją na tym samym testowym profilu.

W przebudowanym EXE dodano rzeczywisty długi adres przez widoczny dialog „Dodaj filtr”. Po zapisie zamknięto i ponownie uruchomiono aplikację na tych samych testowych danych. Zapis zachował wszystkie trzy granice NQ, warunek `NOT LIKE` i widok `default`. Monitoring po restarcie ukończył cztery odczyty: 23, 24, 23 i 24 rekordy, każdy na 2 stronach. Brak błędów paginacji, integralność SQLite poprawna, kolejka alertów pusta. Zmienna liczba rekordów wynika z bieżącej listy. Testową aplikację zamknięto normalnie. Test offline EXE potwierdził UI, tła kafelków i dołączone Chromium. Kod normalizacji, aplikacji i diagnostyki w pakiecie jest zgodny ze źródłami według porównania kodu bajtowego.

`pagination_query_comparison` zawiera wynik `exact`, `known_alias` lub `mismatch`, kod aliasu `none` albo `last_7_days`, numer filtra i strony oraz korelację odczytu. Każda klasa pojawia się najwyżej raz na próbę. Bez zapytania, adresu, wartości warunków i treści zgłoszeń. Awaria diagnostyki nie przerywa odczytu.

## Odbiór 4 listopada 2026

Obserwacja przeglądarki Codex potwierdziła zamianę daty, zgodność pozostałych warunków i kanoniczny zapis na drugiej stronie. Lista liczyła wtedy 23 wyniki; nie jest to stała testowa.

Po poprawce rzeczywisty czytnik aplikacji w nowym, tymczasowym profilu odczytał filtr dwukrotnie: po 22 rekordy na 2 stronach, w 7,38 s i 6,84 s. Następnie odczytał filtr kontrolny: 0 rekordów na 1 stronie w 1,30 s. Sonda nie zapisywała historii ani nie uruchamiała transportów powiadomień. Dane użytkownika pozostały bez zmian.

Testy syntetyczne obejmują cztery gałęzie NQ, wiele lokalizacji OR, oba kierunki aliasu, trzy strony, zmianę zapisu między nimi, odrzucanie zmienionych warunków oraz brak sekretów i nadmiarowych wpisów diagnostyki. Przeszło 75 testów zakresowych: nowy alias i kontekst, walidacja i kontrolki paginacji, skróty URL, stan i transakcje filtrów, Teams, Google Chat oraz diagnostyka. Moduły uruchamiano w izolowanych procesach Windows.

Przebudowany lokalny EXE 1.8.1 przeszedł dwa pełne cykle monitoringu na tym samym odizolowanym profilu: po 21 rekordów na 2 stronach dla „Dyżur 1L” i po 0 na 1 stronie filtra kontrolnego. Oba cykle zakończyły się poprawnym zapisem, bez błędów paginacji. Diagnostyka potwierdziła `known_alias/last_7_days` dla filtra dyżuru i `exact/none` dla kontrolnego. Kolejka alertów była pusta, integralność testowego SQLite poprawna. Monitoring zatrzymano i aplikację zamknięto normalnie. Zmiana liczebności względem wcześniejszych sond odzwierciedla dynamiczną listę.
