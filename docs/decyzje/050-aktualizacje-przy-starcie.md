# 050 — Sprawdzanie aktualizacji przy starcie

**Status.** Przyjęta i wdrożona w źródłach.

**Decyzja.** Główna instancja standardowo raz sprawdza najnowsze stabilne wydanie po inicjalizacji Tk. Użytkownik może wyłączyć sprawdzenie przy następnym starcie w sekcji **Uruchamianie i okno aplikacji**. Przycisk ręczny korzysta ze wspólnego odczytu i okna wyniku. Kliknięcie w trakcie sprawdzenia startowego dołącza do bieżącej próby.

**Powód.** Sprawdzenie ma działać również podczas oczekiwania na zalogowanie do ServiceNow i przy zminimalizowanym monitorze. Wspólny odczyt zachowuje jedno źródło porównania wersji, komunikatów i obsługi limitu GitHuba.

**Realizacja.** `ReleaseCheck` uruchamia odczyt w wątku w tle, odbiera wynik w Tk i zamyka oczekujące wywołania przy wyjściu z aplikacji. `release_check` zapisuje źródło, wynik, czas, kategorię błędu i użycie odczytu zastępczego, ze wspólną korelacją próby. [Mechanizm](../../neto_incident_monitor/release_check.py) · [Diagnostyka](004-bezpieczna-diagnostyka.md)

**Widoczność.** Monit o nowej wersji może pojawić się jako samodzielne okno, gdy monitor jest ukryty. Automatyczny monit nie zakłada blokady modalnej, dzięki czemu istniejący dialog logowania zachowuje swoją blokadę. Po pokazaniu głównego okna staje się ono właścicielem monitu. Przy ukrytym monitorze komunikat o braku nowej wersji lub błędzie czeka na przywrócenie okna. Otwarcie strony wydania wymaga kliknięcia. [Zasady odsłaniania okna głównego](028-odsloniecie-glownego-okna.md)
