# Kontrakt odczytu dashboardu i zagrożeń

## Obowiązujący kontrakt REST

Oba odczyty działają w kolejce `SharedSession` na tej samej karcie i sesji ServiceNow. Konfiguracja lokalna powstaje z arkusza. Dashboard wykonuje jedną grupowaną agregację SLA dla wybranego okresu, dwie agregacje Wstrzymanych L1 i pięć agregacji Wniosków L1. WJRUW powstaje z tej samej migawki SLA. Odczyty L1 pokazują stan bieżący. Cache przechowuje trzy niezależne migawki i czas ostatniego pełnego sukcesu.

Zagrożenia obejmują sześć kategorii. P1–P5 liczą SLA rozwiązania z progami 1, 2, 4, 24 i 48 godzin. Podjęcie liczy SLA odpowiedzi z progiem 5 minut. Każdy próg obejmuje terminy już przekroczone. Przed zapisaniem bieżącej listy, historii i alertów aplikacja potwierdza komplet rekordów. Liczniki dotyczą wierszy SLA, a lista grupuje je według incydentu. Zapis niepełnej listy jest odrzucany z zachowaniem poprzedniej migawki.

Pigułki pokazują kolejkę, odczyt, logowanie, ponowienie i wynik. Diagnostyka REST zapisuje cel i numer wywołania, kod HTTP, czas, wynik walidacji oraz zapis danych. Szczegóły konfiguracji i odbioru opisują [instrukcja REST](../servicenow-api-sesja-przegladarki.md) i [decyzja 033](../decyzje/033-odczyty-analityki-przez-api.md).

## Historyczny kontrakt odczytu przez DOM

Stan kontraktu: 1 listopada 2026; lokalny build 1.8.0 z 2 listopada zawiera wdrożenie i przeszedł offline smoke-test. Nie jest to pełny rzeczywisty test odczytu z EXE. Odbiór: [raport](../weryfikacja/odbior-stabilizacji-dashboardu.md).

| Sekcja | Wymagane dane | Ustawienia |
| --- | --- | --- |
| SLA | Liczba zgłoszeń; Zgłoszenia P1–P5; Przekroczone P1–P5 (11 liczb). WJRUW wyliczany z tego samego kompletu. | Wybrany miesiąc; wszystkie statusy, lokalizacje i osoby przypisane. |
| Wstrzymane L1 | >14 dni i >7 dni (2 liczby). | Wszyscy agenci L1; stan bieżący, nie zakres miesiąca SLA. |
| Wnioski L1 | Otwarte, >7 dni, >14 dni, nieprzypisane i Wnioski Smartfon – start >3 dni (5 liczb). | Wszyscy agenci L1; stan bieżący. |
| Zagrożenia | P1–P5 oraz Podjęcie (6 liczb). | Właściwa zakładka zagrożeń; progi 1/2/4 h, 1/2 dni i 5 min, także po terminie. |

Każdy zaakceptowany zestaw musi pochodzić z właściwego dashboardu i zakładki, po zastosowaniu wymaganych ustawień, z jednoznacznych widżetów bez lokalnego ładowania. Wartości: pełne nieujemne liczby całkowite; zero nie jest brakiem danych. Krótka stabilność jest zabezpieczeniem dodatkowym, nie dowodem świeżości.

Na dashboardzie ServiceNow kliknięcie „Wybierz wszystko” przy częściowym wyborze najpierw czyści zaznaczenie. Czytnik rozpoznaje stan pośredni przez `aria-checked="mixed"` lub `indeterminate`. Potwierdzony pusty wybór pozwala na osobne zaznaczenie całości. Jeśli przejście pozostaje niepotwierdzone, czytnik zgłasza `wrong_filter` do istniejącego mechanizmu ponowień. Końcowa kontrola wymaga jednoznacznego pełnego wyboru. Zdarzenie `category_partial_resolved` rejestruje alias kategorii oraz potwierdzony stan kontrolki, bez nazw wybranych opcji.

Wszystkie cztery sekcje używają `read_tile/read_scores`. Nie ma fallbacku do odczytu globalnego. Kategorie są osobno zatwierdzane; brak obserwowalnego potwierdzenia odświeżenia powoduje odtworzenie dokumentu i ustawień. Kontrolki i karty mogą powstać dopiero po przewinięciu. Odczyt nie wymaga zmiany samej liczby.

