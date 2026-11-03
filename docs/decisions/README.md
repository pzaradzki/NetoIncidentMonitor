# Decyzje projektowe

Krótkie uzasadnienia rozwiązań wpływających na wiele funkcji. Dokumentują ustalenia; nie zastępują kodu, testów ani polecenia wdrożenia.

| ID | Decyzja |
| --- | --- |
| [001](001-watki-i-kolejki.md) | Jeden właściciel Playwright; Tk i zadania w tle komunikują się kolejkami. |
| [002](002-harmonogram-zagrozen.md) | Zagrożenia po logowaniu i 60 s od zakończenia; wtrącanie między całymi filtrami. |
| [003](003-poprawnosc-i-aktualnosc.md) | Brak danych i błąd nie oznaczają zera ani świeżego sukcesu. |
| [004](004-bezpieczna-diagnostyka.md) | Wspólna, ograniczona diagnostyka bez danych wrażliwych. |
| [005](005-kompletny-odczyt-listy.md) | Pełna walidacja listy przed zapisaniem; ograniczone ponowienie od początku. |
| [006](006-odczyt-sekcji-dashboardu.md) | Wspólny czytnik, jeden budżet odzyskiwania i osobna aktualność każdej sekcji dashboardu. |
| [007](007-ukryty-dashboard.md) | Ukryty odczyt analityki z kontrolowanym renderowaniem i potwierdzaniem spóźnionych kategorii. |
| [008](008-obserwacja-logowania.md) | Wspólne stany logowania; konflikt i nieudana obserwacja wykluczają potwierdzenie sesji. |
| [009](009-renderowanie-ukrytego-logowania.md) | Przyjęte i wdrożone ograniczone renderowanie 1×1 ukrytego logowania, z odrębną granicą zaufania i obsługą ręczną. |
| [010](010-cykl-zycia-zadania-dashboardu.md) | Zamrożony okres i blokada kontrolek przez cały cykl żądania dashboardu; zakończenie i wyniki powiązane z ID. |
| [011](011-transakcyjny-stan-filtrow.md) | Historia i obecność w jednej transakcji SQLite. |

## Format i utrzymanie

Nowy plik: kolejny numer i krótka nazwa. Wystarczą: **data/status → decyzja → powód → realizacja i ograniczenia**. Kilkanaście wierszy zwykle wystarczy.

Statusy: **proponowana**, **przyjęta**, **zastąpiona**. Przyjęta zasada może być wdrożona częściowo — zawsze wskazuj zakres realizacji. Nie wpisuj propozycji z planu jako obowiązującego zachowania kodu.

Zmiana decyzji: dodaj nowy zapis, połącz oba odnośnikami, a poprzedni oznacz jako zastąpiony. Bieżącą mapę modułów aktualizuj w [architekturze](../architecture.md), a postęp wdrażania w [planach](../plans/README.md). Nie kopiuj całych planów do decyzji.
