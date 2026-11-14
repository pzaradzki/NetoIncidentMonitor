# ServiceNow REST API w zalogowanej sesji Chromium

## Uruchomienie odczytów API

Uruchom `.venv\Scripts\python.exe tools/import_dashboard_api.py data/dashboard-api-kafelki.xlsx`, aby utworzyć lokalną definicję `data/dashboard-api.json`. Bieżąca kopia w katalogu projektu pochodzi z 24 filtrów. Uruchom źródła poleceniem `.venv\Scripts\python.exe launcher.pyw`. Instalacja EXE korzysta z `%LOCALAPPDATA%\NetoIncidentMonitor\dashboard-api.json`.

Po zalogowaniu porównaj Dashboard SLA dla dwóch miesięcy oraz Wstrzymane i Wnioski L1. W widoku zagrożeń porównaj sześć kafelków i bieżącą listę możliwie blisko w czasie. Uwzględnij niepusty wynik, gdy będzie dostępny. Na wybranych pozycjach porównaj kategorię, pozostały czas i procent. Do zgłoszenia wystarczy nazwa sekcji i różnica. [Plan i kryteria odbioru](plany/zakonczone/dashboard-servicenow-api.md)

Stan wiedzy z 14 listopada 2026. Materiał referencyjny do przyszłej migracji odczytów Neto Incident Monitor. Opisuje próby na instancji ADEO i kod z gałęzi `codex/dashboard-p2-api-pilot`. Na `master` dashboard nadal odczytuje widżety z interfejsu ServiceNow. Zakres obecnego rozwiązania opisuje [architektura aplikacji](architektura.md).

## Uwierzytelnianie

1. Użytkownik loguje się normalnie przez SSO w Chromium aplikacji. `SharedSession` potwierdza sesję ServiceNow i pozostaje właścicielem karty. W próbie grupowanej dokumentem roboczym była strona startowa SOW (`/now/sow/home`). Wczesna próba użyła dokumentu listy SLA osadzonego w ramce `gsft_main`. SOW wystarczyło, więc odczyt API nie wymaga nawigacji na dashboard ani listę.
2. W kontekście dokumentu ServiceNow wykonujemy `fetch` do tej samej instancji. Chromium samo dołącza ciasteczka pasujące do adresu. Opcja `credentials: 'same-origin'` ogranicza ich użycie do tego samego originu. Aplikacja nie odczytuje wartości ciasteczek i nie składa nagłówka `Cookie`.
3. Dokument udostępnia bieżącą wartość `window.g_ck`. W obrębie tego samego wywołania JavaScript przekazujemy ją do ServiceNow w nagłówku `X-UserToken`. To token sesji używany do ochrony żądań przeglądarkowych. Ciasteczka wiążą żądanie z sesją użytkownika. Token pobieramy z bieżącego dokumentu przy każdym żądaniu, a do Pythona zwracamy jedynie zweryfikowane liczniki i status. Po odnowieniu sesji kolejny odczyt korzysta z aktualnej wartości.
4. Przed żądaniem sprawdzamy dokładny origin instancji i obecność tokenu. Adres API jest stały, metoda to `GET`, a `redirect: 'error'` zatrzymuje przekierowanie, również do logowania. Nie przenosimy sesji do osobnego klienta HTTP, nie kopiujemy tokenu z konsoli i nie utrwalamy poświadczeń w kodzie, konfiguracji ani logach.

