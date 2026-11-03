# Kontrakt odczytu dashboardu i zagrożeń

Stan kontraktu: 1 listopada 2026; lokalny build 1.8.0 z 2 listopada zawiera wdrożenie i przeszedł offline smoke-test. Nie jest to pełny rzeczywisty test odczytu z EXE. Odbiór: [raport](../verification/dashboard-stabilization-verification.md).

| Sekcja | Wymagane dane | Ustawienia |
| --- | --- | --- |
| SLA | Liczba zgłoszeń; Zgłoszenia P1–P5; Przekroczone P1–P5 (11 liczb). WJRUW wyliczany z tego samego kompletu. | Wybrany miesiąc; wszystkie statusy, lokalizacje i osoby przypisane. |
| Wstrzymane L1 | >14 dni i >7 dni (2 liczby). | Wszyscy agenci L1; stan bieżący, nie zakres miesiąca SLA. |
| Wnioski L1 | Otwarte, >7 dni, >14 dni, nieprzypisane (4 liczby). | Wszyscy agenci L1; stan bieżący. |
| Zagrożenia | P1–P5 oraz Podjęcie (6 liczb). | Właściwa zakładka zagrożeń; progi 1/2/4 h, 1/2 dni i 5 min, także po terminie. |

Każdy zaakceptowany zestaw musi pochodzić z właściwego dashboardu i zakładki, po zastosowaniu wymaganych ustawień, z jednoznacznych widżetów bez lokalnego ładowania. Wartości: pełne nieujemne liczby całkowite; zero nie jest brakiem danych. Krótka stabilność jest zabezpieczeniem dodatkowym, nie dowodem świeżości.

Wszystkie cztery sekcje używają `read_tile/read_scores`. Nie ma fallbacku do odczytu globalnego. Kategorie są osobno zatwierdzane; brak obserwowalnego potwierdzenia odświeżenia powoduje odtworzenie dokumentu i ustawień. Kontrolki i karty mogą powstać dopiero po przewinięciu. Odczyt nie wymaga zmiany samej liczby.

Najwyżej dwie próby we wspólnym aktywnym budżecie 60 s; pierwsza do 39 s. Oczekiwanie na ręczne logowanie jest rozliczane osobno. Brak pewności po kliknięciu nie powoduje jego ponownego dostarczenia w tej samej próbie. Budżet jest kooperacyjny i nie stanowi gwarancji zakończenia zablokowanego procesu Chromium.

Cache schematu 2 przechowuje niezależne, kompletne zestawy trzech sekcji dashboardu. Każdy ma własny czas sukcesu, ostatnią próbę i kontekst. Migracja dawnego cache nie przypisuje sekcjom wymyślonych dat. Błąd nie odmładza wyniku ani nie wygasza alarmu zagrożeń. Szczegóły: [decyzja 006](../decisions/006-odczyt-sekcji-dashboardu.md).

Dolny komunikat pokazuje jeden timestamp ostatniego zakończonego sukcesem odczytu całego dashboardu. Czasy sekcji pozostają wewnętrzne. Znacznik jest przesuwany dopiero po przyjęciu kompletu SLA/Wstrzymanych/Wniosków z tego samego żądania; częściowy odczyt, błąd, Stop i stare wyniki go nie odmładzają. Opcjonalne `last_complete_read_at` w cache schematu 2 zachowuje go między uruchomieniami. Dla starszego cache bez tego dowodu pokazujemy „—” do następnego pełnego sukcesu, zamiast zgadywać z maksimum dat sekcji. Zdarzenie `dashboard_complete` zapisuje zakończenie z korelacją żądania; zapis cache korzysta z dotychczasowej diagnostyki. To poprawka źródeł po buildzie 1.8.0.

## Okres i cykl żądania — poprawka źródeł po buildzie 1.8.0

Miesiąc i rok są zablokowane od kolejkowania żądania dashboardu do pasującego końca, także podczas logowania, ponowień i restartu Chromium. Guard zmiennych nie pozwala programowej zmianie unieważnić aktywnego ID. Koniec ze starym ID/okresem nie odblokowuje nowszego żądania. Stop i błędy kolejkowania/startu zwalniają kontrolki; samo przełączenie widoku tego nie robi.

Wyniki mają ID i okres żądania; inny okres lub wynik po zakończeniu nie zastępuje danych ani cache. Zmiana dat w bezczynności dotyczy tylko aktualności SLA; stare kafelki pozostają podpisane okresem ich odczytu. Nie unieważnia ona bieżących Wstrzymanych/Wniosków. Szczegóły: [010](../decisions/010-cykl-zycia-zadania-dashboardu.md). Poprawka nie jest jeszcze w zbudowanym EXE.

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

Powyższe 48 testów i dwa pomiary opisują pierwszy etap prac. Późniejsze wdrożenie obejmuje wspólny czytnik, kontekst, budżet, odzyskiwanie i cache. Aktualne wyniki oraz rozróżnienie testów źródeł i EXE znajdują się w [raporcie odbioru](../verification/dashboard-stabilization-verification.md).

## Widoczność i renderowanie

Próba sekcji korzysta z `BrowserRuntime.dashboard_read`. Przy ukryciu: potwierdzona sesja → docelowy dashboard → lokalne podtrzymanie renderowania → normalne kontrolki i czytnik → sprzątanie. Gotowa kontrolka daty nie jest warunkiem uruchomienia mechanizmu. Logowanie zatrzymuje go, a ręczna obsługa pokazuje i fokusuje okno. Błąd `rendering_unavailable` nie jest samodzielnie ponawiany; zachowuje poprzedni sukces. Użytkownik może pokazać przeglądarkę i zlecić nowy widoczny odczyt.

`rendering_start/deferred/error/stop` zawierają stałą przyczynę, czas, `frame_count`, `ack_count`, `payload_bytes` (długość zakodowanych danych) i `cleanup_errors`, nigdy same dane ramek. `category_check_recovered/failed` opisują wynik obserwacji po dostarczonym zaznaczeniu. Niezaznaczona lub pośrednia kategoria nie jest uznawana za poprawną. Zasady: [007](../decisions/007-ukryty-dashboard.md); [odbiór wdrożenia](../verification/hidden-dashboard-verification.md).

Weryfikacja wspólnego timestampu (2 listopada 2026): 43 testy zakresowe zaliczone; po doprecyzowaniu testu starego/uszkodzonego znacznika ponowiono 7 testów snapshotów, także zaliczonych. Logi lokalne: `data/dashboard-single-timestamp-final-tests.log`, `data/dashboard-single-timestamp-cache-tests.log`. Nie testowano nowego EXE ani nie zmieniano interakcji ServiceNow.
