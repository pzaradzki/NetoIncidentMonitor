# Audyt odczytu filtrów INC / REQ / RITM / SCTASK

Data: **2 listopada 2026**. **Analiza i testy, bez zmian funkcjonalnych.** Badano obecne źródła 1.8.0, nie gotowy EXE. Wniosek: podstawowe odczyty i paginacja działają w sprawdzonych warunkach, również przy całkowicie ukrytym Chromium, ale nie ma podstaw do uznania całego procesu za niezawodny. Najważniejsze braki dotyczą potwierdzania celu odczytu oraz spójności zapisu i powiadomień.

## Zakres i źródła

Przejrzano przepływ URL → logowanie/nawigacja → wybór tabeli → kolumny/wiersze → paginacja → historia/obecność → kolejka UI/powiadomienia, wraz z harmonogramem, anulowaniem i diagnostyką. Punkty odniesienia: [architektura](../../architektura.md), [005 — kompletny odczyt](../../decyzje/005-kompletny-odczyt-listy.md), [004 — diagnostyka](../../decyzje/004-bezpieczna-diagnostyka.md), [wcześniejszy odbiór paginacji](../../plany/zakonczone/stabilizacja-paginacji.md), zasady AGENTS.md. Nie przenoszono wymagań planowanych powiadomień zagrożeń na zwykłe filtry.

Główne pliki: [app.py](../../../neto_incident_monitor/app.py) (`collect`, `empty_list`, `navigate`, `_monitor_browser`, `drain`), [list_context.py](../../../neto_incident_monitor/list_context.py), [pagination.py](../../../neto_incident_monitor/pagination.py), [service_now_urls.py](../../../neto_incident_monitor/service_now_urls.py), [columns.py](../../../neto_incident_monitor/columns.py), [filter_state.py](../../../neto_incident_monitor/filter_state.py), [history.py](../../../neto_incident_monitor/history.py), [browser_policy.py](../../../neto_incident_monitor/browser_policy.py), `browser_actions.py`, `monitoring.py`, `table_loading.py`, transporty Teams/Google Chat i `login_diagnostics.py`.

## Co już jest prawidłowo zaprojektowane

- Jeden właściciel Playwright i kolejka zdarzeń do Tk. Wynik listy jest publikowany dopiero po zakończeniu czytnika, nie po każdej stronie.
- Dopuszczony tenant i cztery typy list; normalizacja opakowanych adresów klasycznej nawigacji. Linki do rekordów są ograniczone do hosta i ścieżki odpowiedniego typu.
- W zwykłym przebiegu główna tabela, kontener i pager są związane. Czytnik sprawdza zakresy, rozmiar/total, unikalność numerów, stabilność kolejnych obserwacji i tożsamość listy między stronami. Przy wykrytej niespójności nie zwraca częściowego wyniku.
- Powrót do pierwszej strony po odtworzeniu zapamiętanej pozycji. Jedno ponowienie całego odczytu, bez ponownego klikania niepewnego „Dalej” w miejscu awarii. Stop/logowanie/odmowa dużej listy to odrębne ścieżki.
- Kolumny są odczytywane według nagłówków i indeksów, nie sztywnych pozycji. Dodatkowe pola zachowywane w `_values`; główny stan SCTASK nie jest mylony ze stanem powiązanego RITM.
- Zwykłe filtry pomijają powiadomienia dla pierwszego poprawnego odczytu; baseline utrzymuje się po restarcie. Obecność odróżnia powrót rekordu od zmiany jego wartości; `first_only` zachowuje odrębną semantykę. Nie zmieniać tego przy okazji napraw czytnika.
- UI sortuje bieżące rekordy od najwyższego numeru i ładuje większe zbiory porcjami. Nie trzeba wymuszać sortowania serwera, aby uzyskać taki widok.
- Istnieją rotowane zdarzenia `pagination_*`, korelacja odczytu i ochrona przed zapisywaniem surowych błędów/sekretów. Awaria sinka diagnostyki nie powinna zatrzymać paginacji.

## Nowa inspekcja rzeczywistej strony

Osobna karta Codex, bez edycji rekordów lub personalizacji listy. Potwierdzono główne tabele i metadane `first_row`, `last_row`, `total_rows`, `rows_per_page`, `sort`, `sort_dir`. Aktualny rozmiar strony wynosił 20. Kontrolki pagera tej instancji nie miały `data-type=list_nav_*`; działały istniejące alternatywy oparte na etykietach. Nie można polegać wyłącznie na jednym wariancie atrybutu.

