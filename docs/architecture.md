# Architektura Neto Incident Monitor

Najnowszy lokalny build i odbiór opisuje [1.8.1](releases/v1.8.1.md). Stan wcześniejszego lokalnego buildu: **2 listopada 2026**, wersja **1.8.0** ze stabilizacją paginacji, dashboardu/zagrożeń i logowania. Gotowy EXE przeszedł offline smoke-test UI/Chromium; 53 moduły i launcher odpowiadają źródłom. Nie jest to pełny test rzeczywistego logowania z EXE; bez publikacji i nowego ZIP-a. Źródła zawierają ponadto opisaną niżej poprawkę okresu dashboardu, której ten EXE jeszcze nie zawiera. Status prac opisuje [indeks planów](plans/README.md).

## Przepływ i odpowiedzialności

`Tk → żądanie/kolejka → wątek monitoringu → Chromium/ServiceNow → walidacja → historia/stan → zdarzenia do Tk → widok/powiadomienia`.

| Obszar | Gdzie szukać | Odpowiedzialność |
| --- | --- | --- |
| Koordynacja i UI | [app.py](../neto_incident_monitor/app.py), `ui.py`, `settings_ui.py` | `App` nadal łączy sterowanie monitoringiem, zdarzenia, ustawienia i część parsowania list. Nie jest to w pełni rozdzielona architektura warstwowa. |
| Harmonogram | [monitoring.py](../neto_incident_monitor/monitoring.py) | `Schedule` budzi worker; `RefreshControl` rezerwuje jedną aktualizację. Kolejność i terminy realizuje `App.monitor`. |
| Logowanie i okno | `authentication.py`, `automatic_login.py`, `browser_actions.py`, [browser_policy.py](../neto_incident_monitor/browser_policy.py), `browser_window.py`, `browser_rendering.py` | Rozpoznanie sesji, automatyczne/ręczne logowanie, przerywalne operacje oraz widoczność i fokus. Polecenia okna przechodzą przez `BrowserRuntime`. |
| Listy INC/SCTASK/REQ/RITM | `service_now_urls.py`, `app.py: collect`, [list_context.py](../neto_incident_monitor/list_context.py), [pagination.py](../neto_incident_monitor/pagination.py) | Normalizacja adresów, odczyt kolumn, powiązanie tabeli i pagera, walidacja kompletnego przejścia. |
| Dashboard | [dashboard.py](../neto_incident_monitor/dashboard.py), `dashboard_ui.py`, `dashboard_progress.py`, `dashboard_cache.py` | SLA i WJRUW, Wstrzymane L1, Wnioski L1, statusy, postęp i cache. |
| Zagrożenia SLA | [threatened.py](../neto_incident_monitor/threatened.py), `threatened_ui.py`, `history.py` | Sześć liczników, zbiorcza lista i historia INC. Kompletna pojedyncza strona pozwala zapisać obecność i dodać alerty do wspólnej kolejki SQLite. |
| Dane i powiadomienia | `history.py`, `filter_state.py`, `notification_templates.py`, `template_library.py`, `notifications.py`, `teams_notifications.py`, `google_chat_notifications.py` | Historia i stan filtrów, szablony oraz kanały Windows/Teams/Google Chat. Automatyczne alerty filtrów mają trwałą kolejkę SQLite. |
| Wspólne podstawy | `theme.py`, `widgets.py`, `themed_dialogs.py`, `runtime_paths.py`, `login_diagnostics.py`, `safe_logging.py` | Styl, kontrolki, dialogi, ścieżki oraz bezpieczna diagnostyka. Duże tabele UI obsługuje porcjami `table_loading.py`. |

## Zasady współpracy modułów

- Tk jest obsługiwane na głównym wątku; worker przekazuje wyniki przez kolejkę zdarzeń. Operacje Playwright należą do jednego workera. Szczegóły: [decyzja 001](decisions/001-watki-i-kolejki.md).
- Start: logowanie → zagrożenia → opcjonalny dashboard → filtry. Zagrożenia są sprawdzane ponownie 60 s od zakończenia poprzedniej próby, w bezpiecznych punktach między filtrami. To nie gwarantuje odczytu dokładnie co minutę: [decyzja 002](decisions/002-harmonogram-zagrozen.md).
- Błąd, brak danych i prawidłowe zero są odrębnymi stanami. Czytnik zbiera wynik, a UI nie powinno zgadywać jego poprawności: [decyzja 003](decisions/003-poprawnosc-i-aktualnosc.md).
- Współdzielimy mechanizmy, nie limity dobrane przypadkowo. Liczba prób, budżet czasu i kompletność są częścią kontraktu danej operacji; nie dodajemy zagnieżdżonych ponowień: [decyzja 005](decisions/005-kompletny-odczyt-listy.md).
- Diagnostyka jest częścią funkcji i korzysta ze wspólnych zabezpieczeń: [decyzja 004](decisions/004-bezpieczna-diagnostyka.md).

