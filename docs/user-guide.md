# Neto Incident Monitor

Neto Incident Monitor to aplikacja desktopowa dla systemu Windows, która monitoruje listy incydentów w ServiceNow i powiadamia o nowych zgłoszeniach. Dane są odczytywane z interfejsu internetowego ServiceNow za pomocą Playwright i przeglądarki Chromium. Aplikacja nie korzysta z API ServiceNow.

## Główne funkcje

- Monitorowanie wielu filtrów z możliwością ich włączania i wyłączania podczas pracy.
- Powiadomienia systemowe Windows oraz powiadomienia Microsoft Teams i Google Chat.
- Oddzielna historia każdego filtra i lokalne oznaczanie incydentów jako przeczytanych.
- Otwieranie incydentów oraz kopiowanie ich numerów i adresów z menu kontekstowego.
- Konfigurowanie widoczności, kolejności i szerokości kolumn.
- Zapamiętywanie układu interfejsu, rozmiaru okna i stanu maksymalizacji.
- Praca w zasobniku systemowym oraz obsługa wybranych scenariuszy automatycznego logowania.

## Wymagania

### Walidacja adresów i treści powiadomień

Ta konfiguracja aplikacji ufa wyłącznie instancji `adeo.service-now.com`. Filtry muszą używać HTTPS, portu 443 (jawnego lub domyślnego) i ścieżki `/incident_list.do` albo `/sc_task_list.do`. Obsługiwane są także linki classic normalizowane do tych ścieżek. Dane logowania w adresie, fragmenty oraz znaki sterujące są odrzucane. Walidacja działa przy odczycie konfiguracji i przed nawigacją. Zmiana zaufanej instancji wymaga świadomej zmiany polityki w `service_now_urls.py`.

Obsługiwane są również skróty `/now/nav/ui/classic/__tinyId__/…` tej samej instancji. Aplikacja rozpoznaje ich docelową listę po zalogowaniu, sprawdza adres i odczytuje ją od pierwszej strony. Rozpoznany rodzaj INC/SCTASK służy do doboru kolumn i harmonogramu. Historia pozostaje przypisana do oryginalnego adresu filtra. Skrót nie może zawierać parametrów, fragmentu ani wskazywać innego hosta; jego cel musi być obsługiwaną listą.

Linki INC i SCTASK są ograniczone do tej samej instancji oraz odpowiednich ścieżek `/incident.do` i `/sc_task.do`. Nieprawidłowy link pozostawia numer jako zwykły tekst; nie można go otworzyć z menu ani dwukrotnym kliknięciem. Zewnętrzna treść powiadomień nie może wprowadzać własnych hiperłączy lub formatowania Markdown. Jawne adresy w opisach są wyświetlane jako tekst bez automatycznego linkowania.

Pillow jest przypięte do wersji 13.0.0 z poprawkami bezpieczeństwa. Aktualizacja biblioteki i kodu wymaga ponownej budowy dystrybucji; wcześniej przygotowane EXE i ZIP nie zmieniają się automatycznie.

- Windows 10 lub Windows 11 w wersji 64-bitowej.
- Dostęp sieciowy do instancji ServiceNow i uprawnienia do odczytu monitorowanych list.
- Python 3.12 w przypadku uruchamiania aplikacji z kodu źródłowego.

Pakiet aplikacji udostępniany w Releases zawiera wymagane biblioteki i przeglądarkę Chromium. Nie wymaga instalacji Pythona. Instalacja zależności dla kodu źródłowego wymaga dostępu do internetu.

## Instalacja i uruchomienie

### Gotowy pakiet dla Windows

