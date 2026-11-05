# Architektura Neto Incident Monitor

Bieżący stan opisuje wersja [1.9.2](wersje/v1.9.2.md). Zakres wykonanych prób jest w opisie wersji, a pozostałe prace w [indeksie planów](plany/README.md).

## Przepływ i odpowiedzialności

`Tk → żądanie/kolejka → wątek monitoringu → Chromium/ServiceNow → walidacja → historia/stan → zdarzenia do Tk → widok/powiadomienia`.

| Obszar | Gdzie szukać | Odpowiedzialność |
| --- | --- | --- |
| Koordynacja i UI | [app.py](../neto_incident_monitor/app.py), `ui.py`, `settings_ui.py` | `App` nadal łączy sterowanie monitoringiem, zdarzenia, ustawienia i część parsowania list. Nie jest to w pełni rozdzielona architektura warstwowa. |
| Harmonogram | [monitoring.py](../neto_incident_monitor/monitoring.py) | `Schedule` budzi worker; `RefreshControl` rezerwuje jedną aktualizację. Kolejność i terminy realizuje `App.monitor`. |
| Logowanie i okno | `authentication.py`, `automatic_login.py`, `browser_actions.py`, [browser_policy.py](../neto_incident_monitor/browser_policy.py), `browser_window.py`, `browser_rendering.py` | Rozpoznanie sesji, automatyczne/ręczne logowanie, przerywalne operacje oraz widoczność i fokus. Polecenia okna przechodzą przez `BrowserRuntime`. |
| Listy INC/SCTASK/REQ/RITM | `service_now_urls.py`, `app.py: collect`, [list_context.py](../neto_incident_monitor/list_context.py), [pagination.py](../neto_incident_monitor/pagination.py) | Normalizacja adresów, odczyt kolumn, powiązanie tabeli i pagera, walidacja kompletnego przejścia. |
| Dashboard | [dashboard.py](../neto_incident_monitor/dashboard.py), `dashboard_ui.py`, `dashboard_progress.py`, `dashboard_cache.py`, `dashboard_drilldown.py` | SLA i WJRUW, Wstrzymane L1, Wnioski L1, statusy, postęp, cache i otwieranie list na żądanie. |
| Zagrożenia SLA | [threatened.py](../neto_incident_monitor/threatened.py), `threatened_ui.py`, `history.py` | Sześć liczników, zbiorcza lista i historia INC. Kompletna pojedyncza strona pozwala zapisać obecność i dodać alerty do wspólnej kolejki SQLite. [Odbiór jednej strony](plany/zakonczone/lista-zagrozonych-i-powiadomienia.md). |
| Dane i powiadomienia | `history.py`, `filter_state.py`, `notification_templates.py`, `template_library.py`, `teams_notifications.py`, `google_chat_notifications.py`, `data_reset.py` | Historia i stan filtrów, reset danych, szablony oraz kanały Windows/Teams/Google Chat. Automatyczne alerty filtrów mają trwałą kolejkę SQLite. |
| Wspólne podstawy | `theme.py`, `widgets.py`, `themed_dialogs.py`, `runtime_paths.py`, `login_diagnostics.py`, `safe_logging.py` | Styl, kontrolki, dialogi, ścieżki oraz bezpieczna diagnostyka. Duże tabele UI obsługuje porcjami `table_loading.py`. |

## Zasady współpracy modułów

### Źródła po audycie technicznym — 4 listopada 2026

Zwykły log i JSONL używają wspólnego bezpiecznego handlera; błąd IO nie wraca do uszkodzonego handlera przez stderr. `alert_writer` obserwuje każde Future. Tylko odczyt outbox ma ograniczone ponowienia 1/5 s; nie powtarzamy niepewnej wysyłki. Wiadomości są dzielone według rozmiaru końcowego JSON bez obcinania treści. Przed utworzeniem App `data_validation.py` sprawdza lokalne dane bez migracji/zapisu; uszkodzenie lub brak dostępu otwiera ekran informacyjny zamiast monitoringu. DPAPI nadal zachowuje nieczytelny szyfrogram. [Decyzja 017](decyzje/017-odpornosc-lokalnego-io.md), [status i próby](../AUDIT.md).

Są to poprawki źródeł po wydaniu 1.9.0, objęte późniejszym zleceniem [wydania 1.9.1](plany/zakonczone/wydanie-1.9.1.md). Po zamknięciu audytu na osobne zlecenie przebudowano główną paczkę `dist/Neto Incident Monitor/` i sprawdzono ją offline; usunięto starsze paczki audytowe oraz nieaktualny ZIP. Logi źródłowe pozostają w `data/`; rozbieżność z ogólną polityką lokalnego katalogu danych użytkownika jest jawnie odłożona do uzgodnienia, nie rozstrzygnięta przez ten audyt.