## Stan danych i granice obecnego rozwiązania

- EXE przechowuje dane użytkownika w `%LOCALAPPDATA%/NetoIncidentMonitor`; uruchomienie ze źródeł używa katalogu projektu `data/`. Rozstrzyga `runtime_paths.py`.
- Historia, stan obecności filtrów i cache dashboardu mają różne role. Nie zastępujemy jednego drugim ani nie dołączamy danych użytkownika do wydania.
- Nowa paginacja zwraca kompletny, zweryfikowany wynik albo błąd. Została sprawdzona w źródłach; test nowego EXE pozostaje osobnym krokiem.
- Dashboard i zagrożenia używają wspólnego `read_tile/read_scores`; liczy się lokalny stan konkretnego widżetu, nie ładowanie obcego wykresu. `dashboard_context.py` potwierdza dashboard, zakładkę i kontrolkę daty; kategorie są stosowane osobno.
- `section_runner.py` jest jedynym właścicielem ponowień sekcji: aktywny budżet 60 s, najwyżej jedno odzyskanie, osobne oczekiwanie na logowanie. `read_budget.py` ogranicza podrzędne oczekiwania. Szczegóły i granice: [decyzja 006](decisions/006-odczyt-sekcji-dashboardu.md).
- Cache schematu 2 przechowuje kompletne wyniki i czasy poszczególnych sekcji. Błąd nie zmienia daty sukcesu ani nie miesza kafelków z różnych prób; WJRUW używa jednego kompletu SLA. Migrowany stary cache ma niepotwierdzone czasy sekcji.
- Poprawka źródeł po lokalnym buildzie 1.8.0 zamraża okres dashboardu od kolejkowania do końca żądania. Tk blokuje obie listy, a zdarzenia workera mają ID/okres; restart nie zwalnia blokady, stary koniec nie zamyka nowej transakcji. Wyniki sprawdzają również okres i zakończenie żądania. [010](decisions/010-cykl-zycia-zadania-dashboardu.md). Istniejący EXE nie zawiera jeszcze tej poprawki.

Nowe rozwiązanie wspólne dopisuj tutaj dopiero po wdrożeniu. Uzasadnienie ważnej zmiany zapisz w [decyzjach](decisions/README.md), a niezakończoną pracę w planie.

Diagnostyka dashboardu i zagrożeń ma już wspólny kontekst odczytu oraz pomiary etapów. Zakres wdrożenia, kontrakt i pozostałe prace: [dashboard-read-contract.md](contracts/dashboard-read-contract.md).

## Ukryta analityka — wdrożenie 007

`BrowserRuntime.dashboard_read` obejmuje każdą próbę SLA/Wstrzymanych/Wniosków/zagrożeń. Przy ukryciu uruchamia `HiddenRendering` wyłącznie dla potwierdzonej sesji i właściwego dashboardu; `ACTION_TICK` synchronizuje preferencje i cykl życia. Na końcu próby wyłącza DevTools i przywraca aktywność filtrów. Start/ACK nie ma własnego retry. Logowanie nadal ma własną politykę, a ręczne pokazanie pozostaje ważne między aktywnościami do zmiany polecenia/opcji lub logowania. Kategorie potwierdzają opóźnione zaznaczenie obserwacją, nie drugim kliknięciem.

Stan źródeł i ograniczenia: [007](decisions/007-ukryty-dashboard.md). Odbiór źródeł zakończony (338 testów, 1 pominięty; rzeczywiste odczyty 44/44 i po ostatniej poprawce 8/8): [raport](verification/hidden-dashboard-verification.md). Ówczesny odbiór dotyczył źródeł. Lokalny EXE 1.8.0 i jego osobny test offline opisuje [opis wersji](releases/v1.8.0.md).

## Logowanie i ukryte SSO — źródła, 2 listopada 2026

