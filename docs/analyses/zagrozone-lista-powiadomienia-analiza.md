# Lista zagrożonych incydentów i powiadomienia — analiza

2 listopada 2026. **Analiza wznowiona; projekt bez wdrożenia.** Plan: [etapy wdrożenia](../plans/lista-zagrozonych-i-powiadomienia.md). Kod aplikacji, EXE i ZIP pozostają bez zmian.

## Wymagania

- Pod kafelkami dwie zakładki: bieżące zagrożenia i historia wszystkich wykrytych INC, zachowywane między uruchomieniami. Jeden wiersz na INC w każdym widoku; numer, pozostały czas roboczy i procent czasu roboczego, dwuklik otwiera incydent w domyślnej przeglądarce. Zniknięcie nie usuwa historii, powrót aktualizuje ten sam wiersz.
- Powiadomienie przy pierwszym potwierdzonym wykryciu i powrocie po potwierdzonym zniknięciu. **Bez cyklicznych przypomnień.** Błąd, niepełny wynik i brak dostępu nie oznaczają zniknięcia.
- Globalne kanały Windows/Teams/Google Chat; odnośnik do zakładki zagrożeń w wiadomości. Bez rzeczywistych wysyłek w analizie.
- Preferowane źródło: lista zbiorcza na zakładce zagrożeń, zamiast sześciu wejść przez kafelki. Odczyt przy ukrytym Chromium, gdy użytkownik wybrał ukrywanie.

## Potwierdzone na rzeczywistej stronie

W karcie audytu Codex potwierdzono sześć kafelków i listę „Zagrożone i po terminie – posortowane wg czasu do przekroczenia SLA”. Lista jest komponentem `SN-PAR-ANALYTICS-LIST-BASE` z `NOW-LIST` i `table.now-list-table[role="grid"]`. Kolumny mają czytelne `aria-label`: Zadanie, Priorytet, Krótki opis, Stan, Przypisane do, Definicja umowy SLA, Cel, Czas naruszenia, Pozostały czas roboczy, Procent czasu roboczego.

To **inny adapter niż klasyczna lista**. W jednym komponencie występują Light DOM i Shadow DOM: tabela jest w zagnieżdżonych komponentach, komunikat pustego wyniku w innej gałęzi. Samo przejście przez `host.shadowRoot` pomija część treści. Tabela może nadal istnieć jako szkielet, gdy widoczny jest komunikat „Brak dostępnych danych.”. Trzeba odróżnić istnienie tabeli od gotowego wyniku.

Pager `NOW-PAGINATION-CONTROL` udostępnia Pierwsza/Poprzednia/Następna/Ostatnia strona; zaobserwowano rozmiar strony 25 i wyłączone przyciski przy pustej liście. **Nie potwierdzono jeszcze** sposobu wyznaczania całkowitej liczby rekordów ani przejścia na drugą stronę. Nie utożsamiać liczby widocznych wierszy z kompletnym wynikiem.

W poprzedniej próbie osobno potwierdzono klasyczny `#task_sla_table`: pola `task`, `business_time_left`, `business_percentage`, metadane zakresu i ID wiersza SLA. Link zadania prowadził przez `/task.do`, a nie `/incident.do`. Nowoczesny link w niepustym wierszu wymaga osobnego sprawdzenia; nie wolno zgadywać adresu z numeru INC ani bezwarunkowo poszerzać `safe_record_url`.

## Próby natywnego ukrycia

Osobny zachowany profil testowy; bez profilu działającego monitora, bez odczytu poświadczeń, zmian dat/konfiguracji i zapisu rzeczywistych rekordów. Chromium 153.0.8010.12. Użyto obecnego `BrowserRuntime.dashboard_read` i `HiddenRendering`, bez rozszerzania granic zaufania. Każda próba przeładowywała stronę **po ustawieniu widoczności**; nie był to tylko odczyt DOM wcześniej załadowanego na widoku.

