# Import filtrów z bocznego menu ServiceNow — analiza techniczna

**Uaktualnienie po osobnym zleceniu implementacji, 6 listopada 2026:** poniższe rozpoznanie zachowuje historyczny zakres. Funkcję wdrożono następnie tylko w źródłach; rzeczywiste obserwacje uzupełniono o szeroki przypięty wariant (również 36 linków i 5 grup) oraz klasę hide-scroll wyników wyszukiwania. [Decyzja 022](../decyzje/022-import-ulubionych-na-zadanie.md) i [raport implementacji](../plany/zakonczone/import-ulubionych-servicenow.md) rozróżniają wykonane testy, plan i ograniczenia.

6 listopada 2026. **Status: rozpoznanie rzeczywistej strony zakończone; funkcja niewdrożona.** Dokument jest podstawą dalszego planowania, nie zgodą na implementację. Zmieniono wyłącznie dokumentację. Bez buildu, publikacji, zapisu filtrów aplikacji lub edycji ulubionych ServiceNow.

Badana strona: `https://adeo.service-now.com/now/sow/home`. Użytkownik zalogował się samodzielnie w niezależnej karcie Codex. Nie używano przeglądarki, profilu ani aktywnego odczytu monitora. Nazwy osobistych grup, identyfikatory pozycji i pełne zapytania filtrów nie są utrwalane w tym opracowaniu; przykłady są syntetyczne.

## 1. Wniosek

Import jest wykonalny bez otwierania kolejno zapisanych filtrów. Rzeczywiste menu Ulubione zawiera elementy `a.item-label` z pełną nazwą w `textContent` i adresem w `href`. Najszybsza potwierdzona metoda to jedna zbiorcza obserwacja właściwego drzewa menu przez otwarte Shadow DOM, a następnie lokalna walidacja i prezentacja wyboru użytkownikowi.

**Szybka ścieżka nie potrzebuje klikania filtrów, przechodzenia na ich listy, eksportu HTML, odczytu danych aplikacyjnych komponentów ani nieudokumentowanego API.** W badanym wariancie nie wymaga też rozwijania grup ani przewijania. Niezawodność oznacza tu potwierdzenie spójnego, kompletnego dostępnego drzewa albo jawny błąd/niekompletność, nigdy ciche zaakceptowanie brakującej części.

Nie da się na podstawie samego DOM udowodnić, że backend zwrócił wszystkie zapisane rekordy użytkownika. Zakres importu to pozycje udostępnione temu użytkownikowi w menu Ulubione. Nie obejmuje filtrów zapisanych wyłącznie wewnątrz list ani innych kont.

## 2. Potwierdzone obserwacje i pomiary

| Próba | Wynik |
| --- | --- |
| Wejście na stronę i logowanie | Wymagana sesja; logowanie przekazane użytkownikowi. |
| Układ wąski, około 751 px | Ulubione otwierane przez `#nav-overflow` → przycisk Ulubione. Kliknięcie widocznego napisu nagłówka nie otworzyło listy. |
| Struktura menu | 14 pozycji najwyższego poziomu: 9 bezpośrednich linków i 5 grup. Grupy zawierały 5, 6, 2, 7 i 7 linków; razem 36 linków. |
| Nazwy i adresy | 36 niepustych pełnych nazw, 36 adresów i 36 unikalnych identyfikatorów pozycji; identyfikator `id` linku odpowiadał `data-id`. Wszystkie href były względne. |
| Typy celów | 23 linki do incident, 7 do sc_task, 3 do sc_request; 3 pozostałe prowadziły do stron/obszaru wiedzy. To 33 kandydatów zgodnych typem listy, jeszcze nie wynik walidatora Pythona. |
| Powtarzające się nazwy | Liczba pozycji przewyższała liczbę unikalnych nazw o 3; w badaniu wszystkie 36 surowych celów było różnych. Nazwa nie nadaje się na klucz deduplikacji. |
| Zwinięcie jednej grupy | `aria-expanded=false`, ale wszystkie 36 linków nadal istniało w DOM z tymi samymi adresami. Po próbie przywrócono rozwinięcie. Nie testowano osobno zwinięcia każdej grupy. |
| Przewinięcie na dół | scrollTop 914 przy scrollHeight 1326 i clientHeight 412; drzewo linków nie zmieniło się. Potwierdzono obecność pozycji poza widokiem. |
| Wyszukiwanie w Ulubionych | Po wpisaniu terminu początkowo nadal 36 linków; później struktura zmieniła się na dwie listy i 16 linków. Po wyczyszczeniu wróciła jedna lista i 36 linków. |
| Kopie menu | Obok aktywnego panelu istniała osobna kopia Ulubionych z innym stanem dzieci. Obie miały geometrię; samo `visible=True` nie jest wystarczającym rozróżnieniem. |
| Zbiorczy odczyt | Pierwszy pomiar około 61 ms. Pięć kolejnych: 41, 36, 35, 36, 34 ms; mediana 36 ms. Wszystkie pięć migawek było identycznych. |