- `login_observation.py` wspólnie klasyfikuje `authentication/logout/unknown/target/session`. Konflikt ramek, własny niedokończony popup i nieudana obserwacja wykluczają sesję; wymagane jest dodatnie potwierdzenie na właściwej powierzchni, bez pobierania pierwszej listy. Własność popupów obejmuje łańcuch `opener`, nie obce karty; [008](decisions/008-obserwacja-logowania.md).
- `AutomaticLogin` pozostaje jedynym automatem akcji. `needs_user` oznacza potrzebną pomoc, `blocked` trwałe oddanie formularza. Sam wybór konta nie blokuje późniejszego potwierdzonego autofill; wpisywanie, wklejenie, ręczne wysłanie i interwencja mają pierwszeństwo. Guard nie przejmuje zwykłej edycji dashboardu ani automatycznych ukrytych formularzy przekierowania SAML.
- Automatyczne akcje i renderowanie logowania dopuszczają tylko zaobserwowany HTTPS `idpb2e.adeo.com:443`, bez userinfo. Hasło wymaga booleana CSS autofill, gotowego tego samego formularza i ponownej kontroli opcji/ingerencji. Wyboru konta oraz dostarczonego lub niepewnego zatwierdzenia nie powtarzamy. Retry dopuszczalne wyłącznie po potwierdzonym braku dostarczenia, do 3 prób.
- Przy auto+hide `BrowserRuntime` ukrywa przed nawigacją i uzgadnia faktyczną widoczność własnego okna. Osobna instancja wspólnego `HiddenRendering(scope='login')` podtrzymuje ograniczone renderowanie; [009](decisions/009-renderowanie-ukrytego-logowania.md). Auto off, MFA/ręczna obsługa lub awaria mechanizmu → wyłączenie renderowania, pokazanie/fokus; po skutecznym pokazaniu bez powtarzania aktywacji. Jawne „Pokaż” ma pierwszeństwo.
- `wait_for_login` zachowuje ledger wysłania podczas zmian opcji i przekierowań. Logout/sieć/brak postępu uruchamia odroczone bezpieczne GET do zwykłego celu (5/15/60/300 s), bez odtwarzania URL SSO i bez nadpisania ręcznego lub niepewnego wysłania. Oczekiwanie nie zatrzymuje monitoringu; Stop anuluje. Dotychczasowy ograniczony restart zamkniętego Chromium pozostaje; permanentna awaria startu/profilu nie jest bezterminowo naprawiana.
- Diagnostyka wiąże run/trace/read/action i generację dokumentu; zapisuje stan, przyczynę, dostarczenie, widoczność i czasy. Allowlista bez wartości formularzy, sekretów i pełnych URL. Błąd zapisu/rotacji nie wypisuje rekordu na stderr; ostrzeżenie raz i ponowienie IO po 30 s, bez przerwania logowania.

Granice pomiarów, pozostałe próby rzeczywiste i status regresji: [raport odbioru](verification/login-stabilization-verification.md), [plan](plans/completed/stabilizacja-logowania.md). Po odbiorze źródeł osobno zlecono i wykonano lokalny build 1.8.0: test offline UI/Chromium, zgodność 53 modułów i launchera ze źródłami. Nie obejmuje to nowej pełnej próby SSO z EXE; [opis wersji](releases/v1.8.0.md).

W źródłach z 3 listopada czytnik odrzuca rekord niewłaściwego typu dla listy oraz pusty komunikat bez powiązanej tabeli. Dla REQ rozpoznaje request_state jako stan wniosku. Wdrożenie pozostałych wymagań śledzi [plan stabilizacji filtrów](plans/stabilizacja-odczytu-filtrow.md).

### Stabilizacja filtrów w źródłach

Czytnik porównuje warunki żądanego filtra z tabelą, oddziela sortowanie i końcowy znacznik EQ oraz odrzuca zły typ rekordu i niepotwierdzoną pustkę. Zmiana schematu uruchamia ponowienie z nowym buforem. Po pierwszym poprawnym zapisie historia i potwierdzona obecność używają wspólnej bazy [SQLite](decisions/011-transakcyjny-stan-filtrow.md). Wyniki i kolumny są publikowane po transakcji i odrzucane po zmianie rewizji filtra lub generacji monitoringu. Automatyczne alerty filtrów trafiają do trwałej kolejki w tej samej transakcji. Po restarcie zadania oczekujące są wznawiane, a rozpoczęte bez zapisanego wyniku oznaczane jako niepewne. Zmiana rewizji konfiguracji powiadomień unieważnia wcześniejsze zadania. Zapisy historii z interfejsu wykonuje osobny wątek. Pozostałe prace prowadzi [plan stabilizacji](plans/stabilizacja-odczytu-filtrow.md).
