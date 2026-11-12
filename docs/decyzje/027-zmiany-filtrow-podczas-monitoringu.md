# 027 — Zmiany filtrów podczas monitoringu

**Status.** Przyjęta i wdrożona w źródłach.

**Decyzja.** Dodanie, edycja i usunięcie zaczynają obowiązywać po zapisaniu konfiguracji. Zmiana nazwy zachowuje bieżący odczyt. Zmiana adresu lub usunięcie unieważnia starsze żądania dotyczące tego filtra. Nowy adres bierze udział w pierwszej partii swojego typu utworzonej po zapisie. Ręczna aktualizacja może zlecić wcześniejszy odczyt.

**Powód.** Kolejka musi utrzymać zakres zleceń użytkownika i pozwalać na pracę pozostałych filtrów podczas zmiany konfiguracji. Powiązanie wyniku z adresem i rewizją chroni go przed zmianą kolejności wierszy, usunięciem oraz ponownym dodaniem adresu.

**Realizacja.** Po zapisaniu konfiguracji aktualizujemy listę dla harmonogramu i usuwamy nieaktualne części oczekujących zleceń. Przerywamy aktywny odczyt w najbliższym punkcie, który może sprawdzić aktualność filtra. Zapis konfiguracji, zapis wyniku SQLite i przyjęcie alertu do wysyłki mają wspólną blokadę. Tk sprawdza rewizję także przy odbieraniu spóźnionych zdarzeń. Historia pozostaje związana z adresem, a ponowne ręczne dodanie adresu zakłada nowy stan początkowy bez alertów o zastanych zgłoszeniach. Wspólną rewizję alertów z decyzji 011 uzupełniamy o rewizje poszczególnych filtrów. [Historia i obecność filtrów](011-transakcyjny-stan-filtrow.md).

**Ograniczenia.** Wynik zatwierdzony przed zmianą pozostaje w historii. Rozpoczęta wysyłka może dotrzeć do odbiorcy. Po usunięciu ostatniego filtra działający monitoring nadal sprawdza zagrożenia SLA.