Pomiary obejmują wywołanie obserwacji przez narzędzie Codex, po otwarciu i załadowaniu menu. Nie obejmują logowania, startu Chromium, sieciowego ładowania strony, walidacji Pythona ani przyszłego zapisu konfiguracji. Nie są benchmarkiem EXE i nie gwarantują takiego czasu na innych kontach.

Podczas pierwszej próby wyszukiwania panel także zamknął się przed następną obserwacją. Przyczyny nie ustalono; powtórna próba potwierdziła opóźnione filtrowanie. Czytnik powinien wykrywać utratę właściwego panelu, zamiast kontynuować na ukrytej kopii.

## 3. Zweryfikowana struktura DOM i zakres selektorów

Schemat istotnej części, bez danych użytkownika:

```text
sn-polaris-header [otwarty Shadow DOM]
  sn-polaris-menu[aria-label="Więcej menu"] [otwarty Shadow DOM]
    .sn-polaris-overflow-body.is-drilled
      .sn-polaris-nav-body[role="list"]
        sn-collapsible-list[role="listitem"] [otwarty Shadow DOM]
          a.item-label[id][data-id][href]                 # pozycja bez grupy
          LUB [role="group"]
            [role="button"][aria-expanded]             # przełącznik grupy
              span[role="heading"]                     # pełna nazwa grupy
            ul → li → span.menu-item-row → a.item-label  # dzieci grupy
```

Potwierdzony zakres w wąskim układzie: `sn-polaris-menu[aria-label="Więcej menu"]`, a w nim po wejściu w Ulubione dokładnie jedna `.sn-polaris-nav-body` przy pustym wyszukiwaniu. Samo istnienie menu Więcej nie dowodzi, że otwarto Ulubione — wymagane są także właściwy ekran podrzędny, jego pole wyszukiwania i przycisk Edytuj ulubione. **Przycisku Edytuj ani przycisków Usuń nie klikamy.**

Potwierdzone otwarcie: `#nav-overflow` → `get_by_role('button', name='Ulubione', exact=True)`. Pole wyszukiwania ma nazwę dostępności `Wprowadź wyszukiwany termin w celu filtrowania menu Ulubione`. Nagłówki grup mają rolę heading na SPAN, nie tag H2. Nie należy wnioskować tagu z poziomu nagłówka AX.

Nazwa pozycji: tekst kotwicy, z usunięciem skrajnych białych znaków. Wewnątrz występował span.item-icon. `aria-label` linku zawiera dodatkowo pozycję typu „1 z 5”, więc nie należy zapisywać go jako nazwy filtra ani usuwać takiego sufiksu zgadywanym regexem. Wizualnego skrócenia nazwy nie kopiujemy ze zrzutu ani tooltipa.

W listach dzieci zaobserwowano **odwrócone znaczenie atrybutów**: `aria-posinset` miało stałą liczebność grupy, a `aria-setsize` kolejne liczby 1..N. Nie używać ich jako normatywnego dowodu kompletności ani automatycznie naprawiać wszędzie przez zamianę. Mogą stanowić tylko pomocniczy sygnał diagnostyczny.

