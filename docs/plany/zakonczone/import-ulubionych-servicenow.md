# Import filtrów z menu Ulubione

6 listopada 2026. **Status: wdrożone w źródłach; odbiór automatyczny zakończony.** Zgodnie ze zleceniem bez buildu, podmiany EXE, nowego numeru i publikacji. Odbiór użytkowy w rzeczywistej sesji pozostaje osobnym krokiem.

## Wykonane etapy

- [x] Przed zmianą dodano regresje blokady import/monitoring i wspólnego cleanup. Dotychczasowy kod nie przechodził tych nowych scenariuszy.
- [x] Wydzielono wspólny setup profilu, guard, runtime i zamknięcie. Import używa oddzielnego zadania, bez App.start i bez wywołań odczytów lub wysyłek. Zakresowe testy: 30/30. Pełna regresja po etapie sesji: 527 testów, 2 pominięcia, bez błędów (build/favorites-session-full.json).
- [x] Zbiorczy czytnik, kontrola wyszukiwania, duplikatów drzewa, struktury i stabilności. Testy przed czytnikiem nie przechodziły; po implementacji 6/6, po rozszerzeniu 8/8. Nie ma klikania każdego linku ani odczytu parametrów komponentów/API.
- [x] Przycisk, podgląd wyboru, wyszukiwanie lokalne, grupy, typy, statusy i zapis przez obecny mechanizm. Brak początkowego zaznaczenia; nowe filtry i trzy kanały powiadomień wyłączone. Poprawiono wykryte w testach użycie API przycisku Canvas oraz właściciela timera Tk.
- [x] Testy konfiguracji i zapisu: względne linki, Unicode, niebezpieczne/obce adresy, skróty, powtarzające się nazwy, duplikaty URL, zmiana konfiguracji na dysku, rzeczywista odmowa replace na syntetycznym pliku, wycofanie pamięci i retry.
- [x] Testy sesji i UI: wspólny budżet bez resetu, wyłączenie czasu logowania, techniczne retry i logowanie w jednej operacji, ponowna potrzeba logowania, Stop podczas logowania, anulowanie podczas aktywnego wątku i podglądu, wynik starego ID, kolejność dopisywania, zachowanie wyboru po odmowie zapisu oraz serializacja bez syntetycznych sekretów.
- [x] Pełna regresja po integracji: 546 testów, 2 pominięcia, bez błędów (build/favorites-full.json). Następny przebieg z dodatkowymi regresjami ujawnił pojedynczą awarię istniejącego testu natywnej ikony Chromium; kod ikony/okna nie był zmieniany. Izolowana powtórka 5 testów okna przeszła, z 1 pominięciem fokusu (build/favorites-native-recheck.json). Dokładnej przyczyny jednorazowego błędu nie ustalono; nie ukryto go ani nie zmieniono asercji.
- [x] Powtórka pełnego przebiegu po sprawdzeniu testu natywnego: 554 testy, 2 pominięcia, bez błędów (build/favorites-final-recheck.json). Końcowy przegląd rozszerzył obsługę błędnej składni URL i odrzucanie zamkniętego panelu z zachowanym DOM; własna karta jest jawnie zamykana przed kontekstem.
- [x] Ostateczna pełna regresja zamrożonego zestawu źródeł: **555 testów, 553 zaliczone, 2 pominięcia środowiskowe (fokus Windows i niedostępny symlink)**, bez błędów modułów lub callbacków Tk (build/favorites-delivery-full.json). Nowe moduły obejmują 32 testy: sesja 4, czytnik 9, model/odzyskiwanie/UI 19.
- [x] Składnia 145 plików, pip check i diff: OK. Sumy kontrolne źródeł podczas końcowego przebiegu i niezmienność EXE/ZIP potwierdzone (build/favorites-delivery-check.json). ZIP zachowuje SHA-256 e7cfaec2f784c301c42f36640e05d137717f449caef9258b4b0a8bc736bc421e; EXE: 6a43a859d17e260f6cdab607813a8c5d9cb713aeda8632d06678d248ae126a1d.

## Rzeczywisty ServiceNow — osobne dowody

