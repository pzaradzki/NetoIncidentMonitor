# Neto Incident Monitor

Aplikacja dla Windows do monitorowania incydentów **INC** i zadań katalogowych **SCTASK** w ServiceNow. Odczytuje dane przez przeglądarkę Chromium, bez korzystania z API ServiceNow.

## Funkcje

- Monitorowanie wielu list z niezależnymi ustawieniami.
- Powiadomienia Windows, Microsoft Teams i Google Chat.
- Oddzielne harmonogramy odczytu dla INC i SCTASK.
- Historia zgłoszeń oraz konfiguracja kolumn dla każdej listy.
- Praca w zasobniku systemowym i obsługa zapamiętanej sesji logowania.
- Sprawdzanie dostępności aktualizacji.
- Osobny widok incydentów zagrożonych SLA, sprawdzany co minutę od zakończenia poprzedniej próby, również pomiędzy odczytami filtrów.
- Pierwszy poprawny odczyt nowego filtra zapisuje stan początkowy bez powiadomień o istniejących zgłoszeniach.

Bieżące wydanie opisano w [notatkach 1.9.2](docs/wersje/v1.9.2.md). Wcześniejsze opisy zachowano w [indeksie wersji](docs/wersje/README.md).

## Uruchomienie

1. Pobierz ZIP z [najnowszego wydania](https://github.com/pzaradzki/NetoIncidentMonitor/releases/latest).
2. Rozpakuj całe archiwum.
3. Uruchom `Neto Incident Monitor.exe`.
4. Dodaj adres listy ServiceNow, wybierz **Uruchom monitoring** i zaloguj się.

Katalog `_internal` musi pozostać obok pliku EXE. Pakiet zawiera Chromium i wymagane biblioteki; instalacja Pythona nie jest potrzebna.

**Wymagania:** Windows 10/11 (64-bit), dostęp do ServiceNow oraz uprawnienia do monitorowanych list. Powiadomienia Teams i Google Chat wymagają konfiguracji webhooka.

Ta konfiguracja aplikacji obsługuje listy z instancji `adeo.service-now.com`.

## Aktualizacja i dane

Aby zaktualizować aplikację, zamknij ją i zastąp katalog aplikacji zawartością nowego pakietu.

Ustawienia, historia, logi i profil przeglądarki są przechowywane w:

```text
%LOCALAPPDATA%\NetoIncidentMonitor
```

Aktualizacja zachowuje dane użytkownika. Nie udostępniaj katalogu danych, ponieważ zawiera konfigurację webhooków i sesję przeglądarki.

## Kod źródłowy

Wymagany Python 3.12. Uruchom `start.bat`, aby przygotować środowisko i uruchomić aplikację.

Szczegółowe informacje: [instrukcja użytkownika](docs/instrukcja-uzytkownika.md) oraz [indeks dokumentacji projektu](docs/README.md).

## Weryfikacja źródeł

W istniejącym środowisku uruchom:

```powershell
.venv\Scripts\python.exe -B -m tools.run_regression --output build/regression.json
```

Runner używa osobnego procesu i tymczasowych danych dla każdego modułu. Testy natywnego fokusu działają pojedynczo; pozostałe w najwyżej trzech procesach (`--jobs 1` wyłącza równoległość). Błędy callbacków Tk powodują niezaliczenie modułu. Wynik JSON zawiera liczniki, identyfikatory testów i przyczyny pominięć; nie zawiera treści wyjątków. Domyślny limit modułu to 180 s (`--timeout`).

`.venv\Scripts\python.exe -B -m tools.preview_ui` tworzy podgląd z danych syntetycznych w `build/ui-preview.png`, bez użycia danych i sesji monitora. Test regresyjny narzędzia sprawdza przepływ z atrapą przechwytywania obrazu, nie stanowi odbioru wizualnego zrzutu.

Naprawy audytu wchodzące do 1.9.1 i granice weryfikacji opisuje [AUDIT.md](AUDIT.md). Testy lokalne i offline nie zastępują nowego odbioru rzeczywistego ServiceNow.