| Typ | Tabela / właściwe linki | Ważne różnice kolumn |
| --- | --- | --- |
| INC | `incident_table`, `/incident.do` | Numer, krótki opis, stan, priorytet, daty i dodatkowe pola; dekoracyjne komórki poprzedzają dane |
| SCTASK | `sc_task_table`, `/sc_task.do` | `state` i osobno `request_item.state`; osoba z `request.requested_for` |
| REQ | `sc_request_table`, `/sc_request.do` | `requested_for`, `opened_by`, `request_state`, `due_date`; w tym widoku brak krótkiego opisu i daty utworzenia |
| RITM | `sc_req_item_table`, `/sc_req_item.do` | `cat_item`, `stage`, `request`, `requested_for`, `request.opened_by`, termin i ilość; brak klasycznej kolumny `state` w tym widoku |

Brak pola w widoku nie oznacza błędu sieci lub pustej listy. `stage` RITM nie jest automatycznie równoważne `state`. W REQ stan wniosku zachowuje się obecnie jako `sn:request_state`; kanoniczne `state` pozostaje puste. W RITM etap jest zachowany jako `sn:stage`. Potrzebny jawny kontrakt tych różnic, zamiast sugerowania, że każdy typ ma wszystkie pola INC.

## Rzeczywiste próby silnika Python

W osobnym, wolnym zachowanym profilu testowym uruchomiono obecne `read_all`, `ListTarget`, `collect`, `navigate` i `BrowserRuntime`. Nie uruchamiano pełnego App/transportów; nie zapisywano odczytów do historii użytkownika. Rekordy istniały tylko w pamięci procesu; utrwalono agregaty, klucze schematu i bezpieczne zdarzenia. Nie zmieniano rozmiaru strony, zapisanych filtrów, dat lub sortowania użytkownika.

| Próba | Widoczne | Całkowicie ukryte | Zakres dowodu |
| --- | --- | --- | --- |
| INC, lista TEST | 530 rekordów / 27 stron, 84,77 s | 530 / 27, 82,75 s | Pełny odczyt; ten sam zbiór numerów w obu przebiegach, bez brakujących linków w obserwacjach |
| SCTASK, lista bieżącego użytkownika | 3 / 1, 2,66 s | 3 / 1, 1,44 s | Pełny odczyt; ten sam zbiór w obu przebiegach |
| REQ, duża lista | 60 / 3, 9,61 s, kontrolowane anulowanie | 60 / 3, 9,20 s, kontrolowane anulowanie | Przejścia stron i Stop; **nie pełny odczyt 2237 rekordów** |
| RITM, duża lista | 60 / 3, 10,94 s, kontrolowane anulowanie | 60 / 3, 11,66 s, kontrolowane anulowanie | Przejścia stron i Stop; **nie pełny odczyt 1508 rekordów** |
| REQ, podzbiór 3 odczytanych numerów | 3 / 1, 1,45 s | 3 / 1, 1,33 s | Pełny wynik zgodny z wybranym podzbiorem rzeczywistych rekordów |
| RITM, podzbiór 3 odczytanych numerów | 3 / 1, 1,59 s | 3 / 1, 1,42 s | Jak wyżej |
| Puste INC/REQ/RITM/SCTASK | Każdy typ: 0 / 1 | Każdy typ: 0 / 1 | Osiem prób z tymczasowym warunkiem numeru bez trafień; każda poprawna, około 1,09–1,25 s |

Łącznie **20 prób: 16 pełnych wyników i 4 celowo przerwane po trzeciej stronie**. Nie liczyć celowego Stop jako awarii ani jako zaliczonej kompletności dużej listy. Wszystkie próby ukryte miały zero próbek widocznego/minimalizowanego okna i zero próbek własnego Chromium na pierwszym planie. Nie używano podtrzymania renderowania analityki — klasyczne listy przeszły w obecnej aktywności `filters`.

To pojedyncze przebiegi każdego wariantu, nie statystyczna gwarancja szybkości. Używano istniejącego profilu/cache, nie nowej instalacji. Stan danych mógł zmieniać się między próbami. Porównano membership pełnych list, nie transakcyjną kopię wszystkich pól z jednej chwili. Po próbach osobne Chromium zamknięto, profil zachowano. Hash modułów aplikacji przed/po był identyczny w obu seriach.

## Potwierdzone luki i zalecenia

P1 = poprawność wyniku lub trwałego stanu; P2 = odporność/diagnostyka i kontrakt danych; P3 = usprawnienie. „Kontrprzykład” oznacza syntetyczny test obecnego kodu, nie incydent zaobserwowany na produkcyjnym ServiceNow.

