# Plan stabilizacji odczytu dashboardu ServiceNow

> Zakończony plan i historia wdrożenia, nie bieżąca lista zadań. Aktualny status, lokalny build 1.8.0 i pozostałe sprawdzenia: [indeks planów](../README.md). Zapisy o braku EXE dotyczą ówczesnego etapu.

Data analizy: **1 listopada 2026**, Europe/Warsaw. Kod aplikacji: **1.7.17**, z lokalnymi zmianami paginacji. Podstawa pracy: aktualny `AGENTS.md`.

Status: **etapy A–E wdrożone w źródłach; etap F zweryfikowany automatycznie i na stronie, bez EXE**. Aktualny [raport odbioru](../../weryfikacja/odbior-stabilizacji-dashboardu.md) opisuje wyniki i ograniczenia. Poniższy audyt zachowuje historyczne ustalenia sprzed implementacji.

## Cel i zakres

Zapewnić, że aplikacja odczytuje właściwe, gotowe wartości dla właściwej zakładki i ustawień, zachowuje poprzednie poprawne dane przy awarii oraz wyjaśnia w diagnostyce przyczynę i etap problemu. Ograniczyć zbędne oczekiwanie i przeładowania bez osłabiania kontroli poprawności.

Zakres: Dashboard SLA, obliczanie WJRUW, Wstrzymane L1, Wnioski L1, wybór miesiąca, filtry, postęp, stany sekcji i lokalny zapis danych. Widok incydentów zagrożonych i jego powiadomienia są osobnym zadaniem; istniejący plan `stabilizacja-odczytu-zagrozen-sla.md` pozostaje aktualny. Wspólne mechanizmy nawigacji i diagnostyki należy uzgodnić, żeby nie powstały dwa różne rozwiązania tego samego problemu.

Nie wprowadzamy w tym zadaniu równoległych operacji Playwright, nowych kanałów powiadomień, pobierania list z kafelków ani dodatkowych kafelków znalezionych na stronie.

## 1. Co sprawdzono ponownie na rzeczywistej stronie

Analizę wykonano w oddzielnej karcie przeglądarki Codex, z istniejącą sesją użytkownika. Nie sterowano Chromium działającej aplikacji. Nie kopiowano HTML, list osób, danych zgłoszeń ani odpowiedzi sieciowych do repozytorium.