- Niezależna karta Codex; użytkownik logował się samodzielnie. Po pierwszym przekierowaniu widoczny był ekran zakończonego wylogowania; bezpieczne ponowne wejście na SOW przywróciło stronę. Nie zmieniano logiki SSO aplikacji.
- Szeroki wariant 1440×900: przypięte Ulubione udostępniają 14 pozycji głównych, 5 grup i 36 linków. Wąski wariant ma tę samą zawartość i działa przez Więcej → Ulubione albo zapamiętany ekran Ulubionych.
- Filtrowanie menu tworzy listy `.sn-polaris-nav-body.hide-scroll`, także gdy zostaje tylko jeden wynik grupowy. Czytnik wyklucza ten wariant; sama liczba korzeni nie jest wystarczającym potwierdzeniem.
- Końcowy kod zbiorczej obserwacji i kontroli struktury wykonano przez narzędzia przeglądarki: trzy identyczne migawki, 36 pozycji, 5 grup, brak błędów i brakujących dzieci, zgodność ID/nazw/href z analizą bazową. Trzy same obserwacje zajęły 143 ms; pomiar nie obejmuje odstępów 200 ms, startu sesji ani logowania.
- Oddzielnie sprawdzono bramki: liczebność dzieci, nagłówki/przełączniki, niepuste nazwy/href, unikalność ID i odwrócone metadane ARIA. Nie kopiowano danych użytkownika do repozytorium, logów ani testów. Menu zamknięto, wyszukiwanie i stan grup przywrócono, override viewportu zresetowano.

**Granica odbioru:** nie uruchamiano całego nowego okna Tk z rzeczywistym profilem ani nie przejmowano sesji monitora. Rzeczywiste dowody dotyczą DOM i logiki obserwacji w Codex; pełny przepływ Tk → worker → logowanie → podgląd sprawdzono syntetycznie, a nie jako rzeczywisty import użytkowy. Nie zapisywano rzeczywistych filtrów. Nie wykonywano nowego odbioru SSO, pustego konta lub nieznanej wirtualizacji; te warianty nie mogą być przedstawiane jako sprawdzone.

## Dostarczenie i pozostałe ograniczenia

### Naturalny rozmiar logowania i startowa pusta karta — 6 listopada 2026

Po wyłączeniu przez użytkownika wykrywania monitu zapisu hasła wdrożono pozostały zakres: usunięto stałe page.set_viewport_size przy starcie importu. Czytnik najpierw potwierdza sesję, potem obejmuje sam odczyt zakresem CDP Emulation 751×884. Finally przywraca naturalny viewport przed logowaniem, ponowieniem i zamknięciem; nie zmienia fizycznego rozmiaru okna użytkownika. Przy jawnie skonfigurowanym viewportcie wywołującego jest on zachowywany. Jedyna karta about:blank jest wykorzystywana, zamiast tworzenia drugiej. Inne zastane karty nie są przejmowane ani zamykane. Diagnostyka rejestruje etapy page/reused, viewport_read i viewport_natural, bez adresów lub danych formularzy.

Przed zmianą dodano regresje. Testy zakresowe: 39/39 (build/favorites-window-final-targeted.json), w tym naturalny viewport bez emulacji po sukcesie, błędzie technicznym, AuthenticationRequired i Stop, sprawdzenie sesji przed resize, zachowanie zastanych kart oraz faktyczna serializacja nowych etapów. Chromium przelicza viewport asynchronicznie; test oczekuje na rzeczywiste naturalne wymiary zamiast uznawać pierwszy odczyt bezpośrednio po komendzie za wynik końcowy. Składnia, pip check i diff: OK. Pełna regresja rozmiaru/kart: 566 testów, 564 zaliczone, 2 pominięcia środowiskowe (fokus Windows i symlink), bez błędów modułów lub callbacków (build/favorites-window-full.json).

Nie było dostępnej niezależnej karty Codex do ponownego odbioru rzeczywistego SSO. Nie przejmowano przeglądarki monitora i nie wymuszano wylogowania. Wymiary i przywracanie zweryfikowano w rzeczywistym Chromium 153 na izolowanych stronach; nie jest to nowy odbiór całego ServiceNow/SSO. Nie dodano oczekiwania na zapis hasła, wykrywania natywnego monitu, zmiany autologowania lub przechowywania poświadczeń. Monitoring, dane, zależności, numer 1.9.4, EXE i publikacja pozostają bez zmian. [Decyzja 023](../../decyzje/023-naturalne-logowanie-importu.md).

### Przezroczyste tło checkboxów tabeli — 6 listopada 2026

Po odbiorze wyglądu wykryto prostokątne tło grafik: obrazy App.TCheckbutton miały na stałe zapisany kolor BG, odmienny od wierszy tabeli i ich zaznaczenia. Wspólny renderer checkbox_images zachowuje dotychczasową geometrię i kolory; zwykłe kontrolki nadal otrzymują tło BG, a import używa obrazów RGBA z przezroczystym otoczeniem. Grafiki należą do okna importu i są utrzymywane przez cały jego czas życia. Nie zmieniono wyboru, sortowania, zapisu ani odczytu ServiceNow.

Regresja przed poprawką nie przechodziła. Test kontroluje faktyczny kanał alfa w narożnikach obu obrazów, nieprzezroczyste wnętrze oraz zmianę grafiki po zaznaczeniu. Testy zakresowe importu i istniejących widoków: 32/32 (build/favorites-alpha-targeted.json). Składnia, pip check i diff: OK. Pełna regresja przezroczystości: 560 testów, 558 zaliczonych, 2 pominięcia środowiskowe, bez błędów modułów lub callbacków (build/favorites-alpha-full.json). Bez nowego EXE i publikacji.