| ID / priorytet | Dowód i skutek | Co zmienić |
| --- | --- | --- |
| F1 / P1 | `ListTarget.find` sprawdza host/ścieżkę/typ tabeli, a `state.identity` śledzi zmianę query dopiero względem pierwszej obserwacji. Kontrprzykład: żądanie `active=true`, tabela o stałym `query=active=false` — zaakceptowano 2 rekordy. Poprawny pager nie dowodzi właściwego filtra | Potwierdzać efektywny kontekst żądania od pierwszej strony: właściwy typ/lista/widok i warunki. Uwzględnić normalizację, ACL, rozwinięcia dynamiczne i sortowanie; nie zastępować tego naiwnym porównaniem dowolnych napisów query. Rozbieżność = brak zatwierdzenia |
| F2 / P1 | `wait_page` przy braku `ListTarget` używa `empty_list(page,url)`, który szuka komunikatu w całej ramce. Trzy obserwacje obcego pustego komunikatu przy braku głównej tabeli zwróciły sukces `{}`. To może skasować obecność i później wytworzyć fałszywe powroty | Wymagać dodatniego dowodu pustego wyniku konkretnej głównej listy. Brak tabeli/metadanych, odmowa dostępu i nieznany dokument pozostają odrębnymi stanami. Zdefiniować jawny kontrakt pustej listy bez tabeli, jeśli rzeczywista strona go wymaga |
| F3 / P1 | `collect` i `ListTarget.state` dopuszczają dowolny prefiks z czterech typów niezależnie od bieżącej tabeli. W syntetycznej tabeli INC z linkami REQ czytnik zwrócił sukces | Powiązać prefiks rekordu, typ tabeli i ścieżkę linku z jednym kontraktem żądanego typu. Zgłaszać niespójność zamiast pomijać lub przyjmować obce rekordy |
| F4 / P1 | `App._monitor_browser`: osobno `history.add_many` → checkpoint → `membership.commit` → kolejka UI. Wstrzyknięta odmowa zapisu membership zostawiła nowy wpis w historii i starą obecność. Stop między zapisami ma podobne okno niespójności | Projekt zatwierdzenia historii/obecności z jedną granicą logiczną i odzyskiwaniem po awarii. Sam atomowy rename każdego pliku osobno nie jest transakcją. UI ma znać wynik zapisu; błąd nie może udawać pełnego sukcesu |
| F5 / P1 | Membership jest zapisany przed zdarzeniem powiadomienia; istniejące transporty nie mają trwałego zamiaru ani identyfikatora alertu. Po restarcie między zapisem obecności a doręczeniem ten sam INC nie odtwarza powiadomienia (potwierdzono lokalnie). Pełna kolejka/nieudany kanał również nie cofają presence | Uzgodnić gwarancję powiadomień. Powiązać zdarzenie wykrycia z trwałym zamiarem, przyjęciem i wynikiem transportu; współdzielić mechanizm z przyszłymi zagrożeniami. Nie zmieniać reguły cichego pierwszego odczytu. Nie obiecywać exactly-once ani automatycznie powtarzać niepewnego POST |
| F6 / P2 | Brak wszystkich metadanych i rozpoznanego pagera jest traktowany jako poprawna lista legacy. Syntetyczna tabela z nierozpoznanym „Load another page” została przyjęta jako kompletna | Domyślnie wymagać znanego kontraktu kompletności; ścieżkę unpaginated dopuścić dla pozytywnie rozpoznanego wariantu, nie na podstawie samego braku selektorów. Nieznany pager/metadane = wynik niepotwierdzony |
| F7 / P2 | `ColumnDiscovery.discover` rzuca zwykły RuntimeError, mimo komunikatu sugerującego ponowne pobranie. Przy zmianie kolumn na drugiej stronie potwierdzono 1 nawigację i RuntimeError — bez drugiej próby. Ten sam obiekt discovery przeżywa ponowienie `read_all` | Typowana przyczyna zmiany schematu w tym samym właścicielu retry; nowy bufor kolumn i danych na każdą próbę, publikowany dopiero po pełnym sukcesie. Sprawdzać identyfikację/mapowanie pól, nie tylko zbiór kluczy; zmiany etykiet nie powinny po cichu zostawić starego schematu |
| F8 / P2 | REQ/RITM faktycznie różnią się od INC; canonical `state` REQ puste przy zachowanym `sn:request_state`. Domyślna syntetyczna próba REQ w istniejących testach ma `short_description`, którego realny widok nie udostępnia | Opisać wymagane/optional pola per typ i jawne aliasy. Stan wniosku, etap i stan zadania nie są automatycznie tożsame. Testować rzeczywiste zestawy nagłówków; puste optional pole nie może być ani awarią, ani zmyśloną wartością |
| F9 / P2 | `safe_record_url` waliduje host/ścieżkę, ale przyjmuje brakujące lub błędne ID rekordu; kontrprzykład `sys_id=not-an-id` zaakceptowany. Wiersz nie ma trwałej walidowanej tożsamości poza numerem | Walidować tożsamość numer/ID/link z obserwacji wiersza. Dopuszczać tylko znany format odnośnika odczytu, bez dowolnych parametrów zmieniających zachowanie. Zachować numer jako tekst, gdy bezpiecznego linku nie da się potwierdzić |
| F10 / P2 | `FilterState` nie waliduje struktury pliku przed użyciem; `[]` daje AttributeError, uszkodzony JSON — JSONDecodeError. Inicjalizacja jest przed pętlą filtrów, więc błąd może zatrzymać cały monitoring | Walidacja schematu/typów/wersji i kontrolowane odzyskanie albo czytelny stan wymagający naprawy. Nie resetować po cichu presence/ever, nie nadpisywać uszkodzonego źródła nowym baseline. Podobnie sprawdzić wczytywanie historii |
| F11 / P2 | `pagination_complete` kończy tylko czytnik; następujące błędy historii/membership są logowane tekstowo z typem, etapem, indeksem i czasem, bez tego samego read ID i bez szczegółowego wyniku zapisu. Typ/ogólne „Błąd odczytu” nie spełniają w pełni najnowszych zasad diagnostyki | Jeden kontekst całego odczytu filtra do końca commit/kolejki; strukturalne kody etapów zapisu i wyników, korelacja run/read/attempt/event. UI powinno rozróżnić niespójność listy, brak kolumn, sieć/sesję i zapis na dysku. Allowlisty oraz testy, że pola naprawdę trafiają do logów |
| F12 / P2 | 15 s gotowości strony i 1800 s całej paginacji nie są propagowane jako jeden budżet do wszystkich wywołań. `collect.evaluate_all` nie ma jawnego lokalnego timeoutu, część count/is_visible/callbacków ma własne oczekiwania. `approve_large_list` czeka do 15 s bez `ACTION_TICK` | Ujednolicić aktywny budżet przez istniejące `read_budget`/checkpoint; krótkie, przerywalne obserwacje, odrębne oczekiwanie na użytkownika. Podczas promptu nadal obsługiwać polecenia okna/Stop. Nie zmniejszać limitów wyłącznie na podstawie jednej szybkiej próby |

