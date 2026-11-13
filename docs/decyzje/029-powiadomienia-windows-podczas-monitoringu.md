# 029 — Powiadomienia Windows podczas monitoringu

**Status.** Przyjęta w źródłach po wydaniu 1.11.0. Uzupełnia [decyzję 011](011-transakcyjny-stan-filtrow.md) i [decyzję 027](027-zmiany-filtrow-podczas-monitoringu.md).

**Decyzja.** Globalny przełącznik Windows jest dostępny w trakcie monitoringu. Jego zmiana obowiązuje po zapisaniu konfiguracji. Przy błędzie aplikacja przywraca poprzedni stan przełącznika i ikon.

**Powód.** Przełącznik był blokowany razem z polami interwału i zapisywany dopiero przy starcie cyklu. Kolejka odczytuje konfigurację przy tworzeniu alertu i przy przyjmowaniu go do wysyłki. Może więc uwzględnić nowe ustawienie bez zatrzymywania cyklu.

**Realizacja.** Zmiana globalnego przełącznika ma osobną rewizję kanału Windows dla alertów filtrów i zagrożeń SLA. Starsza konfiguracja zachowuje poprzedni identyfikator aż do pierwszej zmiany. Wyłączenie i ponowne włączenie nie wznawia wcześniejszych oczekujących alertów Windows. Alerty Google Chat i Teams zachowują swoje rewizje. Zapis konfiguracji i przyjęcie alertu do wysyłki korzystają z tej samej blokady.

**Ograniczenia.** Alert przyjęty do wysyłki przed zapisem zmiany może już dotrzeć. Włączenie kanału dotyczy nowych alertów.
