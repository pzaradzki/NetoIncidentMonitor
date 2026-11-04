# Kontrakt odczytu list ServiceNow

## Warunki i kompletność

Czytnik wiąże widoczną tabelę, pager, typ rekordu i metadane z jedną listą. Jawne zapytanie i widok muszą odpowiadać żądaniu. Kolejność warunków i grupowanie OR/NQ pozostają istotne. Ignorowane są jedynie końcowe dyrektywy `EQ` i sortowania oraz potwierdzona równoważność z [decyzji 015](../decyzje/015-rownowaznosc-dat-filtrow.md).

W warunku pola `sys_updated_on` kompletne wartości `javascript:gs.daysAgoStart(7)` i `javascript:gs.beginningOfLast7Days()` są traktowane jednakowo dla operatorów `=`, `!=`, `<`, `<=`, `>` i `>=`. Pole, operator, prefiksy i inne fragmenty pozostają bez zmian. Tekst w opisach, inne argumenty i dodatkowy kod nie korzystają z reguły. Zapytanie nie jest wykonywane jako JavaScript w aplikacji ani przepisywane w konfiguracji.

Na każdej stronie wymagane są spójne zakresy, liczebność, unikalność i stała tożsamość listy. Rzeczywista zmiana warunków powoduje `query_mismatch` na pierwszej stronie lub `list_changed` podczas przejścia. Możliwe jest jedno ponowienie całego odczytu z nowym buforem, w dotychczasowym budżecie. Stop i utrata sesji zachowują odrębne ścieżki. Wynik częściowy nie trafia do historii, obecności ani kolejki alertów.

## Diagnostyka

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
