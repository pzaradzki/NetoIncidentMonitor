# Migracja importu Ulubionych ServiceNow na REST API

**Status:** wdrożono w źródłach i odebrano 15 listopada 2026 r.

Akcja **Import z ServiceNow** ma pobierać Ulubione bieżącego użytkownika przez API, na żądanie, we wspólnej sesji aplikacji. Zachowujemy okno podglądu i pojedynczy zapis wybranych filtrów. Po potwierdzeniu nowego odczytu usuwamy czytnik menu wraz ze starszą ścieżką opartą na osobnym Chromium. Po każdej serii zmian zapisz wynik weryfikacji i zaznacz ukończone kroki.

## Stan wyjściowy

- `app.py` przekazywał zlecenie z `FavoritesImport` do `SharedSession`, a `favorites_worker.read_on_session()` wywoływał `favorites_reader`. Czytnik otwierał stronę SOW oraz menu Ulubione, używał Shadow DOM, tymczasowego rozmiaru strony i ukrytego renderowania. `favorites_ui.py` zawierał starszą ścieżkę z własnym wątkiem i profilem. [Analiza menu](../../analizy/import-ulubionych-servicenow.md) · [Wspólna sesja](../../decyzje/025-wspolna-sesja-servicenow.md)
- `favorites.classify()` obsługuje adresy względne względem instancji, sprawdza typ listy i wykrywa duplikaty po normalizacji adresu. `commit_selection()` ponownie sprawdza konfigurację i zapisuje wybrane pozycje jako wyłączone, z wyłączonymi powiadomieniami. [Dotychczasowy plan importu](import-ulubionych-servicenow.md)
- `analytics_api.get()` już przed zmianą wykonywał dozwolone żądania GET na wspólnej karcie, korzystając z zalogowanej sesji. Lista dozwolonych tras nie obejmowała jeszcze zakładek. [Integracja REST w aplikacji](../../servicenow-api-sesja-przegladarki.md)

## Potwierdzony odczyt Ulubionych

```http
GET /api/now/ui/navigator/favorites
```

Żądanie wykonano ze strony startowej SOW w odrębnej, zalogowanej sesji zwykłego użytkownika, używając tego samego sposobu uwierzytelniania co obecne odczyty REST. Trasa działa bez parametrów. Pierwszy odczyt odbył się przed otwarciem menu, a powtórzenie po ponownym wczytaniu SOW. Obie odpowiedzi miały HTTP 200 i kompletny zestaw **37 pozycji**. Porównanie z menu wykazało zgodność 37 identyfikatorów i 37 par nazwa–adres. Obecna klasyfikacja w obu przypadkach dopuściła te same **34 filtry** i odrzuciła 3 nieobsługiwane cele.

Odpowiedź zawiera `result.favorites`. W badanym koncie na najwyższym poziomie było 10 zakładek i 5 grup. Grupy zawierały łącznie 27 zakładek w tablicach `favorites`. `id`, `title` i `url` wystarczają do odwzorowania pozycji do podglądu. Grupę rozpoznajemy po tablicy `favorites`, a pozycję do klasyfikacji po jej nazwie i adresie. Nie zaobserwowano nagłówków paginacji. Konto bez Ulubionych i inne role pozostają do sprawdzenia.

