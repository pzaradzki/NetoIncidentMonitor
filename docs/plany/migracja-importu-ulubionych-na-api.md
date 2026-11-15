# Migracja importu Ulubionych ServiceNow na REST API

**Status:** plan do wdrożenia. Rozpoznanie wykonano 15 listopada 2026 r.

Akcja **Import z ServiceNow** ma pobierać Ulubione bieżącego użytkownika przez API, na żądanie, we wspólnej sesji aplikacji. Zachowujemy okno podglądu i pojedynczy zapis wybranych filtrów. Po potwierdzeniu nowego odczytu usuwamy czytnik menu wraz ze starszą ścieżką opartą na osobnym Chromium. Po każdej serii zmian zapisz wynik weryfikacji i zaznacz ukończone kroki.

## Stan wyjściowy

- `app.py` przekazuje zlecenie z `FavoritesImport` do `SharedSession`, a `favorites_worker.read_on_session()` wywołuje `favorites_reader`. Czytnik otwiera stronę SOW oraz menu Ulubione, używa Shadow DOM, tymczasowego rozmiaru strony i ukrytego renderowania. `favorites_ui.py` zawiera też starszą ścieżkę z własnym wątkiem i profilem. [Analiza menu](../analizy/import-ulubionych-servicenow.md) · [Wspólna sesja](../decyzje/025-wspolna-sesja-servicenow.md)
- `favorites.classify()` przyjmuje nazwę i adres. Obsługuje adresy względne względem instancji, sprawdza typ listy i wykrywa duplikaty po normalizacji adresu. `commit_selection()` ponownie sprawdza konfigurację i zapisuje wybrane pozycje jako wyłączone, z wyłączonymi powiadomieniami. [Dotychczasowy plan importu](zakonczone/import-ulubionych-servicenow.md)
- `analytics_api.get()` wykonuje dozwolone żądania GET na wspólnej karcie, korzystając z zalogowanej sesji. Zwraca wynik, licznik i informację o następnej stronie. Lista dozwolonych tras nie obejmuje jeszcze zakładek. [Integracja REST w aplikacji](../servicenow-api-sesja-przegladarki.md)

## Zapytanie do sprawdzenia