Zgodnie z [decyzją 019](../decyzje/019-odzyskiwanie-sesji-sekcji.md): jedno ponowienie błędu odczytu i jedno niezależne odzyskanie logowania, najwyżej trzy odczyty we wspólnym aktywnym budżecie 60 s; pierwsza próba do 39 s. Oczekiwanie na ręczne logowanie jest rozliczane osobno. Brak pewności po kliknięciu nie powoduje jego ponownego dostarczenia w tej samej próbie. Budżet jest kooperacyjny i nie stanowi gwarancji zakończenia zablokowanego procesu Chromium.

Cache schematu 2 przechowuje niezależne, kompletne zestawy trzech sekcji dashboardu. Każdy ma własny czas sukcesu, ostatnią próbę i kontekst. Migracja dawnego cache nie przypisuje sekcjom wymyślonych dat. Błąd nie odmładza wyniku ani nie wygasza alarmu zagrożeń. Szczegóły: [decyzja 006](../decyzje/006-odczyt-sekcji-dashboardu.md).

Dolny komunikat pokazuje jeden timestamp ostatniego zakończonego sukcesem odczytu całego dashboardu. Czasy sekcji pozostają wewnętrzne. Znacznik jest przesuwany dopiero po przyjęciu kompletu SLA/Wstrzymanych/Wniosków z tego samego żądania; częściowy odczyt, błąd, Stop i stare wyniki go nie odmładzają. Opcjonalne `last_complete_read_at` w cache schematu 2 zachowuje go między uruchomieniami. Dla starszego cache bez tego dowodu pokazujemy „—” do następnego pełnego sukcesu, zamiast zgadywać z maksimum dat sekcji. Zdarzenie `dashboard_complete` zapisuje zakończenie z korelacją żądania; zapis cache korzysta z dotychczasowej diagnostyki. To poprawka źródeł po buildzie 1.8.0.

## Okres i cykl żądania — poprawka źródeł po buildzie 1.8.0

Miesiąc i rok są zablokowane od kolejkowania żądania dashboardu do pasującego końca, także podczas logowania, ponowień i restartu Chromium. Guard zmiennych nie pozwala programowej zmianie unieważnić aktywnego ID. Koniec ze starym ID/okresem nie odblokowuje nowszego żądania. Stop i błędy kolejkowania/startu zwalniają kontrolki; samo przełączenie widoku tego nie robi.

Wyniki mają ID i okres żądania; inny okres lub wynik po zakończeniu nie zastępuje danych ani cache. Zmiana dat w bezczynności dotyczy tylko aktualności SLA; stare kafelki pozostają podpisane okresem ich odczytu. Nie unieważnia ona bieżących Wstrzymanych/Wniosków. Szczegóły: [010](../decyzje/010-cykl-zycia-zadania-dashboardu.md). Poprawka nie jest jeszcze w zbudowanym EXE.

Zdarzenia `dashboard_request_state`, `dashboard_period_state` i `dashboard_result_rejected` zapisują ID, dozwolony `request_state`, rok/miesiąc i w razie potrzeby oczekiwany okres/aktywny ID. Nie zawierają wartości kafelków, URL lub danych konta. Korzystają z istniejącej korelacji, allowlisty i ograniczania powtórzeń.

## Diagnostyka

- `run_id`: losowy identyfikator procesu; `read_id`: nowe faktyczne wykonanie żądania, także okresowego; `session`: konkretna sekcja; `attempt`: jej próba. Istniejący `trace` pozostaje zachowany.
- `source`, `section` i bezpieczne opcje konstruktora są dołączane do kolejnych zdarzeń. `request_id` wiąże odczyt z żądaniem UI.
- `dashboard_stage_end`: operacja, kategoria, czas w ms i sposób opuszczenia etapu. `returned` znaczy powrót bez wyjątku, **nie potwierdzenie kompletnego sukcesu**. Ten opisują istniejące zdarzenia `section_read_complete/partial/error`.
- `dashboard_observation`: przyczyna oczekiwania i liczba widocznych gotowych/oczekiwanych liczników, bez samych wartości biznesowych. `dashboard_context` osobno potwierdza kontekst. Logowane są także stan lokalnego kafelka, zastosowanie kategorii, tryb odświeżenia, powód odzyskiwania, końcowy wynik i zapis cache.
- Obserwatory nawigacji dokumentu są dołączane na czas sekcji i odłączane po jej opuszczeniu. Logi pozostają filtrowane i rotowane.

