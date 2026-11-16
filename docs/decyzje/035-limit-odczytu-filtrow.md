# 035 — Limit 1000 rekordów w odczycie filtra

**Status** — przyjęta i wdrożona w bieżących źródłach. Użytkownik potwierdził obsługę przekroczenia limitu. Szczegółowe pomiary wydajności na ServiceNow celowo pominięto.

**Decyzja** — aktualizacja filtra użytkownika wysyła jedno żądanie Table API z limitem 1000 rekordów. Większy wynik wymaga zmiany warunków filtra przez użytkownika.

**Powód** — seryjny odczyt dużych, zmieniających się list zwiększa liczbę żądań i ryzyko utraty spójności. Pełny wynik do ustalonego limitu nadal pozwala wykrywać wejścia do filtra i wyjścia z niego. Zastępuje wariant wielostronicowy z [decyzji 034](034-odczyt-filtrow-przez-rest.md).

**Realizacja i ograniczenia** — czytnik porównuje nagłówek licznika z liczbą wierszy i sygnałem następnej strony. Przekroczenie limitu kończy odczyt i wyłącza filtr w harmonogramie, aby ograniczyć kolejne odczyty. Aplikacja pokazuje monit po zapisaniu zmiany, a stopka podaje nazwę, liczebność i limit. Dane, historia, stan obecności i powiadomienia pozostają oparte na ostatniej pełnej migawce. Ręczne odczyty wyłączonego filtra nadal są dostępne. Ponowienia techniczne i odzyskanie sesji zachowują istniejące budżety. [Kontrakt odczytu](../kontrakty/kontrakt-odczytu-list.md)

W bieżącym interfejsie liczebność, limit i akcja edycji pojawiają się w belce danego filtra. Zapisane wyłączenie filtra spoza widocznego widoku nadal wyświetla monit. Błąd zapisu ma osobny komunikat. [Decyzja 039](039-statusy-widokow-i-kolejki.md).
