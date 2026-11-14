# Audyt techniczny Neto Incident Monitor

Data: 4 listopada 2026. Badany stan źródeł: commit `20c6540`, wersja aplikacji `1.9.0`.
Zakres zmian audytu: wyłącznie ten raport. Nie naprawiano aplikacji, nie instalowano zależności, nie wykonywano buildu ani publikacji.

Późniejsza publikacja napraw ma osobne zlecenie i raport [wydania 1.9.1](../plany/zakonczone/wydanie-1.9.1.md). Poniższe zapisy o braku publikacji opisują granice pierwotnych etapów audytu.

## Realizacja napraw po audycie — 4 listopada 2026

Powyższy zakres dotyczy pierwotnego audytu. Użytkownik następnie zatwierdził naprawy i osobne buildy. Opisy A01–A10 poniżej zachowują dowody stanu sprzed napraw; aktualny status znajduje się tutaj. Bez zmiany schematów, selektorów, zależności, wersji i bez publikacji.

| Etap | Problemy | Status i weryfikacja |
| --- | --- | --- |
| 1 | A01 | Naprawione. Zakresowe 37/37. Pełny przebieg 468 testów, 2 pominięcia; 5 modułów początkowo niezaliczonych wskutek błędów nowego runnera i istniejącego timera dialogu. Po diagnozie końcowe ponowienie wszystkich dotkniętych modułów + ochrony logów: 47/47. Build i offline smoke końcowego EXE: OK (`dist/audit-stage1`). |
| 2 | A02 | Naprawione. Zakresowe 18/18; pełna regresja 473 testy, 2 pominięcia, 0 niezaliczonych modułów. Osobny build i offline smoke OK (`dist/audit-stage2`). Odczyt kolejki do 3 prób, opóźnienia 1/5 s przerywane Stop; wyjątki Future i zapisu stanu obserwowane, bez ponawiania POST. |
| 3 | A03, A04 | Naprawione. Zakresowe 34/34; pełna regresja 477 testów, 2 pominięcia, 0 niezaliczonych modułów. Build i offline smoke OK (`dist/audit-stage3`). Kompletne części mierzone po serializacji; zbyt duży nagłówek Teams odrzucany przed transportem. |
| 4 | A05 | Naprawione. Zakresowe 37/37 oraz 7/7 rozszerzonych testów ekranu/SQLite. Pełna regresja 484 testy, 2 pominięcia, bez niezaliczonych modułów. Build i offline smoke z kontrolą uszkodzonej konfiguracji OK (`dist/audit-stage4`). Odczyt danych bez migracji; błędy danych/IO poprzedzają App, executory i autostart. |
| 5 | A06, A09, A10 częściowo | Zakończone. Zakresowe 13/13. Końcowa regresja 486 testów: 484 zaliczone, 2 pominięte, 0 failures/errors i błędów callbacków. Build i offline smoke OK (`dist/audit-stage5`). Preview sprawdzony z atrapą przechwycenia obrazu; bez nowego odbioru wizualnego. Dokumentacja stanu odbioru uzupełniona; lokalizacja logów pozostaje bez zmian. |

A07 odłożone zgodnie z decyzją użytkownika. A08 odłożone do pomiarów. Lokalizacja logów źródłowych wymaga osobnego uzgodnienia. [Wykonany plan](../plany/zakonczone/naprawy-audytu.md).

Etap 1 objął także wąską poprawkę A09: anulowanie timera geometrii dialogu dużej listy po jego zniszczeniu. Runner przygotowuje pusty katalog danych, anuluje timery przez właściwego właściciela i opróżnia zadania bezczynności przed zniszczeniem Tk. Błędy wykryte przez runner nie zostały wyciszone. JSON-y wyników znajdują się w ignorowanym `build/`, poza wydaniem. `pip check`: poprawny.

### Końcowy odbiór napraw

**Porządkowanie paczek — 4 listopada 2026:** na osobne zlecenie użytkownika przebudowano aktualne źródła istniejącym PyInstallerem do `dist/Neto Incident Monitor/`. Nowy EXE przeszedł offline smoke UI/Chromium oraz walidacji uszkodzonej konfiguracji na tymczasowym LOCALAPPDATA. Usunięto pięć wcześniejszych katalogów `dist/audit-stage1` … `dist/audit-stage5` i nieaktualny ZIP. Poniższe ścieżki etapowe opisują historyczne wyniki; bieżąca paczka znajduje się w głównym katalogu dist. Nie zmieniono wersji i nie publikowano wydania.

**Zamknięcie etapu — 4 listopada 2026:** użytkownik zaakceptował zakończenie po wstępnych testach wybranych funkcji, podczas których nie zauważył problemów. Testy automatyczne, próby offline i zgłoszone testy użytkowe nie wykazały poważnych regresji; na tej podstawie etap napraw uznano za zamknięty i można rozpocząć planowanie kolejnych funkcjonalności. Nie jest to deklaracja pełnego odbioru integracyjnego ani gwarancja braku usterek. Ewentualne późniejsze usterki będą obsługiwane jako osobne poprawki. Publikacja pozostaje osobnym krokiem; A07/A08 i decyzja o lokalizacji logów zachowują status odłożonych tematów.