## Historyczna weryfikacja pierwszej części etapu A

48 testów celowanych: zaliczone, 64,874 s (`data/dashboard-measurements-tests.log`). Obejmują nowe identyfikatory, kontekst sekcji/próby, czasy, anulowanie, bezpieczne wyjątki i awarię ujścia diagnostyki oraz regresje dashboardu, logowania diagnostycznego i harmonogramu.

Kontrola rzeczywistej zakładki zagrożeń w Codex: 6 liczników; dwa wywołania „Odśwież bieżącą kartę” do widoczności sześciu wartości bez loaderów trwały 577 i 428 ms. Czasy obejmują obsługę narzędzia i nie mierzą pełnej nawigacji/odczytu Python ani nie dowodzą świeżości bazy. Nie zapisano treści tabeli.

Powyższe 48 testów i dwa pomiary opisują pierwszy etap prac. Późniejsze wdrożenie obejmuje wspólny czytnik, kontekst, budżet, odzyskiwanie i cache. Aktualne wyniki oraz rozróżnienie testów źródeł i EXE znajdują się w [raporcie odbioru](../weryfikacja/odbior-stabilizacji-dashboardu.md).

## Widoczność i renderowanie

Próba sekcji korzysta z `BrowserRuntime.dashboard_read`. Przy ukryciu: potwierdzona sesja → docelowy dashboard → lokalne podtrzymanie renderowania → normalne kontrolki i czytnik → sprzątanie. Gotowa kontrolka daty nie jest warunkiem uruchomienia mechanizmu. Logowanie zatrzymuje go, a ręczna obsługa pokazuje i fokusuje okno. Błąd `rendering_unavailable` nie jest samodzielnie ponawiany; zachowuje poprzedni sukces. Użytkownik może pokazać przeglądarkę i zlecić nowy widoczny odczyt.

`rendering_start/deferred/error/stop` zawierają stałą przyczynę, czas, `frame_count`, `ack_count`, `payload_bytes` (długość zakodowanych danych) i `cleanup_errors`, nigdy same dane ramek. `category_check_recovered/failed` opisują wynik obserwacji po dostarczonym zaznaczeniu. Niezaznaczona lub pośrednia kategoria nie jest uznawana za poprawną. Zasady: [007](../decyzje/007-ukryty-dashboard.md); [odbiór wdrożenia](../weryfikacja/odbior-ukrytego-dashboardu.md).

Weryfikacja wspólnego timestampu (2 listopada 2026): 43 testy zakresowe zaliczone; po doprecyzowaniu testu starego/uszkodzonego znacznika ponowiono 7 testów snapshotów, także zaliczonych. Logi lokalne: `data/dashboard-single-timestamp-final-tests.log`, `data/dashboard-single-timestamp-cache-tests.log`. Nie testowano nowego EXE ani nie zmieniano interakcji ServiceNow.

### Cele nawigacji kafelków

Poniższe próby dokumentują wcześniejszą nawigację. W bieżących źródłach kafelki dashboardu i zagrożeń SLA są informacyjne. Usunięto pobieranie adresów list i otwieranie kart w tym celu. [Decyzja 024](../decyzje/024-kafelki-informacyjne.md).

W rzeczywistym ServiceNow kliknięcie kafelka smartfonów otworzyło listę zadań katalogowych w tej samej karcie. Adres nawigacji zawierał skrót `sysparm_tiny`. Próba kafelka nieprzypisanych wniosków także zakończyła się widokiem listy ze skrótem. Nie potwierdzono trwałego wzorca obejmującego filtry L1 ani zależność celu SLA od okresu. Dashboard aplikacji ma paletę sekcji i korzysta ze wspólnego komponentu kafelków. Na tym etapie akcje dashboardu czekały na zweryfikowane cele. WJRUW jest wskaźnikiem lokalnym.

### Weryfikacja list L1 bez skrótów