- Tk jest obsługiwane na głównym wątku; worker przekazuje wyniki przez kolejkę zdarzeń. Operacje Playwright należą do jednego workera. Szczegóły: [decyzja 001](decyzje/001-watki-i-kolejki.md).
- Start: logowanie → opcjonalny dashboard → zagrożenia → filtry. Pełna ręczna aktualizacja także wykonuje dashboard przed zagrożeniami i filtrami. Aktualizacje pojedynczych sekcji pozostają niezależne. Zagrożenia są sprawdzane ponownie 60 s od zakończenia poprzedniej próby, po dashboardzie i między całymi filtrami; nie tworzymy zaległych minut ani natychmiastowej powtórki po obsłużeniu kolejki. Dashboard, jego retry lub logowanie mogą opóźnić zagrożenia: [decyzja 018](decyzje/018-kolejnosc-aktualizacji.md), zastępująca 002.
- Błąd, brak danych i prawidłowe zero są odrębnymi stanami. Czytnik zbiera wynik, a UI nie powinno zgadywać jego poprawności: [decyzja 003](decyzje/003-poprawnosc-i-aktualnosc.md).
- Współdzielimy mechanizmy, nie limity dobrane przypadkowo. Liczba prób, budżet czasu i kompletność są częścią kontraktu danej operacji; nie dodajemy zagnieżdżonych ponowień: [decyzja 005](decyzje/005-kompletny-odczyt-listy.md).
- Diagnostyka jest częścią funkcji i korzysta ze wspólnych zabezpieczeń: [decyzja 004](decyzje/004-bezpieczna-diagnostyka.md).

## Stan danych i granice obecnego rozwiązania

- EXE przechowuje dane użytkownika w `%LOCALAPPDATA%/NetoIncidentMonitor`; uruchomienie ze źródeł używa katalogu projektu `data/`. Rozstrzyga `runtime_paths.py`.
- Historia, stan obecności filtrów i cache dashboardu mają różne role. Nie zastępujemy jednego drugim ani nie dołączamy danych użytkownika do wydania.
- Paginacja zwraca kompletny, zweryfikowany wynik albo błąd. Odbiór źródeł i wydania 1.9.0 opisuje kontrakt list. Paczki po audycie mają odbiór offline, bez ponownego odczytu rzeczywistego ServiceNow.
- Dashboard i zagrożenia używają wspólnego `read_tile/read_scores`; liczy się lokalny stan konkretnego widżetu, nie ładowanie obcego wykresu. `dashboard_context.py` potwierdza dashboard, zakładkę i kontrolkę daty; kategorie są stosowane osobno.
- `section_runner.py` jest jedynym właścicielem ponowień sekcji: aktywny budżet 60 s, najwyżej jedno ponowienie błędu odczytu oraz jedno niezależne odzyskanie logowania (łącznie najwyżej trzy odczyty); pierwsza próba najwyżej 39 s, czas logowania rozliczany osobno. Wznowienie zachowuje żądanie i blokady; wyczerpany budżet nie pozwala na kolejny odczyt. [Decyzja 019](decyzje/019-odzyskiwanie-sesji-sekcji.md) zastępuje dawny limit dwóch prób. `read_budget.py` ogranicza podrzędne oczekiwania. Szczegóły i granice: [decyzja 006](decyzje/006-odczyt-sekcji-dashboardu.md).
- Cache schematu 2 przechowuje kompletne wyniki i czasy poszczególnych sekcji. Błąd nie zmienia daty sukcesu ani nie miesza kafelków z różnych prób; WJRUW używa jednego kompletu SLA. Migrowany stary cache ma niepotwierdzone czasy sekcji.
- W wersji 1.8.1 aplikacja zamraża okres dashboardu od kolejkowania do końca żądania. Tk blokuje obie listy, a zdarzenia workera mają ID/okres; restart nie zwalnia blokady, stary koniec nie zamyka nowej transakcji. Wyniki sprawdzają również okres i zakończenie żądania. [010](decyzje/010-cykl-zycia-zadania-dashboardu.md).

Nowe rozwiązanie wspólne dopisuj tutaj dopiero po wdrożeniu. Uzasadnienie ważnej zmiany zapisz w [decyzjach](decyzje/README.md), a niezakończoną pracę w planie.

Diagnostyka dashboardu i zagrożeń ma już wspólny kontekst odczytu oraz pomiary etapów. Zakres wdrożenia, kontrakt i pozostałe prace: [dashboard-read-contract.md](kontrakty/kontrakt-odczytu-dashboardu.md).

## Ukryta analityka — wdrożenie 007

