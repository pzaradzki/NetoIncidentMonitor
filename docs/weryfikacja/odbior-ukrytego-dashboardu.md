# Odbiór wdrożenia ukrytego dashboardu

> Raport dotyczy wskazanej w nim serii źródeł i pomiarów. Późniejszy lokalny build EXE 1.8.0 opisano [osobno](../wersje/v1.8.0.md); nie zastępuje on prób rzeczywistego SSO.

1 listopada 2026. **Odbiór zakończony. Źródła wdrożone i sprawdzone; bez nowego EXE/ZIP i publikacji.**

Zakres: [plan D1–D5](../plany/zakonczone/odczyt-dashboardu-w-ukrytym-chromium.md), [decyzja 007](../decyzje/007-ukryty-dashboard.md). Badania prototypu A–C pozostają osobnym dowodem.

## Wynik końcowy

**Pełna regresja ostatecznego kodu: 338 testów, OK (1 pominięty), 465,709 s.** Wynik: `data/hidden-implementation-rechecked-tests.log`. Pominięty przypadek dotyczy ograniczenia przyznawania pierwszego planu przez Windows, opisanego niżej. Zestaw obejmuje również nowy deterministyczny test nakładającego się sprzątania i natywne zamykanie strony z kontrolą braku błędów callbacków.

Główna seria: **44/44 poprawne odczyty**; po ostatniej, izolowanej poprawce sprzątania: **8/8** dalszych rzeczywistych odczytów, bez zmiany czytnika. Nie sumować nakładających się zestawów testów automatycznych jako niezależnych przypadków.

## Dowody etapowe

- Inspekcja w Codex: pojedynczy DIV daty w PAR-FILTER-PILL-VARIANT, przyciski kategorii w NOW-BUTTON-BARE; trzy zaznaczone kontrolki „Wybierz wszystko” w NOW-CHECKBOX. Karta inspekcyjna zamknięta bez zmiany ustawień strony.
- Nowe testy celowane: 20/20, w tym rzeczywisty lokalny DOM z opóźnieniem i podmianą checkboxa, stan pośredni/prawdziwy brak zmiany, jawne błędy CDP/ACK, sprzątanie, kontrola originu, dodatnia sesja, nadpisania widoczności i zapis diagnostyki bez syntetycznych sekretów.
- Pierwsza pełna regresja przed poprawką sprzątania: **332 testy, OK (1 pominięty)**, 461,515 s; lokalny wynik `data/hidden-implementation-final-tests.log`. Pominięto pomiar pasywnego fokusu, ponieważ Windows nie przyznał testowemu oknu aplikacji pierwszego planu; nie przedstawiać tego przypadku jako zaliczonego. Pierwsze przebiegi przerwano/przeładowano podczas dopracowywania kodu, w tym po wykryciu i naprawieniu podwójnego przywołania okna podczas ręcznego „Pokaż”.
- Dodatkowy test natywny Windows/Chromium: **1/1**, 4,817 s. Produkcyjny `wait_for_login` i `BrowserRuntime`, lokalne syntetyczne logowanie z kontrolowanym zakończeniem, zmiany ukrywania w aktywnym zakresie odczytu, ręczne „Pokaż” zachowane w następnym odczycie oraz Stop. Sprawdzono widoczność i zakończenie CDP; nie jest to test rzeczywistego wygaśnięcia SSO ani dowód niepominiętego pomiaru pasywnego fokusu.
- Główne pomiary rzeczywiste wykonano w osobnym tymczasowym profilu, z produkcyjnym BrowserRuntime, bez podmiany Playwright ani czytnika. Techniczne dane: `data/hidden-implementation-lab/results.json`.

## Główna seria pomiarowa

Chromium 153.0.8010.12, dwa uruchomienia, 5 cykli widocznych i 5 ukrytych; dodatkowo jeden ukryty po minimalizacji. **44/44 odczyty poprawne, zero ponowień.**

| Sekcja | Mediana widoczny / ukryty | Maksimum widoczny / ukryty |
| --- | --- | --- |
| Zagrożenia | 7,39 / 6,31 s | 7,66 / 6,99 s |
| SLA (komplet do WJRUW) | 16,50 / 16,74 s | 18,58 / 19,42 s |
| Wstrzymane | 4,75 / 5,05 s | 4,97 / 5,16 s |
| Wnioski | 10,89 / 10,66 s | 11,58 / 11,55 s |
| Cały cykl | 37,02 / 37,36 s | 42,61 / 39,67 s |