| Obszar | Obserwacja z aktualnej strony | Znaczenie dla projektu |
| --- | --- | --- |
| Nawigacja | Dostępne są zakładki `Dasboard SLA` (literówka po stronie ServiceNow), `Wstrzymane L1`, `Wnioski L1` i osobna zakładka zagrożeń. Po przełączeniu zakładka może być już wybrana, podczas gdy jej karty są jeszcze pustymi kontenerami. | `aria-selected=true` nie oznacza gotowych danych. Identyfikacja zakładki musi być oddzielona od gotowości jej zawartości. |
| Widżety | Karty mają kontenery `.grid-stack-item-content`; liczniki używają `now-score-basic .now-score-value`. W gotowych kartach wymaganych przez aplikację znaleziono pojedyncze wartości i przyciski. | Powiązać nagłówek, liczbę i stan ładowania z jednym widżetem, a nie z całą stroną. Nie zakładać, że metadane przycisku zawsze powstają równocześnie z liczbą. |
| Zmiana okresu | Sprawdzono zmianę październik → wrzesień → październik 2026. Bezpośrednio po zastosowaniu nowej daty stare liczby pozostawały w widżetach, jednocześnie pojawił się tekst `Trwa ładowanie danych wizualizacji`. Następnie liczby zmieniły się i sygnał ładowania zniknął. | Sama obecność liczby lub krótka stabilność wartości nie potwierdza ukończenia nowego odczytu. |
| Wybór daty | Pola `Data rozpoczęcia` i `Data zakończenia` oraz nazwa przycisku wybranego okresu odpowiadają obecnym selektorom. Widoczne były cztery przyciski `Zastosuj`. Przycisk daty był ostatnim z nich, ale nie był potomkiem elementu `role=dialog` w selektorze Playwright. Dla niezmienionego okresu był nieaktywny. | Obecne `.last` działa w zaobserwowanej strukturze, ale zależy od kolejności DOM. Nie zastępować go zgadywanym `dialog.get_by_role(...)`; ta wersja nie znalazła przycisku. Najpierw ustalić rzeczywiste powiązanie popovera. |
| Filtry SLA | Status zgłoszenia, Lokalizacja i Przypisany do: każdy filtr miał jeden widoczny kontener, własne `Wybierz wszystko` i własny przycisk `Zastosuj`. Wszystkie były zaznaczone. | Zachować lokalne powiązanie kategorii i jej kontrolek. Potwierdzać również zastosowanie wyboru, nie tylko stan checkboxa. |
| Wstrzymane L1 | Potwierdzono oba oczekiwane liczniki, filtr Agent L1 i zaznaczenie wszystkich agentów. Są też dodatkowe wykresy. | Oczekiwanie nie może zależeć od ukończenia obcych wykresów. |
| Wnioski L1 | Potwierdzono cztery oczekiwane liczniki i filtr Agent L1 z zaznaczeniem wszystkich. Strona zawiera też dodatkowy licznik dotyczący smartfonów oraz wykresy. | Dodatkowe elementy nie mogą zmieniać mapowania wymaganych kafelków ani blokować ich odczytu. |
| Zakres czasu | Kontrolka okresu występuje w SLA. W dwóch pozostałych zakładkach potwierdzono Agent L1, bez analogicznej kontrolki okresu w odczytywanym układzie. | Nie przedstawiać bez weryfikacji wszystkich sekcji jako danych za wybrany miesiąc. Zdefiniować zakres czasu osobno dla każdej sekcji. |

Po analizie przywrócono zakładkę SLA i okres 1–31 października 2026; potwierdzono wybranie zakładki i właściwą nazwę okresu. Stanów kategorii nie zmieniano. Nie zapisywano konfiguracji dashboardu ani zmian zgłoszeń.

### Granice tej obserwacji

- Odtworzono normalne ładowanie, zmianę miesiąca i przejścia między zakładkami. Nie wymuszano awarii serwera, wygaśnięcia sesji ani błędu zapisu na dysku rzeczywistego konta.
- Ten przebieg nie dowodzi, że każda wersja strony renderuje liczniki dopiero po przewinięciu. Pierwsze puste kontenery i późniejsze wartości potwierdzono, ale nie odizolowano w tym badaniu wpływu przewijania od upływu czasu. Tę zależność trzeba sprawdzić kontrolowanym porównaniem.
- Nie potwierdzono, czy każde ponowne wejście na wcześniej otwartą zakładkę wymusza świeże zapytanie ServiceNow. Nie należy utożsamiać stabilnej liczby z nowym odczytem z serwera.
- To inspekcja strony w Codex; nie jest testem nowego EXE ani obietnicą nieprzerwanej dostępności ServiceNow.

## 2. Ustalenia z kodu

### Dobre mechanizmy, które zachowujemy

- Odczyt po tytułach zamiast po kolejności kafelków; parser pełnych, nieujemnych liczb całkowitych.
- Kontrole Stop i sesji w pętlach; krótkie obserwacje zamiast pojedynczego długiego oczekiwania.
- Możliwość ponowienia sekcji po przywróceniu logowania; brak zastępowania błędu zerem.
- Ponowne użycie otwartego workspace dla kolejnych zakładek, z ograniczonym powrotem do pełnej nawigacji.
- Lokalna kontrola ładowania i jednoznaczności widżetów we Wnioskach L1, w tym obsługa liczby bez gotowych metadanych przycisku.
- Wymuszanie renderowania kart, postęp, identyfikator żądania chroniący UI przed spóźnionymi wynikami oraz atomowa wymiana pliku cache.

