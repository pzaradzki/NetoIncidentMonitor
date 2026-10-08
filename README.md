# Neto Incident Monitor

Aplikacja dla Windows do monitorowania list incydentów w ServiceNow. Odczytuje strony w Chromium przez Playwright, bez używania API ServiceNow.

## Uruchomienie gotowej aplikacji

1. Rozpakuj **cały** folder wersji folderowej.
2. Uruchom `Neto Incident Monitor.exe`.
3. Zachowaj folder `_internal` obok EXE — zawiera biblioteki, grafiki i Chromium.

Aplikacja uruchamiana z EXE zapisuje ustawienia, historię incydentów, logi i profil przeglądarki w `%LOCALAPPDATA%\NetoIncidentMonitor`.

Aby zaktualizować aplikację, zamknij ją i zastąp jej folder nową wersją. Twoje ustawienia i historia pozostaną zachowane, ponieważ są przechowywane osobno.

Gotowych plików EXE, Chromium i folderu `dist` nie przechowujemy w repozytorium kodu.

## Uruchomienie z kodu

Wymagania: Windows 10/11 x64, Python 3.12 oraz dostęp do docelowego ServiceNow. Pierwsza instalacja wymaga internetu do pobrania bibliotek i Chromium.

Najprościej uruchomić `start.bat`. Skrypt tworzy `.venv`, instaluje zależności i Chromium, następnie uruchamia aplikację.

Alternatywnie w PowerShell, w katalogu projektu:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe launcher.pyw
```

Po instalacji można uruchamiać `Neto Incident Monitor.vbs`, aby otworzyć aplikację bez konsoli. Wersja uruchamiana z kodu używa lokalnego folderu `data`, niezależnego od danych wersji EXE.

## Krótka instrukcja obsługi

1. Kliknij **Dodaj filtr**, wpisz nazwę i pełny adres listy ServiceNow z wybranym filtrem.
2. Kliknij **Uruchom monitoring** i zaloguj się w otwartym Chromium. Aplikacja sama wykryje zakończenie logowania.
3. Pierwszy poprawny odczyt nowego filtra tworzy punkt odniesienia. Powiadomienia dotyczą incydentów wykrytych dopiero w kolejnych odczytach.
4. Przełączniki przy filtrach pozwalają włączać i wyłączać je podczas pracy. Ten sam INC w kilku filtrach ma jeden wiersz, z połączonymi nazwami filtrów.
5. **Bieżące incydenty** pokazują ostatni odczyt aktywnych filtrów. **Historia zgłoszeń** zawiera wcześniej wykryte incydenty; zapisane dane mogą różnić się od aktualnych w ServiceNow. Zmiana stanu istniejącego INC nie jest nowym incydentem.
6. Dwuklik otwiera incydent w domyślnej przeglądarce i oznacza go jako przeczytany. Prawy klik udostępnia otwieranie, kopiowanie numeru/linku i oznaczanie przeczytania. Te oznaczenia są lokalne.
7. **Przeczytaj wszystkie** oznacza całą historię jako przeczytaną. **Wyczyść historię** usuwa historię po potwierdzeniu, zachowując pamięć wcześniej widzianych numerów.
8. **Kolumny** pozwala wybrać widoczne pola. Brakujące pola są automatycznie ukrywane po odczycie. Kolejność i szerokości wspólnych kolumn synchronizują się między zakładkami; kolumna „Wykryto (historia)” pozostaje na końcu historii.
9. Przeciągaj nagłówki, aby zmieniać kolejność, a ich krawędzie, aby zmieniać szerokość. Kliknięcie nagłówka przełącza sortowanie: rosnąco, malejąco, domyślnie.
10. **Ustawienia** (zębatka) zawierają częstotliwość odczytu, powiadomienia, automatyczne logowanie i minimalizację. Częstotliwość i powiadomienia Windows są blokowane podczas monitorowania; zmień je po zatrzymaniu i uruchom ponownie monitoring.

Rozmiar i maksymalizacja okna, szerokość panelu filtrów oraz układ kolumn są zapamiętywane. Separator między panelami można przeciągać. **Zatrzymaj** kończy monitoring, a zamknięcie głównego okna kończy aplikację. Przy minimalizacji do zasobnika monitoring pozostaje aktywny.

## Logowanie i Teams

Automatyczne logowanie obsługuje rozpoznane strony ADEO: wybiera jedno zapamiętane konto i wysyła formularz tylko przy już uzupełnionym haśle. Przy pustym haśle, wielu kontach, błędzie lub MFA aplikacja czeka na użytkownika. Nie zapisuje samodzielnie hasła. Profil Chromium bota jest osobny od zwykłego Chrome.

Powiadomienia Teams wymagają własnego webhooka Power Automate. Szczegółowa instrukcja: [INSTRUKCJA_TEAMS.md](INSTRUKCJA_TEAMS.md), dostępna również przez przycisk **Instrukcja** w konfiguracji Teams. Wygaśnięcie sesji może wysłać alert Teams, jeśli powiadomienia są skonfigurowane i włączone.

Foldery `data` i LocalAppData zawierają dane użytkownika, w tym webhook i sesję przeglądarki. Nie dodawaj ich do repozytorium ani do paczek aplikacji.

## Budowanie wersji folderowej

W PowerShell:

```powershell
.\build_exe.ps1
```

Skrypt wymaga wcześniej utworzonego `.venv`, instaluje narzędzia budowania i Chromium oraz tworzy:

```text
dist/
  Neto Incident Monitor/
    Neto Incident Monitor.exe
    _internal/
```

Folder należy udostępniać w całości. Konfiguracja użytkownika nie jest częścią pakietu.

## Testy i diagnostyka

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
```

Testy interfejsu wymagają sesji Windows z pulpitem. Testy odczytu używają lokalnych stron testowych i Chromium; nie wymagają konta ServiceNow. Integrację z docelowym logowaniem i filtrami należy sprawdzić oddzielnie.

Test gotowej aplikacji bez łączenia z ServiceNow:

```powershell
& '.\dist\Neto Incident Monitor\Neto Incident Monitor.exe' --smoke-test "$PWD\smoke-result.json"
```

Raport potwierdza uruchomienie interfejsu i dołączonego Chromium. Logi błędów są w `monitor.log` w folderze danych, z rotacją do trzech kopii.

## Pliki projektu

- `app.py`, `ui.py`, `widgets.py`, `theme.py` — aplikacja i interfejs.
- `automatic_login.py`, `pagination.py`, `monitoring.py` — logowanie i odczyt list.
- `history.py`, `notifications.py`, `teams_notifications.py`, `tray.py` — historia i powiadomienia.
- `runtime_paths.py`, `single_instance.py`, `launcher.pyw` — ścieżki, pojedyncza instancja i uruchamianie.
- `assets/` — grafiki i ikony wymagane przez aplikację.
- `test_*.py`, `package_smoke.py`, `preview_ui.py` — testy i narzędzia diagnostyczne.
- `Neto Incident Monitor.spec`, `build_exe.ps1` — budowanie wersji folderowej.
