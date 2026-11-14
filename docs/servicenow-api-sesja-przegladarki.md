# ServiceNow REST API w zalogowanej sesji Chromium

W bieżących źródłach **Dashboard SLA**, **Wstrzymane L1**, **Wnioski L1** i **Incydenty zagrożone SLA** korzystają z REST na karcie `SharedSession`. Ręczne i cykliczne odczyty przechodzą przez tę samą kolejkę. Filtry użytkownika nadal korzystają z czytnika list w interfejsie ServiceNow. [Decyzja 033](decyzje/033-odczyty-analityki-przez-api.md) · [Kontrakt odczytu](kontrakty/kontrakt-odczytu-dashboardu.md)

## Odczyty i zapis

| Zakres | Źródło | Zapis wyniku |
| --- | --- | --- |
| Dashboard SLA | Jedno zapytanie Aggregate API do `task_sla` z grupowaniem po `task.priority,has_breached` | Migawka wybranego miesiąca, z której aplikacja oblicza WJRUW. |
| Wstrzymane L1 | Dwie agregacje w `incident_metric` dla progów 7 i 14 dni | Migawka stanu bieżącego. |
| Wnioski L1 | Pięć agregacji w `sc_task`, także dla pustego przypisania i zmiennej katalogowej | Migawka stanu bieżącego. |
| Incydenty zagrożone SLA | Table API w `task_sla`, do 100 wierszy na stronę i 10 stron | Jedna zweryfikowana migawka dla liczników, bieżącej listy, historii i alertów. |

Każda sekcja dashboardu ma własną migawkę w `dashboard-cache.json`. Czas pełnej aktualizacji zmienia się po sukcesie wszystkich trzech sekcji. Zagrożenia liczą rekordy SLA według kategorii i grupują zgłoszenia według INC. Niepełny odczyt zachowuje poprzednią listę i stan powiadomień. [Czytniki dashboardu](../neto_incident_monitor/dashboard_api.py) · [Czytnik zagrożeń](../neto_incident_monitor/threatened_api.py)

## Uruchomienie odczytów API

Uruchom `.venv\Scripts\python.exe tools/import_dashboard_api.py data/dashboard-api-kafelki.xlsx`, aby utworzyć lokalną definicję `data/dashboard-api.json`. Bieżąca kopia w katalogu projektu pochodzi z 24 filtrów. Uruchom źródła poleceniem `.venv\Scripts\python.exe launcher.pyw`. Instalacja EXE korzysta z `%LOCALAPPDATA%\NetoIncidentMonitor\dashboard-api.json`.

Po zalogowaniu porównaj Dashboard SLA dla dwóch miesięcy oraz Wstrzymane i Wnioski L1. W widoku zagrożeń porównaj sześć kafelków i bieżącą listę możliwie blisko w czasie. Uwzględnij niepusty wynik, gdy będzie dostępny. Na wybranych pozycjach porównaj kategorię, pozostały czas i procent. Do zgłoszenia wystarczy nazwa sekcji i różnica. [Plan i kryteria odbioru](plany/zakonczone/dashboard-servicenow-api.md)

## Uwierzytelnianie

1. Użytkownik loguje się normalnie przez SSO w Chromium aplikacji. `SharedSession` potwierdza sesję ServiceNow i pozostaje właścicielem karty. W próbie grupowanej dokumentem roboczym była strona startowa SOW (`/now/sow/home`). Wczesna próba użyła dokumentu listy SLA osadzonego w ramce `gsft_main`. SOW wystarczyło, więc odczyt API nie wymaga nawigacji na dashboard ani listę.
2. W kontekście dokumentu ServiceNow wykonujemy `fetch` do tej samej instancji. Chromium samo dołącza ciasteczka pasujące do adresu. Opcja `credentials: 'same-origin'` ogranicza ich użycie do tego samego originu. Aplikacja nie odczytuje wartości ciasteczek i nie składa nagłówka `Cookie`.
3. Dokument udostępnia bieżącą wartość `window.g_ck`. JavaScript przekazuje ją w nagłówku `X-UserToken`, a do Pythona wracają wynik odczytu i metadane odpowiedzi. Po odnowieniu sesji kolejne żądanie używa aktualnej wartości tokenu.
4. Przed żądaniem transport sprawdza origin i obecność tokenu. Gdy potrzeba, wraca na SOW w tej samej karcie. Wysyła `GET` do jednej z dozwolonych tras. `redirect: 'manual'` pozwala rozpoznać przekierowanie bez przechodzenia pod jego adres. HTTP 401 i przekierowanie uruchamiają mechanizm odzyskiwania sesji. HTTP 403 oznacza odmowę dostępu, a HTTP 429 kończy próbę bez natychmiastowego ponowienia. Wywołanie ma limit do 5 sekund w ramach wspólnego budżetu sekcji. [Transport i klasyfikacja błędów](../neto_incident_monitor/analytics_api.py)