- **Naprawione:** A01–A06 oraz A09. A10 zamknięte w części dokumentacyjnej; rozstrzygnięcie ścieżki logów źródłowych nadal otwarte. A07/A08 pozostają odłożone, a nie „naprawione”.
- **Pełne przebiegi:** etap 2: 473/2 pominięcia; etap 3: 477/2; etap 4: 484/2; etap 5: 486/2. Każdy zakończył się kodem 0 i bez niezaliczonych modułów. Pierwszy przebieg etapu 1 i jego ponowienia opisano jawnie w tabeli, nie zastąpiono wyniku pierwotnego sukcesem.
- **Pominięcia:** `test_passive_show_keeps_foreground_and_supports_browser_actions` — Windows nie przyznał fokusu testowemu oknu; `test_redirect_in_profile_is_rejected` — brak możliwości utworzenia symlinka. Inne testy okna/resetu przeszły. Nie pominięto całych modułów.
- **Diagnostyka:** dodatkowe 5/5 testów potwierdziło rzeczywisty zapis run/read/action, numerów prób, kanału i liczby przyjętych części oraz brak syntetycznego sekretu. Testy logów obejmują awarie otwarcia, rotacji, flush, close i odzyskanie IO; testy kolejki obejmują Stop i błąd zapisu stanu bez ponownego POST.
- **Składnia i zależności:** 134 pliki Python/PYW poprawne składniowo; `pip check` poprawny; `git diff --check` bez błędów whitespace. Nie uruchamiano nieobecnych narzędzi lint/typecheck/SCA i nie instalowano bibliotek.
- **Buildy:** pięć osobnych paczek PyInstaller 6.22.3 w `dist/audit-stage1` … `dist/audit-stage5`. Każda przeszła offline UI/Chromium smoke z tymczasowym LOCALAPPDATA. Paczki etapów 4/5 dodatkowo potwierdziły odrzucenie uszkodzonej konfiguracji bez zmiany pliku. Końcowa paczka ma 1441 plików; kontrola nazw nie wykazała konfiguracji, historii, logów ani profilu użytkownika. To kontrola składu, nie pełny skan sekretów wszystkich binariów.
- **Gotowa paczka lokalna:** `dist/audit-stage5/Neto Incident Monitor/`. Numer wersji 1.9.0 zachowany zgodnie ze zleceniem; nie zastąpiono działającej instalacji, nie zmieniono tagu, nie utworzono publikacji.
- **Pozostałe decyzje:** okres i zasady retencji outbox (ewentualna migracja osobno), docelowe ścieżki logów źródłowych oraz publikacja nowego wydania. Brak nowego odbioru rzeczywistego ServiceNow/SSO i brak wielostronicowego odbioru zagrożeń.

Odtworzenie regresji: `.venv\Scripts\python.exe -B -m tools.run_regression --output build/regression.json`. Raporty etapów: `build/audit-stageN-tests.json`, końcowe wyniki smoke: `build/audit-stageN-smoke.json`. Próby syntetyczne nie używały profilu działającego monitora ani nie wysyłały wiadomości biznesowych. Walidacja uszkodzonych danych nie zapisuje konfiguracji/historii; zapis stałej kategorii w diagnostyce pozostaje dozwolony.

## Ocena i sposób klasyfikacji

Najważniejsze ustalenia dotyczą odporności na awarie diagnostyki, obsługi błędów trwałej kolejki alertów oraz kompletności wiadomości. Nie wykryto potwierdzonego problemu P0. Nie jest to gwarancja braku innych usterek ani certyfikat bezpieczeństwa.

- **P0** — bezpośrednie zagrożenie wymagające natychmiastowego zatrzymania eksploatacji.
- **P1** — pilna naprawa: błąd może przerwać kluczową funkcję aplikacji.
- **P2** — istotny błąd w określonym scenariuszu lub konkretne ryzyko eksploatacyjne.
- **P3** — mniejszy błąd narzędzia, dokumentacji lub jakości utrzymania.

„Potwierdzony” oznacza reprodukcję lokalną albo jednoznaczny przepływ wykonania w kodzie. Nie oznacza wystąpienia u użytkownika. Ryzyka przyszłego wzrostu danych i sugestie architektoniczne są opisane osobno. Numery linii odnoszą się do badanego stanu, przed naprawami.

## 1. Mapa projektu i przepływów

Windows, Python 3.12, Tkinter/ttk, synchroniczny Playwright z Chromium, SQLite z biblioteki standardowej, urllib, Windows DPAPI/Win32 przez ctypes, Pillow, plyer i pystray. Pakowanie: PyInstaller, PowerShell, BAT i VBS. Nie znaleziono serwera aplikacyjnego, zewnętrznej bazy ani bezpośredniego klienta API ServiceNow.

Przepływy:

1. `launcher.pyw` → blokada instancji → wznowienie ewentualnego resetu → logi → `app.main` → Tk.
2. Tk → preferencje/kolejki → jeden worker Playwright → SSO/ServiceNow → walidacja tabeli, typu, warunków i paginacji → transakcja historii/obecności/alertów → kolejka wyników → Tk.
3. Dashboard → wspólny budżet i właściciel ponowień sekcji → kompletna migawka sekcji → Tk/cache. Kliknięcie kafelka osobno zleca pozyskanie celu na tymczasowej karcie.
4. Zagrożenia → sześć liczników → próba kompletnej listy → SQLite → wspólna kolejka alertów. Brak pełnej listy zachowuje wcześniejszą historię.
5. Automatyczne alerty → SQLite outbox → `alert_writer` → Windows/Teams/Chat. Testy i wysyłki ręczne mają odrębne kolejki `Sender`.
6. Historia edytowana przez UI → `history_writer`; duże tabele → przygotowanie w tle i porcjowanie operacji Tk.
7. Konfiguracja → atomowa podmiana pliku; webhooki → DPAPI użytkownika. Reset → znacznik, zamknięcie właścicieli danych, staging, usunięcie i autostart.

