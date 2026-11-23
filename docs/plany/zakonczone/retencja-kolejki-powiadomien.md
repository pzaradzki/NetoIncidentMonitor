# Etap 1. Retencja kolejki powiadomień

Ograniczyć czas przechowywania zakończonych powiadomień w `alert_outbox`. Czyszczenie obejmuje techniczną kolejkę w SQLite. Historia zgłoszeń, obecność w filtrach i migawki zagrożeń SLA zachowują własne reguły zapisu. [Plan ogólny](../uporzadkowanie-architektury.md#etap-1-retencja-kolejki-powiadomień) · [Kontrakt kolejki](../../kontrakty/kolejka-i-trwalosc.md#automatyczne-powiadomienia)

## 1. Stan wyjściowy i polityka retencji

- [x] Sprawdzono schemat. `alert_outbox` ma kolumny `id`, `state` i `payload`. Zakończenie wysyłki zapisuje stan, a pełna treść pozostaje w wierszu. Baza nie przechowuje daty zakończenia. [Schemat i przejścia stanów](../../../neto_incident_monitor/history.py)
- [x] Sprawdzono odzyskiwanie. Rozpoczęte `sending` przechodzi przy odzyskiwaniu w `uncertain`. Do dostarczenia wybierane są `pending`. [Kontrakt dostarczania](../../decyzje/017-odpornosc-lokalnego-io.md) · [Regresja restartu](../../../tests/test_filter_atomic_commit.py)
- [x] Sprawdzono cykl życia magazynu. `user_version=0` dopuszcza bazę z zagrożeniami i alertami przed pierwszym zapisem filtra. Pierwszy kompletny zapis filtra ustawia `user_version=1`. Kontrola startowa jest odczytowa. [Kontrakt migracji](../../kontrakty/kolejka-i-trwalosc.md#lokalne-dane-i-migracja) · [Kontrola startowa](../../../neto_incident_monitor/data_validation.py)
- [x] Ustalono 30 dni dla `accepted` i `cancelled` od przejścia do stanu końcowego. [Decyzja 041](../../decyzje/041-retencja-kolejki-alertow.md)
- [x] Ustalono, że `uncertain` po 30 dniach zachowuje identyfikator, stan, czas z podstawą naliczenia i rozpoznany kanał. Po 90 dniach usuwany jest cały wpis. [Decyzja 041](../../decyzje/041-retencja-kolejki-alertow.md)
- [x] Ustalono podstawę czasu dla wpisów bez daty. Odliczanie zaczyna się od pierwszego rozpoznania wpisu, z oznaczeniem odmiennej podstawy naliczenia. [Decyzja 041](../../decyzje/041-retencja-kolejki-alertow.md)
- [x] Zapisano ochronę `pending` i `sending` oraz brak ponowienia wysyłki po przejściu w `uncertain`. [Decyzja 041](../../decyzje/041-retencja-kolejki-alertow.md)

## 2. Schemat i migracja istniejących baz

- [x] Dodano testy starszych baz w wersjach 0 i 1, bazy bez tabeli alertów oraz pierwszego zapisu zagrożeń. [Testy retencji](../../../tests/test_alert_retention.py)
- [x] Czas UTC w sekundach i podstawa naliczenia są zapisywane w JSON `payload`. `user_version` nadal dotyczy historii filtrów. [Decyzja 041](../../decyzje/041-retencja-kolejki-alertow.md)
- [x] Kod `History` i kontroli startowej wyjęty z EXE `1.12.0-experimental.4` po czyszczeniu otworzył syntetyczne bazy w wersjach 0 i 1, odczytał migawki i dopisał alert. Bieżący kod ponownie przeszedł kontrolę startową i odczytał oba alerty. [Zapis i kontrola schematu](../../../neto_incident_monitor/history.py)
- [x] Wpisy są uzupełniane porcjami, z wycofaniem transakcji po błędzie lub anulowaniu. Test potwierdził ponowne otwarcie i brak zmian pliku podczas kontroli startowej. [Testy retencji](../../../tests/test_alert_retention.py)
- [x] Test przejść potwierdził zapis czasu dla `accepted`, `cancelled`, `uncertain` i odzyskanego `sending`. [Testy retencji](../../../tests/test_alert_retention.py)
- [x] Starsze wpisy otrzymują podstawę `observed`. Test potwierdził jej użycie po ponownym otwarciu bazy i zachowanie pełnego pierwszego okresu. [Testy retencji](../../../tests/test_alert_retention.py)

## 3. Czyszczenie i praca w tle

- [x] SQLite w jednej transakcji sprawdza i przetwarza najwyżej 128 wierszy. Test pokazał ponowne podjęcie pracy po zatrzymaniu i restarcie. [Czyszczenie](../../../neto_incident_monitor/alert_retention.py) · [Testy retencji](../../../tests/test_alert_retention.py)
- [x] Po 30 dniach `uncertain` zawiera tylko metrykę i dozwolony kanał, jeśli był rozpoznany. Test potwierdził brak treści w polu JSON i dostępność wyłącznie `pending` do wysyłki. [Testy retencji](../../../tests/test_alert_retention.py)
- [x] Start około 5 s po utworzeniu kontrolera. Przegląd obsługuje do czterech porcji na zadanie, kontynuuje po 30 s i po ukończeniu wraca po dobie. Test potwierdził ponowne uruchomienie także bez zgłoszenia wysyłki. [Harmonogram retencji](../../../neto_incident_monitor/alert_retention.py)
- [x] Zadanie korzysta z `history_writer`. Główny wątek odbiera wynik dopiero po zakończeniu zadania. Test objął anulowanie przed zatwierdzeniem i wznowienie czyszczenia po restarcie. [Integracja w App](../../../neto_incident_monitor/app.py) · [Testy retencji](../../../tests/test_alert_retention.py)
- [x] Zajęta baza odracza próbę o 30 s, inny błąd o 5 min. Testy wymusiły zajętą bazę i błąd usuwania. Potwierdziły rollback, zachowanie nowego alertu i pojedyncze wywołanie atrapy kanału oczekującej wysyłki. [Testy retencji](../../../tests/test_alert_retention.py)
- [x] Na 20 000 syntetycznych wpisów usunięto 19 980 w 157 porcjach. Mediana porcji wyniosła 5,26 ms, maksimum 8,97 ms. SQLite zwolnił 2930 stron, a plik miał nadal 12 025 856 bajtów. Czyszczenie używa zakresu po `rowid`. Próbny indeks dla odczytu `pending` dał 0,15 ms zamiast 9,72 ms przed czyszczeniem. Decyzja o dodatkowym indeksie pozostaje osobną optymalizacją odczytu kolejki. [Ustalenie A07](../../archiwum/AUDIT.md#4-konkretne-ryzyka-eksploatacyjne-i-luki-w-kontroli-jakości)

## 4. Diagnostyka

- [x] Dodano zdarzenie `alert_retention` z identyfikatorem uruchomienia i operacji, czasem, limitem, licznikami, wynikiem i czasem do następnej próby. [Diagnostyka](../../../neto_incident_monitor/login_diagnostics.py)
- [x] W zapisanym JSONL sprawdzono korelację, liczniki i wyniki sukcesu, braku zmian, anulowania i błędu. Test wyklucza zapis syntetycznych sekretów, treści i adresu. [Testy retencji](../../../tests/test_alert_retention.py)
- [x] Wymuszona awaria otwarcia pliku logu pozostawiła prawidłowy wynik czyszczenia i oczekujący alert. [Testy retencji](../../../tests/test_alert_retention.py)

## 5. Testy i zamknięcie etapu

- [x] Testy sprawdziły sekundę przed i w chwili upływu retencji oraz ponowne czyszczenie. Chronione wiersze zachowały identyczny stan i treść. [Testy retencji](../../../tests/test_alert_retention.py)
- [x] Sprawdzono przerwanie między porcjami, wznowienie po restarcie i sytuację, w której drugi wykonawca trzyma transakcję z nowym wpisem. [Testy retencji](../../../tests/test_alert_retention.py)
- [x] Po otwarciu bazy i błędzie czyszczenia test wykonał jedną wysyłkę oczekującego wpisu przez atrapę. Przerwane `sending` przeszło do `uncertain`. [Test retencji i dostarczania](../../../tests/test_alert_retention.py) · [Testy restartu](../../../tests/test_filter_atomic_commit.py)
- [x] Test wersji 0 i 1 potwierdził zachowanie historii zgłoszeń, obecności, migawki i liczników zagrożeń po uzupełnieniu dat i usunięciu wpisu. Ponowny start i pierwszy zapis filtra przeszły. [Testy retencji](../../../tests/test_alert_retention.py) · [Testy trwałości zagrożeń](../../../tests/test_threatened_details.py)
- [x] Zaliczone 40 testów zakresowych bez pominięć. Pełna regresja Windows objęła 546 testów w 72 modułach. Zaliczone 544, 2 pominięte, bez błędów testów i callbacków Tk. Próby fokusu Chromium i dowiązania symbolicznego pozostały pominięte także po osobnym ponowieniu z powodu ograniczeń środowiska. [Runner regresji](../../../tools/run_regression.py)
- [x] Zaktualizowano decyzję, kontrakt i architekturę. Plan szczegółowy przeniesiono do zakończonych. [Decyzja 041](../../decyzje/041-retencja-kolejki-alertow.md) · [Kontrakt](../../kontrakty/kolejka-i-trwalosc.md#automatyczne-powiadomienia) · [Architektura](../../architektura.md)

## Aktualizowanie checkboxów

Po wykonaniu każdego kroku zmienić `[ ]` na `[x]` w tym pliku i przy tej pozycji dopisać krótki wynik lub odnośnik do decyzji, testu albo raportu. Przy częściowym wyniku pozostawić `[ ]` i zapisać, co zostało do sprawdzenia. Jeżeli weryfikacja wykaże regresję, ponownie otworzyć właściwy krok i odnotować przyczynę. Checkbox rozpoznania kodu potwierdza wyłącznie stan wyjściowy.
