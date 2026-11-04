# 012. Usunięcie lokalnego stanu przeczytania

**Status** — wdrożone w źródłach.

**Decyzja.** Usuwamy lokalny stan przeczytania i wszystkie sterowane nim elementy interfejsu. Źródłem alertów pozostaje potwierdzona obecność w filtrze i historia wykryć.

**Powód.** Otwieranie zgłoszenia służy nawigacji, a historię wykryć i alerty obsługuje wspólny zapis transakcyjny.

**Realizacja i ograniczenia.** Starsze pola `read` z historii JSON lub SQLite są pomijane w pamięci. Nowe i aktualizowane wpisy zapisują się bez tego pola. Sam odczyt nie przepisuje bazy. Dawny klucz ustawienia i układy kolumn są oczyszczane przy zwykłym zapisie konfiguracji. Istniejące zadania wysyłki i członkostwo filtrów zachowują dotychczasowy format.

**Weryfikacja.** Regresja Windows w 60 izolowanych modułach, z powtórkami zmienionych modułów po poprawkach. Zaliczono 426 testów, jeden pominięto. Próby objęły starszy JSON, istniejący SQLite, zachowanie kolejki po ponownym otwarciu, zapis konfiguracji z DPAPI, tabele, menu i zasobnik. Testy wykonywano lokalnie na danych syntetycznych.