### Potwierdzone słabe punkty

1. **Niespójny silnik odczytu.** SLA i Wstrzymane L1 korzystają z globalnego wyszukiwania przycisków i globalnego tekstu ładowania. Wnioski L1 mają osobną, dokładniejszą logikę lokalną. Zmiana struktury strony może więc inaczej wpływać na poszczególne sekcje (`dashboard.py`: `read_dashboard`, `read_held_dashboard`, `_request_tile`).
2. **Słabe potwierdzenie świeżości.** Kontrola nazwy okresu i stabilności liczb przez sekundę nie wiąże wyniku jednoznacznie z ukończeniem zastosowania filtrów. Checkbox sprawdzany po `Zastosuj` nie dowodzi jeszcze zakończenia przeliczenia kafelków. Przy ponownym użyciu zakładki nie ma osobnego potwierdzenia nowego odczytu.
3. **Zależność od kolejności przycisków daty.** Wybór ostatniego widocznego `Zastosuj` może trafić w inny element po rozbudowie strony.
4. **Brak pełnego potwierdzenia kontekstu.** Przed publikacją zestawu nie jest ponownie sprawdzana wspólna tożsamość dashboardu, wybranej zakładki, okresu i kategorii. Użytkownik może w tym czasie zmienić kartę lub ustawienia w kontrolowanym Chromium.
5. **Brak jednego budżetu odczytu.** Kolejne oczekiwania mają własne limity; Wnioski L1 dodatkowo ponawiają cały przebieg. Łączny czas nie wynika z jednego limitu sekcji lub żądania. Przewijane są wszystkie widoczne kontenery kart, także dodatkowe wykresy i filtry.
6. **Nierówne odzyskiwanie po błędach.** Zwykły błąd SLA może zakończyć całe żądanie przed próbą Wstrzymanych i Wniosków. Dwie dalsze sekcje mają częściową niezależność; Wnioski dopuszczają także wynik częściowy. To nie jest jedna jasno określona polityka (`app.py`: `read_dashboard_request`).
7. **Mieszanie wieku danych w cache.** `dashboard_ui.py: result` scala nowe wartości z poprzednim zestawem, jeśli okres nie zmienił się. Każda publikacja nadaje wspólny nowy `read_at` i zapisuje całość. Po sukcesie SLA oraz awarii innej sekcji jej starsze liczby mogą więc znajdować się w pliku z nowym wspólnym znacznikiem czasu. Obecny schemat nie przechowuje osobnej daty i wyniku dla sekcji.
8. **Niepełna diagnostyka przebiegu.** Zdarzenia opisują operacje i błędy, ale brakuje spójnych czasów etapów oraz przyczyn oczekiwania w SLA i Wstrzymanych. Pola `source` i `section` przekazywane do konstruktora `LoginDiagnostics` są zapisywane w zdarzeniu startowym; nie są automatycznie dołączane do każdego następnego zdarzenia. `session`/`trace` pozwalają na korelację, ale brakuje osobnego, konsekwentnego powiązania całego żądania dashboardu i jego sekcji.

### Co mówią dostępne logi

W bieżącym lokalnym pliku diagnostycznym znaleziono zdarzenia odczytu dashboardu i pojedynczy błąd sklasyfikowany jako `Error / unexpected` po około 0,5 s. Bez powiązania z pełnym kontekstem próby nie stanowi on podstawy do wskazania konkretnej przyczyny błędu zwykłego dashboardu; może dotyczyć odczytu zagrożeń opisanego w osobnym planie. Nie kopiowano surowych wpisów do tego dokumentu.

Wnioski o słabych punktach powyżej wynikają z kodu i obserwacji DOM. Nie twierdzimy, że odtworzono obecnie wszystkie możliwe awarie.

## 3. Docelowy przebieg