### Pokrycie przeglądu kodu

Poniższa mapa obejmuje wszystkie **54 moduły pakietu**. W grupach przejrzano odpowiedzialności, istotne ścieżki wykonania i kontrakty między modułami. Nie oznacza to wykonania każdej gałęzi ani formalnej weryfikacji każdego wywołania Win32.

| Obszar | Pliki w `neto_incident_monitor/` | Sprawdzony zakres |
| --- | --- | --- |
| Koordynacja | `app.py`, `monitoring.py` | Start/Stop, harmonogram, odczyty, kolejki, rewizje, generacje, zdarzenia, restart Chromium, zamykanie |
| SSO | `authentication.py`, `automatic_login.py`, `login_observation.py` | Pochodzenie strony, obserwacja bez wartości poświadczeń, popupy, ręczne przejęcie, dostarczenie kliknięcia, odzyskiwanie sesji |
| Przeglądarka | `browser_actions.py`, `browser_policy.py`, `browser_rendering.py`, `browser_window.py`, `browser_icon.py` | Właściciel Playwright, budżety, widoczność, CDP, cleanup, ograniczenie operacji do własnego procesu |
| Listy | `service_now_urls.py`, `list_context.py`, `pagination.py`, `read_budget.py` | Polityka URL, skróty i opakowania, warunki/widoki, pager, kompletność, ponowienia, anulowanie |
| Kolumny i tabele | `columns.py`, `dynamic_columns.py`, `table_loading.py` | Schemat, sortowanie, daty, prezentacja, anulowanie, porcjowanie, zapisy ustawień |
| Dashboard | `dashboard.py`, `dashboard_context.py`, `dashboard_cache.py`, `dashboard_drilldown.py`, `dashboard_progress.py`, `dashboard_ui.py`, `section_runner.py` | Kafelki, zero/brak/błąd, okres, filtry kategorii, retry, cache, transakcja UI, linki, postęp |
| Zagrożenia | `threatened.py`, `threatened_ui.py` | Liczniki, lista SLA, scalanie po INC, zgodność liczebności, historia, aktualność, nawigacja |
| Dane | `history.py`, `filter_state.py`, `secret_config.py`, `data_reset.py`, `default_filters.py` | Migracja, transakcje, blokady, outbox, szyfrowanie, walidacja, atomowe podmiany, reset |
| Powiadomienia | `teams_notifications.py`, `google_chat_notifications.py`, `notification_text.py`, `notification_templates.py`, `template_library.py` | Docelowe hosty, brak redirectów, escaping, szablony literalne, podział wiadomości, kolejki |
| Ustawienia powiadomień | `filter_settings.py`, `google_chat_ui.py`, `notification_template_ui.py`, `template_library_ui.py` | Draft/zapis, rollback, wybór szablonu, testy, zachowanie niedostępnych sekretów |
| UI i system | `ui.py`, `settings_ui.py`, `widgets.py`, `theme.py`, `themed_dialogs.py`, `tray.py`, `window_style.py`, `startup.py`, `single_instance.py` | Tk, zasobnik, kontrolki, dialogi, układ, autostart, mutex, komunikacja z głównym wątkiem |
| Podstawy i aktualizacje | `runtime_paths.py`, `safe_logging.py`, `login_diagnostics.py`, `release_check.py`, `__init__.py` | Ścieżki, rotacja, wyjątki, allowlisty, korelacja, HTTP aktualizacji i wersjonowanie |

Dodatkowo przejrzano: `launcher.pyw`, `start.bat`, `Neto Incident Monitor.vbs`, oba pliki requirements, spec i skrypt buildu, `tools/package_smoke.py`, `tools/preview_ui.py`, strukturę 65 modułów testowych i fixture, `.gitignore`, manifest motywu oraz dokumentację bieżącej architektury, indeksów decyzji/planów, kontraktów i wybranych decyzji związanych z badanymi przepływami. Sprawdzono powiązania z opisem i odbiorem wydania 1.9.0. Zasoby graficzne zinwentaryzowano; nie przeprowadzano ich szczegółowego audytu wizualnego.

### Obszary pominięte lub zweryfikowane częściowo

