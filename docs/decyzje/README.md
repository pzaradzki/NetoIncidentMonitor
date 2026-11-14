# Decyzje projektowe

Krótkie uzasadnienia rozwiązań wpływających na wiele funkcji. Dokumentują ustalenia; nie zastępują kodu, testów ani polecenia wdrożenia.

| ID | Decyzja |
| --- | --- |
| [001](001-watki-i-kolejki.md) | Jeden właściciel Playwright; Tk i zadania w tle komunikują się kolejkami. |
| [002](002-harmonogram-zagrozen.md) | Zastąpiona przez 018; zachowuje pierwotne uzasadnienie priorytetu zagrożeń. |
| [003](003-poprawnosc-i-aktualnosc.md) | Brak danych i błąd nie oznaczają zera ani świeżego sukcesu. |
| [004](004-bezpieczna-diagnostyka.md) | Wspólna, ograniczona diagnostyka bez danych wrażliwych. |
| [005](005-kompletny-odczyt-listy.md) | Pełna walidacja listy przed zapisaniem; ograniczone ponowienie od początku. |
| [006](006-odczyt-sekcji-dashboardu.md) | Niezależna aktualność sekcji. Czytnik zastąpiła 032. |
| [007](007-ukryty-dashboard.md) | Historyczne renderowanie ukrytej analityki, zastąpione przez 032. |
| [008](008-obserwacja-logowania.md) | Wspólne stany logowania; konflikt i nieudana obserwacja wykluczają potwierdzenie sesji. |
| [009](009-renderowanie-ukrytego-logowania.md) | Przyjęte i wdrożone ograniczone renderowanie 1×1 ukrytego logowania, z odrębną granicą zaufania i obsługą ręczną. |
| [010](010-cykl-zycia-zadania-dashboardu.md) | Zamrożony okres i blokada kontrolek przez cały cykl żądania dashboardu; zakończenie i wyniki powiązane z ID. |
| [011](011-transakcyjny-stan-filtrow.md) | Historia i obecność w jednej transakcji SQLite. |
| [012](012-usuniecie-stanu-przeczytania.md) | Zgodność historii i konfiguracji po usunięciu lokalnego stanu przeczytania. |
| [013](013-reset-danych-aplikacji.md) | Wznawialny reset lokalnych danych pod blokadą instancji. |
| [014](014-linki-dashboardu-na-zadanie.md) | Zastąpiona przez 024. Uzasadnienie wcześniejszego otwierania list z kafelków. |
| [015](015-rownowaznosc-dat-filtrow.md) | Ścisłe porównywanie filtrów z potwierdzoną równoważnością siedmiodniowej daty. |
| [016](016-normalizacja-adresow-list.md) | Rozpakowanie długich adresów list bez utraty kodowania i parametrów. |
| [017](017-odpornosc-lokalnego-io.md) | Odporne logowanie, obserwowana kolejka alertów, kompletny podział wiadomości i walidacja przed startem. |
| [018](018-kolejnosc-aktualizacji.md) | Dashboard → zagrożenia → filtry; zachowany niezależny harmonogram zagrożeń. |

| [019](019-odzyskiwanie-sesji-sekcji.md) | Niezależne ponowienie odczytu i odzyskanie logowania, wspólny budżet 60 s. |

| [020](020-spojne-statusy-dashboardu.md) | Spójna aktywność sekcji, nagłówka i stopki dashboardu, chroniona cyklem żądania. |

## Format i utrzymanie

[032 — Podgląd Chromium](032-podglad-chromium.md) opisuje skrót diagnostyczny i jego wpływ na widoczność sesji.

[031 — Automatyczny zapis interwałów](031-automatyczny-zapis-odstepow.md) określa czas zapisu po edycji i przy zamykaniu ustawień.

[032 — Dashboard i zagrożenia SLA przez REST API](032-odczyty-analityki-przez-api.md) wprowadza wspólny transport oraz weryfikację kompletnej listy zagrożeń.

[030 — Odstępy odczytów podczas monitoringu](030-odstepy-podczas-monitoringu.md) opisuje zapis i przeliczenie następnego terminu bez przerywania rozpoczętej partii.

[029 — Powiadomienia Windows podczas monitoringu](029-powiadomienia-windows-podczas-monitoringu.md) opisuje zapis przełącznika i rewizję oczekujących alertów Windows.

[028 — Odsłonięcie głównego okna](028-odsloniecie-glownego-okna.md) rozdziela aktywację, fokus i odsłonięcie głównego okna po logowaniu.

[027 — Zmiany filtrów podczas monitoringu](027-zmiany-filtrow-podczas-monitoringu.md) opisuje zakres partii, unieważnianie odczytów oraz rewizje powiadomień.

[026 — Potwierdzenie zapisu poświadczeń](026-potwierdzenie-zapisu-poswiadczen.md) utrzymuje Chromium widoczne po ręcznym wpisaniu hasła przy włączonym autologowaniu.

[025 — Wspólna sesja ServiceNow](025-wspolna-sesja-servicenow.md) określa właściciela karty, start po logowaniu i kolejkę odczytów oraz importu.

[024 — Kafelki informacyjne](024-kafelki-informacyjne.md) usuwa nawigację z kafelków dashboardu i zagrożeń SLA, zachowując animację najechania.

[023 — Naturalny rozmiar logowania importu](023-naturalne-logowanie-importu.md): viewport tylko podczas odczytu i wykorzystanie jedynej startowej pustej karty; częściowo zastępuje 022.

[022 — Import ulubionych w sesji na żądanie](022-import-ulubionych-na-zadanie.md): wyłączność profilu, zbiorczy odczyt i wybór przed zapisem; wdrożone tylko w źródłach.

[021 — Gotowość i potwierdzenie kontekstu dashboardu](021-zatwierdzanie-kontekstu-dashboardu.md): oczekiwanie na Zastosuj i wspólna obserwacja stanu kategorii bez ponawiania kliknięć.

Nowy plik: kolejny numer i krótka nazwa. Wystarczą: **data/status → decyzja → powód → realizacja i ograniczenia**. Kilkanaście wierszy zwykle wystarczy.

Statusy: **proponowana**, **przyjęta**, **zastąpiona**. Przyjęta zasada może być wdrożona częściowo — zawsze wskazuj zakres realizacji. Nie wpisuj propozycji z planu jako obowiązującego zachowania kodu.

Zmiana decyzji: dodaj nowy zapis, połącz oba odnośnikami, a poprzedni oznacz jako zastąpiony. Bieżącą mapę modułów aktualizuj w [architekturze](../architektura.md), a postęp wdrażania w [planach](../plany/README.md). Nie kopiuj całych planów do decyzji.
