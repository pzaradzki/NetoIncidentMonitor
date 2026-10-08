# Neto Incident Monitor

Neto Incident Monitor to aplikacja desktopowa dla systemu Windows, która monitoruje listy incydentów w ServiceNow i powiadamia o nowych zgłoszeniach. Dane są odczytywane z interfejsu internetowego ServiceNow za pomocą Playwright i przeglądarki Chromium. Aplikacja nie korzysta z API ServiceNow.

## Główne funkcje

- Monitorowanie wielu filtrów z możliwością ich włączania i wyłączania podczas pracy.
- Powiadomienia systemowe Windows oraz powiadomienia Microsoft Teams.
- Historia wykrytych incydentów i lokalne oznaczanie ich jako przeczytanych.
- Otwieranie incydentów oraz kopiowanie ich numerów i adresów z menu kontekstowego.
- Konfigurowanie widoczności, kolejności i szerokości kolumn.
- Zapamiętywanie układu interfejsu, rozmiaru okna i stanu maksymalizacji.
- Praca w zasobniku systemowym oraz obsługa wybranych scenariuszy automatycznego logowania.

## Wymagania

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

### Konfiguracja monitorowania

1. Wybierz **Dodaj filtr** i wprowadź nazwę oraz pełny adres listy ServiceNow z zastosowanym filtrem.
2. Wybierz **Uruchom monitoring** i zaloguj się w otwartym oknie Chromium. Aplikacja automatycznie rozpoznaje zakończenie logowania.
3. Korzystaj z przełączników przy filtrach, aby włączać lub wyłączać poszczególne listy, również podczas monitorowania.

Pierwszy poprawny odczyt nowego filtra ustala zestaw początkowy. Powiadomienia dotyczą incydentów wykrytych w kolejnych odczytach. Zmiana danych istniejącego incydentu, na przykład jego stanu, nie powoduje uznania go za nowy incydent.

Jeśli ten sam incydent występuje w kilku filtrach, jest prezentowany w jednym wierszu. Kolumna **Monitorowany filtr** zawiera nazwy wszystkich powiązanych filtrów.

### Bieżące incydenty i historia

Zakładka **Bieżące incydenty** przedstawia wyniki ostatniego odczytu aktywnych filtrów. Zakładka **Historia zgłoszeń** zawiera zapisane incydenty wykryte podczas monitorowania. Dane historyczne nie są na bieżąco aktualizowane i mogą różnić się od aktualnych danych w ServiceNow.

Dwukrotne kliknięcie wiersza otwiera incydent w domyślnej przeglądarce i oznacza go jako przeczytany. Menu kontekstowe, dostępne po kliknięciu prawym przyciskiem myszy, umożliwia otwarcie incydentu, skopiowanie numeru lub adresu oraz oznaczenie go jako przeczytanego. Status przeczytania jest zapisywany lokalnie i nie zmienia danych w ServiceNow.

Przycisk **Przeczytaj wszystkie** oznacza całą historię jako przeczytaną. **Wyczyść historię** usuwa zapisane wpisy po potwierdzeniu operacji. Aplikacja zachowuje informacje o wcześniej rozpoznanych numerach, aby nie traktować ich ponownie jako nowych incydentów.

### Kolumny i układ interfejsu

Przycisk **Kolumny** otwiera konfigurację widocznych pól. Pola niedostępne w monitorowanych listach ServiceNow są automatycznie ukrywane po odczycie danych.

- Przeciągnięcie nagłówka zmienia kolejność kolumn.
- Przeciągnięcie krawędzi nagłówka zmienia szerokość kolumny.
- Kliknięcie nagłówka przełącza sortowanie pomiędzy kolejnością rosnącą, malejącą i domyślną.

Kolejność i szerokości wspólnych kolumn są synchronizowane między zakładkami. Kolumna **Wykryto (historia)** występuje wyłącznie w historii i pozostaje na końcu tabeli.

Separator pomiędzy panelem filtrów a tabelą umożliwia zmianę szerokości panelu. Układ kolumn, szerokość panelu oraz rozmiar i stan maksymalizacji okna są zapamiętywane między uruchomieniami.

### Ustawienia i praca w tle

Przycisk **Ustawienia**, oznaczony ikoną koła zębatego, otwiera konfigurację częstotliwości odczytu, powiadomień, logowania i minimalizacji. Zmiana częstotliwości odczytu oraz ustawień powiadomień Windows wymaga zatrzymania monitorowania i ponownego jego uruchomienia.

Przycisk **Zatrzymaj** kończy monitorowanie. Zamknięcie głównego okna kończy działanie aplikacji. Przy włączonej minimalizacji do zasobnika systemowego monitoring pozostaje aktywny po zminimalizowaniu okna.

## Logowanie i powiadomienia Microsoft Teams

Automatyczne logowanie obsługuje rozpoznane strony logowania ADEO. Może wybrać pojedyncze zapamiętane konto i zatwierdzić formularz, jeśli pole hasła jest już uzupełnione. Gdy wymagane jest podanie hasła, wybór spośród wielu kont, uwierzytelnianie wieloskładnikowe lub obsługa błędu, aplikacja oczekuje na działanie użytkownika. Nie zapisuje samodzielnie hasła. Korzysta z własnego profilu Chromium, niezależnego od profilu przeglądarki Chrome użytkownika.

Powiadomienia Microsoft Teams wymagają skonfigurowania adresu webhook w Power Automate. Procedurę opisuje [instrukcja konfiguracji powiadomień Teams](docs/INSTRUKCJA_TEAMS.md), dostępna także przez przycisk **Instrukcja** w oknie konfiguracji. Przy włączonych i skonfigurowanych powiadomieniach aplikacja może również wysłać alert o wygaśnięciu sesji.

## Przechowywanie danych

| Sposób uruchomienia | Katalog danych |
| --- | --- |
| Pakiet z plikiem EXE | `%LOCALAPPDATA%\NetoIncidentMonitor` |
| Kod źródłowy | `data` w katalogu projektu |

Katalog danych zawiera ustawienia, historię, logi i profil przeglądarki. Wersja wykonywalna i wersja uruchamiana z kodu źródłowego korzystają z oddzielnych katalogów danych.

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