W osobnej karcie Codex kliknięto pięć kafelków Wniosków L1 i oba kafelki Wstrzymanych L1. Lista docelowa zawiera w ramce `gsft_main` tabelę klasyczną z atrybutami `glide_table`, `query` i `total_rows`. Wnioski prowadzą do `sc_task`, a Wstrzymane do `incident_metric`. Dla każdego z siedmiu kafelków bezpośrednia lista z zakodowanym `sysparm_query` zwróciła identyczne zapytanie i liczebność jak lista otwarta z kafelka. Liczby, identyfikatory agentów i treści rekordów pominięto w raporcie.

Zapytania Wniosków zawierają identyfikatory agentów, których pola wyboru nie udostępniają w atrybutach HTML. Dalsza praca obejmuje bezpieczne pozyskanie zapytania z docelowej listy w izolowanym kontekście nawigacji i powiązanie go z migawką kafelka. Odbiór SLA nadal wymaga porównania dwóch okresów.

### Podłączenie list L1 do migawek

Poniższy opis oraz kolejne etapy odbioru automatycznego pozyskiwania wszystkich linków dokumentują wcześniejszą implementację. Zastąpiło ją opisane na końcu otwieranie list na żądanie; dawnych limitów sekcji ani wymogu nowego odczytu przed kliknięciem już nie stosujemy.

Po przyjęciu wartości Wniosków L1 lub Wstrzymanych L1 monitor używa osobnej, tymczasowej karty tej samej sesji. Potwierdza zakładkę, stosuje wybór wszystkich agentów i porównuje wartość kafelka z przyjętą migawką przed kliknięciem. Z potwierdzonej listy odczytuje zapytanie i buduje bezpośredni adres. Pierwsza wersja próby pozyskania linków miała osobny limit 18 sekund na sekcję. Dostępność linku nie decyduje o poprawności liczby. Aplikacja zapisuje w diagnostyce wyłącznie liczby prób i wynik otwarcia według sekcji i indeksu kafelka.

Linki są przechowywane tylko w pamięci. Błąd odświeżenia zachowuje poprzednią wartość i jej link. Kolejny poprawny odczyt zastępuje oba. Po restarcie wartości z cache można zobaczyć od razu, a akcje pojawiają się po uzyskaniu linków w nowym odczycie. Testy lokalne potwierdziły powiązanie linku z przyjętym wynikiem oraz brak zapisu zapytania do cache. Przebieg tej ścieżki z rzeczywistym ServiceNow oraz dwa okresy SLA pozostają do odbioru.

### Weryfikacja celów SLA

W osobnej karcie sprawdzono wszystkie jedenaście kafelków SLA dla listopada 2026. Każdy otworzył listę `task_sla`. Bezpośrednia lista z pełnym zapytaniem zwróciła zgodne zapytanie i liczebność we wszystkich jedenastu próbach. Dla kafelka Liczba zgłoszeń powtórzono porównanie dla września 2026, a po próbie przywrócono listopad. Zakres zapisany przez ServiceNow zawiera jawne daty pierwszego i ostatniego dnia miesiąca. Sprawdzony dodatkowo preset względny tworzy inne zapytanie i nie jest przyjmowany dla migawki miesiąca.

Monitor korzysta ze wspólnego mechanizmu pozyskania linków dla wszystkich sekcji. Dla SLA ustawia w karcie pomocniczej miesiąc przyjętej migawki, zatwierdza trzy kategorie, a przed aktywacją kafelka wymaga jawnego warunku dat odpowiadającego temu miesiącowi. W obecnym kodzie próba pozyskania linków ma budżet 48 sekund dla SLA i 24 sekundy dla każdej sekcji L1. Test syntetyczny w Chromium przeszedł od ustawienia okresu przez kliknięcie i odczyt ramki po zwolnienie karty pomocniczej. Pełna próba z aplikacji na rzeczywistym ServiceNow pozostaje otwarta.

### Odbiór workera w ukrytym Chromium

Na rzeczywistym ServiceNow, w osobnym profilu testowym, uruchomiono pełny odczyt workera aplikacji dla listopada 2026. Pierwszy przebieg potwierdził 3/11 linków SLA, 2/2 Wstrzymanych i 3/5 Wniosków. Po skróceniu przygotowania właściwego kontekstu i zmianie limitów drugi przebieg potwierdził 5/11 SLA, 2/2 Wstrzymanych i 4/5 Wniosków, w tym smartfony. Wszystkie wartości sekcji były kompletne. W 662 próbkach drugiej próby okno pozostawało ukryte i bez fokusu, a karta pomocnicza została zamknięta. Pozostałe cele nie przeszły jeszcze odbioru workera. Kolejna zmiana wykorzystuje powrót w historii karty, jeśli przywraca właściwy dashboard, i wymaga ponownego pomiaru.