F1–F3 i F6 są udowodnionymi kontrprzykładami na syntetycznych stronach. Nie stwierdzono, że bieżące rzeczywiste listy zwracają zły filtr, mieszane typy lub nieznany pager. F4/F5/F10 potwierdzono lokalnie na syntetycznych danych i plikach; dla F4 odtworzono kolejność obecnego pipeline, nie awarię rzeczywistego dysku podczas pełnego App. F7 obejmuje rzeczywiste `read_all` z syntetyczną zmianą DOM. F12 jest ryzykiem z przeglądu kodu; nie symulowano zawieszenia silnika Chromium ani nie zmieniano sieci systemu.

## Testy i granice odbioru

- **86 istniejących testów w 16 modułach: wszystkie zaliczone, bez pominięć.** List context, paginacja i kontrolki, duże listy, REQ/RITM, SCTASK, obecność/historia, dynamiczne kolumny, niezawodność, monitoring, widoki, kolejność filtrów, szablony/powiadomienia i diagnostyka. Uruchamiano moduły w osobnych procesach. To regresja zakresowa, nie pełny zestaw aplikacji.
- Dodatkowe kontrprzykłady celowo dokumentują **niepożądany wynik obecnego kodu**; nie są „zaliczonymi testami nowej poprawki”. Minimalne fixture zawierają dane syntetyczne, bez kopiowania HTML lub treści zgłoszeń.
- Powiązanie tabeli/pagera, pierwsza strona, ciągłość, aktualne 20 wierszy i pełna ostatnia strona INC sprawdzone ponownie natywnie. Strony 100/205 sprawdzono syntetycznie; wcześniejsze rzeczywiste próby 100 opisuje historyczny plan. W tym audycie nie zmieniano preferencji wielkości strony.
- Duże REQ/RITM: nie wykonano przejścia do ostatniej strony wielotysięcznego zbioru ani rzeczywistego >1000 promptu. Małe podzbiory potwierdzają pełny wynik, duże — pierwsze 3 strony i odrzucenie częściowego wyniku przy Stop.
- Wygaśnięcie sesji i zmiany DOM/rozmiaru/licznika testowane lokalnie. Nie wymuszano rzeczywistego logout, błędnych haseł, MFA, zerwania sieci, zmiany uprawnień lub awarii dysku. Naturalne odzyskiwanie SSO ma osobny raport; nie uznawać go automatycznie za dowód każdego przerwania filtra.
- Nie wysyłano wiadomości, nie testowano gotowego EXE, nie wykonywano eksportu danych ani zapisu do profilu działającego monitora.

