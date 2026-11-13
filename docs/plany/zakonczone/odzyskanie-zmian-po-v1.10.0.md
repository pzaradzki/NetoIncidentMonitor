# Odzyskanie zmian po wydaniu 1.10.0

**Zakończono 12 listopada 2026.** Odtworzono 38 brakujących plików i przeniesiono je do repozytorium. Użytkownik potwierdził, że jedno kliknięcie przycisku monitora na pasku zadań przywraca jego okno.

**Punkt odniesienia.** GitHub opublikował [v1.10.0](https://github.com/pzaradzki/NetoIncidentMonitor/releases/tag/v1.10.0) 12 listopada o 11:11:40 czasu warszawskiego. Tag wskazuje `750707260f296b74c6896816b6f901454bfb2598`. Commit bazowy `c51b75f` dopisał dokumentację odbioru i publikacji. Ustalenie opiera się na lokalnym [raporcie wydania](wydanie-1.10.0.md), `build/release-1.10.0-verified.json` i porównaniu tagu z tym commitem.

Po każdym wykonanym i sprawdzonym kroku od razu zaznacz jego checkbox i dopisz wynik, źródło odzyskanego kodu oraz wynik testu. Jeżeli przerwiesz pracę, zapisz stan, przeszkodę i następny krok przy otwartym checkboxie. Zaznacz etap po zakończeniu jego kroków. Po wznowieniu przeczytaj ostatnią notatkę i sprawdź diff.

- [x] **Inwentaryzacja.** Przejrzano główny czat od publikacji do utraty plików oraz wykonane poprawki z narzędzi. Powiązano pięć zmian z plikami, zachowaną dokumentacją i wynikami testów. `git ls-files --deleted` zwrócił 38 ścieżek, w tym 18 objętych poprawkami po wydaniu. W 20 pozostałych nie znaleziono zmian po wydaniu w przejrzanym czacie.

| Zmiana w kolejności z czatu | Stan po utracie plików | Zachowany ślad |
| --- | --- | --- |
| Wskaźniki Windows, Google Chat i Teams na liście filtrów | Brakuje kodu widoku i testu. Trzy obrazy PNG oraz wpisy pakowania są na dysku. | 13:19–13:27, instrukcja, `build/filter-notification-icons-tests.json` |
| Google Chat nad Microsoft Teams w ustawieniach filtra | Brakuje kodu i testu ustawień. | 13:29–13:30, `build/filter-notification-order-tests.json` |
| Przekazanie fokusu po ukryciu Chromium | Brakuje kodu i testów. Pierwsza wersja poprawki była gotowa przed kolejnym zgłoszeniem o zasłoniętym oknie. | 13:31–13:36, architektura, `build/login-focus-regression.json` i `build/login-focus-startup.json` |
| Dodawanie, edycja i usuwanie filtrów podczas monitoringu | Brakuje kodu interfejsu, kolejki, zapisu historii, konfiguracji i zmienionych testów. | 13:43–14:05, [decyzja 027](../../decyzje/027-zmiany-filtrow-podczas-monitoringu.md), `build/live-filter-final-regression.json` i `build/live-filter-ui-rerun.json` |
| Odsłonięcie i natywne przywracanie okna | Brakuje kodu i testów. Natywna próba przeszła przed utratą plików. Odbiór pierwszego kliknięcia na pasku zadań został przerwany. | 14:10–14:29, [decyzja 028](../../decyzje/028-odsloniecie-glownego-okna.md), `build/recovery-login-focus-2026-11-12.json` |

Rozmowa o samym przycisku **Dodaj filtr** z 12:02 była analizą. Wdrożenie obejmujące dodawanie, edycję i usuwanie zaczęło się po zleceniu z 13:48. Wspólna sesja i jedna karta, import, kolejka ręcznych odczytów, odczyt wyłączonych filtrów, blokady przycisków aktualizacji, poprawka dashboardu, domyślne 60 s dla wniosków, odczyt 100 wierszy, kolumna **Wiek (min)**, wyśrodkowanie importu i ustawień, komunikat zapisu poświadczeń, szerokość panelu 329 px i pierwotna poprawka fokusu startu są już w tagu. Ich brak w katalogu roboczym uzupełnia baza Git.

- [x] **Etap 1. Zabezpiecz materiały i odtwórz bazę w osobnym katalogu**
  - [x] Zapisz bieżący stan Git i zabezpiecz zachowane zmiany w dokumentacji, `scripts/Neto Incident Monitor.spec`, trzy pliki w `icons/`, raporty regresji i pakiet odzyskiwania fokusu. Zachowaj pozostałe lokalne pliki użytkownika. Materiały potrzebne do odtworzenia oddziel od danych monitora, profilu Chromium i ustawień z poświadczeniami.
    - `build/odzyskanie-v1.10.0/00-stan.json` zawiera stan Git i 38 brakujących ścieżek. Sprawdzono odczyt i SHA-256 wszystkich 24 pozycji w `kopie/00-zachowane.zip`. Zakres archiwum nie obejmuje danych aplikacji, logów ani profilu.
  - [x] Sprawdź, czy IT udostępniło kopie sprzed incydentu SentinelOne. Porównuj je w osobnym katalogu z tagiem i spisem poniżej. Jeżeli brakuje potwierdzonych kopii, użyj bazy z Gita i pełnych poprawek z czatu. Na tym etapie istniejący katalog roboczy pozostaje punktem odniesienia.
    - Użytkownik potwierdził brak własnych ręcznych zmian i brak dostępnej kopii IT. Źródłem są `HEAD` oraz pełne poprawki zapisane w czacie.
  - [x] Przygotuj izolowany katalog z `c51b75f`. Potwierdź zgodność źródeł i testów z `v1.10.0` oraz obecność wszystkich 38 ścieżek z inwentarza. Przenieś zachowane pliki dopiero po porównaniu ich z bazą.
    - `zrodla/` odtworzono z `kopie/01-baza.zip`. Git wykazał identyczne moduły, testy, skrypty i zasoby w `c51b75f` i `v1.10.0`. Bajty wszystkich 38 ścieżek zgadzają się z archiwum.
  - [x] Wydobądź z zapisu głównego czatu wyłącznie pełne treści zmian do kodu i testów. Przypisz je do etapów według tabeli na końcu planu. Sprawdź pełność i udane wykonanie każdej poprawki. Jeżeli plik udało się odzyskać w nowszej wersji, porównaj go z zestawem poprawek i uzupełnij tylko brakujące fragmenty.
    - `02-poprawki.json` i `poprawki/` zawierają 39 oryginalnych operacji w grupach 5 + 1 + 3 + 16 + 14. Dla wszystkich sprawdzono pełny tekst i udane wywołanie. Zakres pokrywa 18 zmienianych brakujących ścieżek oraz zachowany plik `.spec`.
  - [x] Na czystej bazie sprawdź import modułów i uruchom testy bazowe kolejki, filtrów, startu i logowania na izolowanych danych. Zapisz ograniczenia środowiska i wynik niezależnie od późniejszej regresji.
    - Import `App` i `SharedSession` przeszedł. `01-regresja-bazowa-Windows.json` obejmuje 50 testów. Kolejka, transakcje i logowanie zaliczyły 40. Moduł startu zgłosił dwa błędy podprzypadków minimalizacji i zasobnika na czystej bazie. Ograniczone środowisko odmówiło zapisu w domyślnym katalogu tymczasowym oraz dostępu do testowego klucza rejestru. Te wyniki są punktem odniesienia dla regresji, bez przypisywania ich odtworzonym zmianom.

- [x] **Etap 2. Odtwórz ikony powiadomień na liście filtrów**
  - [x] Połącz listę z trzema zachowanymi PNG. Wyświetl wskaźniki **Windows → Google Chat → Teams** tuż przed przełącznikiem filtra. Zachowaj ich informacyjną rolę.
    - Odtworzono oryginalną zmianę widoku. SHA-256 trzech PNG zgadza się z zachowaną kopią. Testy widoku przeszły (6).
  - [x] Pokaż kolor dla kanału włączonego w danym filtrze i szarość dla wyłączonego. Ukryj kanał wyłączony globalnie. Zachowaj dotychczasowe wartości domyślne, gdy w starszej konfiguracji brakuje flagi danego kanału.
    - Odtworzono reguły 1:1. Test widoku potwierdza kolory i znikanie kanału. Domyślne flagi zweryfikowano w odtworzonym kodzie.
  - [x] Odśwież wskaźniki przy pierwszym wyświetleniu listy, po zmianie globalnego przełącznika i po udanym zapisie ustawień filtra. Sprawdź też wiersz filtra wyłączonego z harmonogramu i zachowanie po przebudowie listy.
    - Test widoku przechodzi po zmianie globalnej i po zapisie filtra, a pięć testów zmiany kolejności przeszło. Stan ikony jest niezależny od przełącznika harmonogramu.
  - [x] Odtwórz układ dla szerokiego i wąskiego panelu. W szerokim panelu **Aktualizuje** mieści się przed ikonami. W wąskim przechodzi pod nazwę, a ikony pozostają w jej rzędzie. Sprawdź obcięcie długich nazw i brak nakładania na przełącznik.
    - Test Tk odtworzył wąski panel i rozłączne pozycje statusu, ikony oraz nazwy. `kopie/02-ikony.zip` i manifest zabezpieczają ten stan źródeł i testów.
  - [x] Porównaj zachowane wpisy `.spec` z trzema plikami z `icons/`. Odtwórz testy widoku, w tym zmianę ustawień i wąski panel, oraz uruchom regresję. Punktem porównania jest 67 wcześniej zaliczonych testów zakresowych.
    - Odtworzona treść `.spec` zgadza się z zachowaną. `02-regresja.json` potwierdza wynik 67/67 testów, bez pominięć.

- [x] **Etap 3. Odtwórz kolejność w ustawieniach filtra**
  - [x] Umieść **Powiadomienia Google Chat** nad **Powiadomieniami Microsoft Teams** w oknie **Ustawienia filtra**.
    - Odtworzono oryginalną zmianę z wiersza 4557. Kolejność w kodzie jest zgodna z ustaleniem.
  - [x] Sprawdź, czy przełącznik i zębatka w każdym wierszu nadal obsługują właściwy kanał, także gdy drugi jest wyłączony globalnie. Odtwórz testy wybierające zębatkę po nazwie kanału oraz przypadki zapisu i czyszczenia adresu. Wcześniej przeszło sześć testów widoku.
    - `03-regresja.json` potwierdza 6/6, w tym wybieranie ustawień po nazwie. Sprawdzono 39 plików w `kopie/03-kolejnosc.zip`.

- [x] **Etap 4. Odtwórz wcześniejsze przekazanie fokusu**
  - [x] Przy pierwszym logowaniu potwierdź ukrycie Chromium, pokaż główne okno i sprawdź osobno pierwszoplanowe okno Windows oraz fokus klawiatury Tk. Zachowaj ograniczone ponowienie i pomiń aktywację przy starcie zminimalizowanym lub gdy fokus należy do modalu aplikacji.
    - Odtworzono oryginalne zmiany startu. Przeszły testy natywnego logowania, wspólnej sesji i modułu startu.
  - [x] Przy odzyskiwaniu sesji utrwal, czy Chromium było na pierwszym planie przed ukryciem lub czy użytkownik zakończył aktywny komunikat zapisu poświadczeń. Przekaż fokus monitorowi w tych przypadkach. Automatyczne odzyskanie w tle ma pozostawić fokus użytkownika w bieżącym oknie.
    - Odtworzono przekazanie sygnału do Tk i testy komunikatu poświadczeń oraz odzyskiwania bez aktywacji. Przeszło 15 testów `test_shared_session`.
  - [x] Odtwórz bezpieczną diagnostykę `session_visibility` dla pierwszego startu i odzyskania, z potwierdzeniem fokusu i wynikiem przekazania. Sprawdź rozdzielenie oczekiwania na logowanie od aktywacji okna i brak danych logowania w zapisach.
    - Odtworzono dozwolone pola i rozdzielne przyczyny przekazania. Testy sesji sprawdzają potwierdzenia fokusu. Kopia 39 ścieżek jest w `kopie/04-fokus.zip`.
  - [x] Odtwórz testy startu, odzyskania i powrotu z komunikatu zapisu poświadczeń. Wcześniej zaliczono 59 z 60 testów po osobnym powtórzeniu modułu startu. Jedna próba fokusu została pominięta przez ograniczenia Windows.
    - `04-regresja.json` ponownie wykazał 59 zaliczonych, 1 pominięty i 0 błędów. Pominięta próba dotyczy przyznawania fokusu przez Windows.

- [x] **Etap 5. Odtwórz edycję filtrów podczas monitoringu**
  - [x] Przywróć działanie **Dodaj filtr**, **Edytuj** i **Usuń** przy uruchomionym monitoringu. Zachowaj wyłączność względem otwartego importu i zamykania aplikacji. Przy zapisie ponownie sprawdź duplikaty oraz to, czy edytowany filtr nadal istnieje w tej samej wersji. Anulowanie i błąd zapisu mają zachować konfigurację, widok i zlecenia sprzed próby.
    - Odtworzono oryginalny zapis i blokady. Przeszły test przycisków podczas monitoringu oraz 25 testów importu.
  - [x] Powiąż wybór, tabelę, wykryte kolumny i status aktualizacji z konkretnym filtrem, z uwzględnieniem zmiany indeksów wierszy. Przy zmianie samej nazwy zachowaj aktywny odczyt, historię i układ kolumn. Zakończony wynik i status mają pokazywać aktualną nazwę.
    - Przywrócono mapowanie po adresie i bieżącej rewizji. Przeszły testy widoku, kolejności i zmiany nazwy.
  - [x] Po udanym zapisie odśwież filtry harmonogramu i obudź go. Dodany filtr lub nowy adres dołącz do pierwszej partii swojego typu utworzonej po zapisie. Skład rozpoczętej partii pozostaje ustalony. **Aktualizuj** pozwala odczytać filtr wcześniej, także gdy jest wyłączony z harmonogramu.
    - Zaliczone testy dodania podczas partii i ręcznych odczytów. Odtworzono wywołanie harmonogramu po zapisie.
  - [x] Zmiana adresu i usunięcie mają usunąć nieaktualne części oczekujących zleceń, zwolnić ich przyciski i przerwać odczyt w bezpiecznym punkcie. Sprawdź także oczekiwanie na logowanie i zgodę na dużą listę. Pozostałe operacje mają się wykonać. Po usunięciu ostatniego filtra monitoring nadal sprawdza zagrożenia SLA.
    - Przeszły test przerwania oczekiwania na logowanie i przejścia do następnego filtra oraz test zachowania cyklu po usunięciu ostatniego filtra. Zgoda na dużą listę zachowuje sprawdzanie przerwania w odtworzonej ścieżce odczytu.
  - [x] Utrwal zakres **Sprawdź teraz** przy przyjęciu żądania, razem z okresem dashboardu. Pomiń później unieważniony adres, zachowując resztę pracy. Kolejne zlecenie ma korzystać z aktualnego zestawu, także gdy nadal trwa zlecenie o innym zakresie. Sprawdź zgodne duplikaty, scalanie i reakcję na zmianę filtrów w trakcie partii.
    - Przeszły testy kolejki, w tym odrębne żądanie ze zmienionym zakresem i pomijanie nieaktualnych części.
  - [x] Sprawdzaj aktualność filtra przed odczytem, przy wznowieniu, przed transakcją SQLite i przy odbiorze zdarzeń przez Tk. Odrzuć spóźnione wyniki, kolumny i statusy. Zsynchronizuj zapis konfiguracji z transakcją wyniku i przyjęciem alertu do wysyłki. Wyniki zatwierdzone przed zmianą pozostają w historii. Sprawdź usunięcie tuż przed zapisem i nieudany zapis rozpoznanego adresu listy.
    - Zaliczone testy wspólnej sesji i atomowego zapisu, w tym usunięcie przed transakcją. Przywrócono cofnięcie rozpoznanego adresu po błędzie zapisu.
  - [x] Odtwórz identyfikator instancji filtra i zgodny odczyt starszych konfiguracji. Przy zmianie adresu oraz ponownym ręcznym dodaniu wcześniej usuniętego adresu ustal świeży stan obecności bez alertów o już zastanych zgłoszeniach. Zachowaj historię po adresie i sprawdź, czy kolejny nowy wpis może wysłać alert.
    - Przeszły testy świeżego stanu początkowego z zachowaniem historii i testy starszej konfiguracji.
  - [x] Rozdziel globalną rewizję powiadomień od rewizji poszczególnych filtrów. Zmiana jednego filtra ma pozostawić ważne alerty innych filtrów i zagrożeń SLA. Zabezpiecz usunięcie i ponowne dodanie tego samego adresu oraz przywrócenie wcześniejszych ustawień. Uwzględnij istniejące alerty ze starszą rewizją. Wysyłka rozpoczęta przed zmianą może już dotrzeć do odbiorcy.
    - Przeszły testy rewizji konfiguracji, zachowania alertów innych filtrów i zagrożeń oraz ponownego dodania tego samego adresu. Testy kolejki alertów używały danych syntetycznych.
  - [x] Odtwórz aktualizację filtrów sesji po zapisaniu ustawień filtra, w tym ponowne przeliczenie konfiguracji powiadomień. W logach i statusie odróżnij pominięcie z powodu zmiany konfiguracji od błędu odczytu. Sprawdź identyfikator żądania i brak adresu filtra w diagnostyce kolejki.
    - Przywrócono zapis zdarzeń konfiguracji i pominięć. Przeszedł test korelacji kolejki bez ujawnienia celu filtra. W `kopie/05-filtry.zip` sprawdzono 39 ścieżek.
  - [x] Odtwórz zmiany w testach SQLite, kolejki, sesji i interfejsu. Przywróć też korektę sprzątania liczników Tk w testach startu oraz oczekiwaną kolejność przełączników w teście Google Chat. Porównaj z 167 wcześniej zaliczonymi testami, wliczając osobne powtórki startu i Google Chat.
    - `05-regresja.json` potwierdza 144/144 uruchomionych testów. Pierwotny limit 75 s przerwał moduł paginacji, który w historycznym raporcie trwał 97,97 s. Powtórka z limitem 180 s na zabezpieczonym stanie etapu 5 zaliczyła 23/23 (`05-paginacja.json`). Łącznie 167/167.

- [x] **Etap 6. Odtwórz odsłonięcie i sprawdź pasek zadań**
  - [x] Na bazie etapu 4 porównaj pełne poprawki z głównego zapisu czatu z 14 zapisami w `build/recovery-login-focus-2026-11-12.json`. Odtwórz tylko aktualną wersję zmian. Pełny oryginał ma pierwszeństwo przed pakietem rekonstruowanym po utracie plików.
    - Wszystkie 14 poprawek w kopii zgadza się znak w znak z oryginałem. Odtworzono je raz, z oryginalnych wywołań. `kopie/06-odsloniecie.zip` zawiera 39 zweryfikowanych plików z manifestem SHA-256.
  - [x] Po ukryciu Chromium użyj wspólnej ścieżki pokazania, przywrócenia i podniesienia właściwej ramki Windows. Oceniaj osobno widoczność, minimalizację, odsłonięcie, aktywację Windows i fokus klawiatury. Zachowaj preferencję startu zminimalizowanego oraz zachowanie odzyskiwania sesji w tle.
    - Zaliczone osobne natywne próby ukrycia Chromium, startu i powrotu z komunikatu zapisu poświadczeń. Osobny test potwierdził pominięcie aktywacji przy starcie zminimalizowanym i odzyskaniu w tle.
  - [x] Jeśli pojedyncze obce okno „zawsze na wierzchu” zasłania aktywny monitor w sprawdzonych punktach, podnieś monitor na czas aktywności. Cofnij podniesienie po utracie fokusu, ukryciu, minimalizacji lub zamknięciu. Sprawdź także sytuację, gdy Windows nie przekaże Tk zdarzenia utraty fokusu. Aktywacja przez Windows ma odsłonić aktywny monitor bez ponownego odbierania fokusu innym aplikacjom.
    - Próba z obcym oknem potwierdziła odsłonięcie, cofnięcie podniesienia i jego ponowne zastosowanie po przywróceniu. Odtworzono kontrolę w kolejce Tk na wypadek braku zdarzenia fokusu.
  - [x] Przywróć rejestrowanie odsłonięcia, podniesienia i cofnięcia oraz test bezpieczeństwa pól logu. W diagnostyce pomiń tytuły, uchwyty i identyfikatory procesów obcych okien.
    - Wszystkie pięć testów diagnostyki przeszło, w tym dopuszczenie pól stanu i odrzucenie metadanych obcego okna.
  - [x] Powtórz na izolowanych danych natywną próbę z zasłaniającym oknem, przełączeniem aktywności i przywróceniem. Wynik wcześniejszej próby zaliczono przed incydentem. Oddziel od niego ręczny odbiór rzeczywistego przycisku paska zadań.
    - `06-regresja.json` potwierdza 9/9, w tym osobną próbę odsłonięcia i przywrócenia. Ten wynik obejmuje natywne przywrócenie okna, a kliknięcie przycisku wymaga odbioru ręcznego.
  - [x] Wykonaj ręczny odbiór przywrócenia okna na Windows przez pojedyncze kliknięcie na pasku zadań.
    - 12 listopada 2026 użytkownik potwierdził pozytywny wynik tej próby. To osobny odbiór od wcześniejszych testów natywnych.

- [x] **Etap 7. Zweryfikuj komplet i przenieś sprawdzony wynik**
  - [x] Porównaj diff z tagiem, inwentarzem 38 ścieżek i pięcioma grupami z czatu. Sprawdź wszystkie zachowane lokalne zmiany w dokumentacji, pliku `.spec` i zasobach. Zapisz dla każdego bloku, co odtworzono z oryginalnej kopii, a co z poprawek.
    - `odzysk.py verify` porównał 143 pliki i sprawdził składnię źródeł i testów. Z 38 brakujących plików 20 jest identycznych bajtowo z Gitem, a 18 zmieniono przez odtworzenie oryginalnych poprawek. Odtworzony `.spec` zgadza się z zachowanym, a trzy PNG z kopiami wejściowymi. Zachowana dokumentacja jest w kopii i w katalogu głównym.
  - [x] Uruchom pełną regresję na izolowanych danych. Powtórz osobno próby Tk i Windows zależne od fokusu. Sprawdź wspólną ścieżkę importu i edycji, ikony po zmianie listy, start i Stop oraz ręczną aktualizację wyłączonego filtra. Wyniki rzeczywistego ServiceNow i Windows zapisz osobno od regresji syntetycznej.
    - `07-regresja-windows.json` i `07-regresja-pozostala.json` obejmują 594 przypadki w 76 modułach. Pierwszy przebieg dał 586 zaliczonych, 2 pominięte i 6 błędów. `test_column_drag` zaliczył oba przypadki w izolacji. `test_dynamic_columns` i `test_filter_views` przeszły w osobnych procesach z pomocniczą korektą sprzątania liczników Tk (`sprawdz_tk.py`), bez zmian w odtworzonych testach i kodzie. Pominięte próby dotyczyły fokusu Windows i dowiązań symbolicznych.
    - W `test_wrapped_list_urls` sześć przypadków przeszło, a jeden stary test tworzy `App.__new__` bez wymaganej inicjalizacji (`quitting`, nowy zapis). Ten sam scenariusz dodania, odczytu po ponownej inicjalizacji i odrzucenia konfliktu przeszedł przez rzeczywisty konstruktor i formularz na osobnej konfiguracji (`sprawdz_filtr_zawijany.py`). Oryginalny test pozostał bez zmian. Regresja była lokalna, z syntetycznymi danymi. Ręczny odbiór jest w etapie 6.
  - [x] Po porównaniu ze stanem bieżącego katalogu przenieś zweryfikowane pliki w małych grupach. Zachowaj lokalne dane, profil, logi, pliki użytkownika i artefakty wydania. Oznacz odzyskanie w dokumentacji. Przebudowa EXE i publikacja mają osobny zakres.
    - Przed przeniesieniem sprawdzono odczyt i SHA-256 264 pozycji w pełnej kopii `kopie/07-odtworzone-zrodla.zip`.
    - Przeniesiono 20 brakujących plików identycznych z bazą Gita i sprawdzono ich bajty w katalogu głównym.
    - Przeniesiono 12 modułów z odtworzonymi poprawkami i sprawdzono ich bajty względem kopii etapu 6.
    - Przeniesiono sześć zmienionych testów. Wszystkie 38 ścieżek w repozytorium zgadza się z manifestem SHA-256. `git ls-files --deleted` jest puste, `git diff` pokazuje 18 oczekiwanych zmian w kodzie i testach, a `git diff --check` przeszedł. Istniejące pliki poza aktualizowaną dokumentacją zachowano. Zaktualizowano architekturę, decyzję 028 i plan wspólnej sesji.
  - [x] Zamknij plan po ręcznym odbiorze z etapu 6.
    - Przeniesiono plan do zakończonych i zaktualizowano odnośniki. Odtworzone źródła są na GitHubie w [commicie `ba959cf`](https://github.com/pzaradzki/NetoIncidentMonitor/commit/ba959cf9e1be89aa7a5b7ef119af46bace4225b5).

## Inwentarz brakujących plików

Ścieżki są względne do repozytorium. Zmiany po wydaniu wykazano przez porównanie listy usuniętych ścieżek z operacjami zapisanymi w czacie.

| Zakres | Moduły aplikacji | Testy i dane testowe |
| --- | --- | --- |
| Z poprawkami po wydaniu (18) | `app.py`, `browser_policy.py`, `data_validation.py`, `filter_settings.py`, `history.py`, `login_diagnostics.py`, `monitoring.py`, `secret_config.py`, `shared_session.py`, `ui.py`, `widgets.py`, `window_style.py` | `test_filter_atomic_commit.py`, `test_filter_views.py`, `test_google_chat_ui.py`, `test_login_diagnostics.py`, `test_shared_session.py`, `test_startup.py` |
| Baza Git, bez ustalonych poprawek po wydaniu (20) | `__init__.py`, `authentication.py`, `browser_icon.py`, `browser_session.py`, `browser_window.py`, `dashboard.py`, `dynamic_columns.py`, `favorites_ui.py`, `pagination.py`, `settings_ui.py`, `threatened_ui.py` | `list_fixture.py`, `test_browser_window.py`, `test_dashboard.py`, `test_dashboard_commit.py`, `test_dynamic_columns.py`, `test_favorites_import.py`, `test_login_stabilization.py`, `test_pagination_validation.py`, `test_update_order.py` |

Moduły należą do `neto_incident_monitor/`, a testy do `tests/`. Zachowały się trzy PNG w `icons/`, zmodyfikowany `scripts/Neto Incident Monitor.spec`, zmiany w dokumentacji i raporty w `build/`. Dwa nieśledzone pliki audytowe są starsze od wydania i pozostają poza odtwarzaniem tej serii zmian.

## Gdzie znaleźć pełne poprawki

Pełne wywołania zachowały się w lokalnym zapisie głównego czatu. Jego ścieżkę zawiera lokalny skrypt `build/odzyskanie-v1.10.0/odzysk.py`, a `02-poprawki.json` w tym samym katalogu zawiera wybrane poprawki. Numery poniżej oznaczają wiersze z oryginalnymi wywołaniami. Raporty zatwierdzeń narzędzi mogą zawierać skrócone kopie. Przy ponownym odtwarzaniu użyj wybranych poprawek zamiast kopiować cały zapis czatu.

| Etap | Wiersze w zapisie |
| --- | --- |
| Ikony | `4395`, `4402`, `4426`, `4462`, `4493` |
| Kolejność kanałów | `4557` |
| Wcześniejsze przekazanie fokusu | `4641`, `4648`, `4655`, `4668`, `4702` |
| Edycja filtrów podczas monitoringu | `4824`, `4838`, `4845`, `4854`, `4861`, `4875`, `4901`, `4919`, `4926`, `4939`, `4962`, `4989`, `4998`, `5036`, `5058`, `5108`, `5128` |
| Odsłonięcie okna | `5363`, `5377`, `5386`, `5393`, `5416`, `5442`, `5477`, `5502`, `5522`, `5538`, `5561`, `5590` |
