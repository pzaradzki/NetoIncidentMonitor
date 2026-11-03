# 003 — Błąd, brak danych i zero

Data: 1 listopada 2026. **Status: przyjęta; realizacja w źródłach.**

**Decyzja:** zero jest wynikiem, który trzeba poprawnie odczytać. Brak kafelka, ładowanie, niejednoznaczność i wyjątek nie mogą tworzyć sztucznego zera. Nieudana próba nie nadaje staremu wynikowi nowego czasu sukcesu. Symulacja pozostaje jawnie oznaczona jako testowa.

**Powód:** fałszywe zero może wygasić alarm, a pozornie świeży wynik wprowadzić użytkownika w błąd.

**Realizacja:** zagrożenia przyjmują komplet sześciu wartości; błąd zachowuje ostatni wynik, czas i aktywny alarm. Dopiero poprawny komplet zer potwierdza brak zagrożeń. Identyfikatory żądań odrzucają spóźnione wyniki UI.

**Uzupełnienie:** zwykły dashboard przyjmuje teraz wyłącznie kompletne zestawy sekcji i przechowuje ich osobne czasy sukcesu. Szczegóły realizacji: [006](006-odczyt-sekcji-dashboardu.md). Sekundowa stabilność pozostaje dodatkowym zabezpieczeniem, nie samodzielnym dowodem świeżości. Nie potwierdza to zawartości wcześniejszego EXE.
