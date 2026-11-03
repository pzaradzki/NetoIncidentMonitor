# Plan: lista zagrożonych incydentów i powiadomienia

3 listopada 2026. **Zakres jednej strony wdrożony i odebrany na rzeczywistym ServiceNow.** Dowody obserwacji ServiceNow zawiera [analiza](../../archiwum/analizy/zagrozone-lista-powiadomienia-analiza.md).

## Cel i niezmienniki

Pod sześcioma kafelkami dwie zakładki: „Bieżące zagrożenia” i „Historia zagrożeń”, po jednym wierszu na INC. Oba zbiory zachowywane między uruchomieniami. Odczyt listy zbiorczej na tej samej zakładce, także przy ukrytym Chromium. Powiadomienie przez globalnie włączone kanały przy pierwszym wykryciu i powrocie po potwierdzonym zniknięciu; bez cyklicznych przypomnień. Pierwsza próba po logowaniu przed dashboardem; kolejne według istniejącego harmonogramu.

Błąd ≠ zero ≠ pełny odczyt. Żaden częściowy wynik nie usuwa obecności ani nie wywołuje fałszywego ponownego pojawienia. Dane techniczne SLA są deduplikowane dopiero po sprawdzeniu kompletności. Ukrywanie i ręczna obsługa logowania korzystają z istniejących polityk; brak alternatywnego mechanizmu okna.

## Etapy i odbiór

| Etap | Praca | Warunek zakończenia |
| --- | --- | --- |
| A. Domknięcie analizy strony | Niepusta lista zbiorcza; zakres względem sześciu kafelków; stabilne ID, link, wartości; większa lista i pager/wirtualizacja; widoczne/ukryte świeże odczyty | Udokumentowane źródło, kompletność i zachowanie na rzeczywistej stronie. Sprawdzono pusty wynik oraz niepustą pojedynczą stronę P3 w natywnym Chromium, po 3 próby widoczne i ukryte. Porównanie P3 potwierdziło identyczny zbiór 3 SLA. Otwarte pozostają odbiór wielostronicowy i zakres pozostałych kategorii |
| B. Kontrakt i model | Rekord SLA, agregat INC, reprezentatywna para czas/procent, kategorie, snapshot/read ID, pochodzenie i aktualność, obecność/generacja zdarzenia | Uzgodnione otwarte wybory poniżej; minimalne syntetyczne fixture oparte na A; zapis decyzji przekrojowej |
| C. Czytnik | Adapter `NOW-LIST` do wspólnego przebiegu sekcji; lokalny loading/empty/error, pager i pełny zbiór; jeden budżet i właściciel ponowień; istniejący renderer | Brak globalnych selektorów tabel; niepewne „Dalej” bez ponownego kliknięcia; Stop/sesja/przebudowa DOM obsłużone; brak utrwalania częściowego wyniku |
| D. Stan i UI | Atomowe zatwierdzanie obecności, historii i nowych zdarzeń; zakładki bieżące/historia, sortowanie nagłówkami, spójne wartości, kategorie i poprawny dwuklik; trwały zapis z walidacją | Zniknięcie usuwa INC wyłącznie z bieżących; historia i obecność przetrwają restart. Wybrany porządek pozostaje po aktualizacji. Reappearance i błąd zapisu nie tworzą fałszywych alertów; UI pozostaje responsywne |
| E. Powiadomienia | Przyjęcie i wynik transportu z job/event ID; wybrane kanały globalne; grupowanie nowych INC; bounded delivery i stan wyniku | Mockowane transporty sprawdzają kolejkę, częściowe wysyłki, niepewny timeout i restart. Brak rzeczywistych webhooków w testach; brak minutowych przypomnień |
| F. Odbiór źródeł | Regresja, realne próby z rekordami, ukrycie, ponowienia/sesja, harmonogram i diagnostyka; aktualizacja dokumentacji | Kryteria niżej spełnione, jawnie podane pozostałe ograniczenia; EXE/ZIP/release poza tym planem |

