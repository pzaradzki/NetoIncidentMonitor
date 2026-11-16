# 038 — Walidacja złożonych warunków filtrów

**Status** — przyjęta i wdrożona w źródłach. Rozszerza [decyzję 037](037-definicje-filtrow-bez-dom.md) o walidację operatorów i trwałe potwierdzenie złożonej definicji.

**Decyzja** — aplikacja zachowuje oryginalny warunek, a przed odczytem rekordów sprawdza pola i argumenty obsługiwanych operatorów. Aktywne zmienne katalogowe odczytuje po dokładnym identyfikatorze z `item_option_new`. Gdy gałąź AND zawiera dokładne ograniczenie pozycji katalogowej, sprawdza bezpośrednie powiązanie albo członkostwo zestawu w `io_set_item`. Filtr **Wnioski** podlega tym samym regułom co pozostałe filtry SCTASK i RITM, bez zależności od konfiguracji Dashboardu.

**Powód** — zwykłe metadane tabel nie zawierają zmiennych katalogowych. W ADEO błędna zmienna zwróciła HTTP 200 i wszystkie rekordy próbki mimo niespełnionego warunku. Odczyt definicji oraz sprawdzenie typu i operatora pozwalają dopuścić nowe wartości bez powiększania zakresu zapytania. [Table API](https://www.servicenow.com/docs/r/api-reference/rest-apis/c_TableAPI.html)

**Realizacja i granice** — potwierdzenia obowiązują do 24 godzin, a błędy pobrania współdzielonych metadanych do 60 sekund. Metadane odczytuje i współdzieli zalogowana sesja. Obsługujemy datę względną `RELATIVELT` w dniach wstecz oraz `ISEMPTY` i `ISNOTEMPTY` dla tekstu jednowierszowego. `SAMEAS` i `NSAMEAS` sprawdzają oba pola i zgodność typów. Warianty spoza potwierdzonego zakresu kończą się przed żądaniem o rekordy. Gotowa definicja nadal używa jednego żądania po rekordy. [Kontrakt list](../kontrakty/kontrakt-odczytu-list.md)