1. Przyjąć żądanie z niezmiennym identyfikatorem i wybranym okresem SLA. Utworzyć wspólny kontekst diagnostyczny oraz budżet czasu.
2. Potwierdzić sesję i gotowość dokumentu po SSO. Nie wykonywać nawigacji nad formularzem ręcznego logowania.
3. Dla każdej sekcji: potwierdzić dashboard i zakładkę, zastosować właściwe ustawienia, potwierdzić ich przyjęcie i przygotować potrzebne widżety.
4. Obserwować wyłącznie wymagane widżety. Osobno rozróżniać: brak, niejednoznaczność, ładowanie, nieprawidłowa wartość, gotowa wartość i prawidłowe zero.
5. Potwierdzić zakończenie aktualizacji dla aktualnego kontekstu. Ustalić na prawdziwej stronie, jaki sygnał jest dostępny także wtedy, gdy nowa liczba jest równa poprzedniej. Nie wymagać zmiany liczby jako warunku świeżości.
6. Zebrać i zweryfikować kompletny zestaw sekcji; przed jego przyjęciem ponownie sprawdzić kontekst. Zmiana zakładki lub filtrów unieważnia próbę, zamiast przypisywać liczby do złego miesiąca.
7. Opublikować wynik sekcji z własnym czasem ostatniego sukcesu. WJRUW obliczyć wyłącznie z kompletnego zestawu SLA pochodzącego z tej samej zaakceptowanej próby.
8. Przy awarii zachować ostatni poprawny wynik danej sekcji z jego oryginalnym czasem. Pokazać błąd lub nieaktualność; nie zerować wartości i nie nadawać im nowej daty sukcesu.
9. Zamknąć kontekst, odłączyć obserwatorów i przywrócić istniejącą politykę widoczności Chromium.

## 4. Kolejność wdrożenia

### Etap A — kontekst, diagnostyka i pomiary

- [x] Zdefiniować kontrakt trzech sekcji: oczekiwana zakładka, wymagane kafelki, filtry, zakres czasu i warunek kompletności.
- [x] Zapewnić identyfikator uruchomienia aplikacji i żądania dashboardu oraz powiązane identyfikatory sekcji i prób. Wykorzystać obecną korelację, bez tworzenia odrębnego systemu logowania.
- [x] Każde zdarzenie wzbogacić o bezpieczny alias sekcji, etap, próbę i czas. Dodać przyczyny oczekiwania i odzyskiwania, stan wymaganych widżetów, zakończenie i wynik zapisu cache.
- [x] Rozróżniać m.in. zmianę dokumentu, złą zakładkę, niezatwierdzony filtr, ładowanie widżetu, brak kafelka, niejednoznaczność, utratę sesji, zamknięcie przeglądarki i Stop.
- [x] Wykonać krótką serię pomiarów: pierwsze wejście i ponowne sprawdzenie, ten sam i inny miesiąc. Mierzyć etapy, nie tylko całkowity czas.

**Warunek zakończenia:** z logów wiadomo, na co czekano i gdzie zużyto czas; w testach awaria diagnostyki nie przerywa odczytu, a syntetyczne sekrety nie trafiają do zapisu.

### Etap B — jeden obserwator widżetów dla trzech sekcji

- [x] Uogólnić mechanizm lokalny używany we Wnioskach na SLA i Wstrzymane. W razie potrzeby poprawić także globalny fallback Wniosków; nie przenosić go bezkrytycznie do wspólnej logiki.
- [x] Wiązać oczekiwany tytuł z pojedynczym widocznym widżetem, liczbą i jego lokalnym ładowaniem. Ignorować ukryte kopie oraz obce wykresy.
- [x] Uzgodnić normalizację tytułów i spacji, ale odrzucać niejednoznaczne dopasowania. Nie wybierać pierwszego pasującego elementu.
- [x] Kontrolować liczbę, kompletność i spójność całego zestawu sekcji. Stałe sekundy stabilności stosować jako dodatkowe zabezpieczenie, a nie jedyny dowód zakończenia aktualizacji.
- [x] Przygotować potrzebne karty także wtedy, gdy na początku nie mają nagłówków; ograniczyć przechodzenie po dodatkowych kartach po znalezieniu wymaganych.