Etapy realizować kolejno; nie żądać zgody na każdą rutynową czynność po zleceniu całości. Jeśli A ujawni niezgodny zakres listy, wrócić do projektu źródła, zamiast milcząco otwierać sześć list lub zmieniać filtr użytkownika.

## Model i zapis — projekt

**Przygotowanie niezależne od rekordów, 2 listopada:** [32 scenariusze syntetyczne](../../archiwum/dane-testowe/zagrozenia-sla/README.md), 60 kroków zaliczonych w izolowanym modelu projektowym; [zakres i ograniczenia](../../archiwum/scenariusze-projektowe-zagrozen-sla.md). To częściowe przygotowanie B, nie implementacja ani zakończenie A. Model nie zakłada selektorów, formatu wierszy ani rzeczywistych metadanych pagera. Przy braku terminu choć jednej umowy model konserwatywnie nie wybiera reprezentatywnej pary; sposób prezentacji braków należy doprecyzować po obserwacji danych.

- Snapshot zawiera komplet rekordów SLA z konkretnego przebiegu i jego wynik. Rekord: stabilne ID SLA, ID/numer incydentu, sprawdzony link, cel SLA i priorytet, termin naruszenia, surowe wybrane wartości do wyświetlenia oraz zweryfikowane wartości liczbowe, gdy rzeczywisty DOM je udostępnia. Nie pobierać opisów i danych osób tylko dlatego, że są w tabeli.
- Incydent grupuje wszystkie własne SLA/kategorie. Przyjęty wybór projektowy po pozostawieniu decyzji agentowi: SLA o najbliższym terminie naruszenia, także gdy jest już po terminie; czas i procent zawsze z tej samej umowy. Remis rozstrzygać stabilnie ID SLA, aby wiersz nie zmieniał się przypadkowo. Brak poprawnego terminu oznaczyć jako brak danych, nie zgadywać reprezentanta z procentu. Nie używać procentu ani tekstu czasu roboczego do odtwarzania niepotwierdzonego filtra kafelków.
- Bieżące zagrożenia przedstawiają ostatni kompletny potwierdzony zestaw, po restarcie oznaczony jako zapisany/nieaktualny do nowego odczytu. Historia jest osobnym zbiorem wszystkich dotąd wykrytych INC: jedno ID incydentu, pierwsze i ostatnie wykrycie, liczba pojawień oraz ostatnie poprawnie odczytane dane. Zniknięcie nie usuwa historii; powrót aktualizuje istniejący wiersz i zwiększa liczbę pojawień. Czas/procent w historii to zapis ostatniego odczytu, nie bieżący odliczany stan SLA. Dwuklik działa w obu zakładkach przez sprawdzony link. Wykorzystać wzorce istniejącej historii filtrów i porcjowanego ładowania UI, nie mieszać ich zbiorów.
- Osobny zakres obecności zagrożeń; nie zmieniać `FilterState.notification_arrivals` zwykłych filtrów. Stan na dysku w lokalnych danych aplikacji; schemat/typy/rozmiar walidowane, atomowy zapis. Błąd zapisu pozostawia poprzedni stan obecności i zgłasza problem, bez udawania trwałego sukcesu.
- Zalecane: jeden atomowo zapisany stan zawierający nową obecność i zamiary wysyłki. Kanały snapshotowane według globalnej konfiguracji w momencie zdarzenia; włączenie kanału później nie zalewa starszymi alertami. Nie zapisywać webhooków ani poświadczeń w tym stanie. Zmiana miejsca docelowego nie powinna po cichu przekierować dawniej zakolejkowanego alertu; użyć wersji konfiguracji niezależnej od sekretów.
- Rozszerzyć istniejące transporty o ID i potwierdzenie przyjęcia. Kolejka pełna nie oznacza sukcesu. Po częściowej wysyłce nie powtarzać potwierdzonych kanałów/części. Wysyłka rozpoczęta bez końcowego potwierdzenia po awarii ma wynik niepewny — nie da się zapewnić exactly-once przez webhook. Nie dodawać automatycznych powtórzeń niepewnych POST ani własnych cyklicznych przypomnień.
- Błąd odczytu nie zmienia membership. Pełny snapshot pusty potwierdza zniknięcie. Zmiana reprezentatywnego SLA/kategorii już obecnego INC aktualizuje wiersz, bez nowego zdarzenia wykrycia.