1. Pobierz plik `Neto.Incident.Monitor.zip` z [najnowszego wydania](https://github.com/pzaradzki/NetoIncidentMonitor/releases/latest).
2. Rozpakuj całe archiwum do wybranego katalogu.
3. Uruchom `Neto Incident Monitor.exe`.

Katalog `_internal` musi znajdować się obok pliku wykonywalnego. Zawiera biblioteki, zasoby graficzne i przeglądarkę niezbędne do działania aplikacji.

Aby zainstalować aktualizację, zamknij aplikację i zastąp jej katalog zawartością nowego pakietu. Ustawienia i historia pozostaną zachowane, ponieważ są przechowywane poza katalogiem instalacji.

### Uruchomienie z kodu źródłowego

W katalogu projektu uruchom `start.bat`. Skrypt tworzy środowisko wirtualne `.venv`, instaluje zależności i Chromium, a następnie uruchamia aplikację.

Środowisko można również przygotować ręcznie w PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe launcher.pyw
```

Po przygotowaniu środowiska plik `Neto Incident Monitor.vbs` umożliwia uruchamianie aplikacji bez okna konsoli.

## Obsługa aplikacji

Obsługiwane listy to INC (`incident_list.do`), SCTASK (`sc_task_list.do`), REQ (`sc_request_list.do`) i RITM (`sc_req_item_list.do`) w instancji `adeo.service-now.com`. REQ i RITM dodaje się tak samo jak inne filtry; działają dynamiczne kolumny, historia oraz powiadomienia z linkami do rekordów. SCTASK, REQ i RITM korzystają ze wspólnego interwału „Zgłoszenia katalogowe”. Licznik czasu od utworzenia INC pozostaje dostępny tylko dla incydentów.

### Konfiguracja monitorowania

1. Wybierz **Dodaj filtr** i wprowadź nazwę oraz pełny adres listy ServiceNow z zastosowanym filtrem.
2. Wybierz **Uruchom monitoring** i zaloguj się w otwartym oknie Chromium. Aplikacja automatycznie rozpoznaje zakończenie logowania.
3. Korzystaj z przełączników przy filtrach, aby włączać lub wyłączać poszczególne listy, również podczas monitorowania.

Każdy filtr ma własną listę bieżących incydentów i własną historię. Czerwone zaznaczenie w panelu filtrów określa zawartość obu zakładek. Ten sam numer incydentu może być niezależnie wykryty w kilku filtrach.

Kolejność filtrów można zmieniać, przeciągając je myszą. Czerwona linia wskazuje miejsce upuszczenia. Zmiany są zapamiętywane między uruchomieniami i można je wprowadzać również podczas monitorowania.

Przycisk **Konfiguruj** obok przycisku **Kolumny** otwiera **Ustawienia filtra** zaznaczonego na liście, obejmujące powiadomienia i zgodę na duże odczyty.

Zębatka po lewej stronie przełącznika Microsoft Teams lub Google Chat otwiera konfigurację powiadomienia danego kanału. Można w niej podać osobny webhook filtra. Przycisk **Zastosuj** zatwierdza adres w otwartych ustawieniach; całość zapisuje przycisk **Zapisz** w oknie filtra. Puste pole korzysta z adresu globalnego. Webhook filtra ma pierwszeństwo także dla opcji **Test powiadomienia**. Adresy są maskowane w oknie i szyfrowane dla bieżącego konta Windows przez DPAPI. Globalne wyłączenie kanału nadal blokuje wysyłanie i ukrywa jego ustawienia w filtrze, zachowując zapisany adres.

- **Powiadomienia Windows**, **Powiadomienia Microsoft Teams** i **Powiadomienia Google Chat** są włączane osobno. Odpowiedni kanał musi być również włączony globalnie; w przeciwnym razie jego ustawienia w filtrze są ukryte.
- **Tylko pierwsze wystąpienie** ogranicza powiadomienia do pierwszego wykrycia numeru w danym filtrze. Domyślnie opcja jest wyłączona, więc powiadomienie jest wysyłane także po potwierdzonym powrocie incydentu.

Powrót oznacza ponowne pojawienie się incydentu po poprawnym odczycie, który potwierdził jego nieobecność. Błąd odczytu, wyłączenie filtra i ponowne uruchomienie aplikacji nie stanowią potwierdzenia zniknięcia. Ostatnia potwierdzona obecność i wcześniejsze wystąpienia są zachowywane między uruchomieniami.

Pierwszy odczyt nowego filtra wykrywa znajdujące się w nim incydenty i może wysłać powiadomienia zgodnie z ustawieniami kanałów. Przy aktualizacji istniejące dane wykrywania są zachowywane, aby uniknąć ponownych alertów tylko z powodu aktualizacji.

Powiadomienie zawiera nazwę filtra, liczbę wykrytych incydentów oraz ich numery, lokalizacje i krótkie opisy. Zmiana danych incydentu pozostającego na liście nie powoduje nowego powiadomienia o pojawieniu się.

### Własny format powiadomień filtra

W zębatce przy Teams lub Google Chat wybierz **Szablon powiadomienia**. Biblioteka nazwanych szablonów jest wspólna dla filtrów i obu kanałów, natomiast wybór jest niezależny dla każdego filtra i kanału. Windows zachowuje standardowy format.

**Dodaj** otwiera edytor z polem nazwy. **Edytuj** zmienia wybrany szablon we wszystkich miejscach użycia. Nazwy muszą być unikalne. **Usuń** wymaga potwierdzenia i przełącza używające go filtry na **Standardowy**. Dla pozycji **Standardowy** przyciski **Edytuj** i **Usuń** są nieaktywne. Standardowy format to `Nazwa filtra · liczba`, a poniżej lista `Numer — Krótki opis`, jednakowo dla INC i SCTASK.

- **Szablon wiadomości** opisuje całą wiadomość i obsługuje `{filtr}`, `{liczba}` oraz `{lista incydentów}`. Lista jest wymagana i może znaleźć się w dowolnym miejscu wiadomości.
- **Szablon elementu listy** jest powtarzany dla każdego INC/SCTASK. Wybierz kolumnę filtra i kliknij **Wstaw kolumnę**. Dostępne są wszystkie kolumny odczytane z tej listy ServiceNow, także niestandardowe i ukryte w tabeli aplikacji. Przed pierwszym odczytem uruchom monitoring filtra.

Przykład elementu: `{Numer} — {Krótki opis}`. Selektor pokazuje nagłówki kolumn, a przycisk **Wstaw** umieszcza wybrany nagłówek w nawiasach klamrowych. Powiązania z identyfikatorami kolumn są zachowane wewnętrznie: zmiana nagłówka nie psuje zapisanego szablonu. Powtarzające się nazwy dostają przyrostek `(2)`, `(3)` itd. Starsze zmienne techniczne nadal działają i są przedstawiane czytelnie po otwarciu edytora. Brakująca wartość jest pusta, a wpisane separatory pozostają. Edytor wskazuje niedostępne kolumny. Numery pozostają klikalne w obu kanałach.

Podgląd aktualizuje się podczas edycji. **Wyślij test** wysyła dane przykładowe na webhook filtra lub adres globalny, bez zapisywania zmian. **Zapisz szablon** od razu zapisuje szablon w bibliotece na dysku. Potwierdzone usunięcie również zapisuje bibliotekę od razu. **Zastosuj** zatwierdza wybór szablonu i webhook w szkicu kanału; **Zapisz** w oknie filtra zapisuje te ustawienia filtra. Anulowanie nadrzędnych okien nie cofa zapisania ani potwierdzonego usunięcia szablonu. Dotychczasowe własne formaty są automatycznie przenoszone do biblioteki; wybór **Standardowy** nie usuwa własnych szablonów.

### Bieżące incydenty i historia

Dwukrotne kliknięcie wpisu na liście filtrów otwiera jego adres w domyślnej przeglądarce. Kliknięcie przełącznika aktywności nie otwiera przeglądarki.

Duże tabele (ponad 150 rekordów historii lub bieżącej listy) są przygotowywane poza wątkiem interfejsu i wczytywane krótkimi partiami. Ukryta duża tabela czeka na otwarcie swojej zakładki. Zmiana filtra lub zakładki przerywa poprzednie ładowanie; postęp jest widoczny nad tabelą. Małe zestawy pozostają wczytywane bezpośrednio. Nie ma limitu liczby zachowanych wpisów historii.

Zakładka **Bieżące zgłoszenia** przedstawia wyniki ostatniego odczytu zaznaczonego filtra. Zakładka **Historia zgłoszeń** zawiera zapisane incydenty wykryte podczas monitorowania. Dane historyczne nie są na bieżąco aktualizowane i mogą różnić się od aktualnych danych w ServiceNow.

Dwukrotne kliknięcie wiersza otwiera incydent w domyślnej przeglądarce i oznacza go jako przeczytany. Menu kontekstowe, dostępne po kliknięciu prawym przyciskiem myszy, umożliwia otwarcie incydentu, skopiowanie numeru lub adresu oraz oznaczenie go jako przeczytanego. Status przeczytania jest zapisywany lokalnie i nie zmienia danych w ServiceNow.

Przycisk **Przeczytaj wszystkie** oznacza historię wybranego filtra jako przeczytaną. **Wyczyść historię** usuwa wpisy tego filtra po potwierdzeniu operacji. Aplikacja zachowuje informacje o wcześniej rozpoznanych numerach, aby nie traktować ich ponownie jako nowych incydentów.

### Kolumny i układ interfejsu

Przycisk **Kolumny** jest dostępny po pierwszym pełnym odczycie filtra. Aplikacja pobiera wszystkie widoczne kolumny z listy ServiceNow, także pola niestandardowe, i początkowo wyświetla je w tej samej kolejności. Odczyt pustej listy z rozpoznanymi nagłówkami również udostępnia konfigurację.

- Przeciągnięcie nagłówka zmienia kolejność kolumn.
- Przeciągnięcie krawędzi nagłówka zmienia szerokość kolumny.
- Dwukrotne kliknięcie separatora dopasowuje kolumnę po jego lewej stronie do nagłówka i zawartości wszystkich wczytanych wierszy. Dopasowana szerokość jest zapamiętywana dla filtra.
- Kliknięcie nagłówka przełącza sortowanie pomiędzy kolejnością rosnącą, malejącą i domyślną.

Widoczność, kolejność i szerokości kolumn są zapisywane osobno dla każdego filtra, wspólnie dla jego bieżącej listy i historii. Dodanie lub usunięcie kolumny w ServiceNow przywraca pełny zestaw i kolejność ze strony. Sama zmiana kolejności na stronie zachowuje własny układ użytkownika. Niepełny lub nieudany odczyt nie zmienia zapisanej konfiguracji.

**Przywróć domyślne** wybiera wszystkie kolumny ServiceNow w ostatnio odczytanej kolejności. Kolumny lokalne znajdują się w osobnej sekcji **Kolumny dodatkowe** i domyślnie są wyłączone oraz umieszczone na końcu. Obejmują stan przeczytania, czas od utworzenia INC i datę wykrycia w historii. Po włączeniu można zmienić także ich położenie. Zmiany w konfiguratorze zatwierdza przycisk **Zapisz**.

Separator pomiędzy panelem filtrów a tabelą umożliwia zmianę szerokości panelu. Układ kolumn, szerokość panelu oraz rozmiar i stan maksymalizacji okna są zapamiętywane między uruchomieniami.

### Ustawienia i praca w tle

Przycisk **Ustawienia**, oznaczony ikoną koła zębatego, otwiera konfigurację częstotliwości odczytu, powiadomień, logowania i minimalizacji. Zmiana częstotliwości odczytu oraz ustawień powiadomień Windows wymaga zatrzymania monitorowania i ponownego jego uruchomienia.

Przycisk **Zatrzymaj** kończy monitorowanie. Zamknięcie głównego okna kończy działanie aplikacji. Przy włączonej minimalizacji do zasobnika systemowego monitoring pozostaje aktywny po zminimalizowaniu okna.

## Logowanie i powiadomienia

Automatyczne logowanie obsługuje rozpoznane strony logowania ADEO. Może wybrać pojedyncze zapamiętane konto i zatwierdzić formularz, jeśli pole hasła jest już uzupełnione. Gdy wymagane jest podanie hasła, wybór spośród wielu kont, uwierzytelnianie wieloskładnikowe lub obsługa błędu, aplikacja oczekuje na działanie użytkownika. Nie zapisuje samodzielnie hasła. Korzysta z własnego profilu Chromium, niezależnego od profilu przeglądarki Chrome użytkownika.

Opcja „Całkowicie ukryj okno przeglądarki” jest domyślnie włączona. Ukrywa Chromium także na pasku zadań podczas sprawdzania filtrów i ma pierwszeństwo przed minimalizacją. Podczas logowania oraz każdej aktualizacji dashboardu, także uruchomionej ręcznie, przeglądarka jest pokazywana. Ukrywanie lub minimalizacja wracają przy rozpoczęciu sprawdzania filtrów, zgodnie z aktualnymi ustawieniami. Okno można też przywrócić poleceniem „Pokaż przeglądarkę” w zasobniku aplikacji. Automatyczne logowanie, minimalizację i ukrywanie można przełączać podczas monitoringu. W czasie logowania i odczytu dashboardu polecenie ukrycia jest odraczane. Wyłączenie automatyzacji blokuje kolejne działania, a ponowne włączenie nie zeruje ochrony po ręcznym przejęciu formularza lub błędzie.

Kliknięcie przycisku logowania ma limit 5 sekund. Po przekroczeniu limitu aplikacja ponawia je tylko wtedy, gdy obserwator w tym samym dokumencie potwierdza brak zdarzeń aktywacji przycisku lub wysłania formularza. Odstęp między próbami wynosi co najmniej 2 sekundy, a limit to 3 próby. Wykryte zdarzenie, zmiana dokumentu lub niepewny wynik wykluczają ponowne automatyczne wysłanie. Diagnostyka rozróżnia niewykonane kliknięcie, zaobserwowaną aktywację i nieznany wynik.

Powiadomienia Microsoft Teams wymagają skonfigurowania adresu webhook w Power Automate. Procedurę opisuje [film instruktażowy konfiguracji powiadomień Teams](https://netology-my.sharepoint.com/:v:/g/personal/piotr_zaradzki_netology_com_pl/IQCv86cQd-JrTLpRyIrcA8ZPAVtyK6Ya9HGxTT4NMxRQ8S0?nav=eyJyZWZlcnJhbEluZm8iOnsicmVmZXJyYWxBcHAiOiJPbmVEcml2ZUZvckJ1c2luZXNzIiwicmVmZXJyYWxBcHBQbGF0Zm9ybSI6IldlYiIsInJlZmVycmFsTW9kZSI6InZpZXciLCJyZWZlcnJhbFZpZXciOiJNeUZpbGVzTGlua0NvcHkifX0&e=wLs9Sr), dostępna także przez przycisk **Instrukcja** w oknie konfiguracji. Przy włączonych i skonfigurowanych powiadomieniach aplikacja może również wysłać alert o wygaśnięciu sesji.

Google Chat jest trzecim, niezależnym kanałem. W ustawieniach globalnych wybierz **Google Chat → Konfiguruj**, wklej adres webhooka, użyj **Wyślij test**, zapisz konfigurację i włącz kanał. Przycisk **Instrukcja** prowadzi do [instrukcji Google](https://developers.google.com/workspace/chat/quickstart/webhooks). Webhook tworzysz w przeglądarkowej wersji Google Chat: wybrana przestrzeń → **Aplikacje i integracje → Dodaj webhooki**. Organizacja Google Workspace musi zezwalać na używanie webhooków. Power Automate i logowanie do Google w naszej aplikacji nie są potrzebne.

Google Chat jest domyślnie wyłączony globalnie. Po skonfigurowaniu można wybierać powiadomienia osobno dla każdego filtra, tak samo jak Windows i Teams. Kanały mogą działać jednocześnie. Obsługiwane są INC i SCTASK, hiperłącza pod numerami oraz **Test powiadomienia** z menu kontekstowego. Ustawienia i webhook są zapamiętywane między sesjami. Wysyłanie działa w tle z ograniczoną kolejką i odstępem między wiadomościami; większe zestawy zgłoszeń są dzielone na części. Adres jest maskowany w oknie konfiguracji, a komunikaty błędów nie zawierają parametrów `key` ani `token`. Webhooki Google Chat i Teams są zapisywane lokalnie w postaci zaszyfrowanej przez Windows DPAPI. Nadal nie należy udostępniać katalogu danych ani profilu przeglądarki.

## Przechowywanie danych

### Ochrona webhooków

Adresy webhooków Teams i Google Chat są przechowywane jako zaszyfrowane wartości w `config.json`, chronione przez Windows DPAPI w zakresie bieżącego użytkownika. Aplikacja odszyfrowuje je wyłącznie do użycia w pamięci. Nie wymaga to dodatkowego hasła, logowania ani uprawnień administratora.

Przy pierwszym odczycie konfiguracji z wcześniejszej wersji jawne webhooki są automatycznie szyfrowane, a plik atomowo zastępowany bez tworzenia jawnej kopii zapasowej. Jeśli migracja się nie powiedzie, dotychczasowy plik pozostaje bez zmian, a aplikacja informuje o problemie. Nie jest stosowany zapis nowych sekretów jawnym tekstem jako mechanizm zastępczy.

Po skopiowaniu danych na inne konto lub komputer odszyfrowanie może nie być możliwe. Aplikacja wyłącza wtedy odpowiedni kanał i wyświetla informację o konieczności ponownego wpisania webhooka. Nieczytelna zaszyfrowana wartość pozostaje zachowana przy zapisie pozostałych ustawień. Przeniesienie samego katalogu aplikacji na tym samym komputerze i koncie nie wymaga ponownej konfiguracji.

Starsze wersje aplikacji nie obsługują nowego formatu sekretów. Po migracji należy korzystać z wersji obsługującej DPAPI. Ochrona nie zastępuje uprawnień dostępu do katalogu danych i nie chroni przed procesem działającym już jako ten sam użytkownik. Wcześniej utworzone kopie jawnej konfiguracji nie są automatycznie usuwane.

| Sposób uruchomienia | Katalog danych |
| --- | --- |
| Pakiet z plikiem EXE | `%LOCALAPPDATA%\NetoIncidentMonitor` |
| Kod źródłowy | `data` w katalogu projektu |

Katalog danych zawiera ustawienia, historię, logi i profil przeglądarki. Wersja wykonywalna i wersja uruchamiana z kodu źródłowego korzystają z oddzielnych katalogów danych.

W ustawieniach, w sekcji **Uruchamianie i okno aplikacji**, można włączyć automatyczny monitoring po uruchomieniu aplikacji, start aplikacji po zalogowaniu do Windows oraz uruchamianie ze zminimalizowanym oknem. Opcje są domyślnie wyłączone. Po jednoczesnym włączeniu **Uruchom aplikację zminimalizowaną** oraz **Minimalizacja do zasobnika** okno przy starcie trafia do zasobnika, również gdy ikona pojawi się z opóźnieniem. Przy błędzie zasobnika okno zostaje przywrócone. Automatyczny monitoring wymaga przynajmniej jednego włączonego filtra; logowanie do ServiceNow działa zgodnie z ustawieniami logowania. Autostart dotyczy bieżącego użytkownika i zapisuje ścieżkę do aplikacji, dlatego po przeniesieniu jej katalogu należy wyłączyć i ponownie włączyć tę opcję.

Dane użytkownika, w tym adres webhook i dane sesji przeglądarki, nie powinny być dodawane do repozytorium ani do pakietów dystrybucyjnych. Repozytorium zawiera kod źródłowy; pliki wykonywalne, Chromium i katalog `dist` są udostępniane jako pakiety wydań.

## Przygotowanie pakietu dystrybucyjnego

Po utworzeniu środowiska `.venv` uruchom w PowerShell:

```powershell
.\scripts\build_exe.ps1
```

Skrypt instaluje narzędzia do budowania oraz Chromium, a następnie przygotowuje pakiet za pomocą PyInstaller:

```text
dist/
  Neto Incident Monitor/
    Neto Incident Monitor.exe
    _internal/
```

Do dystrybucji wymagany jest cały katalog `Neto Incident Monitor`. Dane i konfiguracja użytkownika nie są częścią pakietu.

## Testy i diagnostyka

Uruchomienie testów automatycznych:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Testy interfejsu wymagają aktywnej sesji pulpitu Windows. Testy odczytu danych korzystają z lokalnych stron testowych i Chromium; nie wymagają konta ServiceNow. Integrację z docelową instancją, filtrami i procesem logowania należy zweryfikować oddzielnie.

Podstawowy test uruchomienia pakietu, bez połączenia z ServiceNow:

```powershell
& '.\dist\Neto Incident Monitor\Neto Incident Monitor.exe' --smoke-test "$PWD\smoke-result.json"
```

Raport potwierdza uruchomienie interfejsu i dołączonej przeglądarki Chromium. Log błędów `monitor.log` znajduje się w katalogu danych aplikacji. Rotacja logów zachowuje do trzech plików archiwalnych.

Szczegółowy przebieg logowania jest automatycznie zapisywany w `login-diagnostics.jsonl` w tym samym katalogu. Dla wersji EXE jest to `%LOCALAPPDATA%\NetoIncidentMonitor`, a dla kodu źródłowego katalog `data`. Każda próba ma własny identyfikator i czas zdarzeń. Log zawiera stan formularza (obecność i autouzupełnienie hasła, dostępność przycisku, liczba kont), próby kliknięć, przyczyny oczekiwania i przejścia do ręcznego logowania oraz typy błędów. Nie zapisuje wartości pól, loginów, haseł, treści strony, ciasteczek, ścieżek ani parametrów adresów SSO. Niezmieniony stan jest odnotowywany co 10 sekund. Plik ma limit 2 MB i trzy archiwalne kopie. Przy problemie z logowaniem zachowaj `login-diagnostics.jsonl` wraz z jego plikami `.1`, `.2`, `.3` oraz `monitor.log`.

## Struktura projektu

```text
NetoIncidentMonitor/
├── neto_incident_monitor/   # kod aplikacji
├── tests/                  # testy automatyczne
├── tools/                  # narzędzia diagnostyczne i podgląd interfejsu
├── scripts/                # skrypt budowania i konfiguracja PyInstaller
├── docs/                   # dokumentacja konfiguracji
├── assets/                 # zasoby graficzne i ikony
├── launcher.pyw            # punkt wejścia aplikacji
├── start.bat               # przygotowanie środowiska i uruchomienie
├── Neto Incident Monitor.vbs
├── requirements.txt
└── requirements-build.txt
```

Kod aplikacji jest zorganizowany jako pakiet `neto_incident_monitor`. Narzędzia pomocnicze należy uruchamiać z katalogu głównego projektu, np. `python -m tools.preview_ui`.

Katalogi `data`, `build` i `dist` oraz środowisko `.venv` są tworzone lokalnie i nie są częścią repozytorium.

Opcja **Podświetlaj nieprzeczytane incydenty** znajduje się w sekcji **Lista incydentów** na końcu ustawień i jest domyślnie wyłączona. Zapisany wcześniej wybór użytkownika jest zachowywany. Jej wyłączenie usuwa wyróżnienie wierszy, ukrywa kolumnę przeczytania, przycisk **Przeczytaj wszystkie**, oznaczanie w menu kontekstowym oraz licznik na ikonie zasobnika. Otwieranie incydentu nie zmienia wtedy oznaczenia przeczytania. Wcześniejsze oznaczenia pozostają zachowane, a ustawienie jest zapamiętywane między uruchomieniami.

### Zadania katalogowe (SCTASK)

Filtry mogą monitorować również listy zadań katalogowych ServiceNow (`sc_task_list.do`). Obsługiwane są zarówno adresy bezpośrednie, jak i linki nawigacyjne `/now/nav/ui/classic/params/target/`. Po dodaniu filtra zadania SCTASK są odczytywane ze wszystkich stron listy i korzystają z osobnej historii oraz ustawień powiadomień tego filtra.

W wyborze kolumn dostępne są także **Wnioskowane dla** i **Otwarte przez**. Pola są odczytywane tylko wtedy, gdy są widoczne na liście ServiceNow. Przy kilku kolumnach o nazwie Stan aplikacja preferuje identyfikator pola stanu zadania. Powiadomienia o SCTASK używają określenia zadanie katalogowe. Aplikacja nie rozwija automatycznie powiązanych REQ ani RITM; monitoruje zadania widoczne na wskazanej liście.


W sekcji **Monitorowanie** można ustawić osobne odstępy odczytu dla **INC** i **SCTASK** (minimum 15 sekund). Zmiana interwałów wymaga zatrzymania i ponownego uruchomienia monitoringu. Ustawienia zapisują się przy uruchomieniu monitorowania. Domyślny interwał SCTASK wynosi 3600 sekund (godzinę); wcześniej zapisane wartości są zachowywane. Licznik wskazuje najbliższy zaplanowany odczyt, a **Sprawdź teraz** sprawdza wszystkie włączone filtry niezależnie od ich rodzaju. Odczyty nadal odbywają się kolejno w jednej przeglądarce, więc długi odczyt może opóźnić następny.

### Ochrona przed dużymi listami

Przy listach zawierających ponad 1000 wpisów aplikacja pyta o zgodę na pełny odczyt. Pytanie dotyczy zarówno INC, jak i SCTASK. Masz 15 sekund na odpowiedź: **Kontynuuj odczyt** pozwala na bieżący odczyt, **Wyłącz filtr** wyłącza filtr, a brak odpowiedzi pomija bieżący odczyt bez wyłączania filtra. Zaznaczenie **Zapamiętaj zgodę dla tego filtra** przy potwierdzeniu zapisuje zgodę między sesjami. Bez zaznaczenia pytanie wróci przy każdym odczycie dużej listy. Gdy licznik wszystkich wpisów w SNOW jest niedostępny, pytanie pojawia się po przekroczeniu 1000 odczytanych rekordów. Pominięcie nie zapisuje częściowego wyniku, nie zmienia historii ani potwierdzonej obecności zgłoszeń.

Zapamiętaną zgodę na duże odczyty można cofnąć w **Ustawieniach filtra**: wyłącz **Pobieraj duże listy bez pytania** i wybierz **Zapisz**. Pytanie wróci przy następnym odczycie listy ponad 1000 wpisów; bieżący odczyt nie jest przerywany.

W powiadomieniach Teams numery INC i SCTASK są hiperłączami do rekordów ServiceNow. Format INC: numer, lokalizacja, krótki opis. Format SCTASK: numer, krótki opis, wnioskowane dla. W powiadomieniach Windows numery pozostają zwykłym tekstem. Przepływ korzystający z `triggerBody()?['text']` otrzymuje gotową treść HTML z hiperłączami.

Opcja **Test powiadomienia** na dole menu kontekstowego wysyła powiadomienie z klikniętym INC lub SCTASK, korzystając z danych bieżącej listy albo historii. Obowiązują globalne i indywidualne ustawienia kanałów powiadomień. Test nie zmienia oznaczenia przeczytania ani pamięci wykrytych zgłoszeń i działa także dla wyłączonego filtra.