Artefakty lokalne (ignorowane): `data/filter-read-audit/{native-results.json,edge-native-results.json,regression.json,regression-summary.json,counterexamples.json,schema-counterexample.json,persistence-counterexamples.json}` i wyjścia modułów testowych. Skrypty: `data/study_filter_reads.py`, `study_filter_edge_reads.py`, `run_filter_audit_tests.py`, `probe_filter_audit_contracts.py`, `probe_filter_persistence.py`. Pierwsze uruchomienie pomocniczego route miało złą sygnaturę, a próba tempfile napotkała ograniczenie sandboxa; skorygowano wyłącznie lab i ponowiono. Tych problemów nie zaliczono do usterek produktu.

## Proponowane etapy aktualizacji

Na podstawie tego audytu przygotowano osobny [szczegółowy plan A–G](../../plany/zakonczone/stabilizacja-odczytu-filtrow.md), obejmujący moduły, zależności, migrację, testy i kryteria odbioru. Poniższe punkty zachowują pierwotny skrót zaleceń audytu.

1. **Kontrakt celu i pustego wyniku (F1–F3, F6, F9):** doprecyzować na rzeczywistym DOM żądanie/efektywny filtr, typ, pusty stan i ID. Najpierw regresje kontrprzykładów, następnie minimalne uszczelnienie wspólnych mechanizmów. Odbiór: zły/niepewny kontekst nigdy nie zatwierdza presence.
2. **Schematy i kontrolowane odzyskiwanie (F7/F8):** kontrakt per typ, aliasy i optional pola, reset discovery między próbami, typowane błędy. Odbiór: zmiana schematu daje najwyżej jedno pełne ponowienie z czystym buforem, brak półstarego schematu lub zgadywania wartości.
3. **Zatwierdzanie i restart (F4/F10):** wspólna granica stanu historii/obecności, obsługa uszkodzonych plików, Stop/awaria w każdym punkcie. Odbiór: brak częściowego zatwierdzenia i bezpieczne wznowienie bez utraty starego stanu; jawna aktualność UI.
4. **Intencje powiadomień (F5):** uzgodnić trwałość i zachowanie błędów kanałów; współdzielić przyszły mechanizm z zagrożeniami zamiast dublować transporty. Odbiór: baseline nadal cichy, powrót/first_only zgodne z ustawieniami, pełna kolejka nie udaje wysłania, niepewne doręczenie jawne.
5. **Budżety i diagnostyka (F11/F12):** projektować od etapu 1, domknąć odbiór całego pipeline tutaj. Odbiór: czasy, kody i korelacja dla czytnika/zapisu/kanałów; Stop i Pokaż przeglądarkę obsługiwane także podczas oczekiwania; brak sekretów/rekordów w logach, awaria sinka bez wpływu na funkcję.
6. **Odbiór całości:** wszystkie cztery typy pełne/puste/multi-page, źródła i osobno EXE po zleceniu. Poszerzyć realne próby o 100 wierszy i dużą końcową stronę REQ/RITM, zachowując/przywracając preferencje. Porównać widoczne/ukryte oraz koszty czasu. Nie wymagać testowego wysyłania na rzeczywiste webhooki do zaliczenia testów automatycznych.

Etapy są propozycją po audycie, **nie zgodą na wdrożenie**. Obecne mechanizmy paginacji i ukrycia warto zachować i rozszerzyć. Nie ma potrzeby przepisywania wszystkiego ani wprowadzania równoległych przeglądarek. Kontrola zakresów/duplikatów nadal nie zapewni transakcyjnej kopii zmieniającej się bazy ServiceNow; ten limit powinien pozostać jawny.