**Warunek zakończenia:** dodatkowy wykres, inny układ, późny przycisk, stare liczby podczas ładowania i prawidłowe zero mają taki sam, przetestowany sposób obsługi w każdej sekcji.

### Etap C — potwierdzanie nawigacji, dat i filtrów

- [x] Potwierdzać właściwy dashboard i wybraną zakładkę przed odczytem oraz ponownie przed przyjęciem wyniku.
- [x] Zastąpić zależność od `.last` zweryfikowanym powiązaniem popovera daty i jego przycisku. Jeżeli aktualny DOM nie udostępnia trwałego powiązania, jawnie odrzucać niejednoznaczność zamiast zgadywać.
- [x] Zweryfikować stan dat po wpisaniu, zamknięciu popovera i przed publikacją. Zachować poprawną ścieżkę nieaktywnego `Zastosuj` dla niezmienionego okresu.
- [x] Rozróżnić zaznaczenie opcji kategorii od skutecznego zastosowania jej do widżetów. Potwierdzić `checked` bez `indeterminate` i dostępny na stronie sygnał przyjęcia filtra.
- [x] Ustalić, czy powrót do zakładki daje świeże dane. Jeżeli nie — wykorzystać zaobserwowaną kontrolkę odświeżenia bieżącej karty i potwierdzić jej wynik. Nie przeładowywać całej strony bez potrzeby.
- [x] Wykrywać ingerencję użytkownika podczas odczytu i bezpiecznie odrzucać niespójny wynik.

**Warunek zakończenia:** liczby nie zostają przypisane do innej zakładki, zakresu dat lub niezastosowanego wyboru.

### Etap D — ograniczone odzyskiwanie i budżet czasu

- [x] Zdefiniować jeden budżet sekcji obejmujący przygotowanie i ponowienie; wartość dobrać po pomiarach. Osobno zdefiniować zachowanie przy oczekiwaniu na ręczne logowanie, aby nie zużywało niejawnie budżetu aktywnego odczytu.
- [x] Współdzielić pozostały czas z operacjami podrzędnymi. Zachować krótkie, przerywalne obserwacje i obsługę Stop.
- [x] Dopuścić najwyżej jedno kontrolowane odzyskanie po przejściowym błędzie sekcji; nie mnożyć niezależnych ponowień na wielu poziomach.
- [x] Po niepewnym kliknięciu najpierw sprawdzić stan, zamiast klikać ponownie. Po odzyskaniu dokumentu odtworzyć cały kontekst sekcji i odrzucić jej poprzedni bufor.
- [x] Oddzielić zwykłą awarię sekcji od utraty sesji, zamknięcia Chromium i anulowania. Błąd SLA nie powinien automatycznie odbierać możliwości sprawdzenia pozostałych sekcji, jeśli sesja i przeglądarka nadal działają.

**Warunek zakończenia:** błąd jest obsłużony w ograniczonym czasie, nie ma pętli nawigacji ani wielokrotnego dostarczania tego samego kliknięcia, a pozostałe sekcje mogą zakończyć się niezależnie.

### Etap E — wyniki sekcji, cache i komunikaty