## Sortowanie list — uzgodnione

- **Bieżące zagrożenia domyślnie:** rosnąco według rzeczywistego terminu naruszenia reprezentatywnego SLA — najpierw najwcześniejsze przekroczenia, następnie najbliższe przyszłe terminy. Nie sortować domyślnie według tekstu pozostałego czasu roboczego; to inna wielkość niż termin naruszenia.
- **Historia zagrożeń domyślnie:** ostatnie wykrycie malejąco, od najnowszych.
- Kliknięcie nagłówka wybiera kolumnę, kolejne przełącza rosnąco/malejąco; strzałka wskazuje aktywną kolumnę i kierunek. Nagłówek dostępny również z klawiatury. Domyślny porządek bieżących ma osobne oznaczenie „Według terminu SLA”, ponieważ termin nie jest tym samym co widoczna kolumna pozostałego czasu; nie sugerować strzałką innego klucza.
- Procenty, licznik pojawień i numer INC porządkować liczbowo (numer po części numerycznej), daty chronologicznie, a ręcznie wybraną kolumnę pozostałego czasu według zweryfikowanej wartości czasu roboczego, z uwzględnieniem znaku. Nie porównywać sformatowanych napisów. Kategorie porządkować stabilnie według P1–P5/Podjęcie, obecność według stałej kolejności stanów.
- Brakujące/niepoprawne wartości zawsze na końcu, w obu kierunkach. Remisy rozstrzygać stabilnie numerem i ID incydentu; aktualizacja nie powinna losowo przestawiać równorzędnych wierszy.
- Pamiętać kolumnę i kierunek osobno dla każdej zakładki podczas przełączania widoków i kolejnych aktualizacji. Sortować cały potwierdzony zbiór przed porcjowanym renderowaniem, nie każdą porcję osobno; zachowywać zaznaczenie po ID. To ustawienie widoku, bez wpływu na odczyt ServiceNow, obecność i powiadomienia. Zachowanie preferencji sortowania po restarcie nie jest częścią obecnego uzgodnienia.

## Testy projektowane

**DOM i kompletność:** zero vs placeholder vs błąd; opóźnione wiersze; Light/Shadow DOM; zmiana kolejności lub brak kolumny; dwa widżety; odłączona tabela; przeładowanie po kliknięciu; 1/25/26 i więcej rekordów; powtarzający się SLA; wiele SLA tego samego INC; zmiana zakresu/total; niepewne „Dalej”; Stop i wygaśnięcie sesji na kolejnej stronie. Większa niż oczekiwana lista musi zakończyć się jawnym wynikiem, nie cichym limitem.

**Wartości i bezpieczeństwo:** polskie jednostki i odstępy, ujemny/zerowy czas, dni/godziny/minuty, przecinek/kropka w procencie i ponad 100%, niedostępna wartość; nie wyliczać procentu z paska. Obcy host, SSO, niewłaściwa tabela i niepoprawne ID w linku są odrzucane. Otwieranie tylko odnośnika powiązanego z danym INC; bez edycji rekordu.

**Przejścia stanu:** pierwszy poprawny wynik dodatni → jeden alert; kolejny identyczny → bez alertu; zmiana czasu/kategorii → bez alertu; pełne zero → zniknięcie; powrót → nowy alert; błąd/partial pomiędzy odczytami → bez zniknięcia; restart nie powiadamia ponownie o zachowanej obecności; uszkodzony stan i błąd atomowego zapisu. Historia zachowuje INC po zniknięciu i restarcie; powrót nie duplikuje wiersza, lecz zwiększa liczbę pojawień. Remis terminów SLA nie zmienia losowo pary czas/procent, a brak terminu nie tworzy zmyślonej wartości. Sprawdzić współpracę symulacji Ctrl+Shift+F12: oznaczyć jako syntetyczną, domyślnie bez rzeczywistych wysyłek i bez zanieczyszczania trwałej obecności ani historii.

