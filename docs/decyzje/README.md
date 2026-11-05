# Decyzje projektowe

Krótkie uzasadnienia rozwiązań wpływających na wiele funkcji. Dokumentują ustalenia; nie zastępują kodu, testów ani polecenia wdrożenia.

| ID | Decyzja |
| --- | --- |
| [001](001-watki-i-kolejki.md) | Jeden właściciel Playwright; Tk i zadania w tle komunikują się kolejkami. |
| [002](002-harmonogram-zagrozen.md) | Zastąpiona przez 018; zachowuje pierwotne uzasadnienie priorytetu zagrożeń. |
| [003](003-poprawnosc-i-aktualnosc.md) | Brak danych i błąd nie oznaczają zera ani świeżego sukcesu. |
| [004](004-bezpieczna-diagnostyka.md) | Wspólna, ograniczona diagnostyka bez danych wrażliwych. |
| [005](005-kompletny-odczyt-listy.md) | Pełna walidacja listy przed zapisaniem; ograniczone ponowienie od początku. |
| [006](006-odczyt-sekcji-dashboardu.md) | Wspólny czytnik, jeden budżet odzyskiwania i osobna aktualność każdej sekcji dashboardu. |
| [007](007-ukryty-dashboard.md) | Ukryty odczyt analityki z kontrolowanym renderowaniem i potwierdzaniem spóźnionych kategorii. |
| [008](008-obserwacja-logowania.md) | Wspólne stany logowania; konflikt i nieudana obserwacja wykluczają potwierdzenie sesji. |
| [009](009-renderowanie-ukrytego-logowania.md) | Przyjęte i wdrożone ograniczone renderowanie 1×1 ukrytego logowania, z odrębną granicą zaufania i obsługą ręczną. |
| [010](010-cykl-zycia-zadania-dashboardu.md) | Zamrożony okres i blokada kontrolek przez cały cykl żądania dashboardu; zakończenie i wyniki powiązane z ID. |
| [011](011-transakcyjny-stan-filtrow.md) | Historia i obecność w jednej transakcji SQLite. |
| [012](012-usuniecie-stanu-przeczytania.md) | Zgodność historii i konfiguracji po usunięciu lokalnego stanu przeczytania. |
| [013](013-reset-danych-aplikacji.md) | Wznawialny reset lokalnych danych pod blokadą instancji. |
| [014](014-linki-dashboardu-na-zadanie.md) | Pobieranie celu pojedynczego kafelka dopiero po kliknięciu, poza odświeżaniem wartości. |
| [015](015-rownowaznosc-dat-filtrow.md) | Ścisłe porównywanie filtrów z potwierdzoną równoważnością siedmiodniowej daty. |
| [016](016-normalizacja-adresow-list.md) | Rozpakowanie długich adresów list bez utraty kodowania i parametrów. |
| [017](017-odpornosc-lokalnego-io.md) | Odporne logowanie, obserwowana kolejka alertów, kompletny podział wiadomości i walidacja przed startem. |
| [018](018-kolejnosc-aktualizacji.md) | Dashboard → zagrożenia → filtry; zachowany niezależny harmonogram zagrożeń. |

| [019](019-odzyskiwanie-sesji-sekcji.md) | Niezależne ponowienie odczytu i odzyskanie logowania, wspólny budżet 60 s. |

| [020](020-spojne-statusy-dashboardu.md) | Spójna aktywność sekcji, nagłówka i stopki dashboardu, chroniona cyklem żądania. |

## Format i utrzymanie

Nowy plik: kolejny numer i krótka nazwa. Wystarczą: **data/status → decyzja → powód → realizacja i ograniczenia**. Kilkanaście wierszy zwykle wystarczy.

Statusy: **proponowana**, **przyjęta**, **zastąpiona**. Przyjęta zasada może być wdrożona częściowo — zawsze wskazuj zakres realizacji. Nie wpisuj propozycji z planu jako obowiązującego zachowania kodu.

Zmiana decyzji: dodaj nowy zapis, połącz oba odnośnikami, a poprzedni oznacz jako zastąpiony. Bieżącą mapę modułów aktualizuj w [architekturze](../architektura.md), a postęp wdrażania w [planach](../plany/README.md). Nie kopiuj całych planów do decyzji.