| Obszar | Ograniczenie i powód |
| --- | --- |
| Rzeczywisty DOM ServiceNow i SSO | Inwentaryzacja przeglądarki Codex wykazała brak otwartych kart/sesji. W systemie działa monitor; nie przejmowano jego przeglądarki ani profilu. Nie zweryfikowano aktualnych selektorów, MFA, dat/filtrów, leniwego renderowania ani przejść stron na produkcji. |
| Rzeczywiste dostarczenie powiadomień | Nie wysyłano wiadomości Windows/Teams/Chat do użytkownika lub kanałów biznesowych. Testy transportów i reprodukcje używają danych syntetycznych/mocków. |
| EXE/ZIP, podpis, publikacja | Tylko przegląd kodu pakowania i wcześniejszego raportu. Nie wykonano nowego buildu, smoke testu paczki, porównania binariów ani kontroli opublikowanego wydania. Audyt/plany nie upoważniają do budowania według AGENTS.md. |
| Dane użytkownika i sesja | Nie analizowano treści `data/`, profili, produkcyjnego SQLite, cookies, logów ani webhooków. Nie wykonywano resetu danych użytkownika. |
| Inne lokalne materiały | `raporty-sprzetu/`, nieśledzone notatki tekstowe, `.venv/`, `build/`, `dist/`, `.git/` nie były przeglądane jako kod aplikacji. Z `.venv` odczytano wyłącznie metadane pakietów i uruchamiano istniejące narzędzia. Nie wykonywano audytu całej historii Git. |
| Dokumentacja historyczna | Zinwentaryzowana; nie czytano każdego archiwalnego raportu i planu. Nie zastępuje bieżącej obserwacji produkcji. |
| Zależności | `pip check`, wersje i ograniczone sprawdzenie advisory producentów. Bez pełnego skanera SCA, audytu kodu bibliotek, SBOM i oceny wszystkich podatności Chromium. |

## 2. Kontrole wykonane podczas audytu

- Sprawdzono strukturę plików oraz stan Git. Przed audytem istniały dwie nieśledzone notatki; nie zmieniano ich.
- Wykonano kompilację składni przez `compile(..., 'exec')` w pamięci dla **126 plików Python/PYW** pakietu, testów, narzędzi i launchera: poprawna. Bez `compileall` i bez zapisywania bajtkodu przez tę kontrolę.
- `.venv\Scripts\python.exe -B -m pip check`: **No broken requirements found**. To kontrola zgodności zależności, nie ich bezpieczeństwa.
- Odczytane wersje: Playwright 1.63.0, Pillow 13.0.0, plyer 2.1.0, pystray 0.19.5, PyInstaller 6.22.3. Requirements dopuszczają zakresy dla części bibliotek; brak lockfile całego środowiska.
- Ruff, mypy, Bandit, pip-audit i coverage nie są zainstalowane w projektowym venv. Nie instalowano ich i nie twierdzimy, że wykonano lint/typecheck/SAST/SCA lub pomiar pokrycia. Nie znaleziono workflow CI w `.github/workflows`.
- Pierwsze uruchomienie `unittest discover -s tests -v` w sandboxie zostało przerwane: błędy sprzątania `TemporaryDirectory` (`PermissionError`) i zatrzymanie postępu przy testach Chromium. Próba modułów z limitem czasu także została przerwana. Nie zaliczono tych prób jako regresji aplikacji.
- Uruchomiono pełne `unittest` poza sandboxem z `runtime_paths.DATA` skierowanym przed importem aplikacji do osobnego `TemporaryDirectory`. Dane wykonawcze tej próby były odizolowane; używano istniejącego venv i `-B`. **465 testów w 631,438 s: 463 zaliczone, 2 pominięte, 0 failures, 0 errors; unittest: OK (skipped=2).** Przebieg wykonano w jednym procesie, w odróżnieniu od wcześniejszego odbioru modułowego wydania.
- **Kod zakończenia całego polecenia wyniósł 1:** po ukończeniu testów zewnętrzny `TemporaryDirectory` nie mógł usunąć `login-diagnostics.jsonl` (WinError 32). Runner audytu nie zamknął globalnego handlera przed sprzątaniem. To błąd sprzątania runnera audytu, nie niezaliczona asercja i nie dowód błędu produkcyjnego resetu. Nie ukryto go jako sukcesu całego polecenia.
- Dodatkowo powtórzono wyłącznie moduły `test_browser_window` i `test_data_reset`, aby wyjaśnić pominięcia: **16 testów, 14 zaliczonych, 2 pominięte, 14,661 s, kod zakończenia 0**. Windows nie przyznał testowej aplikacji fokusu (`test_passive_show_keeps_foreground_and_supports_browser_actions`); tworzenie symlinka było niedostępne (`test_redirect_in_profile_is_rejected`). Tym razem runner jawnie zamknął diagnostykę przed sprzątaniem. Pozostałość po pierwszym runnerze usunięto po zakończeniu procesu, sprawdzając dokładną ścieżkę jego katalogu tymczasowego.
- Podczas testów występują komunikaty Tcl o timerach po zniszczeniu okien (`invalid command name`, `application has been destroyed`). Sam wynik unittest nie obejmuje wszystkich takich błędów callbacków — patrz A09.
- Wykonano dodatkowe, jednorazowe reprodukcje w pamięci: awaria handlera logów, rozmiar payloadu Teams, utrata treści Chat, wyjątek zadania outbox, nieprawidłowe struktury konfiguracji i istnienie metody wywoływanej przez preview. Nie dodano plików testów ani nie uruchamiano transportów sieciowych.

### Zależności i bezpieczeństwo — granice wniosku