Po wdrożeniu powrotu do dashboardu przez historię karty pełna próba workera dla listopada potwierdziła 11/11 linków SLA, 2/2 Wstrzymanych L1 i 5/5 Wniosków L1, w tym smartfony. Wszystkie linki spełniły walidację docelowej listy i okresu, gdy dotyczył SLA. W 539 próbkach Chromium pozostało ukryte i bez fokusu. Karta pomocnicza została zamknięta.

Powtórka pełnego workera dla września 2026 również potwierdziła 11/11 SLA, 2/2 Wstrzymanych L1 i 5/5 Wniosków L1. Walidacja wszystkich jedenastu zapytań SLA potwierdziła granice września. W 591 próbkach okno pozostało ukryte i bez fokusu, a karta pomocnicza została zamknięta. Osobny test Tk potwierdza, że zmiana wyboru miesiąca bez nowego odczytu pozostawia link z poprzedniej, nadal wyświetlanej migawki.

Przy jednym pierwszym odświeżeniu karta pomocnicza zgłosiła potrzebę uwierzytelnienia w każdej sekcji, choć główna karta kontynuowała odczyt. W takim przypadku monitor sprawdza sesję głównej karty. Jeśli jest nadal poprawna, ponawia nawigację dla bieżącego kafelka najwyżej raz, bez użycia historii karty i w tym samym budżecie sekcji. Sygnał utraty sesji głównej zatrzymuje pozyskiwanie linków. Diagnostyka odróżnia ponowienie od końcowego błędu.

### Dawne otwieranie list na żądanie

Odświeżenie dashboardu pobiera wyłącznie wartości. Każdy kafelek z wynikiem poza WJRUW może zlecić otwarcie listy. Tk przekazuje pojedyncze żądanie do tego samego workera, który obsługuje odczyty, wraz z okresem wyświetlanej migawki SLA. Po kliknięciu monitor pokazuje „Otwieranie listy…” i próbuje uzyskać tylko jeden link, z budżetem 18 sekund od rozpoczęcia pracy w przeglądarce. Operacja wymaga działającego monitoringu. Nieudana próba umożliwia kolejne kliknięcie bez aktualizacji dashboardu. Po zatrzymaniu monitoringu oczekujące żądanie zostaje anulowane. Linki nie są zapisywane na dysku.

Rzeczywista próba workera na osobnym profilu testowym (3 listopada, wieczorem) potwierdziła trzy osobne żądania: smartfony we Wnioskach L1, pierwszy kafelek Wstrzymanych L1 i pierwszy kafelek SLA. Diagnostyka każdego żądania zawiera `expected_count=1` i `ready_count=1`. Czasy wykonania wyniosły odpowiednio 5657, 4796 i 9688 ms. To odbiór trzech reprezentatywnych żądań nowej ścieżki; wcześniejsze porównania wszystkich 18 celów dotyczą wzorców list, a nie czasu nowej ścieżki.

Testy lokalne obejmują kolejkę i obudzenie workera, brak pracy bez kliknięcia, korelację odpowiedzi, anulowanie i spóźniony wynik, ponowienie po błędzie, kliknięcie wyniku zero i wyniku z cache, zachowanie miesiąca migawki SLA, walidację adresu oraz brak celu WJRUW. W syntetycznym Chromium sprawdzany jest cały przebieg jednego kliknięcia i zamknięcie karty pomocniczej. Przebudowa EXE pozostaje osobnym krokiem.

Końcowa regresja zakresowa: 107 testów w modułach dashboardu, jego okresu i migawek, Wniosków, kolejki otwarcia, monitoringu, harmonogramu odświeżeń, stanu filtrów, zagrożeń SLA i diagnostyki — wszystkie przeszły. Moduły korzystające z Tk uruchamiano również osobno. Kontrola odnośników dokumentacji i `diff --check` zakończyły się bez błędów.