- [x] Wprowadzić wersjonowany zapis z osobnym ostatnim poprawnym zestawem, czasem sukcesu, kontekstem i informacją o kompletności każdej sekcji.
- [x] Dla nowego odczytu przyjmować kompletny zestaw sekcji atomowo. Nie scalać kilku kafelków z nowej próby z pozostałymi kafelkami tej samej sekcji ze starej próby. Częściowy odczyt może służyć diagnostyce, lecz nie udawać pełnego sukcesu.
- [x] Zachować poprzednie poprawne liczby przy błędzie, oznaczając je jako stare. Pokazać osobno czas próby i czas ostatniego sukcesu, jeśli jest to potrzebne do zrozumienia stanu.
- [x] Przenieść stary cache do nowego schematu jako dane o niepotwierdzonej aktualności; nie wymyślać historycznych czasów dla sekcji, których dawny format nie zawiera.
- [x] Zachować atomowy zapis, kontrolowane ponowienia błędu dostępu oraz możliwość pracy bez zapisu. Przetestować uszkodzony plik i brak uprawnień.
- [x] WJRUW liczyć z jednego kompletnego odczytu SLA; dla zerowego mianownika zachować `Brak danych`. Walidacje zależności liczbowych uzgodnić z definicjami metryk, zamiast arbitralnie uznawać różnice za błąd.
- [x] Ujednolicić stany i postęp. Anulowanie nie jest błędem odczytu, a 100% nie oznacza częściowego sukcesu. Spóźnione zdarzenia starego żądania nie mogą zmienić nowego widoku.
- [x] W opisie okresu odróżnić miesięczne SLA od bieżących Wstrzymanych i Wniosków, zgodnie z potwierdzoną semantyką strony.

**Warunek zakończenia:** świeża sekcja nie odmładza starszych danych innej sekcji, a cache i UI pozwalają jednoznacznie ocenić aktualność każdej z nich.

### Etap F — pełna weryfikacja i dopiero potem EXE

- [x] Rozbudować minimalne syntetyczne strony zgodnie z zaobserwowanym DOM i przeprowadzić poniższą macierz przypadków.
- [x] Powtórzyć serię na prawdziwej stronie: pierwszy odczyt, ponowne sprawdzenie bez zmiany miesiąca, zmiana miesiąca, przejścia między zakładkami. Przywrócić ustawienia po testach.
- [x] Porównać wyniki i czasy etapów z pomiarem początkowym; nie podawać obietnicy stałego czasu niezależnego od ServiceNow i sieci.
- [x] Uruchomić pełny zestaw testów źródeł i oddzielić go od inspekcji strony.
- [ ] Zbudować i sprawdzić EXE — odłożone zgodnie z poleceniem użytkownika; nie jest warunkiem zakończenia obecnego zadania.

## 5. Macierz dodatkowych testów

| Grupa | Przypadki i oczekiwane zachowanie |
| --- | --- |
| Tożsamość | Inny dashboard, inna zakładka, wybrana zakładka z pustą zawartością, podmiana dokumentu i Shadow DOM, dodatkowy lub ukryty widżet. Brak przyjęcia wartości z obcego kontekstu. |
| Gotowość | Stara liczba i lokalny loader, loader opóźniony po `Zastosuj`, niezmieniona liczba po poprawnym odświeżeniu, brak loadera przy szybkim sukcesie, opóźnione metadane przycisku, niezwiązany wolny wykres. |
| Wartości | Zero, odstępy tysięczne, placeholder, tekst błędu zamiast liczby, dwa identyczne tytuły, dwa liczniki w jednej karcie, brak jednego wymaganego kafelka. Bez zgadywania i bez zamiany błędu na zero. |
| Leniwe renderowanie | Pierwsze wejście i powrót, karty poza widocznym obszarem, różne wysokości okna, nagłówki powstające dopiero po przewinięciu, dodatkowe karty przed lub między wymaganymi. |
| Daty i kategorie | Ten sam okres, inny miesiąc, granica roku i luty przestępny, opóźniona edycja, overlay, wiele przycisków `Zastosuj`, odroczone zastosowanie kategorii, stan mieszany, zmiana użytkownika w połowie odczytu. |
| Odzyskiwanie | Późne przekierowanie po SSO, wygaśnięcie sesji w każdym etapie, błąd nawigacji, niepewne dostarczenie kliknięcia, zamknięcie karty/Chromium, Stop podczas oczekiwania i ponowienia, wyczerpanie budżetu. |
| Wynik i cache | Sukces SLA z błędem innej sekcji, częściowe Wnioski bez odmładzania starych kafelków, inny miesiąc niż poprzedni, restart, stary/uszkodzony schemat, odmowa zapisu i spóźniony wynik poprzedniego żądania. |
| WJRUW | Oryginalne wagi 50/10/5/2/1, brak składnika, nieprawidłowy typ, zerowy mianownik, zachowanie po awarii lub zmianie okresu. Bez mieszania prób. |
| Diagnostyka | Pełny przebieg sukcesu i błędu z korelacją i czasami, przejściowy problem zakończony sukcesem, Stop, nieudany zapis, niedostępny logger, rotacja oraz syntetyczne loginy/hasła/tokeny/treści, których nie może być w logach. |