| Tryb | Wynik | Czasy od przeładowania do rozpoznania stanu | Mediana |
| --- | --- | --- | --- |
| Widoczne okno | 3/3, poprawnie rozpoznany pusty wynik | 4,55 / 6,75 / 6,92 s | 6,75 s |
| Całkowicie ukryte okno | 3/3, poprawnie rozpoznany pusty wynik | 5,92 / 5,78 / 5,48 s | 5,78 s |

W ukrytych próbach: zero próbek widocznego/minimalizowanego okna i zero próbek fokusu własnego Chromium. Są to próbki, nie ciągła rejestracja każdej klatki. Wszystkie liczniki były zerowe; wynik nie dowodzi poprawności odczytu rzeczywistych wierszy, paginacji ani zgodności filtrów. Wspólny profil i cache przeglądarki: to nowe załadowania strony, **nie** próby po usunięciu cache ani na świeżym profilu. Trzy próby na tryb nie uzasadniają gwarancji identycznej szybkości; nie zaobserwowano w nich spowolnienia ukrycia.

Pierwsze dwie serie skryptu badawczego nie są awariami aplikacji: pierwsza zbyt wcześnie wymagała potwierdzonej sesji po reload, druga pomijała Light DOM pustego komunikatu. Poprawiono wyłącznie skrypt pomiarowy i dopiero potem wykonano powyższą serię. Lokalne, ignorowane artefakty: `data/study_threat_aggregate.py`, `data/threat-aggregate-lab/` (również nieudane próby). Hash wszystkich modułów aplikacji przed i po pomiarze jest zgodny. Nie przechowywano klatek renderera, HTML ani rekordów.

## Zalecany projekt

1. **Jeden kompletny odczyt listy zbiorczej.** Powiązać nagłówek, tabelę, pusty stan, ładowanie i pager z tym samym widżetem i żądaniem. Mały adapter nowoczesnej listy; wspólne budżety, anulowanie, diagnostyka i walidacja kompletności, bez kopiowania całego klasycznego czytnika.
2. **Dwa poziomy tożsamości.** Najpierw zachować rekordy SLA według stabilnego ID źródłowego i zweryfikować pełną listę; dopiero potem grupować według ID incydentu. Numery INC nie są kluczem unikalności wiersza SLA. Nie sumować liczników jako liczby unikalnych INC.
3. **Atomowy wynik logiczny.** Odczyt zbiera kandydat; dopiero pełny i zgodny zestaw zmienia listę obecności oraz generuje nowe zdarzenia. Awaria zostawia poprzedni wynik oznaczony jako nieaktualny. Prawidłowo potwierdzona pusta lista usuwa obecność. Niezgodność kafelków/listy oznacza próbę niespójną, nie automatyczne zero; odświeżyć w jednym ograniczonym budżecie.
4. **Jeden wiersz, spójne wartości SLA.** Po pozostawieniu wyboru agentowi przyjęto: wybrać SLA o najbliższym terminie naruszenia, pobrać z niego parę czas/procent i pokazać wszystkie wykryte kategorie. Nie łączyć minimum czasu z maksimum procentu innej umowy. Progi kafelków dotyczą terminu, więc nie klasyfikować kategorii wyłącznie na podstawie tekstowego czasu roboczego. Remis rozstrzygać stabilnie ID SLA; brak poprawnego terminu jawnie oznaczyć, bez zgadywania z procentu.
5. **Obecność i zdarzenia niezależne od wyglądu.** Pierwszy poprawny odczyt zagrożeń powiadamia, inaczej niż zwykły filtr. `present -> absent -> present` tworzy nową generację zdarzenia; zmiana procentu lub kategorii obecnego INC nie wywołuje ponownego alertu. Cache/UI nie są źródłem prawdy o doręczeniu. Użytkownik potwierdził zachowanie obecności między restartami i dodał trwałą historię. W historii przechowywać pierwsze/ostatnie wykrycie, liczbę pojawień i ostatnie poprawnie odczytane wartości (zapis historyczny, nie żywe odliczanie). Brakujące/nieczytelne dane nie mogą po cichu udawać pustej historii.
6. **Wysyłka przez istniejące transporty.** Rozszerzyć korelację zadanie/wynik, nie tworzyć kolejnej pary wątków HTTP. Obecne `submit` nie potwierdza przyjęcia do pełnej kolejki, a wynik nie zawiera ID konkretnego alertu. Potrzebne rozróżnienie przygotowano/przyjęto do kolejki/zaakceptowano przez usługę/błąd/wynik niepewny. HTTP po timeout nie daje gwarancji jednokrotnego doręczenia. Nie wznawiać bezmyślnie niepewnego POST.
7. **Widok i harmonogram.** Porcjowane renderowanie tabeli, dwuklik wyłącznie do sprawdzonego adresu ServiceNow. Zachować pojedynczego właściciela Playwright i punkty wtrącania między całymi filtrami. 60 s liczyć od końca całej próby zagrożeń (kafelki + szczegóły), bez nakładających się zadań i nowych timerów powiadomień.