`BrowserRuntime.dashboard_read` obejmuje każdą próbę SLA/Wstrzymanych/Wniosków/zagrożeń. Przy ukryciu uruchamia `HiddenRendering` wyłącznie dla potwierdzonej sesji i właściwego dashboardu; `ACTION_TICK` synchronizuje preferencje i cykl życia. Na końcu próby wyłącza DevTools i przywraca aktywność filtrów. Start/ACK nie ma własnego retry. Logowanie nadal ma własną politykę, a ręczne pokazanie pozostaje ważne między aktywnościami do zmiany polecenia/opcji lub logowania. Kategorie potwierdzają opóźnione zaznaczenie obserwacją, nie drugim kliknięciem.

Stan źródeł i ograniczenia: [007](decyzje/007-ukryty-dashboard.md). Odbiór źródeł zakończony (338 testów, 1 pominięty; rzeczywiste odczyty 44/44 i po ostatniej poprawce 8/8): [raport](weryfikacja/odbior-ukrytego-dashboardu.md). Ówczesny odbiór dotyczył źródeł. Lokalny EXE 1.8.0 i jego osobny test offline opisuje [opis wersji](wersje/v1.8.0.md).

## Logowanie i ukryte SSO — źródła, 2 listopada 2026

- `login_observation.py` wspólnie klasyfikuje `authentication/logout/unknown/target/session`. Konflikt ramek, własny niedokończony popup i nieudana obserwacja wykluczają sesję; wymagane jest dodatnie potwierdzenie na właściwej powierzchni, bez pobierania pierwszej listy. Własność popupów obejmuje łańcuch `opener`, nie obce karty; [008](decyzje/008-obserwacja-logowania.md).
- `AutomaticLogin` pozostaje jedynym automatem akcji. `needs_user` oznacza potrzebną pomoc, `blocked` trwałe oddanie formularza. Sam wybór konta nie blokuje późniejszego potwierdzonego autofill; wpisywanie, wklejenie, ręczne wysłanie i interwencja mają pierwszeństwo. Guard nie przejmuje zwykłej edycji dashboardu ani automatycznych ukrytych formularzy przekierowania SAML.
- Automatyczne akcje i renderowanie logowania dopuszczają tylko zaobserwowany HTTPS `idpb2e.adeo.com:443`, bez userinfo. Hasło wymaga booleana CSS autofill, gotowego tego samego formularza i ponownej kontroli opcji/ingerencji. Wyboru konta oraz dostarczonego lub niepewnego zatwierdzenia nie powtarzamy. Retry dopuszczalne wyłącznie po potwierdzonym braku dostarczenia, do 3 prób.
- Przy auto+hide `BrowserRuntime` ukrywa przed nawigacją i uzgadnia faktyczną widoczność własnego okna. Osobna instancja wspólnego `HiddenRendering(scope='login')` podtrzymuje ograniczone renderowanie; [009](decyzje/009-renderowanie-ukrytego-logowania.md). Auto off, MFA/ręczna obsługa lub awaria mechanizmu → wyłączenie renderowania, pokazanie/fokus; po skutecznym pokazaniu bez powtarzania aktywacji. Jawne „Pokaż” ma pierwszeństwo.
- `wait_for_login` zachowuje ledger wysłania podczas zmian opcji i przekierowań. Logout/sieć/brak postępu uruchamia odroczone bezpieczne GET do zwykłego celu (5/15/60/300 s), bez odtwarzania URL SSO i bez nadpisania ręcznego lub niepewnego wysłania. Oczekiwanie nie zatrzymuje monitoringu; Stop anuluje. Dotychczasowy ograniczony restart zamkniętego Chromium pozostaje; permanentna awaria startu/profilu nie jest bezterminowo naprawiana.
- Diagnostyka wiąże run/trace/read/action i generację dokumentu; zapisuje stan, przyczynę, dostarczenie, widoczność i czasy. Allowlista bez wartości formularzy, sekretów i pełnych URL. Błąd zapisu/rotacji nie wypisuje rekordu na stderr; ostrzeżenie raz i ponowienie IO po 30 s, bez przerwania logowania.

Granice pomiarów, pozostałe próby rzeczywiste i status regresji: [raport odbioru](weryfikacja/odbior-stabilizacji-logowania.md), [plan](plany/zakonczone/stabilizacja-logowania.md). Po odbiorze źródeł osobno zlecono i wykonano lokalny build 1.8.0: test offline UI/Chromium, zgodność 53 modułów i launchera ze źródłami. Nie obejmuje to nowej pełnej próby SSO z EXE; [opis wersji](wersje/v1.8.0.md).

W źródłach z 3 listopada czytnik odrzuca rekord niewłaściwego typu dla listy oraz pusty komunikat bez powiązanej tabeli. Dla REQ rozpoznaje request_state jako stan wniosku. Przebieg prac opisuje [plan stabilizacji filtrów](plany/zakonczone/stabilizacja-odczytu-filtrow.md).