**Sortowanie UI:** oba porządki domyślne, przełączanie kierunku nagłówkiem i klawiaturą, poprawna strzałka/oznaczenie klucza; liczby 9/10/100, procenty ponad 100%, ujemny czas, daty na granicy miesiąca/roku, remisy i braki zawsze na końcu. Nowy snapshot i przełączenie zakładki zachowują własny porządek oraz zaznaczenie; porcje renderowania tworzą jeden globalnie uporządkowany zbiór. Sortowanie nie generuje nowych powiadomień ani nie zmienia historii wykryć.

**Transport i harmonogram:** wszystkie kombinacje globalnych kanałów, brak konfiguracji, pełna kolejka, błąd jednego kanału i fragmentu, timeout po potencjalnym przyjęciu, zamknięcie aplikacji z zadaniem, zmiana konfiguracji. Zagrożenia wtrącane między filtrami, brak duplikatów z ręcznego/scheduled check, zablokowane przyciski podczas pracy, po Stop brak spóźnionego zatwierdzenia. Budżet obejmuje szczegóły; brak zagnieżdżonych ponowień.

**Rzeczywisty odbiór:** niepuste i puste wyniki przy widocznym/ukrytym oknie, reload, przewijanie, co najmniej jedna wielostronicowa próba jeśli źródło ją udostępni. Porównywać zgodność w ramach możliwie bliskich odczytów, uwzględnić zmiany serwera. Rejestrować czasy etapów i próbki natywnej widoczności/fokusu. Obecne 3+3 próby pustego wyniku nie zastępują tego odbioru.

## Diagnostyka

Wspólny run/trace/read/attempt + niezależne losowe snapshot/event/job ID. Start/koniec i czasy: wejście na zakładkę, gotowość listy, strona/range/total, wiersze SLA i unikalne INC, walidacja/agregacja, commit, przyjęcie do kolejki i wynik kanału. Stałe kategorie przyczyn: kontekst, kolumna, dane, zakres, sesja, budżet, anulowanie, zapis, kolejka, transport i niepewny wynik. Zachować pierwszą przyczynę oraz wynik odzyskania; bez logowania każdego poll.

Logować liczniki i etapy, **nie** numery/ID zgłoszeń, wartości pól, pełne adresy, webhooki, dane formularzy lub treści wiadomości. Syntetyczne sekrety muszą być nieobecne także po błędzie/rotacji. Awaria diagnostyki nie przerywa czytnika ani nie maskuje pierwotnego błędu. Przy odbiorze sprawdzić, że allowlisty rzeczywiście przepuszczają potrzebne pola.

Dla zmiany sortowania wystarczy bezpieczne zdarzenie UI: alias widoku/kolumny, kierunek i liczba wierszy, bez wartości komórek; nie logować każdego porównania ani porcji.

## Ustalenia po odpowiedzi użytkownika — 2 listopada 2026

1. Użytkownik pozostawił wybór SLA agentowi. Przyjmujemy najbliższy termin naruszenia; czas/procent z tej samej umowy, wszystkie kategorie pokazane.
2. Użytkownik zatwierdził pamięć między uruchomieniami i dodał wymóg bieżącej listy oraz historii wszystkich wykrytych incydentów. Te same obecne INC bez nowego alertu aż do potwierdzonego zniknięcia i powrotu. INC, który zniknął i wrócił wyłącznie podczas wyłączonej aplikacji, jest niewykrywalny w samych snapshotach.
3. Proponowana treść pozostaje do zatwierdzenia: tytuł „Incydenty zagrożone SLA · N”, tylko nowe pojawienia w wiadomości zbiorczej, numer + kategorie + pozostały czas + procent i odnośnik do zakładki; limity kanałów i Windows respektowane. Bez całej stale obecnej listy w każdym powiadomieniu.