Każda sekcja i cykl spełniają próg max(15%, 2 s). Dodatkowy cykl po minimalizacji trwał 41,58 s; również zakończył się poprawnie. 885 próbek aktywnego ukrytego odczytu: zero pokazania i zero przejęcia fokusu własnego okna. Próbkowanie nie wyklucza zdarzenia krótszego od interwału.

Ciągłe ukrycie trwało 609,27 s; wszystkie 600 próbek niewidoczne. Mechanizm jest w bezczynności wyłączony. Następny ukryty odczyt czterech sekcji przeszedł bez ponowienia (34,02 s). CPU własnych procesów Chromium: około 5,26 s podczas bezczynności; mediana sumy przyrostów na cykl V/H 43,13/41,61 s. To przybliżony czas procesora, nie procent obciążenia ani pomiar energii; metoda pomija procesy zakończone pomiędzy próbkami.

Pierwotny miesiąc przywrócono, własne okno/profil zamknięto i usunięto. Odciski źródeł przed/po głównej serii są identyczne.

## Poprawka sprzątania po głównej serii

Dodatkowy test zamknięcia rzeczywistej strony wykazał błąd callbacku pomimo wyniku unittest „OK”: zagnieżdżone `stop` mogło wyzerować `self.started` przed obliczeniem czasu końca. Zachowano początkowy wynik i ślad w lokalnym pliku `data/hidden-implementation-native-final-tests.log`.

Naprawa kopiuje czas rozpoczęcia do lokalnej zmiennej, tak jak uchwyt sesji, przed wysłaniem poleceń mogących uruchomić kolejne callbacki. Dodano deterministyczny przypadek ponownego wejścia oraz wymaganie braku wpisów błędów `asyncio` w natywnym teście zamykania strony. **23 testy celowane/natywne po poprawce: OK**, 13,795 s (`data/hidden-implementation-cleanup-regression.log`). Nie zmieniano czytnika ani polityki widoczności.

Na ostatecznych źródłach wykonano **8/8 dodatkowych odczytów ServiceNow** (ukryty+widoczny, wszystkie sekcje; `data/hidden-post-cleanup-lab/results.json`). W 203 próbkach ukrytych: zero pokazania i przejęcia fokusu; pierwotny miesiąc przywrócony, źródła przed/po identyczne, sesja zamknięta. Ponowna pełna regresja ostatecznego kodu zakończona: **338 testów, OK (1 pominięty)** (`data/hidden-implementation-rechecked-tests.log`). Tych późniejszych odczytów nie łączyć z głównym porównaniem wydajności; odbywają się podczas regresji i służą potwierdzeniu poprawności integracji.

## Warunki pomiarów

Pierwsze dwie pary cykli V/H wykonały się równolegle z końcówką pełnych testów. Bramka PowerShell rozpoznała pojedyncze małe „ok” jako końcowe „OK” (dopasowanie bez rozróżnienia wielkości liter). Nie usuwa się tych prób; przy odbiorze porównać je również osobno. Pełna regresja zakończyła się podczas 10-minutowego ukrycia, więc późniejsze pary nie mają tego dodatkowego obciążenia. To badanie jednego komputera i zmiennego serwisu, nie gwarancja identycznego czasu wszystkich odczytów.

## Granice odbioru

Testowane są źródła, nie nowy EXE. Wyniki dotyczą jednego komputera i wskazanej wersji Chromium; eksperymentalne CDP wymaga kontroli po aktualizacji. Rzeczywiste logowanie użytkownika do testowego ServiceNow odbyło się przed odczytami; sterowane wygaśnięcie SSO i błędy odtwarzano syntetycznie. Natywny test produkcyjnego przekazania logowania używał lokalnej strony bez poświadczeń. Jednego pomiaru pasywnego fokusu Windows nie udało się przeprowadzić; nie zastępują go asercje widoczności. Zero, niezmienione dane i ochrona poprzedniego sukcesu mają regresje syntetyczne.

## Decyzja odbiorowa

D1–D5 przyjęte w źródłach. Nie ma podstaw do wycofania nowej polityki: kompletność, niewidoczność i ustalony próg median spełniono; sam wynik unittest nie był wystarczający, dlatego dodatkowy błąd callbacku naprawiono i zweryfikowano oddzielnie. Po ostatecznych odczytach ponownie przywrócono miesiąc, zamknięto własne Chromium i potwierdzono niezmienność źródeł podczas testu. Nowy EXE, zmiana wersji i publikacja pozostają osobnym zleceniem.