Samo wejście pod adres API w pasku przeglądarki zwróciło `User is not authenticated`. Taka nawigacja nie ustawiła nagłówka `X-UserToken`. Na tym samym koncie żądanie wykonane z aktywnego dokumentu sesji zwróciło HTTP 200. Konto nie miało dostępu do REST API Explorer, który ma osobne wymagania dotyczące ról. Dostęp do kolejnych tabel i endpointów trzeba potwierdzać oddzielnie. [Uwierzytelnianie REST i role ServiceNow](https://www.servicenow.com/docs/r/api-reference/rest-api-explorer/c_RESTAPI.html) · [Przykład ServiceNow z nagłówkiem sesji](https://developer.servicenow.com/blog.do?p=%2Fpost%2Fdebugging-inbound-rest-calls-and-the-business-rules%2Facls-that-impact-them%2F)

## Żądanie dla Dashboard SLA

Przykład pokazuje kontrakt transportu. `originInstancji` oznacza sprawdzony, stały origin ADEO. `filtr` to gotowe zapytanie wygenerowane lokalnie dla wybranego okresu. Ten fragment działa wewnątrz dokumentu ServiceNow na wątku właściciela karty, np. przez `page.evaluate`. Kod czytnika w pilotażu znajduje się w `neto_incident_monitor/dashboard_sla_api.py`.

```javascript
async ({originInstancji, filtr}) => {
    if (location.origin !== originInstancji || typeof window.g_ck !== 'string' || !window.g_ck) {
        return {reason: 'no_session'};
    }
    const url = new URL('/api/now/stats/task_sla', originInstancji);
    url.search = new URLSearchParams({
        sysparm_query: filtr,
        sysparm_count: 'true',
        sysparm_group_by: 'task.priority,has_breached',
    });
    const response = await fetch(url, {
        method: 'GET',
        headers: {Accept: 'application/json', 'X-UserToken': window.g_ck},
        credentials: 'same-origin',
        redirect: 'error',
        signal: AbortSignal.timeout(5000),
    });
    // Sprawdź status i sparsuj wyłącznie pola liczników opisane poniżej.
    // Granicę JavaScript → Python przekraczają tylko sprawdzone metryki.
};
```

- **Filtr.** Składamy go przed żądaniem z lokalnej konfiguracji i pierwszego oraz ostatniego dnia wybranego miesiąca. Zachowujemy zweryfikowaną składnię zakresu `task.opened_atBETWEENjavascript:gs.dateGenerate('YYYY-MM-DD','start')@javascript:gs.dateGenerate('YYYY-MM-DD','end')`. Pozostałe warunki to lokalizacje (`task.locationIN`), stany (`task.stateIN1,2,3,6,7,8`), przypisane osoby (`task.assigned_toIN`), grupa przypisania (`task.assignment_group=`), `stage!=cancelled`, `sla.nameLIKE6/22` i `task.ref_incident.parent_incidentISEMPTY`. W pilotażu zestawy 104 lokalizacji i 47 osób oraz ID grupy pochodzą z lokalnego, ignorowanego przez Git pliku `data/dashboard-p2-api.json`. „Wybierz wszystko” w dashboardzie przekłada się na konkretne zestawy. Przy zmianie definicji dashboardu lub składu zestawów trzeba odświeżyć konfigurację i powtórzyć porównanie. Ręczny import był jednorazowym przygotowaniem danych.
- **Odpowiedź.** W trybie grupowanym `result` jest tablicą. Każdy element ma `stats.count` i tablicę `groupby_fields`. Rozpoznajemy pola grupy po nazwach, ponieważ kolejność w odpowiedzi może się różnić od kolejności w żądaniu. W ADEO licznik był tekstem z cyframi, priorytet tekstem, a flaga `has_breached` miała wartości `'true'` lub `'false'`. Odczyt P2 bez grupowania zwracał `result.stats.count`.
- **Liczniki.** „Liczba zgłoszeń” to suma wszystkich grup, również grup z priorytetem poza P1–P5, jeśli wystąpią. „Zgłoszenia Pn” to suma obu grup danego priorytetu. „Przekroczone Pn” bierze tylko grupę z flagą `true`. Brak pojedynczej grupy w poprawnej, kompletnej odpowiedzi oznacza zero. Pustą tablicę dla całego miesiąca obsługuje kod, ale taki przypadek sprawdzono lokalnie. Przed przełączeniem źródła warto potwierdzić go na rzeczywistym API. WJRUW liczymy istniejącą funkcją `calculate_wjruw` z tej samej migawki.
- **Walidacja.** Odrzucamy błędny status HTTP, odpowiedź inną niż oczekiwany JSON, niepełne pola grup, duplikaty kluczy grup i sygnał kolejnej strony. Brak danych z powodu błędu zachowuje ostatnią poprawną migawkę. W pilotażu limit żądania wynosi 5 sekund. [Parametry i schemat Aggregate API](https://www.servicenow.com/docs/r/api-reference/rest-apis/c_AggregateAPI.html)

## Wyniki i granice weryfikacji

| Próba | Wynik |
| --- | --- |
| P2 w aplikacji | HTTP 200. Wrzesień 64, październik 191, listopad 116. Zarejestrowany czas od rozpoczęcia odczytu 125–187 ms, poza kolejką. |
| Grupowany SLA, wrzesień 2026 | HTTP 200. Razem 2715, zgodność 11/11 z dashboardem. Jeden P1. Odpowiedź w 1,08 s. |
| Grupowany SLA, październik 2026 | HTTP 200. Razem 3225, zgodność 11/11. Brak grupy P1 zgodny z zerem w dashboardzie. Odpowiedź w 0,64 s. |

Próby grupowane wykonano w osobnym Chromium po zwykłym logowaniu na stronie SOW. Dodatkowe zapytanie kontrolne bez grupowania potwierdziło sumę w obu miesiącach. Pełne filtry 11 kafelków SLA zweryfikowano na ich listach docelowych. Opcja **Kopiuj zapytanie** na wcześniejszym warunku może zwrócić tylko początek filtra. Podczas analizy warto zweryfikować pełny filtr listy i jej licznik. Przycisk grupowany w worktree przeszedł 40 testów zakresowych, a jego odbiór w aplikacji na Windows, w tym widoczność Chromium w czasie odczytu, pozostaje do potwierdzenia.

## Założenia pilotażu

- Dodawaj odczyt do wspólnej kolejki `SharedSession`. Zwiąż wynik z identyfikatorem operacji i okresem wybranym przy jej przyjęciu. Pilotaż pokazuje wynik tylko w pamięci, a zwykłe odświeżenie SLA zastępuje go wynikiem obecnego czytnika. Decyzja o przełączeniu źródła i zapisie danych API do cache wymaga osobnego odbioru. [Własność sesji i kolejki](decyzje/025-wspolna-sesja-servicenow.md)
- Przy braku tokenu, HTTP 401 lub przekierowaniu sprawdź stan dokumentu i sesji. W docelowym odczycie korzystaj z istniejącej ścieżki odzyskiwania po potwierdzonej utracie sesji. Samo 401 może też wynikać z polityki endpointu. HTTP 403 klasyfikuj jako odmowę dostępu. Oddziel wygaśnięcie sesji, odmowę, timeout, przerwanie i niepoprawną odpowiedź. Nie zapisuj pełnych URL, filtrów, nagłówków, odpowiedzi ani identyfikatorów referencji. Wystarczą okres, ID operacji, kod HTTP, czas, kategoria i licznik. [Zasady diagnostyki](decyzje/004-bezpieczna-diagnostyka.md)
- **Wstrzymane L1** prowadzą do `incident_metric`, a **Wnioski L1** do `sc_task`. Ich listy i filtry potwierdzono przez interfejs. Te sekcje pokazują bieżący stan, niezależnie od miesiąca SLA. Osobno sprawdź dostęp przez API, zgodność progów względnych, filtr po zmiennej katalogowej w kafelku smartfonów i warunek pustego przypisania. Dopiero po porównaniu z aktualnymi kafelkami rozważ wspólne zapytania. [Kontrakt dashboardu](kontrakty/kontrakt-odczytu-dashboardu.md)