Samo wejście pod adres API w pasku przeglądarki zwróciło `User is not authenticated`. Taka nawigacja nie ustawiła nagłówka `X-UserToken`. Na tym samym koncie żądanie wykonane z aktywnego dokumentu sesji zwróciło HTTP 200. Konto nie miało dostępu do REST API Explorer, który ma osobne wymagania dotyczące ról. Dostęp do kolejnych tabel i endpointów trzeba potwierdzać oddzielnie. [Uwierzytelnianie REST i role ServiceNow](https://www.servicenow.com/docs/r/api-reference/rest-api-explorer/c_RESTAPI.html) · [Przykład ServiceNow z nagłówkiem sesji](https://developer.servicenow.com/blog.do?p=%2Fpost%2Fdebugging-inbound-rest-calls-and-the-business-rules%2Facls-that-impact-them%2F)

## Agregacja Dashboard SLA

- **Filtr.** Składamy go przed żądaniem z lokalnej konfiguracji i pierwszego oraz ostatniego dnia wybranego miesiąca. Zachowujemy zweryfikowaną składnię zakresu `task.opened_atBETWEENjavascript:gs.dateGenerate('YYYY-MM-DD','start')@javascript:gs.dateGenerate('YYYY-MM-DD','end')`. Pozostałe warunki to lokalizacje (`task.locationIN`), stany (`task.stateIN1,2,3,6,7,8`), przypisane osoby (`task.assigned_toIN`), grupa przypisania (`task.assignment_group=`), `stage!=cancelled`, `sla.nameLIKE6/22` i `task.ref_incident.parent_incidentISEMPTY`. Lokalną konfigurację przygotowuje importer arkusza. W odbiorze wdrożenia użyto zestawów 104 lokalizacji i 46 osób. Po zmianie definicji dashboardu lub składu grupy przygotuj konfigurację ponownie i porównaj wyniki z ServiceNow.
- **Odpowiedź.** W trybie grupowanym `result` jest tablicą. Każdy element ma `stats.count` i tablicę `groupby_fields`. Rozpoznajemy pola grupy po nazwach, ponieważ kolejność w odpowiedzi może się różnić od kolejności w żądaniu. W ADEO licznik był tekstem z cyframi, priorytet tekstem, a flaga `has_breached` miała wartości `'true'` lub `'false'`. Odczyt P2 bez grupowania zwracał `result.stats.count`.
- **Liczniki.** „Liczba zgłoszeń” to suma wszystkich grup, również grup z priorytetem poza P1–P5, jeśli wystąpią. „Zgłoszenia Pn” to suma obu grup danego priorytetu. „Przekroczone Pn” bierze tylko grupę z flagą `true`. Brak pojedynczej grupy w poprawnej, kompletnej odpowiedzi oznacza zero. Pustą tablicę dla całego miesiąca sprawdzono na danych syntetycznych. WJRUW liczymy istniejącą funkcją `calculate_wjruw` z tej samej migawki.
- **Walidacja.** Odrzucamy błędny status HTTP, odpowiedź inną niż oczekiwany JSON, niepełne pola grup, duplikaty kluczy grup i sygnał kolejnej strony. Brak danych z powodu błędu zachowuje ostatnią poprawną migawkę. [Parametry i schemat Aggregate API](https://www.servicenow.com/docs/r/api-reference/rest-apis/c_AggregateAPI.html)

## Historyczne wyniki pilotażu

| Próba | Wynik |
| --- | --- |
| P2 w aplikacji | HTTP 200. Wrzesień 64, październik 191, listopad 116. Zarejestrowany czas od rozpoczęcia odczytu 125–187 ms, poza kolejką. |
| Grupowany SLA, wrzesień 2026 | HTTP 200. Razem 2715, zgodność 11/11 z dashboardem. Jeden P1. Odpowiedź w 1,08 s. |
| Grupowany SLA, październik 2026 | HTTP 200. Razem 3225, zgodność 11/11. Brak grupy P1 zgodny z zerem w dashboardzie. Odpowiedź w 0,64 s. |

Próby grupowane wykonano w osobnym Chromium po zwykłym logowaniu na stronie SOW. Dodatkowe zapytanie kontrolne bez grupowania potwierdziło sumę w obu miesiącach. Pełne filtry 11 kafelków SLA zweryfikowano na ich listach docelowych. Opcja **Kopiuj zapytanie** na wcześniejszym warunku może zwrócić tylko początek filtra. Podczas analizy warto zweryfikować pełny filtr listy i jej licznik. Pilotaż miał osobny przycisk do odczytu. Odbiór właściwej implementacji, w tym wyniki Windows i Chromium, opisuje [zakończony plan migracji](plany/zakonczone/dashboard-servicenow-api.md).
