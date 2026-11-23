# Odbiór etapu 3. Płynność Tk

## Metoda

Pomiar bazowy wykonano na źródłach commitu `2144f87`, a pomiar po zmianie na tym samym stanowisku Windows z wdrożonym etapem 3. Oba używały Pythona 3.12.6, Tk 8.6.13, 96 DPI i trzech powtórzeń scenariusza. Narzędzie otwiera rzeczywiste widoki, korzysta z tymczasowej konfiguracji, historii i cache. Wyniki dashboardu trafiają do tej samej kolejki co podczas pracy aplikacji. Próby odbyły się z danymi syntetycznymi i bez połączenia z ADEO. [Narzędzie pomiarowe](../../tools/measure_tk_latency.py)

Lekki callback `after(16)` mierzy różnicę między planowanym a rzeczywistym wywołaniem. Bez obciążenia maksymalna różnica wyniosła około 1,6 ms, a koszt callbacku do 0,08 ms. Tabele podają największe p95 i maksimum z trzech prób oraz medianę czasu całej operacji. Czas cache obejmuje odbiór zdarzenia przez Tk, którego kolejka jest normalnie sprawdzana co 200 ms. Przy krótkich scenariuszach p95 może być równe maksimum.

Kryterium poprawy dla operacji obciążających Tk to zmniejszenie największego opóźnienia o co najmniej 75% przy zejściu poniżej 60 ms w próbie pełnego zapisu z odmową oraz historii z 10 tys. wierszy. Przy zwykłym zapisie i małych tabelach sprawdzono porównywalny czas widocznej aktualizacji. Poprawność zapisu i szerokości oceniają osobne testy funkcjonalne. Wyniki czasowe dotyczą tego stanowiska.

## Zapis cache Dashboardu SLA

Scenariusze obejmowały pojedynczą sekcję, pełny odczyt oraz serię trzech pełnych odczytów. Próbę powtarzano przy zwykłej podmianie pliku, z opóźnieniem 60 ms, z dwiema kolejnymi odmowami podmiany przed sukcesem oraz z odmową wszystkich prób. Czasy podano w milisekundach.

| Scenariusz pełnego odczytu | p95 przed → po | Maksimum przed → po | Mediana do zmiany widoku przed → po | Mediana do rozliczenia zapisu przed → po |
| --- | ---: | ---: | ---: | ---: |
| Zwykły zapis | 9,76 → 1,58 | 9,76 → 1,58 | 52,94 → 43,91 | 52,96 → 43,93 |
| Opóźnienie podmiany | 249,13 → 1,97 | 249,13 → 4,32 | 300,09 → 52,62 | 300,11 → 248,04 |
| Przejściowa odmowa | 624,77 → 4,76 | 624,77 → 5,78 | 666,57 → 53,56 | 666,59 → 449,03 |
| Końcowa odmowa | 1231,58 → 1,76 | 1231,58 → 3,71 | 1268,60 → 54,22 | 1268,61 → 849,11 |

Przy końcowej odmowie w serii trzech odczytów maksimum spadło z 1225,04 do 7,39 ms, największe p95 z 1218,63 do 3,29 ms, a mediana czasu do rozliczenia serii z 4118,91 do 1068,16 ms. Scalenie oczekujących migawek zmniejszyło liczbę prób podmiany z 48 do 12 przy tej serii. Dla pojedynczej sekcji przy końcowej odmowie pozostały cztery próby, a maksimum spadło z 309,08 do 6,23 ms. [Kontrakt zapisu](../kontrakty/kolejka-i-trwalosc.md#zapis-cache-dashboardu)

## Dopasowanie kolumn

| Scenariusz | p95 przed → po (ms) | Maksimum przed → po (ms) | Mediana do zastosowania przed → po (ms) |
| --- | ---: | ---: | ---: |
| Bieżące zgłoszenia, 100 wierszy | 20,41 → 2,32 | 20,41 → 2,32 | 21,30 → 20,01 |
| Bieżące zgłoszenia, 1000 wierszy | 49,98 → 8,40 | 49,98 → 8,40 | 68,89 → 73,56 |
| Historia, 10 000 wierszy | 460,53 → 6,56 | 460,53 → 8,79 | 472,72 → 536,03 |
| Dopasowanie po wstawieniu pierwszego z 1000 wierszy | 7,17 → 8,99 | 7,17 → 8,99 | 62,98 → 127,48 |

Przy 10 tys. wierszy osobny pomiar bazowy wskazał do 2,04 ms na pobranie identyfikatorów, 12,82 ms na odczyt wartości i 449,67 ms na pomiar fontu. Zapis profilu zwykle zajmował 2–4 ms. Dopasowanie rozpoczęte podczas wczytywania wcześniej mogło uwzględnić tylko pierwszy wiersz. Teraz czeka na całą tabelę. W jednej z trzech prób trwało 1,24 s od dwukliku, przy maksimum 8,16 ms opóźnienia Tk. W gotowej historii cały pomiar trwał dłużej o około 63 ms według mediany, a Tk reagował między porcjami. [Decyzja 043](../decyzje/043-plynnosc-tk.md)

## Odbiór funkcjonalny

W osobnym oknie Windows użyto przycisku Aktualizuj na dashboardzie, przewinięto dashboard i historię, przełączono obie zakładki zgłoszeń i dwuklikiem dopasowano kolumnę Opis w historii z 10 tys. wierszy. Dopasowanie zmieniło szerokość z 180 do 1426 px. Po zwykłym zamknięciu odczyt pliku potwierdził wartość z drugiego odświeżenia.

W drugiej, sterowanej czasowo próbie natywnej wywołano zamknięcie aplikacji przy jednocześnie aktywnym zapisie cache i pomiarze kolumny. Zamknięcie anulowało dopasowanie i poczekało na zapis. Odczyt pliku po zamknięciu potwierdził ostatnią zaakceptowaną migawkę.

Testy obejmują kompletność i znaczniki czasu migawek, spóźnione wyniki, ponowienia zapisu, kolejność rewizji, ostatnią migawkę przy zamknięciu, odrzucenie oczekującej migawki przy resecie i dopasowanie do najdłuższego wiersza poza ekranem. Logi testowe potwierdzają czasy, liczniki i korelację z wykluczeniem syntetycznej treści komórki oraz danych z błędu pliku. [Migawki](../../tests/test_dashboard_snapshots.py) · [Okres](../../tests/test_dashboard_period.py) · [Reset](../../tests/test_data_reset.py) · [Kolumny](../../tests/test_dynamic_columns.py)

## Regresja Windows

Pierwsza próba zakresowa wykazała brak numeru zgłoszenia w dwóch nowych przypadkach syntetycznych. Po poprawieniu danych ponowienie zaliczyło 89 z 90 testów. Końcowa pełna regresja po dodatkowym sprawdzeniu błędu zapisu profilu i ochrony przed spóźnionym wynikiem przy zamykaniu zaliczyła 553 z 554 testów, bez błędów callbacków Tk. W obu przebiegach pominięto sprawdzanie dowiązania w profilu resetu, ponieważ środowisko Windows nie pozwoliło go utworzyć. [Runner regresji](../../tools/run_regression.py)

Lokalne wyniki pomiarów to `build/tk-latency-before.json` i `build/tk-latency-after.json`. Końcowy wynik regresji zapisano w `build/regression-tk-latency-final.json`. [Zakończony plan z checklistą](../plany/zakonczone/plynnosc-tk.md)