Docelowy czytnik powinien sprawdzać granice Shadow DOM i znany schemat, a nie opierać się na pozycjach nth, dynamicznych now-id/component-id lub zapisanych identyfikatorach konkretnego użytkownika. Nie używać nieograniczonego skanowania wszystkich linków całej strony. Nie akceptować po cichu dzieci bez nazwy/adresu lub nieznanej struktury grupy.

## 4. Rekomendowany algorytm odczytu

1. **Żądanie i sesja.** Nadać import_id, ustalić generację sesji i jedno zadanie odczytu. Skorzystać z istniejącego właściciela Playwright, logowania i kontroli Stop. W przyszłej funkcji użyć pomocniczej karty tego samego kontekstu przeglądarki z polityką BrowserRuntime, nie przejmować strony właśnie odczytywanego dashboardu. Nie uruchamiać drugiego równoległego klienta Playwright.
2. **Otwarcie i kontekst.** Wejść na znany adres SOW. Potwierdzić tenant, sesję i dostęp do Ulubionych; otworzyć je odpowiednią zaobserwowaną ścieżką UI. Nie tworzyć ulubionych, nie przypinać menu i nie wchodzić w jego edycję.
3. **Brak wyszukiwania.** Zapamiętać zastany tekst wyszukiwania tylko w pamięci; wyczyścić na czas odczytu, jeśli jest niepusty. Poczekać na zakończenie przebudowy i pojedyncze drzewo główne. Nie akceptować migawki tuż po fill, gdy wciąż zawiera stary wynik. Po operacji przywrócić zastany tekst, jeśli zachowujemy kartę; nie logować go.
4. **Migawka atomowa.** Jednym evaluate na potwierdzonym korzeniu przejść po elementach i ich otwartych Shadow DOM. Zebrać wyłącznie identyfikator pozycji, pełną nazwę, surowy href, ścieżkę grup, kolejność, stan grup i liczniki struktury. Dane są lokalnym wynikiem w pamięci. Znany obecny wariant ma jeden poziom grup; głębsze grupy wymagają obsługi rekurencyjnej z walidacją albo jawnego odrzucenia jako nieobsługiwane, nie pominięcia.
5. **Stabilność i kompletność.** Uzyskać co najmniej dwie identyczne pełne migawki, rozdzielone krótkim kooperacyjnym oczekiwaniem około 200 ms. Porównywać uporządkowane identyfikatory, nazwy, adresy i ścieżki grup, nie samą liczbę. Wymagać pustego wyszukiwania, jednego właściwego panelu, rozpoznania każdego dziecka i braku oczekiwania/loadera. Schemat oraz ewentualny stan pusty/loader muszą zostać jeszcze zaobserwowane przed implementacją ich selektorów. Stabilne zero samo w sobie nie potwierdza pustych ulubionych.
6. **Rozwijanie tylko w razie potrzeby.** W obecnym DOM zwinięta grupa zachowuje linki, więc nie rozwijać jej rutynowo. Jeśli rozpoznana grupa nie ma dostępnych dzieci, można jednokrotnie rozwinąć ją przez zaobserwowany przełącznik i ponownie obserwować. Stan `aria-expanded` sprawdzać po akcji; nie powtarzać niepewnego kliknięcia. Przywrócić zastany stan grupy. Brak postępu lub nieznany wariant kończy się jawną niekompletnością.
7. **Wariant wirtualizowany.** Nie był potrzebny w badaniu. Jeśli inne konto ujawni wirtualizację, sam odczyt dwóch równych migawek nie wystarczy. Najpierw osobna obserwacja tego wariantu i jego wskaźników końca/całkowitej liczby; dopiero potem ograniczone przejście viewportami z unią identyfikatorów i sprawdzeniem granic. Bez takiego dowodu nie oferować wyniku jako „wszystkie”. Nie dodawać teraz spekulatywnego scrollowania w ciemno.
8. **Klasyfikacja lokalna.** Rozwiązać href względem katalogu głównego potwierdzonego tenanta (`https://adeo.service-now.com/`), nie względem `/now/sow/home`. Polaris zwraca również nazwy bez początkowego ukośnika, np. syntetyczne `incident_list.do?sysparm_query=active%3Dtrue`. Przekazać pełny wynik do istniejącego normalize_list_url/validate_urls. Nie przepisywać zapytań, widoków ani warunków użytkownika. Obce hosty, niebezpieczne schematy i cele inne niż listy pozostają nieimportowalne z czytelnym powodem. Nie wykonywać javascript: ani kodu z parametrów URL. Skrót __tinyId__ traktować istniejącą ścieżką; nie otwierać wszystkich skrótów automatycznie podczas szybkiego zbierania menu.
9. **Podgląd.** Pokazać rozpoznane pozycje i status: do dodania, już istnieje, nieobsługiwana lub wymagająca rozwiązania skrótu. Zachować grupy i kolejność; zaznaczenie jest decyzją użytkownika. Dopiero osobne zatwierdzenie uruchamia zapis. Awaria odczytu, Stop i odrzucenie podglądu niczego nie zapisują.