Nie stwierdzono w tym zakresie potwierdzonej podatności zainstalowanego pakietu. Nie oznacza to wyniku „zero CVE”. Sprawdzony [komunikat producenta Pillow o Ghostscript](https://github.com/python-pillow/Pillow/security/advisories/GHSA-w889-685w-c8fh) wskazuje poprawkę w 13.0.0, czyli wersji przypiętej w projekcie. Sprawdzono również [komunikat producenta o dekoderze JPEG](https://github.com/python-pillow/Pillow/security/advisories/GHSA-8g5g-8vmr-9782) i [stronę advisory Playwright](https://github.com/microsoft/playwright/security/advisories). Ta wyrywkowa kontrola nie zastępuje SCA całego środowiska i dołączonej przeglądarki.

## 3. Potwierdzone błędy — kolejność według pilności

### A01 — P1: awaria zwykłego logu powoduje rekurencję i może przerwać działanie

**Lokalizacja:** `launcher.pyw:18`, `launcher.pyw:52`, `launcher.pyw:59`; porównaj bezpieczny handler w `safe_logging.py:10`.

**Dowód:** zwykły `RotatingFileHandler` przy błędzie emituje diagnostykę logging na stderr. Launcher zastępuje stderr przez `LogStream`, który ponownie zapisuje do tego samego loggera. W reprodukcji handler z `delay=True` miał `shouldRollover` zgłaszające syntetyczny `OSError`; stderr był `LogStream`. Jedno `root.error` zakończyło się **RecursionError po 125 próbach**. Plik logu nie był tworzony.

**Konsekwencje:** pełny dysk, utrata uprawnień albo błąd rotacji może zamienić zwykły wpis w wyjątek, zamaskować pierwotną przyczynę i przerwać callback/worker. Specjalizowany log JSONL ma ochronę, ale ogólny log jej nie dziedziczy.

**Pewność:** wysoka; reprodukcja lokalna. Nie symulowano rzeczywistego zapełnienia dysku użytkownika.

**Naprawa:** wykorzystać istniejący `DiagnosticFileHandler` lub wspólny równoważny mechanizm bez rekurencyjnego stderr, z ograniczeniem prób i ostrzeżeniem poza uszkodzonym sinkiem. Objąć także inicjalizację logu oraz `flush`.

**Ryzyko zmiany:** małe/średnie. Testować błąd zapisu i rotacji, przywrócenie IO, brak sekretów, brak zalewu komunikatów i zachowanie pierwotnego błędu.

### A02 — P2: błędy magazynu kolejki alertów giną w nieobserwowanym Future

**Lokalizacja:** `app.py:1183`, `app.py:1185`, `app.py:1191`, `app.py:1222`; zlecenia `app.py:1933`, `app.py:2207`, `app.py:2388`.

**Dowód:** odczyt `pending_alerts` oraz część przejść stanów są poza ochroną właściwej wysyłki. Wyniki `alert_writer.submit(...)` nie mają callbacka analizującego wyjątek, w przeciwieństwie do `write_history`. Reprodukcja: `pending_alerts` zgłasza syntetyczny `sqlite3.OperationalError`; `Future.exception()` zawiera ten błąd, kolejka UI ma **0 zdarzeń**. Wyjątki z ThreadPoolExecutor nie trafiają do `threading.excepthook`.

**Konsekwencje:** chwilowy problem SQLite może zostawić pending bez informacji dla użytkownika i bez zaplanowanego ponowienia do nowego zdarzenia lub restartu monitoringu. Awaria zapisu wyniku może zostawić sending; kolejny start oznaczy go uncertain. To wymaga zachowania ostrożności wobec duplikatów, ale nie uzasadnia cichego błędu infrastruktury.

**Pewność:** wysoka dla zgubienia błędu; scenariusz zablokowanej produkcyjnej bazy nie był wykonywany.

**Naprawa:** dodać obserwację każdego Future i wspólne bezpieczne zdarzenia kolejki. Dla błędów przed rozpoczęciem wysyłki zapewnić ograniczone, przerywalne wznowienie w obecnym workerze. Zachować zasadę niepowtarzania niepewnego POST. Ujednolicić diagnostykę także dla filtrów — `log_threatened_delivery` obecnie pomija ich zadania.

**Ryzyko zmiany:** średnie; testować blokadę bazy, błąd przejścia stanu, Stop, restart i brak podwójnej wysyłki.

### A03 — P2: dzielenie Teams nie gwarantuje limitu gotowego payloadu

**Lokalizacja:** `teams_notifications.py:79–89`.

**Dowód:** sprawdzenie 25 000 bajtów działa tylko, gdy `current` już zawiera tekst. Pojedyncza część długości do 1000 znaków może po zamianie numerów na linki i zapisaniu dwóch reprezentacji przekroczyć limit. Reprodukcja: 190 powtórzeń `INC1`, oddzielonych spacją, jeden poprawny syntetyczny link rekordu i tytuł `Synthetic`. `message_chunks` zwraca jedną część; JSON z `payload` ma **36 621 bajtów**. Nie wysyłano jej do Teams.

**Konsekwencje:** brak gwarancji deklarowanej przez funkcję, ryzyko odrzucenia dużej wiadomości. Nie potwierdzono konkretnego kodu HTTP prawdziwego endpointu. Tytuł również nie ma niezależnego budżetu długości.

Kontrola z numerem o długości akceptowanej przez czytnik: 90 powtórzeń `INC1234567` (989 znaków tekstu), syntetyczny sys_id i dopuszczalny 64-znakowy `sysparm_view` dają jeden payload **33 001 bajtów**. Błąd nie wymaga krótkich identyfikatorów testowych.

**Pewność:** wysoka dla przekroczenia lokalnego limitu; średnia dla zachowania konkretnej konfiguracji Teams.

**Naprawa:** mierzyć końcowy JSON również dla pierwszego atomu, dzielić adaptacyjnie z zachowaniem numerów/linków i jawnie obsłużyć zbyt długi nagłówek. Nie ucinać treści.

**Ryzyko zmiany:** małe/średnie; regresje Unicode, escaping, długich tytułów, granic linków i kompletności partii.

### A04 — P2: Google Chat bezpowrotnie ucina treść po rozwinięciu linków

**Lokalizacja:** `google_chat_notifications.py:38–67`, szczególnie `55–56`.

**Dowód:** funkcja dzieli surową linię, następnie rozwija linki i przy >26 000 bajtów ucina gotowy tekst. Reprodukcja: 590 powtórzeń `INC1` z poprawnym syntetycznym linkiem daje jeden payload, **295 wystąpień numeru zamiast 590** i końcową wielokropkową informację o obcięciu. Kod nie tworzy kolejnej części z utraconego sufiksu.

**Konsekwencje:** ubytek danych w poprawnie wygenerowanej wiadomości; możliwe przecięcie składni linku. Dotyczy linii mocno rozbudowywanych przez linki, np. własnego szablonu. Nie twierdzimy, że każdy zwykły alert jest obcinany.

Kontrola z `INC1234567`: 270 powtórzeń (2969 znaków) i link z dopuszczalnym 64-znakowym `sysparm_view` pozostawiają **151 pełnych wystąpień** w jednym payloadzie zakończonym wielokropkiem.

**Pewność:** wysoka; reprodukcja lokalna.

**Naprawa:** pakować tokeny tekst/link w części z pomiarem końcowego JSON, zamiast obcinać bajty gotowego markup. Zapewnić zachowanie całej treści i poprawność każdej części.

**Ryzyko zmiany:** małe/średnie; testy kompletnych numerów, kolejności, wielobajtowego Unicode i limitów po serializacji.

### A05 — P2: nieprawidłowa struktura lokalnej konfiguracji może zablokować cały start

**Lokalizacja:** `secret_config.py:143–144`, `app.py:158–175`, `app.py:673`; analogiczna granica w `history.py:24–46`.

**Dowód:** `load_filters(..., tolerate_invalid=True)` toleruje nieprawidłowy URL, lecz nie strukturę dokumentu. Dla `{'filters': None}`, `{'filters': [{}]}`, `{'filters': [None]}` otrzymano odpowiednio **TypeError, KeyError, TypeError**. Konstruktor App wywołuje tę funkcję przed zakończeniem budowy UI; globalna obsługa wyświetla błąd i kończy aplikację. Niepoprawny JSON także nie ma lokalnej ścieżki odzyskania. History waliduje słownik zewnętrzny, ale zakłada strukturę jego rekordów.

**Konsekwencje:** częściowo uszkodzony lub ręcznie edytowany lokalny plik blokuje również ustawienia/reset dostępny przez UI. Nie jest to potwierdzona możliwość zdalnego ataku ani dowód, że normalny atomowy zapis generuje taki plik.

**Pewność:** wysoka dla konfiguracji; przegląd statyczny dla analogicznej obsługi uszkodzonych rekordów historii.

**Naprawa:** walidacja typów i wymaganych pól na granicy odczytu, kontrolowany tryb naprawy z zachowaniem pliku, rozróżnienie złej konfiguracji od awarii IO. Nie zastępować automatycznie uszkodzonej historii pustą i nie nadpisywać nieczytelnych sekretów.

**Ryzyko zmiany:** średnie; konieczne testy migracji, uszkodzeń i braku cichej utraty danych.

### A06 — P3: narzędzie podglądu wywołuje usuniętą metodę

**Lokalizacja:** `tools/preview_ui.py:30`.

**Dowód:** `app.history.mark_read(...)` nie istnieje w aktualnej klasie History; `hasattr(History, 'mark_read')` daje **False**. Kod narzędzia nadal ustawia także dawny `new_numbers`. Usunięcie stanu przeczytania jest opisane w decyzji 012.

**Konsekwencje:** standardowy przebieg narzędzia kończy się AttributeError przed wykonaniem podglądu. Nie uruchamiano go w całości, ponieważ zapisuje obraz w `data/`; brak metody potwierdzono bez tego zapisu.

**Pewność:** wysoka.

**Naprawa:** usunąć nieaktualne wywołania, dostosować syntetyczne URL do aktualnej polityki i izolować także cache/diagnostykę. Dodać krótki test samej ścieżki demo.

**Ryzyko zmiany:** małe, poza funkcją produkcyjną monitora.

## 4. Konkretne ryzyka eksploatacyjne i luki w kontroli jakości

### A07 — P2: kolejka przechowuje wszystkie zakończone payloady bez retencji

**Lokalizacja:** `history.py:84–89`, `history.py:124–148`, `app.py:1183`.

**Dowód:** outbox dodaje pełny payload, a zakończenie zmienia jedynie state. W pakiecie nie znaleziono usuwania zakończonych alertów ani polityki retencji. Odczyt pending filtruje po state i sortuje po rowid; schemat nie ma indeksu po state. Historia zagrożeń i zbiór ever także rosną wraz z kolejnymi rekordami.

**Konsekwencje:** trwały wzrost bazy i czasu skanowania outbox, dłuższe przechowywanie kopii treści biznesowych. To **ryzyko przy długiej pracy**, nie zmierzony wyciek RAM ani potwierdzona powolność bieżącej bazy.

**Pewność:** wysoka dla braku retencji/indeksu, średnia dla praktycznej skali wpływu.

**Naprawa:** uzgodnić czas przechowania accepted/cancelled, zachować potrzebne informacje o uncertain, usuwać porcjami w tle; rozważyć indeks pending po pomiarze. Oddzielić retencję technicznego payloadu od świadomej historii użytkownika. Nie usuwać pending/sending.

**Ryzyko zmiany:** średnie; migracja schematu, kopia danych i testy restartu/niepewnej wysyłki. Nie wprowadzać automatycznego VACUUM w wątku UI.

### A08 — P3: synchroniczne IO w Tk pozostaje źródłem opóźnień

**Lokalizacja:** `dashboard_ui.py:410`, `dashboard_ui.py:424`, `dashboard_cache.py:81–99`, `dynamic_columns.py:199–217`.

**Dowód:** cache jest zapisywany z obsługi wyniku na Tk; ponowienia PermissionError śpią łącznie 300 ms plus czas IO. Dopasowanie szerokości kolumny przechodzi synchronicznie po każdym załadowanym wierszu i mierzy tekst fontem Tk. Są to wyjątki od ogólnie poprawnego porcjowania dużych tabel.

**Konsekwencje:** możliwe zauważalne przerwy UI na wolnym/zablokowanym dysku i dużych tabelach. Nie wykonano benchmarku dużego produkcyjnego zbioru, więc nie klasyfikujemy tego jako zaobserwowanego zawieszania.

**Pewność:** wysoka dla miejsca wykonania; średnia dla odczuwalności.

**Naprawa:** cache zapisywać w istniejącym mechanizmie zadań z zachowaniem kolejności rewizji; pomiar fontu porcjować na Tk. Najpierw zmierzyć najgorszą przerwę pętli zdarzeń.

**Ryzyko zmiany:** średnie; możliwe zapisanie starej migawki po nowszej przy naiwnym przeniesieniu do tła.

### A09 — P3: wynik unittest może być zielony mimo błędów timerów Tcl

**Lokalizacja:** `tests/test_activity_status.py:17–18`, `app.py:728`, `app.py:2783`; także inne testy niszczące Tk bez wspólnego cleanup.

**Dowód:** w pełnym przebiegu obserwowano `invalid command name ...drain`, `...save_window_layout`, `...refresh` i `ttk::ThemeChanged` po zniszczeniu aplikacji. Cleanup testów nie jest jednolity: część anuluje timery, część tylko niszczy root. Są to komunikaty Tcl, a nie zawsze failure/error unittest.

**Konsekwencje:** szum utrudnia zauważenie rzeczywistego błędu UI; wykonanie wszystkich asercji nie dowodzi braku błędów callbacków. Nie potwierdzono na tej podstawie błędu normalnego produkcyjnego zamykania.

**Pewność:** wysoka dla przebiegu testów; przyczyna poszczególnych timerów może wymagać izolacji modułu.

**Naprawa:** wspólny cleanup Tk i zadań pomocniczych, przechwytywanie wyjątków callbacków jako błędów testów; zachować osobne procesy dla testów natywnych, jak przy wcześniejszym odbiorze wydania. Nie wyciszać globalnie stderr.

**Ryzyko zmiany:** małe/średnie, głównie testy. Cleanup nie może ukrywać niedokończonej istotnej operacji.

### A10 — P3: dokumentacja stanu wdrożenia i ścieżek diagnostyki jest niespójna

**Lokalizacja:** `docs/decyzje/005-kompletny-odczyt-listy.md:3`, `docs/decyzje/006-odczyt-sekcji-dashboardu.md:3`, `docs/decyzje/006-odczyt-sekcji-dashboardu.md:11`, `runtime_paths.py:13`, `launcher.pyw:52`, `login_diagnostics.py:263`.

**Dowód:** decyzje nadal mówią o braku odbioru nowego EXE oraz braku powiadomień zagrożeń, podczas gdy architektura i raport 1.9.0 opisują ich wdrożenie. Źródła zapisują logi w projektowym `data/`; AGENTS.md wymaga lokalnego katalogu danych użytkownika. Dokumentacja architektury opisuje ten wyjątek, ale nie usuwa sprzeczności z instrukcją repozytorium.

**Konsekwencje:** ryzyko błędnej interpretacji stanu wydania i niezamierzonego objęcia logów kopią całego katalogu projektu. `data/` jest ignorowany przez Git, a spec nie dołącza go do paczki — nie stwierdzono wycieku w bieżącym repozytorium.

**Pewność:** wysoka dla rozbieżności. W audycie nie porównywano obecnego EXE ze źródłami.

**Naprawa:** dopisać odnośniki do późniejszego odbioru bez usuwania historii uzasadnienia; jawnie uzgodnić politykę logów źródłowych, a ewentualną zmianę ścieżki wdrożyć z migracją i ochroną przed kolizją instancji.

**Ryzyko zmiany:** małe dla dokumentów, średnie dla ścieżek — wpływ na reset, blokadę instancji i istniejące dane.

## 5. Sugestie utrzymaniowe — nie są potwierdzonymi błędami funkcji

1. **Kontrolowane wydzielenie koordynacji alertów z App.** `app.py` ma około 3000 linii i łączy Tk, parsowanie, scheduling, transakcje i transport. Najpierw zamknąć A02 testami, potem wydzielić istniejące operacje outbox bez nowej równoległej implementacji. Nie proponuje się przepisywania UI ani migracji frameworka. Ryzyko średnie.
2. **Reprodukowalny odbiór zależności.** `requirements.txt:1` i `start.bat:8` pozwalają pobierać nowsze wersje przy kolejnym starcie skryptu. Zachować świadome aktualizacje bezpieczeństwa, ale utrwalać pełne wersje środowiska użytego do wydania i wersję Chromium; dodać odrębny kontrolowany krok aktualizacji. Brak lockfile nie dowodzi obecnej niezgodności. Ryzyko małe/średnie.
3. **Usuwanie pozostałości po wcześniejszych kontraktach dopiero po sprawdzeniu użycia.** `dynamic_columns.py:177` jest pustym hookiem, a dawne helpery pagera i formatowania są utrzymywane głównie dla testów/zgodności. `read_all` nadal przyjmuje `empty_list`, którego nowy czytnik nie używa. Nie jest to wystarczający powód do szerokiego sprzątania; usunąć lub opisać kompatybilność przy najbliższej zmianie danego kontraktu. Ryzyko małe przy kontroli wywołań.
4. **Jedno polecenie bezpiecznej regresji.** Obecny odbiór opisuje moduły w oddzielnych procesach, ale brak śledzonego runnera izolującego DATA i normalizującego wyniki/timeouty. Dodać go przed CI, bez danych konta i bez produkcyjnego profilu. Lint wdrażać stopniowo; nie mieszać masowej zmiany formatowania z naprawami funkcjonalnymi.

Nie proponuje się zmian wyłącznie stylistycznych. Duplikacja kodu Win32, dwa typy nadawców i rozmiar App są kosztami utrzymania, ale nie zostały same w sobie uznane za błędy P1/P2.

## 6. Dobre mechanizmy, które należy zachować

- Jeden właściciel operacji Playwright i komunikacja do Tk przez kolejki.
- Odrzucanie niekompletnego odczytu zamiast zapisywania częściowego wyniku jako zera.
- Powiązanie listy, pagera, typu rekordu, warunków i schematu oraz ponowienie od początku.
- SQLite obejmujące historię, obecność i utworzenie alertu w jednej transakcji; testy rollbacku.
- Rozróżnienie pending/sending/uncertain i brak automatycznego ponowienia niepewnego POST.
- Polityka zaufanych hostów, walidacja linków rekordów, brak przekierowań webhooków, escaping danych i szablony bez eval.
- DPAPI użytkownika, atomowa podmiana konfiguracji i zachowanie nieczytelnego szyfrogramu przy innych zmianach.
- Strukturalne allowlisty diagnostyki, bezpieczny formatter wyjątków i ograniczony handler JSONL.
- Rozdzielenie czasów sukcesu sekcji dashboardu i ochrona okresu aktywnego żądania.
- Znacznik wznowienia resetu, blokada instancji i odrzucanie reparse pointów.

Te mechanizmy zmniejszają ryzyko, lecz testy syntetyczne nie potwierdzają aktualności DOM i zachowania dzisiejszej usługi ServiceNow.

## 7. Plan napraw w bezpiecznych etapach

| Etap | Zakres | Kryterium odbioru i ryzyko |
| --- | --- | --- |
| 1. Odporność infrastruktury | A01, A02 | Syntetyczne błędy zapisu/rotacji i SQLite nie przerywają funkcji ani nie giną; UI otrzymuje bezpieczny wynik; brak sekretów w logach; brak automatycznego duplikowania niepewnej wysyłki. Osobne małe zmiany. |
| 2. Kompletność powiadomień | A03, A04 | Każdy końcowy JSON mieści się w przyjętym limicie; cała treść i kolejność są zachowane; testy długich linków, nagłówków, Unicode i częściowego przyjęcia. Bez rzeczywistej wysyłki do biznesowego kanału. |
| 3. Odzyskiwanie danych i retencja | A05, A07 | Macierz uszkodzeń konfiguracji/historii, brak nadpisania danych przy błędzie, jawny tryb naprawy; migracja retencji sprawdzona na syntetycznej bazie i kopii, nigdy na jedynej produkcyjnej bazie. |
| 4. Powtarzalne narzędzia i regresja | A06, A09, runner, kontrola zależności | Preview działa na izolowanych danych; testy nie zostawiają aktywnych timerów i wykrywają błędy callbacków; odtwarzalne wersje odbioru. |
| 5. Pomiary i dokumentacja | A08, A10 | Pomiar opóźnień Tk przed/po, brak zapisu starego cache po nowym, zgodność dokumentacji i jawna polityka ścieżek. Dopiero potem małe refaktoryzacje. |
| 6. Osobny odbiór integracyjny i wydania | ServiceNow, pełne SSO/MFA, zagrożenia wielostronicowe, paczka | Osobna sesja/profil, najpierw obserwacja DOM; potwierdzone selektory i zachowanie, przywrócenie dat/filtrów. Build i publikacja dopiero na osobne zlecenie. Wyniki produkcji, syntetyczne i EXE raportować oddzielnie. |

Odłożona paginacja listy zagrożeń jest istniejącym ograniczeniem produktu, nie nowo odkrytą regresją: `threatened.py` odrzuca niekompletną stronę, a plan wymaga rzeczywistej listy wielostronicowej. Nie obchodzić tego przez akceptowanie pierwszej strony. Nie rozszerzać zakresu o SMTP, równoległe sterowanie Chromium ani nowy magazyn danych w ramach tych napraw.