## 6. Zasady diagnostyki i ochrony danych

Korzystać z istniejącej rotowanej diagnostyki oraz list dopuszczonych pól. Rejestrować stałe kody zdarzeń, np. rozpoczęcie żądania, zmianę etapu, potwierdzenie kontekstu, zmianę stanu widżetu, powód odzyskiwania, zakończenie sekcji i zapis cache. Nie zapisywać każdego odpytywania; logować zmiany stanu i ograniczone podsumowania oczekiwania.

Kontekst: identyfikator uruchomienia/żądania/sekcji/próby, alias celu, etap, powód, liczba oczekiwanych/gotowych kafelków, czas etapu i wynik. Zakres miesiąca może być polem liczbowym, bez pełnego URL. Nie są potrzebne same wartości biznesowe liczników, nazwiska agentów ani treści zgłoszeń.

Nie zapisywać surowych wyjątków, pełnych adresów SSO, loginów, haseł, tokenów, cookies, HTML ani odpowiedzi sieciowych. Bezpieczny fallback diagnostyki nie może przerywać odczytu ani ujawniać pierwotnej treści błędu. Logi mają być dopisywane i rotowane między uruchomieniami; nie należą do paczki wydania.

## 7. Weryfikacja bieżącego stanu

- [x] Ponownie przeczytano kod odczytu, sterowania, postępu, cache i diagnostyki oraz istniejące testy.
- [x] Zweryfikowano aktualne trzy zakładki na rzeczywistej stronie, kontrolkę daty, filtry i lokalne stany widżetów.
- [x] Dodatkowy przebieg istniejących testów dashboardu: **41 testów, wszystkie zaliczone**, 58,182 s. Moduły: `test_dashboard`, `test_dashboard_navigation`, `test_dashboard_controls`, `test_dashboard_lazy_widgets`, `test_requests_dashboard`, `test_dashboard_progress`. Wynik zapisano lokalnie w `data/dashboard-audit-tests.log`. To potwierdzenie bieżących testów syntetycznych i UI; nie dowodzi obsługi wszystkich luk opisanych w planie.
- [x] Wdrożenie etapów A–E i weryfikacja źródeł etapu F — wykonane na wyraźne polecenie użytkownika. Nowy EXE pozostaje osobnym zadaniem.

Rekomendacja: wdrażać etapami z testem po każdym etapie. Najpierw ustalić kontrakt i diagnostykę, potem ujednolicić rzeczywisty odczyt oraz potwierdzanie kontekstu. Zmianę cache wykonać osobno, z migracją i testami zachowania starych danych.

## 8. Wynik realizacji

Wspólny czytnik i budżet, potwierdzenie kontekstu, niezależne wyniki sekcji, migracja cache i diagnostyka są w źródłach. Seria rzeczywista wykryła dodatkowe wyścigi podmiany DOM, usunięte i objęte regresją. Czasów nie porównujemy jako benchmarku wydajności: wcześniejsze pomiary Codex i pełnego silnika mają różny zakres. Szczegóły: [raport odbioru](../../weryfikacja/odbior-stabilizacji-dashboardu.md).