Przykładowy wynik wewnętrzny, nie proponowany publiczny interfejs ani nowy schemat konfiguracji:

```text
{complete, items: [{source_id, name, href, group_path, order}],
 top_count, group_count, item_count, skipped_count, outcome}
```

Surowe URL i nazwy są potrzebne podglądowi i późniejszej konfiguracji użytkownika, ale nie logom lub dokumentacji repozytorium. Nie przenosić pełnego snapshotu do trwałego cache importu. Jeśli struktura zmienia się podczas odczytu, odrzucić cały niezatwierdzony zbiór i ponowić ograniczoną obserwację; nie sklejać starych i nowych drzew przy zwykłym wariancie.

## 5. Włączenie do istniejącej aplikacji — propozycja

- Zachować regułę [001](../decyzje/001-watki-i-kolejki.md): Playwright w istniejącym workerze, Tk otrzymuje zdarzenia kolejką. Wzór pomocniczej karty i jej cleanup istnieje w dashboard_drilldown.collect_drilldown; wymaga użycia polityki runtime, nie kopiowania tylko context.new_page().
- Nie zmieniać znaczenia obecnych filtrów. app.load_filters obsługuje wpisy name/url i walidację, app.edit_filter waliduje jeden adres oraz deduplikuje URL, app.persist_filters zapisuje bieżące filtry i urls. Zapis wykonuje się dopiero po potwierdzeniu zaznaczenia; użyć istniejącego save_json i wycofania stanu w pamięci przy odmowie zapisu.
- Deduplikacja źródeł: source_id tylko w obrębie odczytu. Deduplikacja importu: wynik istniejącej normalizacji adresu, nie nazwa i nie dowolnie sortowane/przepisane warunki zapytania. Różne zapytania o tej samej nazwie muszą pozostać rozróżnialne. Równoważność skrótu i adresu bezpośredniego nie zawsze jest znana bez rozwiązania; nie obiecywać wykrycia wszystkich takich duplikatów.
- Nowe filtry proponuje się dodawać jako wyłączone (enabled=false), z wyłączonymi powiadomieniami, bez nadpisywania istniejących nazw/polityk. To rekomendacja do zatwierdzenia w planie UI, nie stan już wdrożony.
- Pozostaje decyzja koordynacyjna: obecna ręczna edycja filtrów jest blokowana podczas działania workera, a jego cykl życia jest związany z monitoringiem. Importu nie można po prostu dopisać jako wywołania Tk. Plan implementacji musi ustalić uruchomienie odczytu na żądanie bez automatycznego startu monitoringu oraz moment zatwierdzania konfiguracji. Rozszerzyć wspólny cykl worker/runtime, nie tworzyć konkurencyjnej przeglądarki ani nawigacji z executora.
- Brak automatycznej synchronizacji po imporcie. Zmiany menu ServiceNow nie usuwają ani nie aktualizują samoczynnie lokalnych filtrów.

## 6. Limity, błędy i diagnostyka