ServiceNow dokumentuje tabelę zakładek `sys_ui_bookmark`, odczyt tabel przez Table API oraz użycie `javascript:gs.getUserID()` w filtrze REST. Poniższe zapytanie łączy te elementy. Nazwy pól zakładki, uprawnienia zwykłego konta i zgodność wyniku z menu trzeba potwierdzić w instancji ADEO. Przy sprawdzaniu dostępu przeglądarka Codex przekierowała do logowania ADEO, więc próby z aktywną sesją jeszcze nie wykonano. [Tabela zakładek](https://www.servicenow.com/docs/r/platform-administration/data-preservation.html) · [Table API](https://www.servicenow.com/docs/r/api-reference/rest-apis/c_TableAPI.html) · [Filtry i parametry REST](https://www.servicenow.com/docs/r/api-reference/rest-api-explorer/c_RESTAPI.html)

```text
GET /api/now/table/sys_ui_bookmark
sysparm_query=user=javascript:gs.getUserID()^ORDERBYsys_id
sysparm_fields=sys_id,user,title,url
sysparm_display_value=false
sysparm_exclude_reference_link=true
sysparm_limit=10
sysparm_offset=0
```

Parametry zakoduje `URLSearchParams` w istniejącym transporcie. `user` służy do potwierdzenia właściciela, `sys_id` do sprawdzania tożsamości i kompletności rekordów, a `title` i `url` są kandydatami na nazwę i adres dla podglądu. Próba ma używać wyłącznie własnych Ulubionych i zwrócić do dokumentacji status, nazwy pól, liczbę rekordów oraz wynik porównania. Wartości pól użytkownika i treści zakładek pozostają w sesji testowej.

## Etapy

- [ ] **1. Potwierdź kontrakt w instancji ADEO**
  - [ ] W odrębnej sesji testowej poproś użytkownika o zalogowanie się na zwykłe konto z Ulubionymi. Wykonaj powyższy GET i potwierdź format `result`, znaczenie pól, działanie filtra właściciela oraz nagłówki `X-Total-Count` i `Link`. Ustal bezpieczny sposób sprawdzania właściciela na podstawie bieżącej sesji, bez zapisywania identyfikatora w konfiguracji.
  - [ ] Porównaj dane API z menu **Ulubione** na tym samym koncie. Sprawdź pozycję samodzielną i w grupie, link skrócony i pełny, pozycję spoza obsługiwanych list oraz, jeśli możliwe, potwierdzone puste konto. Ustal, czy tabela zawiera też zakładki spoza tego menu i jak je rozpoznać. Wykaż kompletność również przy więcej niż jednej stronie, obniżając limit próby.
  - [ ] Wybierz Table API, jeśli zwraca komplet właściwych zakładek na zwykłym koncie. Przy odmowie dostępu lub różnicy wobec menu sprawdź w narzędziach sieciowych, jakie odczytowe żądanie wykonuje samo menu. Rozważ tę trasę po potwierdzeniu uprawnień, zakresu bieżącego użytkownika, kontraktu i ryzyka zmiany w kolejnej wersji ServiceNow. Jeśli żadna trasa nie spełnia tych warunków, zapisz przyczynę i pozostaw istniejący importer do czasu decyzji.

- [ ] **2. Zaimplementuj odczyt i walidację odpowiedzi**
  - [ ] Dodaj wyłącznie potwierdzoną trasę do jawnej listy dozwolonych adresów. Wykorzystaj istniejący transport, sesję i kartę. Pobieraj tylko pola wymagane do walidacji i podglądu. Przy gotowym kontekście nie otwieraj menu ani strony każdej zakładki. Wspólny transport może przygotować kontekst ServiceNow na tej samej karcie, jeśli go brakuje.
  - [ ] W typowym przypadku wykonaj jeden GET. Jeśli Table API sygnalizuje kolejną stronę, pobierz ją deterministycznie w granicach budżetu importu. Ustal limit strony po próbie i sprawdzaj postęp, tożsamość rekordów, licznik oraz sygnał końca. Buduj kolejne zapytania do tej samej trasy z kontrolowanym przesunięciem. Sam rozmiar strony nie dowodzi kompletności, bo ServiceNow stosuje limit przed kontrolą dostępu. [Parametry Table API](https://www.servicenow.com/docs/r/api-reference/rest-apis/c_TableAPI.html)
  - [ ] Sprawdź strukturę i zakres właściciela przed przekazaniem danych do podglądu. Rozróżnij potwierdzone zero, brak dostępu, brak wymaganych pól i niepełny wynik. Zmiana licznika, powtarzająca się strona lub dane spoza zakresu kończą próbę bez podglądu częściowych danych. Po ponowieniu buduj wynik od początku. Poprawnie odczytane zakładki spoza obsługiwanych list nadal przechodzą przez klasyfikację jako niedostępne do importu.

- [ ] **3. Podłącz kolejkę, podgląd i diagnostykę**
  - [ ] Zachowaj zlecenie `favorites` w `SharedSession`, niezależnie od stanu monitoringu. Dopuść jeden import do zamknięcia podglądu. Po odczycie kolejka przyjmuje kolejną pracę, również gdy podgląd nadal jest otwarty. Anulowanie importu usuwa tylko jego zlecenie i unieważnia spóźnione wyniki. Zamknięcie aplikacji anuluje pracę sesji.
  - [ ] Użyj wspólnej obsługi sesji, anulowania i ograniczonych ponowień. Przy `401` lub przekierowaniu do logowania wznów odczyt po odzyskaniu sesji w dotychczasowym budżecie aktywnej pracy. `403` oznacza brak dostępu, a `429` kończy próbę bez natychmiastowego ponowienia. Zweryfikuj zachowanie po zamknięciu Chromium i utracie sesji między stronami.
  - [ ] Przekaż komplet danych jako nazwy i adresy do istniejącego podglądu. Zachowaj wyszukiwanie, wybór i normalizację adresów INC, REQ, RITM i SCTASK, w tym obsługiwane warianty skrótów. Przed zapisem ponownie sprawdź konfigurację oraz duplikaty. Zapisz zatwierdzone pozycje w jednej operacji jako wyłączone i z wyłączonymi powiadomieniami. Odczyt definicji nowo dodanego filtra należy do jego późniejszej aktualizacji.
  - [ ] Dopasuj komunikaty do źródła API oraz odróżnij pustą listę od błędu. Wspólna diagnostyka ma wiązać przyjęcie do kolejki, próby, status HTTP, liczniki stron, logowanie, przerwanie i wynik z identyfikatorem importu. Zapisuj kategorie, liczniki i czasy. Nazwy zakładek, adresy, właściciele, treść odpowiedzi i dane sesji pozostają poza logami. Awaria zapisu logów nie przerywa importu.

- [ ] **4. Usuń dawną ścieżkę odczytu**
  - [ ] Po potwierdzeniu działania REST usuń `favorites_reader.py`, selektory i zbieranie drzewa menu, zmianę rozmiaru strony oraz mechanizm stabilizacji migawek. Usuń `run_import()`, `select_import_page()` i gałąź osobnego wątku w `FavoritesImport`, jeśli przegląd wywołań potwierdzi brak innych konsumentów. Przy braku gotowej sesji użyj stanu oczekiwania lub niedostępności w interfejsie.
  - [ ] Usuń zakres `favorites` z `BrowserRuntime` i `HiddenRendering`, jego odświeżanie przy przełączaniu widoczności i pola diagnostyki używane wyłącznie przez menu. Zachowaj renderowanie logowania i odczytu definicji filtrów. Zweryfikuj współdzielone zależności, w tym `HOME`, którego potrzebują logowanie i transport REST. Usuń zbędne testy starej ścieżki po przeniesieniu testów zachowania importu na nową.

- [ ] **5. Sprawdź import i zamknij plan**
  - [ ] Na danych syntetycznych sprawdź pojedynczy GET, paginację, pełne zero, niekompletną odpowiedź, zły zakres, `401`, `403`, `429`, anulowanie w kolejce i przy odczycie oraz spóźniony wynik. Sprawdź błędy zapisu konfiguracji, duplikaty dodane podczas podglądu i zachowanie dotychczasowych filtrów przy każdej awarii. Przetestuj przydatność diagnostyki, awarię logowania zdarzeń i brak syntetycznych sekretów w plikach logów.
  - [ ] W ServiceNow porównaj podgląd z Ulubionymi na zwykłym koncie. Potwierdź import przy włączonym i zatrzymanym monitoringu, jedną kartę, brak mignięcia przy aktywnej sesji oraz brak automatycznego włączania importowanych filtrów. Zapisz wynik rzeczywistej próby osobno od regresji lokalnej.
  - [ ] Zaktualizuj architekturę, opis integracji REST, kontrakt importu i `AGENTS.md`. Dodaj decyzję o źródle odczytu i oznacz jako zastąpione tylko odpowiednie ustalenia dawnych decyzji. Potwierdź wyszukiwaniem brak wywołań starego czytnika, uruchom regresję i przenieś plan do zakończonych.