To wewnętrzna trasa nawigatora ServiceNow. Wynik potwierdza działanie na zwykłym koncie w ADEO w dniu próby. Podczas wdrożenia zapisz minimalny kontrakt i zaplanuj próbę po aktualizacji ServiceNow, ponieważ kształt odpowiedzi może się zmienić. [Opis nawigacji ServiceNow](https://www.servicenow.com/docs/r/platform-user-interface/using-the-next-experience-global-header.html)

### Wynik wcześniejszej próby z Table API

Początkowy kandydat opierał się na tabeli `sys_ui_bookmark` i filtrze `javascript:gs.getUserID()`. [Tabela zakładek](https://www.servicenow.com/docs/r/platform-administration/data-preservation.html) · [Filtry i parametry REST](https://www.servicenow.com/docs/r/api-reference/rest-api-explorer/c_RESTAPI.html)

```text
GET /api/now/table/sys_ui_bookmark
sysparm_query=user=javascript:gs.getUserID()^ORDERBYsys_id
sysparm_fields=sys_id,user,title,url
sysparm_display_value=false
sysparm_exclude_reference_link=true
sysparm_limit=10
sysparm_offset=0
```

Próby z tym filtrem i limitami 10 oraz 100 zwróciły HTTP 200, `X-Total-Count: 37` i zero rekordów w `result`. Większy limit objął cały zgłoszony zakres i odpowiedź nie wskazała następnej strony. Menu na tym samym koncie pokazało 37 zakładek. Zachowanie jest zgodne z dokumentacją opisującą ocenę uprawnień po zastosowaniu limitu strony. Szczegółowa reguła obowiązująca w ADEO pozostaje nieustalona. Operacje GraphQL zaobserwowane przy otwieraniu menu obsługiwały inne funkcje interfejsu. [Parametry Table API](https://www.servicenow.com/docs/r/api-reference/rest-apis/c_TableAPI.html)

## Etapy

- [x] **1. Wybierz źródło odczytu w instancji ADEO**
  - [x] Sprawdź Table API na zwykłym koncie z limitem 10 i 100. Oba odczyty zwróciły pustą tablicę przy liczniku 37.
  - [x] Wykonaj bezpośredni GET z API nawigatora w zalogowanej sesji przed otwarciem menu. Potwierdzono treść `result.favorites`, zwracaną bez parametrów.
  - [x] Porównaj z menu na tym samym koncie. Zgodziły się 37 identyfikatorów, 37 par nazwa–adres i zestaw 34 obsługiwanych filtrów.
  - [x] Powtórz próbę po ponownym wczytaniu SOW i wybierz źródło. GET z API nawigatora ponownie zwrócił ten sam zestaw. Plan wdrożenia opiera się na tej trasie.

- [x] **2. Zaimplementuj odczyt i walidację odpowiedzi**
  - [x] Dodaj dokładną trasę `/api/now/ui/navigator/favorites` do jawnej listy dozwolonych adresów. Wykonaj jeden GET bez parametrów w aktualnej sesji na wspólnej karcie. Użyj istniejącego mechanizmu przygotowania kontekstu, gdy go brakuje. Odczyt nie otwiera menu ani celów zakładek.
  - [x] Sprawdź tablicę `result.favorites` oraz strukturę grup i pozycji. Użyj `id` do kontroli powtórzeń, przejdź po grupach w kolejności otrzymanej od serwera i dopasuj `title` oraz `url` do obecnego podglądu. Zastosuj jawne ograniczenia liczby elementów i głębokości. Nieoczekiwana paginacja, brak wymaganych pól, powtórzony identyfikator lub przekroczony limit kończą próbę bez częściowego wyniku.
  - [x] Rozróżnij pustą tablicę w poprawnej odpowiedzi od braku dostępu, braku tablicy i błędu schematu. Po ponowieniu buduj wynik od początku. Poprawnie odczytane zakładki spoza obsługiwanych list przekazuj do obecnej klasyfikacji jako niedostępne do importu.

  Weryfikacja lokalna czytnika objęła 7 zaliczonych testów tras, grup, ograniczeń, błędów, klasyfikacji adresów i diagnostyki.

- [x] **3. Podłącz kolejkę, podgląd i diagnostykę**
  - [x] Zachowaj zlecenie `favorites` w `SharedSession`, niezależnie od stanu monitoringu. Dopuść jeden import do zamknięcia podglądu. Po odczycie kolejka przyjmuje kolejną pracę, również gdy podgląd nadal jest otwarty. Anulowanie importu usuwa tylko jego zlecenie i unieważnia spóźnione wyniki. Zamknięcie aplikacji anuluje pracę sesji.
  - [x] Użyj wspólnej obsługi sesji, anulowania i ograniczonych ponowień. Przy `401` lub przekierowaniu do logowania wznów odczyt po odzyskaniu sesji w dotychczasowym budżecie aktywnej pracy. `403` oznacza brak dostępu, a `429` kończy próbę bez natychmiastowego ponowienia. Zweryfikuj zachowanie po zamknięciu Chromium i utracie sesji podczas próby.
  - [x] Przekaż komplet danych jako nazwy i adresy do istniejącego podglądu. Zachowaj wyszukiwanie, wybór i normalizację adresów INC, REQ, RITM i SCTASK, w tym obsługiwane warianty skrótów. Przed zapisem ponownie sprawdź konfigurację oraz duplikaty. Zapisz zatwierdzone pozycje w jednej operacji jako wyłączone i z wyłączonymi powiadomieniami. Odczyt definicji nowo dodanego filtra należy do jego późniejszej aktualizacji.
  - [x] Dopasuj komunikaty do źródła API oraz odróżnij pustą listę od błędu. Wspólna diagnostyka ma wiązać przyjęcie do kolejki, próby, status HTTP, liczbę zakładek i grup, logowanie, przerwanie i wynik z identyfikatorem importu. Zapisuj kategorie, liczniki i czasy. Nazwy zakładek, adresy, właściciele, treść odpowiedzi i dane sesji pozostają poza logami. Awaria zapisu logów nie przerywa importu.

  Weryfikacja zakresowa Windows zaliczyła 51 testów. Przerwanie importu wskutek zamknięcia Chromium kończy jego zlecenie przed standardowym ponownym połączeniem sesji. Katalog testowy pierwszego przebiegu utrzymał otwarty plik diagnostyki przy sprzątaniu. Kolejne przebiegi zamykają uchwyty przed usunięciem danych tymczasowych.

- [x] **4. Usuń dawną ścieżkę odczytu**
  - [x] Po potwierdzeniu działania REST usuń `favorites_reader.py`, selektory i zbieranie drzewa menu, zmianę rozmiaru strony oraz mechanizm stabilizacji migawek. Usuń `run_import()`, `select_import_page()` i gałąź osobnego wątku w `FavoritesImport`, jeśli przegląd wywołań potwierdzi brak innych konsumentów. Przy braku gotowej sesji użyj stanu oczekiwania lub niedostępności w interfejsie.
  - [x] Usuń zakres `favorites` z `BrowserRuntime` i `HiddenRendering`, jego odświeżanie przy przełączaniu widoczności i pola diagnostyki używane wyłącznie przez menu. Zachowaj renderowanie logowania i odczytu definicji filtrów. Zweryfikuj współdzielone zależności, w tym `HOME`, którego potrzebują logowanie i transport REST. Usuń zbędne testy starej ścieżki po przeniesieniu testów zachowania importu na nową.

  Wyszukanie dotychczasowych wywołań czytnika, viewportu importu i osobnej karty nie znalazło odwołań w kodzie ani w pakowaniu. Zaliczone 21 testów zakresowych API i pozostałych mechanizmów renderowania.

- [x] **5. Sprawdź import i zamknij plan**
  - [x] Na danych syntetycznych sprawdź pojedynczy GET, układ grup i pojedynczych zakładek, poprawną pustą tablicę, niekompletną odpowiedź, nieoczekiwaną paginację, `401`, `403`, `429`, anulowanie w kolejce i przy odczycie oraz spóźniony wynik. Sprawdź błędy zapisu konfiguracji, duplikaty dodane podczas podglądu i zachowanie dotychczasowych filtrów przy każdej awarii. Przetestuj przydatność diagnostyki, awarię logowania zdarzeń i brak syntetycznych sekretów w plikach logów.
  - [x] W ServiceNow porównaj podgląd z Ulubionymi na zwykłym koncie. Potwierdź import przy włączonym i zatrzymanym monitoringu, jedną kartę, brak mignięcia przy aktywnej sesji oraz brak automatycznego włączania importowanych filtrów. Jeśli dostępne jest puste konto, sprawdź też pustą odpowiedź. Zapisz wynik rzeczywistej próby i jej ograniczenia osobno od regresji lokalnej.
  - [x] Zaktualizuj architekturę, opis integracji REST, kontrakt importu i `AGENTS.md`. Dodaj decyzję o źródle odczytu i oznacz jako zastąpione tylko odpowiednie ustalenia dawnych decyzji. Potwierdź wyszukiwaniem brak wywołań starego czytnika, uruchom regresję i przenieś plan do zakończonych.

  **Regresja Windows.** Wszystkie 68 modułów zakończyło pracę w osobnych procesach z izolowanymi danymi. Z 507 testów zaliczono 505 i pominięto 2. Dodatkowy test duplikatu dodanego pomiędzy wyświetleniem podglądu i zapisem również przeszedł. Pełny przebieg w jednym procesie zatrzymał się, więc wyniki końcowe pochodzą z powtórzenia z izolacją modułów. [Kontrakt importu](../../kontrakty/kontrakt-importu-ulubionych.md) · [Decyzja 036](../../decyzje/036-import-ulubionych-przez-rest.md)

  **ADEO, 15 listopada 2026.** Aplikacja z osobnym profilem zwróciła 37 pozycji, w tym 34 obsługiwane, przy zatrzymanym i aktywnym monitoringu testowym. W obu odczytach zgodziło się 37 identyfikatorów, nazw, ścieżek grup oraz adresów rozwiązywanych względem instancji. Trzy adresy miały różną postać przed normalizacją. Każdy import wykonał jeden GET i korzystał z jednej karty. Pomiar widoczności okna Chromium obejmował 179 próbek bez wykrytego odsłonięcia. Pierwszy import ponownie wczytał SOW w ramach przygotowania kontekstu. Oba podglądy miały puste zaznaczenie, a ich zamknięcie zachowało konfigurację. Odczyty cykliczne w próbie były syntetyczne, a zapis wybranych filtrów i przypadek pustego konta zweryfikowano w testach lokalnych.
