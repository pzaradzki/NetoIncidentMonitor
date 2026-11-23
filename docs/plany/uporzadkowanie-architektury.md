# Plan uporządkowania architektury Neto Incident Monitor

Plan obejmuje cztery etapy po audycie architektury. Pierwszy ogranicza ilość danych przechowywanych przez kolejkę powiadomień. Kolejne zmniejszają zależności od `App`, weryfikują opóźnienia Tk i pozwalają odtworzyć budowę EXE z udokumentowanych wejść. Punktem odniesienia jest lokalna paczka 1.12.0-experimental.4 po usunięciu starszej pętli. [Architektura](../architektura.md) · [Opis paczki](../wersje/v1.12.0-experimental.4.md)

## Zakończone prace

Naprawiono restart po pierwszym zapisie zagrożeń SLA, przeniesiono testy na `SharedSession` i usunięto starszą pętlę. Wersja 1.12.0-experimental.4 przeszła próbę pobrania zakresu dashboardu na świeżym profilu ADEO i ponownego użycia zapisu po restarcie. [Kontrakt trwałości](../kontrakty/kolejka-i-trwalosc.md#lokalne-dane-i-migracja) · [Wycofanie pętli](zakonczone/wycofanie-starszej-petli.md) · [Odbiór ADEO](zakonczone/startowy-odczyt-zakresu-dashboardu.md#4-testy-i-odbiór)

## Etap 1. Retencja kolejki powiadomień

**Zakończony w źródłach.** Okresy 30 i 90 dni ograniczają przechowywanie zakończonych wpisów. Testy potwierdziły ochronę `pending` i `sending`, zachowanie historii użytkownika, odzyskiwanie po restarcie i zgodność baz w wersjach 0 i 1 z paczką 1.12.0-experimental.4. Pełna regresja Windows zaliczyła 544 testy, a 2 pominięto. [Zakończony plan z checklistą](zakonczone/retencja-kolejki-powiadomien.md) · [Polityka retencji](../decyzje/041-retencja-kolejki-alertow.md)

## Etap 2. Zależności od App

**Zakończony w źródłach.** Wydzielono konfigurację, logowanie, odczyty Dashboardu SLA i zagrożeń oraz obsługę ich zdarzeń w widokach. Pełna regresja Windows zaliczyła 546 testów, a 2 pominięto. Odbiór na ADEO potwierdził ręczne logowanie, ukrycie Chromium i ponowne połączenie. [Zakończony plan z checklistą](zakonczone/zaleznosci-od-app.md) · [Decyzja 042](../decyzje/042-granice-app-i-sesji.md)

## Etap 3. Płynność Tk

**Zakończony w źródłach.** Wprowadzono zapis cache dashboardu w tle z zachowaniem kolejności migawek oraz pomiar szerokości dużych tabel w porcjach Tk. Zakończono porównanie przed i po oraz weryfikację zachowania przy zamknięciu, resecie i błędzie zapisu. Pełna regresja Windows zaliczyła 553 testy, a jeden pominięto. [Zakończony plan z checklistą](zakonczone/plynnosc-tk.md) · [Pomiary i odbiór](../weryfikacja/plynnosc-tk.md) · [Decyzja 043](../decyzje/043-plynnosc-tk.md)

## Etap 4. Odtwarzalna budowa EXE

Ustalić wersjonowane źródło zatwierdzonych parametrów dashboardu używanych przez PyInstaller oraz zapisać wersje narzędzi i Chromium użyte do budowy. Parametry zapytań stanowią wejście paczki. Listy agentów i lokalizacji należą do lokalnego profilu użytkownika. [Specyfikacja PyInstallera](<../../scripts/Neto Incident Monitor.spec>) · [Parametry dashboardu](../servicenow-api-sesja-przegladarki.md#uruchomienie-odczytów-api)

Etap jest ukończony, gdy z czystego checkoutu i udokumentowanych wejść można zbudować paczkę, a rozpakowane EXE przechodzi próbę offline z izolowanym profilem.

## Kolejność i plany szczegółowe

Następny etap to odtwarzalna budowa EXE.

Przed wdrożeniem każdego etapu dodać w indeksie odnośnik do jego szczegółowego planu. Plan etapu określa zakres zmiany, decyzje do podjęcia, scenariusze błędu, testy regresji, diagnostykę i kryteria odbioru. Dla zmian w logowaniu lub zachowaniu Chromium uwzględnić odbiór właściwych scenariuszy na ADEO. Wyniki i otwarte kwestie zapisać po wykonaniu etapu. [Zasady utrzymania planów](README.md#utrzymanie) · [Regresja Windows](../../tools/run_regression.py)

Ewentualne współdzielenie mechaniki ponowień i wykonawców powiadomień ocenić po etapie 2. Budżety odczytów i reguły odzyskiwania wysyłki pozostają warunkami odbioru tych zmian. Lokalizacja logów uruchomień ze źródeł pozostaje osobną decyzją. [Kontrakt kolejki](../kontrakty/kolejka-i-trwalosc.md) · [Wyniki audytu technicznego](zakonczone/naprawy-audytu.md)
