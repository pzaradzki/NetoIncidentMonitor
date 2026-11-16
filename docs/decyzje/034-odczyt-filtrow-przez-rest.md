# 034 — Filtry użytkownika przez Table API

**Status** — odczyt rekordów przez Table API pozostaje wdrożony. Ustalenia o czytniku metadanych klasycznej listy i zapisie układu przy filtrze zastąpiła [decyzja 037](037-definicje-filtrow-bez-dom.md). Szczegółowy odbiór pierwszej migracji na ServiceNow pominięto na decyzję użytkownika.

**Decyzja** — definicja identyfikuje tabelę, pełne warunki, widok i techniczne pola kolumn dla adresu i instancji filtra. Przed pierwszym odczytem API aplikacja uzupełnia brakujące metadane na wspólnej karcie i potwierdza zapis konfiguracji. Gotowa definicja obsługuje kolejne odczyty bez otwierania listy. Zmiana adresu unieważnia zapis. Zmiany widoku ServiceNow użytkownik pobiera na żądanie przez **ⓘ**.

**Powód** — jednorazowe rozpoznanie zachowuje znaczenie skrótów, warunków i niestandardowych widoków. Table API skraca aktualizację i pozwala wykonywać ją w tle. Zachowanie wszystkich pól z widoku ServiceNow umożliwia późniejsze pokazanie lokalnie ukrytych kolumn i stosowanie szablonów powiadomień.

**Realizacja i ograniczenia** — kolejka, karta, wznowienie sesji i zapis historii korzystają z istniejących mechanizmów. REST sprawdza licznik, unikalność i odpowiedź dla wszystkich wymaganych pól. Dostęp i równoważność zależą od instancji, warunków oraz uprawnień konta. Ten sposób realizuje zasadę pełnego odczytu z [decyzji 005](005-kompletny-odczyt-listy.md). Wariant pobierania wielu stron zastępuje [decyzja 035](035-limit-odczytu-filtrow.md). [Kontrakt](../kontrakty/kontrakt-odczytu-list.md) · [Plan i odbiór](../plany/zakonczone/migracja-odczytu-filtrow-na-api.md)