Przykład wiadomości, dane syntetyczne: **Incydenty zagrożone SLA · 2**; `INC0000001 · P2 · Pozostało: 1 godz. 20 min · Wykorzystano: 83,3%`; następny INC w kolejnej linii; na końcu „Otwórz incydenty zagrożone w SNOW” z uzgodnionym linkiem. Powiadomienie grupuje tylko nowe pojawienia z zakończonego odczytu, nie całą stale obecną listę. Treść pozostaje do potwierdzenia przed wdrożeniem; pamięć po restarcie zatwierdzona przez użytkownika.

## Braki dowodowe i warunki rozpoczęcia implementacji

Przygotowano część niezależną od realnych wierszy: [scenariusze syntetyczne](../fixtures/threatened/README.md) i [wynik izolowanego modelu](../verification/threatened-design-scenarios.md) — 32 scenariusze / 60 kroków. Nie są to testy produktu ani dowód poprawności DOM/paginacji; poniższe braki pozostają aktualne.

- Rzeczywista niepusta lista: stabilne ID SLA/INC, adres INC, obie wartości i stan po terminie, kilka SLA jednego INC, response i resolution.
- Potwierdzenie, że filtr listy odpowiada unii sześciu kafelków; same tytuły i wspólny pusty wynik tego nie dowodzą. Nie znamy jeszcze jawnego źródłowego zapytania listy. Nie wchodzić w edycję/zapis konfiguracji dashboardu w ramach analizy.
- Kompletność większa niż strona: metadane, zakres, zmiana strony, możliwa wirtualizacja i zmiana danych podczas przejścia. Nie przenosić założeń o klasycznych stronach 20/100.
- Próby widoczne/ukryte z rzeczywistymi rekordami, po reload i przewijaniu. Kontrolowane przypadki błędów, duplikatów i ponowień na syntetycznych strukturach; takie testy nie zastąpią rzeczywistej listy.

**Wniosek:** wspólna lista jest właściwym kierunkiem i ukryty odczyt pustego wyniku działa z obecnym mechanizmem. Nie ma jeszcze dowodu wystarczającego do obietnicy pełnej poprawności listy i powiadomień. Plan zawiera etap domknięcia tych dowodów przed zmianą aplikacji.

## Niepusta lista — obserwacja 3 listopada 2026

W zalogowanej karcie Codex zakładka zagrożeń pokazała 3 w kafelku P3 i zera w pozostałych pięciu. Tabela miała trzy wiersze rozwiązywania SLA priorytetu 3 i trzy różne INC. To zgodność liczby i kategorii w jednej obserwacji, bez porównania członkostwa z listą kafelka.

