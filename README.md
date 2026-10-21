# Neto Incident Monitor

Aplikacja dla Windows do monitorowania incydentów **INC** i zadań katalogowych **SCTASK** w ServiceNow. Odczytuje dane przez przeglądarkę Chromium, bez korzystania z API ServiceNow.

## Funkcje

- Monitorowanie wielu list z niezależnymi ustawieniami.
- Powiadomienia Windows, Microsoft Teams i Google Chat.
- Oddzielne harmonogramy odczytu dla INC i SCTASK.
- Historia zgłoszeń oraz konfiguracja kolumn dla każdej listy.
- Praca w zasobniku systemowym i obsługa zapamiętanej sesji logowania.
- Sprawdzanie dostępności aktualizacji i formularz zgłoszeń.

## Uruchomienie

1. Pobierz ZIP z [najnowszego wydania](https://github.com/pzaradzki/NetoIncidentMonitor/releases/latest).
2. Rozpakuj całe archiwum.
3. Uruchom `Neto Incident Monitor.exe`.
4. Dodaj adres listy ServiceNow, wybierz **Uruchom monitoring** i zaloguj się.

Katalog `_internal` musi pozostać obok pliku EXE. Pakiet zawiera Chromium i wymagane biblioteki; instalacja Pythona nie jest potrzebna.

**Wymagania:** Windows 10/11 (64-bit), dostęp do ServiceNow oraz uprawnienia do monitorowanych list. Powiadomienia Teams i Google Chat wymagają konfiguracji webhooka.

## Aktualizacja i dane

Aby zaktualizować aplikację, zamknij ją i zastąp katalog aplikacji zawartością nowego pakietu.

Ustawienia, historia, logi i profil przeglądarki są przechowywane w:

```text
%LOCALAPPDATA%\NetoIncidentMonitor
```

Aktualizacja zachowuje dane użytkownika. Nie udostępniaj katalogu danych, ponieważ zawiera konfigurację webhooków i sesję przeglądarki.

## Kod źródłowy

Wymagany Python 3.12. Uruchom `start.bat`, aby przygotować środowisko i uruchomić aplikację.

Szczegółowe informacje zawiera [dokumentacja użytkownika i projektu](docs/user-guide.md).