## Przejściowa obsługa paginacji

- [x] Potwierdzono niepustą pojedynczą stronę w ukrytym Chromium oraz obecność SLA rozwiązania i podjęcia w zbiorczej tabeli ServiceNow.
- [x] Uznać niepusty wynik za kompletny, gdy zakres i przycisk następnej strony potwierdzają jedną stronę, a zweryfikowane wiersze SLA odpowiadają licznikom według kategorii. Potwierdzoną pustkę rozpoznawać osobno.
- [x] Przy aktywnej następnej stronie, niespójnym zakresie lub niepewnej kompletności zgłaszać niepełny odczyt szczegółów. Zachować poprzednią listę i historię oraz nie generować zdarzeń pojawienia ani zniknięcia. Odczyt sześciu liczników ma własny wynik.
- [x] Sprawdzono odrzucenie niepełnej strony na syntetycznym widżecie.
Wdrożenie i odbiór przejścia dalej przeniesiono do [osobnego zadania paginacji](../paginacja-listy-zagrozen-sla.md). Odbiór tego planu obejmuje pojedynczą stronę.

- [x] Zapis bieżącej listy, historii i alertów w jednej transakcji SQLite. Wspólna kolejka respektuje globalne kanały i rewizję konfiguracji.
- [x] Dwie zakładki, sortowanie nagłówkami lub Alt+numer kolumny, porcjowanie wierszy i otwieranie INC dwuklikiem.
- [x] Próby syntetyczne obejmują Shadow DOM pagera, rozbieżność liczników, wiele SLA jednego INC, restart, ponowne pojawienie i przerwany zapis.
- [x] Odbiór zintegrowanego odczytu na rzeczywistym ServiceNow w ukrytym Chromium. Wcześniejsze pomiary dotyczyły skryptu badawczego.
- [x] Wynik wysyłki zapisuje identyfikator żądania, identyfikator zadania, kanał i liczbę przyjętych części.
- [x] Sprawdzono w Tk wyrenderowanie 1200 syntetycznych wpisów historii, czterech bieżących zgłoszeń i domyślne sortowanie historii.
- [x] Domknąć odbiór diagnostyki w tym samym przebiegu co zintegrowany odczyt pojedynczej strony w ukrytym Chromium.

3 listopada 2026. Zintegrowany czytnik aplikacji potwierdził pustą listę i sześć zer w rzeczywistym ServiceNow. W 39 próbkach okno Chromium było niewidoczne i nie miało fokusu. Zapisana historia oraz kolejka pozostały puste. Przechwycono zdarzenie `threatened_details_complete` z liczbą rekordów 0. Zapis pliku diagnostycznego w tym przebiegu zgłosił problem. Do odbioru pozostają rzeczywisty niepusty wynik i potwierdzenie zapisu diagnostyki z tego przebiegu.

### Zamknięcie odbioru pojedynczej strony

3 listopada 2026 około 19:48. Zintegrowana ścieżka aplikacji ze źródeł 1.8.1 wykonała dwa odczyty rzeczywistego ServiceNow w osobnym Chromium z pakietu EXE. Za każdym razem odczytano dwa zagrożenia, zgodne z licznikiem P2. Pozostałe liczniki wyniosły zero. W 77 próbkach okno pozostawało ukryte i bez fokusu.

Pierwszy odczyt zapisał dwa wpisy historii i jedno zbiorcze zadanie w testowej kolejce SQLite. Drugi zachował oba wpisy bez nowego zadania. Sonda zastąpiła przygotowanie treści i uruchomienie nadawcy atrapami. Odbiór obejmował transakcję i eliminację duplikatu, bez wysyłki do kanałów.

Plik JSONL zawiera dwa zdarzenia `threatened_details_complete` o odrębnych identyfikatorach odczytu w ramach jednego uruchomienia. Oba mają `records_read=2`, a `row_count` wynosi kolejno 2 i 0. Odczyty trwały 7,3 s i 5,4 s. Paginacja pozostaje osobnym planem.