### Stabilizacja filtrów w źródłach

Czytnik porównuje warunki żądanego filtra z tabelą, oddziela sortowanie i końcowy znacznik EQ oraz odrzuca zły typ rekordu i niepotwierdzoną pustkę. Zmiana schematu uruchamia ponowienie z nowym buforem. Po pierwszym poprawnym zapisie historia i potwierdzona obecność używają wspólnej bazy [SQLite](decyzje/011-transakcyjny-stan-filtrow.md). Wyniki i kolumny są publikowane po transakcji i odrzucane po zmianie rewizji filtra lub generacji monitoringu. Automatyczne alerty filtrów trafiają do trwałej kolejki w tej samej transakcji. Po restarcie zadania oczekujące są wznawiane, a rozpoczęte bez zapisanego wyniku oznaczane jako niepewne. Zmiana rewizji konfiguracji powiadomień unieważnia wcześniejsze zadania. Zapisy historii z interfejsu wykonuje osobny wątek. Odbiór zakresowy opisuje [plan stabilizacji](plany/zakonczone/stabilizacja-odczytu-filtrow.md).

W bieżących źródłach historia filtrów przechowuje zgłoszenia i daty wykrycia. Starsze znaczniki przeczytania są pomijane przy wczytywaniu. Ustawienia dawnych kolumn są oczyszczane przy zwykłym zapisie konfiguracji. [Decyzja 012](decyzje/012-usuniecie-stanu-przeczytania.md).

Reset danych korzysta ze ścieżki zamykania i blokady pojedynczej instancji. Launcher wznawia przerwaną operację przed otwarciem logów, a w trybie źródłowym zakres ogranicza lista danych wykonawczych. [Decyzja 013](decyzje/013-reset-danych-aplikacji.md).

Autostart Windows jest ukryty w UI: użytkownik nie może go włączyć z ustawień aplikacji. Mechanizm rejestracji, naprawy istniejącego wpisu i usuwania przy resecie pozostaje dostępny wewnętrznie. Domyślnie autostart jest wyłączony — brak wpisu nie powoduje jego utworzenia. Ukrycie opcji nie usuwa wcześniej istniejących wpisów. Autostart Windows odczytuje wpis `Run` bieżącego wariantu pod blokadą głównej instancji. Jeśli wpis istnieje i wskazuje dawną ścieżkę, aplikacja nadpisuje tę samą wartość. Ustawienia systemowe wyłączające uruchamianie wpisu pozostają w gestii Windows.

Sekcja Wnioski L1 obejmuje pięć kafelków. Starszy zapis czterech wartości jest pomijany dla tej sekcji. Poprawne migawki SLA i Wstrzymanych L1 pozostają dostępne, a wspólny czas pełnego odczytu jest czyszczony.

Porównywanie warunków listy zachowuje strukturę OR/NQ i dopuszcza potwierdzony alias siedmiodniowej daty pola `sys_updated_on`. Nieznana różnica nadal odrzuca odczyt. Diagnostyka rozróżnia zgodność dokładną, zaakceptowany alias i niezgodność bez zapisu zapytania. [Decyzja 015](decyzje/015-rownowaznosc-dat-filtrow.md), [kontrakt list](kontrakty/kontrakt-odczytu-list.md).

Otwieranie listy dashboardu jest zlecane dopiero po kliknięciu kafelka z wynikiem, także z cache. Odświeżenie wartości nie otwiera list pomocniczych. Istniejący worker przeglądarki korzysta z tymczasowej karty tej samej sesji i potwierdza pełne warunki listy. SLA używa jawnego zakresu dat wyświetlanej migawki. Link nie jest utrwalany. Błąd pozwala ponowić kliknięcie, a Stop anuluje otwarcie. WJRUW nie ma celu nawigacji. [Decyzja 014](decyzje/014-linki-dashboardu-na-zadanie.md), [kontrakt i wyniki odbioru](kontrakty/kontrakt-odczytu-dashboardu.md).

Wspólny `AnimatedMetricTile.bind_content` ustawia tło wszystkich elementów od razu przy ich podłączeniu. Pierwszy poprawny wygląd kafelków nie zależy od najechania kursorem ani uruchomienia animacji.

`normalize_list_url` rozpakowuje długie adresy list z ponownym kodowaniem parametrów i zachowaniem widoku. Nowe opakowane adresy stają się bezpośrednie, a zapis istniejących adresów bezpośrednich pozostaje bez zmian. Sprzeczne parametry są odrzucane przed zapisem. [Decyzja 016](decyzje/016-normalizacja-adresow-list.md).