Proponowany punkt startowy: 30 s aktywnego budżetu odczytu menu, poza czasem oczekiwania na użytkownika podczas logowania; stałe krótkie obserwacje, bez wielosekundowych sleep. Wspólne read_budget i browser_actions, bez zmiany limitów obecnych odczytów dashboardu. Do ustalenia w planie: jedno ograniczone odtworzenie odczytu po błędzie przejściowym i jedno odzyskanie sesji, bez nowego budżetu oraz bez ponawiania niepewnych akcji. Utrata sesji unieważnia dotychczasowy niezatwierdzony snapshot. Stop sprawdzać przed/po obserwacji, nawigacji i oczekiwaniu.

Stany wyniku rozdzielić: kompletny, potwierdzone puste menu, niekompletny/nieobsługiwany wariant, potrzebne logowanie, anulowany i błąd. Przekroczenie limitu lub zmiana struktury nie oznacza pustego menu. Nie zapisywać częściowego importu automatycznie. Ochronę przed zbyt dużym drzewem/zakresem ustalić jawnie; limit nie może obcinać wyniku z flagą complete=true.

Diagnostyka przez wspólny LoginDiagnostics: run/read/import_id, próba, etap, czas, wariant UI, liczba korzeni/grup/pozycji, liczba obsługiwanych/odrzuconych/duplikatów, kategoria błędu i wynik. Etapy: start, sesja, otwarcie, gotowość, snapshot, walidacja, podgląd, zatwierdzenie/anulowanie i koniec. Logować przejścia, nie każde odpytywanie. Bez nazw, URL, zapytań, danych konta, ID źródłowych ulubionych i zawartości wyszukiwania. Nowe stałe kody dodać do istniejących allowlist i sprawdzić faktyczną serializację. Awaria logu nie może przerwać importu.

## 7. Testy i granice dalszego odbioru

Przed implementacją czytnika utrwalić minimalny syntetyczny DOM z otwartymi Shadow DOM, dwiema kopiami menu i listami/grupami. Nie kopiować rzeczywistego HTML ani warunków użytkownika.

Testy wymagane: wszystkie grupy i pozycje poza widokiem, zwinięta grupa z zachowanymi dziećmi, grupa montowana z opóźnieniem, pełna nazwa mimo wizualnego skrócenia, mylący aria-label, powtarzalne nazwy, względne href, odrzucenie obcych/niebezpiecznych celów, kodowanie Unicode i zagnieżdżonych adresów, skróty, zmiana grupy w trakcie odczytu, wyszukiwanie z opóźnieniem i dwoma listami, brak uprawnień, potwierdzone puste menu, zamknięcie panelu, utrata sesji, Stop, budżet, zamknięcie Chromium, odmowa zapisu, anulowanie podglądu i brak sekretów w diagnostyce. Dodatkowo sprawdzić brak automatycznego włączenia monitoringu/powiadomień i brak zmian istniejących filtrów.

Kryterium szybkości: standardowy gotowy panel odczytywany zbiorczo, bez nawigacji do każdego filtra i bez jednego protokołowego odczytu na każdą nazwę/href. Dwie stabilne migawki i walidacja powinny stanowić niewielki koszt wobec otwarcia strony; rzeczywisty cel czasowy EXE ustalić pomiarem przyszłego prototypu, nie na podstawie samych 34–41 ms.

**Nie sprawdzono:** szerokiego/przypiętego wariantu menu, pustego konta, innych uprawnień, bardzo dużego/wirtualizowanego drzewa, głębszych podgrup, zmiany danych przez inną kartę w czasie importu, wymuszonego wylogowania, restartu Chromium i bezpośredniego wywołania walidatora Python na rzeczywistych linkach. Nie badano ani nie zakładano endpointów API; nie testowano przyszłego importera, bo nie istnieje. To warunki dalszego planu i odbioru, nie potwierdzone funkcje.

Po badaniu: przywrócono rozwinięcie grupy, puste wyszukiwanie i zamknięte menu; adres pozostał /now/sow/home, a zbiór 36 pozycji był zgodny z bazowym. Nie otwierano celów filtrów, nie edytowano ulubionych i nie zapisywano konfiguracji ServiceNow. Pełne nazwy i href przetworzono tylko w pamięci narzędzia; opracowanie przechowuje strukturę i zagregowane wyniki.