- Nagłówki i komórki udostępniają `data-column-key`. Potwierdzone klucze: `task`, `task.priority`, `sla.target`, `planned_end_time`, `business_time_left` oraz `business_percentage`. Termin miał format daty i czasu do sekund, czas roboczy polskie jednostki, procent przecinek dziesiętny. Strefa terminu, format przekroczenia i obsługa SLA podjęcia wymagają osobnej próby.
- Każdy z trzech wierszy miał odrębny 32-znakowy klucz szesnastkowy w `tr[data-key]`. Komórka `task` zawierała odnośnik `task.do` z parametrem identyfikatora oraz numer INC jako etykietę. Nie ustalono jeszcze trwałości klucza po zmianie strony ani docelowego przekierowania odnośnika.
- W `now-pagination-control` dostępny był osobny tekst zakresu „Pokazywanie 1-3 z 3”, przycisk strony 1 i nieaktywny przycisk następnej strony. Odczyt całego tekstu Shadow DOM pagera skleja końcową liczbę z numerem strony i daje pozorny total 31. Czytać wyłącznie element tekstu zakresu i niezależny stan przycisku w obrębie tego samego pagera. Przejścia na kolejną stronę nie było możliwe w tej próbce.
- Nadal otwarte są porównanie rekordów z listami kafelków, inne kategorie, wiele SLA dla tego samego INC, nawigacja wielostronicowa i powtórzenie niepustego odczytu w rzeczywiście ukrytym oknie aplikacji. Ten pomiar odbył się w przeglądarce Codex. Bez zmian w aplikacji i wysyłek.

### Natywne Chromium, niepusty wynik — 3 listopada 2026

Odczyt testowy na osobnym profilu, z istniejącymi BrowserRuntime i rendererem dashboardu. Pierwsza próba widoczna osiągnęła limit 60 s pomimo gotowej tabeli: sonda błędnie traktowała pasek procentu w wierszu jako ładowanie. Serię przerwano i powtórzono po wykluczeniu wskaźników w obrębie wierszy z detekcji ładowania. W adapterze należy rozróżnić pasek danych i lokalny sygnał ładowania tabeli.

Po tej korekcie 3/3 prób widocznych (4,75–6,72 s) i 3/3 ukrytych (5,58–5,70 s) zakończyło się gotowym odczytem po przeładowaniu. W każdej były trzy wiersze z wymaganymi polami i odrębnymi kluczami SLA, zakres 1–3 z 3 oraz wyłączona następna strona. W 56 próbkach ukrytych brak widoczności, minimalizacji i fokusu okna. Pomiary dotyczą odczytu po zalogowaniu; profil i cache współdzielone w serii. Wyniki potwierdzają wykonalność ukrytego odczytu jednej niepustej strony, bez podstaw do uogólnienia szybkości na inne dane i konfiguracje. Paginacja oraz zgodność rekordów z pozostałymi kategoriami nadal wymagają osobnej próby. Kod aplikacji pozostał bez zmian.

### Porównanie członkostwa P3 — 3 listopada 2026

W osobnym Chromium odczytano w ukryciu trzy wiersze listy zbiorczej. Następnie w tym samym kontekście otwarto klasyczną listę docelową kafelka P3. Miała trzy wiersze, a zbiór kluczy SLA był identyczny z listą zbiorczą. Porównanie wykonano w pamięci; raport zapisał tylko liczby i wynik. Następna strona listy zbiorczej była nieaktywna. Ta próba zamyka porównanie dla zaobserwowanej próbki P3. Nie potwierdza zakresu pozostałych kategorii, w tym Podjęcia, ani przejścia na kolejną stronę.

### Dodatkowa obserwacja odpowiedzi i przekroczenia

W zalogowanej karcie Codex zbiorcza lista pokazała zakres 1–2 z 2. W jednej tabeli były SLA rozwiązania i odpowiedzi (kafelek Podjęcie wskazywał 1). Oba wiersze udostępniały numer INC jako link do `task.do` z identyfikatorem, cel, priorytet, termin naruszenia, czas roboczy i procent. Dla przekroczonych SLA czas pozostały pokazywał `0 s`, a procent przekraczał 100 i miał kropkę dziesiętną. Parser powinien przyjmować kropkę i przecinek oraz zachować wartości powyżej 100%. Samo zero czasu nie rozróżnia chwili upływu od przekroczenia. Próba odczytowa w karcie Codex; bez ponownego pomiaru ukrytego okna dla tych dwóch wierszy i bez testu następnej strony.