### Poprawki interfejsu importu — 6 listopada 2026

Zgłoszone: pasek przycisków znikał przy małej wysokości, nagłówki nie sortowały, a znaki Unicode zaznaczenia nie odpowiadały stylowi aplikacji. Przed poprawką trzy nowe regresje odtworzyły problemy (build/favorites-ui-polish-before.json).

Układ grid rezerwuje stałą przestrzeń dla statusu, wyszukiwania i stopki; przy zmniejszaniu okna kurczy się tabela. Minimalny rozmiar uwzględnia rzeczywiste wymiary kontrolek, a opis zawija się do aktualnej szerokości. Oba paski przewijania pozostają w obszarze tabeli. Nagłówki wszystkich kolumn przełączają sortowanie rosnące, malejące i powrót do kolejności źródłowej, ze strzałką jak w pozostałych tabelach. Sortowanie zmienia tylko kolejność wyświetlania; wybór jest nadal powiązany z identyfikatorem pozycji, a zapis zachowuje kolejność źródła. Kliknięcie nagłówka nie zaznacza wiersza, a obsługa kliknięcia wiersza chroni fokus po jego przesunięciu wskutek sortowania.

Pierwsza poprawka kolumny Wybór używała root.checkbox_images z App.TCheckbutton zamiast znaków ☑/☐; późniejszy przezroczysty wariant wspólnego renderera opisano wyżej. Nieobsługiwane wiersze nie mają aktywnego checkboxa. Zachowano obsługę klawiaturą, zaznaczenia podczas wyszukiwania oraz dotychczasowy mechanizm zapisu i diagnostykę importu; nie dodano logowania każdego sortowania lub resize.

Testy zakresowe: 24/24, w tym mała wysokość, obrazy motywu, trzy fazy sortowania, zachowanie wyboru i rzeczywiste zdarzenia kliknięcia nagłówka Tk (build/favorites-ui-polish-final-targeted.json). Kontrola wizualna na Windows: własny podgląd 750×300 z danymi syntetycznymi, widoczne wszystkie przyciski i zaznaczony czerwony checkbox. Nie uruchamiano przeglądarki ani nie zapisywano rzeczywistych filtrów; syntetyczny podgląd zamknięto, własny proces testowy zakończono. Składnia, pip check i diff: OK. Pełna regresja UI: 560 testów, 558 zaliczonych, 2 pominięcia środowiskowe (fokus Windows i symlink), bez błędów modułów i callbacków (build/favorites-ui-polish-full.json). Bez buildu, podmiany EXE, zmiany numeru lub publikacji.

### Poprawka klasyfikacji po zgłoszeniu użytkownika — 6 listopada 2026

Rzeczywiste menu potwierdziło href w postaci `incident_list.do` bez początkowego ukośnika. Importer używał urljoin względem `/now/sow/home`, tworząc nieobsługiwane `/now/sow/incident_list.do`. Wcześniejsze testy zawierały ukośnik, a obserwacja DOM nie sprawdzała tego przejścia przez klasyfikator Pythona.

Dodano regresję odtwarzającą błąd (build/favorites-bare-url-before.json), następnie zmieniono bazę rozwiązywania linków na główny adres tenanta. Zachowano pełne zapytania, widoki i dotychczasową walidację; nie rozszerzono listy obsługiwanych ścieżek. Syntetyczna strona czytnika używa teraz rzeczywistego formatu bez ukośnika i sprawdza także wynik klasyfikacji. Test obejmuje cztery typy list, deduplikację obu zapisów adresu, Unicode, nieobsługiwane strony i obcy host. Testy zakresowe: 41/41 (build/favorites-bare-url-targeted.json). Składnia, pip check i diff: OK. Pełna regresja poprawki: 556 testów, 554 zaliczone, 2 pominięcia środowiskowe, bez błędów modułów i callbacków (build/favorites-bare-url-full.json). Bez buildu i podmiany EXE. Po zmianie wymagany jest restart aplikacji źródłowej; samo ponowne otwarcie okna importu w starym procesie nie przeładuje modułu.

Wersja pozostaje 1.9.4; dist, ZIP, tag i GitHub bez zmian. Dwie prywatne notatki pozostawiono nietknięte. Funkcja wymaga przyszłego odbioru użytkowego ze źródeł; brak nowego EXE jest zamierzony. Nieznane warianty kończą odczyt bez zapisu, a nie potwierdzonym zerem. Nie ma automatycznej synchronizacji lub rozwiązywania wszystkich skrótów, migracji danych ani zmian selektorów istniejących czytników.

[Decyzja 022](../../decyzje/022-import-ulubionych-na-zadanie.md), [analiza](../../analizy/import-ulubionych-servicenow.md).
