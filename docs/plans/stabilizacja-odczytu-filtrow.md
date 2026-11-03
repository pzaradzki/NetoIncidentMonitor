# Stabilizacja odczytu filtrów INC / REQ / RITM / SCTASK

Data: **2 listopada 2026**. **Status: zatwierdzony, częściowo wdrożony w źródłach.** Podstawa: [audyt F1–F12](../analyses/filtry-odczyt-audyt.md), [architektura](../architecture.md), decyzje [001](../decisions/001-watki-i-kolejki.md), [003](../decisions/003-poprawnosc-i-aktualnosc.md), [004](../decisions/004-bezpieczna-diagnostyka.md) i [005](../decisions/005-kompletny-odczyt-listy.md). To nowe prace po historycznej [stabilizacji paginacji](completed/stabilizacja-paginacji.md), nie ponowne otwarcie tamtego zakończonego planu.

## Checklista postępu

Zaznaczone punkty opisują wykonany zakres. Wdrożenie i odbiór mają osobne pola.

- [x] **A.** Sprawdzić strukturę list ServiceNow i przygotować przypadki testowe.
- [x] **B.** Sprawdzać warunki, widok, typ zgłoszenia i kompletność stron. Odrzucać niepotwierdzoną pustkę.
- [x] **B.** Odrzucać anonimowe tabele bez metadanych zakresu.
- [x] **C.** Ponawiać odczyt z nowym buforem po zmianie kolumn. Zachować zgodność zapisanych szablonów REQ.
- [x] **D.** Zapisywać historię i obecność w jednej transakcji SQLite. Sprawdzić wycofanie zapisu po błędzie i migrację danych syntetycznych.
- [x] **D.** Przenieść czyszczenie historii i oznaczanie przeczytania poza wątek interfejsu.
- [x] **D.** Sprawdzić migrację na kopii rzeczywistych danych. Zachowano 933 wpisy historii i stan 9 filtrów.
- [x] **D.** Sprawdzić zapis i błąd zapisu w testach interfejsu oraz oczekiwanie na obie kolejki przy zamykaniu z atrapą okna.
- [x] **E.** Dodać zapis zadań i przejścia stanów alertu w SQLite.
- [x] **E.** Sprawdzać ustawienia przed wysyłką każdej części i raportować częściową awarię.
- [x] **E.** Podłączyć trwałą kolejkę do odczytu i nadawców. Zapisywać stan zadania i anulować wysyłkę po wykryciu zmiany adresu odbiorcy.
- [x] **E.** Wznawiać oczekujące zadania po restarcie. Wstrzymywać ponowienie wysyłki o niepewnym wyniku. Sprawdzono ponowne otwarcie bazy i częściową awarię na atrapie.
- [x] **E.** Zapisywać niezależną wersję ustawień powiadomień i porównywać ją przed wysyłką.
- [x] **F.** Powiązać wyniki z przebiegiem monitoringu i wersją filtra. Zachować budżet odczytu przy ponowieniu i logowaniu.
- [x] **F.** Sprawdzić limity i zatrzymanie w lokalnym zestawie testów paginacji, dużych list i monitora.
- [x] **G.** Zakończyć pełne odczyty INC, SCTASK, REQ i RITM na danych rzeczywistych na wersjach roboczych.
- [x] **G.** Wykonać końcowy odbiór na jednej wersji kodu, w tym restart, zmianę odbiorcy i awarię po wysłaniu części wiadomości.

## Cel i granice

Kompletny, potwierdzony odczyt właściwego filtra; spójna historia i obecność; kontrolowana wysyłka; rozpoznawalna przyczyna każdego niepowodzenia. Zachować działające mechanizmy i poprawić luki wskazane w audycie, bez przepisywania całej aplikacji.

Nie obejmuje dodania SMTP, wdrożenia listy/powiadomień zagrożeń, równoległych kart/workera ani przebudowy SSO. Wspólne mechanizmy mają umożliwić późniejsze wykorzystanie, ale nie aktywować przyszłych funkcji. EXE/ZIP/publikacja dopiero na osobne polecenie. Zlecenie przygotowania dokumentu nie upoważnia do wdrożenia.

**Zachowanie do utrzymania:** pierwszy poprawny odczyt zwykłego filtra jest cichym baseline; obecność, `ever` i `first_only` pozostają rozdzielone; powrót po potwierdzonym zniknięciu może powiadamiać zgodnie z opcjami. Błąd/partial/anulowanie nie oznacza zniknięcia. Zachować per-filtr ustawienia kanałów, szablony, linki nawigacyjne/skróty, historię, przeczytanie, kolejność i układ kolumn, domyślne sortowanie numerów oraz porcjowane UI. Zagrożenia nadal mają własną politykę.

## Przebieg docelowy

`żądanie z ID i generacją monitoringu → potwierdzenie celu → próba odczytu ze świeżym buforem/schematem → kompletność → kandydat → zatwierdzenie historii/obecności/intencji → publikacja UI → przekazanie do transportów → potwierdzenie wyniku`.

Granica zatwierdzenia jest jednoznaczna: Stop przed nią odrzuca kandydata; Stop po niej nie cofa danych na dysku. Nie rozpoczęte wysyłki pozostają w kontrolowanym stanie. Spóźniony wynik starej generacji nie zastępuje nowszego widoku i nie uruchamia nowej wysyłki w UI.

| Etap | Wynik | Zależności / audyt | Status |
| --- | --- | --- | --- |
| A | Aktualny kontrakt strony, kontrprzykłady i infrastruktura odbioru | F1–F12, bez zmiany zachowania | Do wykonania |
| B | Potwierdzanie celu, typu, zera i kompletności | A; F1/F2/F3/F6/F9 | Do wykonania |
| C | Schemat per typ i jedno kontrolowane odzyskiwanie | B; F7/F8 | Do wykonania |
| D | Spójny trwały stan, migracja i odzyskiwanie | A/B/C; F4/F10 | Do wykonania |
| E | Trwałe intencje powiadomień i wyniki kanałów | D; F5 | Do wykonania |
| F | Budżety, koordynacja UI i pełna diagnostyka | Projektowane od A, odbiór po E; F11/F12 | Do wykonania |
| G | Odbiór wszystkich typów i dokumentacja źródeł | B–F | Do wykonania |

Po zleceniu całości realizować etapami bez potwierdzania każdej drobnej zmiany. Blokada jednej próby rzeczywistej nie wstrzymuje niezależnych testów, ale nie wolno oznaczyć jej jako zaliczonej. Nowa wiedza zmienia kontrakt/plan, nie jest podstawą do zgadywania selektorów.

## A. Przygotowanie i kontrakt odbioru

1. Przeczytać stan źródeł i niezakończone zmiany; zapisać fingerprint modułów oraz bazowy wynik testów. Nie wycofywać zmian użytkownika. Obecna baza: 86 testów zakresowych i 20 prób rzeczywistych opisanych w audycie, nie dowód nowej wersji.
2. Przenieść lokalne kontrprzykłady z `data/filter-read-audit/` do utrzymywanych testów regresyjnych z syntetycznymi rekordami. Nie kopiować rzeczywistych rekordów, HTML lub URL zawierających ich ID. Rozróżnić test potwierdzający starą lukę od testu wymagającego jej usunięcia.
3. Ponownie sprawdzić aktualny DOM wszystkich czterech list w Codex: dodatni/pusty wynik, tabelę i kontener, metadane query/widoku, numer i link, loading/error, pager. Dodatkowe obserwacje wymagane dla F1/F2/F9: możliwe przekształcenia query, pusta lista bez tabeli, ID linku i wiersza. Nie zapisywać konfiguracji ani zgłoszeń.
4. Spisać krótki kontrakt odczytu w `docs/contracts/`: wymagane dowody celu/rekordu/kompletności, różnice typów, dopuszczone warianty oraz typowane wyniki. Nie rozszerzać allowlist na niezaobserwowane ścieżki.
5. Przygotować osobny profil i runner testów natywnych, wyłączyć rzeczywiste transporty i zapisy do stanu użytkownika. Dla koniecznej zmiany rozmiaru strony odczytać stan początkowy i zapewnić przywrócenie w `finally`; w razie braku uprawnień oznaczyć lukę w odbiorze.

**Odbiór A:** istnieje macierz obserwacji z datą i jawnymi brakami, odtwarzalne syntetyczne kontrprzykłady oraz scenariusze testów. Wnioski z listopadowego audytu nie zastępują świeżej inspekcji po zmianie strony.

## B. Właściwy cel i kompletne dane

**Moduły:** `service_now_urls.py`, `list_context.py`, `pagination.py`, `app.py: collect/empty_list/navigate`.

- Zdefiniować kontekst żądania: ID operacji/generacji, stabilna tożsamość filtra, typ/prefiks, oczekiwany cel po normalizacji, widok i warunki. Skutecznie rozwiązany skrót ma ten sam kontrolowany kontekst; nie zgadywać typu przed rozwiązaniem ani klasyfikować RITM jako INC na stałe.
- Oddzielić oczekiwany kontekst od obserwowanej tożsamości tabeli. Potwierdzać zgodność już na pierwszej stronie, następnie na każdej stronie i przed zatwierdzeniem. Stabilne błędne query nie może być uznane za poprawny baseline.
- Normalizować kodowanie tylko w znanych granicach, zachowywać znaczenie OR/NQ i kolejność gałęzi. Sortowanie i zakres strony odróżnić od warunków. Nie uruchamiać wyrażeń `javascript:` ani nie konstruować własnego interpretatora dynamicznych filtrów. Zaobserwowane równoważne reprezentacje query objąć testami; nieznane rozwinięcia/ACL/widok → wynik niepotwierdzony i czytelna przyczyna, nie arbitralne usuwanie warunków. Jeżeli DOM nie pozwala dowieść zgodności, zatrzymać ten wariant i uzupełnić analizę; nie udawać, że porównanie hosta wystarcza.
- Wybrać jedną główną tabelę. Gdy kontener musi obejmować body, dodatkowo powiązać pager/komunikaty z identyfikatorem głównej listy; nie akceptować pustej listy powiązanej lub komunikatu obcego widżetu. Niejednoznaczność odrzucić.
- Prawidłowe zero wymaga konkretnego dowodu dla żądanego celu (np. potwierdzone metadane total=0 i zgodny pusty stan). Brak tabeli, odmowa dostępu, placeholder i nieznany dokument nie tworzą `{}`. Ewentualny prawidłowy wariant bez tabeli musi mieć osobny, obserwacyjnie potwierdzony kontrakt.
- Wiersz musi odpowiadać typowi: INC/incident, SCTASK/sc_task, REQ/sc_request, RITM/sc_req_item. Walidować numer i ID z właściwej komórki/wiersza. Link: zaufany tenant, właściwa ścieżka i zaobserwowany format ID/parametrów; bez dowolnych akcji w query. Nie wyprowadzać `sys_id` z numeru. Gdy dane pozwalają potwierdzić rekord, ale nie link, zachować tekst bez klikalnego odnośnika i oznaczyć degradację; gdy nie da się potwierdzić samego rekordu, odrzucić wynik, nie pomijać wiersza.
- Zachować ciągłość zakresów, total/size, brak duplikatów i ponowną kontrolę po callbackach. Jawnie rozpoznany wariant unpaginated jest dopuszczalny; brak metadanych/pasującego selektora nie jest takim dowodem. Nie ucinać dużej listy do limitu bez komunikatu.

**Testy B:** różne query przy tym samym host/path; OR/NQ/dynamic, opakowany URL/skróty; obcy typ i prefiks, błędny/brakujący ID, link obcego hosta; dwie tabele i obce pagery; pusty sibling przy braku głównej listy, error z pustym komunikatem; nieznany pager; ciągłość 20/100, krótka ostatnia strona, duplikaty i zmiany total/query. Odbiór: kontrprzykłady F1/F2/F3/F6/F9 odrzucone bez zapisu lub powiadomień, a potwierdzone warianty realnych list nadal działają.

## C. Schematy, opcjonalne pola i ponowienia

**Moduły:** `columns.py`, kolektor w `app.py`, `pagination.py`, profile kolumn i szablony.

1. Rozdzielić techniczny klucz pola, etykietę i indeks komórki. Wymagane są dowody tożsamości rekordu; krótki opis, osoba, priorytet i daty są opcjonalne zależnie od widoku. Zachować dowolne widoczne kolumny i dot-walki w `_values`.
2. Udokumentować mapowanie per typ. REQ `request_state` zachować jawnie jako stan wniosku; RITM `stage` jako etap, nie automatycznie `state`. Zgodny alias w UI/szablonie dopuścić tylko z zachowaniem znaczenia i dotychczasowego klucza. Nie zmieniać bez migracji zapisanych szablonów/wyborów kolumn. SCTASK `state` i `request_item.state` pozostają odrębne.
3. Wprowadzić typowany błąd zmiany schematu. `read_all` nadal jest jedynym właścicielem najwyżej dwóch prób; kolektor nie ma własnego retry. Każda próba otrzymuje nowy bufor rekordów i nowy `ColumnDiscovery`; po niepowodzeniu pierwszy schemat nie zanieczyszcza drugiego.
4. Reordering kolumn bez zmiany identyfikacji obsłużyć przez ponowne mapowanie indeksów. Zmiana zestawu/niejednoznaczność w trakcie odczytu unieważnia próbę; kontrolować również etykiety i mapowanie, nie tylko set kluczy. Publikować profil i dostępność dopiero z końcowym wynikiem. Nie zerować preferencji użytkownika z powodu nieudanego odczytu.

**Testy C:** zmiana schematu na drugiej stronie → jedna nowa próba od początku; po jej sukcesie wyłącznie nowy schemat/dane; drugi błąd → poprzedni wynik UI. Rzeczywiste minimalne nagłówki REQ/RITM bez `short_description`, opcjonalne braki, dwa pola o tej samej etykiecie, dot-walk, zmiana etykiet/języka, reordering. Odbiór: brak zwykłego RuntimeError udającego retry, brak zgadywania wartości i brak regresji zapisanych szablonów.

## D. Jedna granica trwałego zatwierdzania

**Moduły:** `history.py`, `filter_state.py`, koordynacja `_monitor_browser`, `drain`, ścieżki danych. Dopuszczalny nowy wspólny moduł repozytorium stanu — uzasadnienie: dwa osobne pliki nie pozwalają spełnić F4 przez samą kolejność rename.

**Preferowany wariant do prototypu:** jeden wersjonowany dokument stanu filtrów, obejmujący historię, presence/ever, generację zatwierdzenia i intencje wysyłki. Wykorzystać obecny wzorzec zapisu do pliku tymczasowego i replace oraz fasady `History`/`FilterState`; nie utrzymywać dwóch źródeł prawdy. Przed wyborem zmierzyć koszt dużej historii. Jeżeli pełna serializacja nie spełnia odbioru responsywności/wydajności, wybrać repozytorium transakcyjne SQLite ze standardowej biblioteki, zachowując te same fasady. Ten wybór zamknąć w ADR przed migracją, nie wdrażać równolegle dwóch backendów ani prowizorycznych dual-write.

1. Repozytorium otrzymuje kompletny kandydat i w jednej serializowanej operacji oblicza arrivals, aktualizuje historię i presence/ever oraz tworzy intencje zgodne z cichym baseline i `first_only`. Używa najnowszego zatwierdzonego stanu, nie starej kopii UI. Stabilny commit ID chroni przed ponownym zastosowaniem tej samej operacji.
2. Zapisać nową generację trwale, a dopiero po sukcesie opublikować niezmienny snapshot pamięci i zdarzenie UI. Błąd zapisu nie zmienia opublikowanego stanu i nie uruchamia wysyłki. Wymagania flush/synchronizacji i odzyskiwania określić dla wybranego backendu; nie obiecywać odporności na utratę zasilania na podstawie samego replace.
3. Odczyty UI korzystają z ostatniego snapshotu bez czekania na I/O. Mutacje przeczytania/wyczyszczenia historii muszą przechodzić przez ten sam model synchronizacji; żadnego obejścia repozytorium. Jeśli zapisy są odroczone poza Tk, wynik wraca istniejącą kolejką; nie pokazywać sukcesu przed potwierdzeniem.
4. Czyszczenie historii nie zeruje obecności ani `ever`, nie tworzy nowych alertów dla nadal obecnych rekordów. Nie tworzyć przy tej okazji nowej semantyki aktualizowania pól historycznych ani nowych kontrolek. Stare wyniki kolejek filtrować po generacji/ID i istnieniu aktywnego filtra; zmiana kolejności filtrów nie zmienia ich tożsamości.
5. Walidować wersję, typy, integralność i rozmiary stanu przed użyciem. Brak pliku przy pierwszym uruchomieniu i uszkodzony istniejący plik są różnymi przypadkami. Kontrolowane odzyskanie ze sprawdzonej kopii albo czytelny stan wymagający pomocy; bez cichego czyszczenia baseline, nadpisywania uszkodzonego pliku i zalewu alertów.

### Migracja i możliwość wycofania

- Wykonać prywatną lokalną kopię dotychczasowych plików, bez logowania ich zawartości i bez dołączania do repo/EXE. Sprawdzić obecność innych procesów korzystających ze stanu; migracja nie może pracować równolegle z dawnym monitorem.
- Wczytać i zwalidować historię, presence/ever oraz obsługiwane stare formaty. Zachować tożsamość filtra po istniejącej normalizacji URL, przeczytanie, daty, nazwy, dane historyczne i istniejący baseline. Rozbieżności istniejących plików odnotować; nie wnioskować, że każdy wpis historii jest obecnie obecny.
- Brak starej obecności przy istniejącej historii nie upoważnia do odtworzenia jej z historii. Pierwszy nowy kompletny odczyt ustanawia cichy baseline dla takiego niepotwierdzonego filtra, z zachowaniem historii i jawnie opisanym stanem odzyskiwania.
- Nowy dokument/baza tworzony obok źródeł, zweryfikowany i atomowo oznaczony jako aktywny. Przerwanie migracji musi pozwolić wznowić ją idempotentnie. Po przełączeniu jedynie nowy magazyn przyjmuje zapisy; stare pliki to kopia, nie aktywne repliki.
- Nie uruchamiać starego EXE na nowym magazynie bez procedury wycofania. Powrót do kopii oznacza utratę późniejszych zmian; po nowych commitach potrzebny kontrolowany eksport do zgodnego formatu. Nie obiecywać automatycznego downgrade ani usuwać kopii w ramach odbioru.

**Testy D:** awaria przed/podczas zapisu/replace/po publikacji, Stop w każdym punkcie, brak miejsca/uprawnień, wadliwy JSON/typ/wersja, dwie równoległe mutacje UI/workera, clear/read/reorder, przerwany restart i migracja. Po restarcie historia i presence odpowiadają jednej generacji. Testy z restartem osobnego procesu, nie tylko JSON round-trip. Duże reprezentatywne zbiory bez blokowania pętli Tk przez zapis i bez narastającej kolejki; w przeciwnym razie zamknąć zmianę backendu przed migracją.

## E. Intencje powiadomień i wynik transportu

**Moduły:** wspólne repozytorium z D, `notify_filter`, kolejka UI, `teams_notifications.py`, `google_chat_notifications.py`, Windows. Rozszerzyć istniejące transporty, nie tworzyć konkurencyjnych senderów dla filtrów i zagrożeń.

- Losowe `event_id`/`job_id`, niezależne od sekretów. Intencja powstaje razem ze zmianą presence, tylko dla nowego zdarzenia i kanałów dopuszczonych ustawieniami. Pierwszy baseline nie tworzy intencji. Samo włączenie kanału później nie odtwarza całej historii.
- Zalecana polityka: zadanie na pewno nierozpoczęte może zostać podjęte po restarcie. Zadanie rozpoczęte bez trwałego potwierdzenia ma wynik **niepewny**, bez automatycznego ponownego wysłania. Przyjęte kanały/części nie są powtarzane; jawnie odrzucone i pełna kolejka mają oddzielny stan. Brak cyklicznego ponawiania wszystkich nowych INC. Ostateczne zasady ponawiania znanych odmów uzgodnić przed aktywacją E.
- `submit` zwraca potwierdzenie przyjęcia lub odmowę, a wynik zawiera job ID i kanał/część. Rozróżnić: prepared, queued, sending, accepted, rejected, uncertain, paused/cancelled. „Accepted” HTTP/SMTP oznacza przyjęcie przez usługę, nie przeczytanie przez człowieka. Windows ma własny poziom potwierdzenia wywołania, nie udaje ACK webhooka.
- Intencja utrwala wyłącznie potrzebne dane zdarzenia i dozwolonego kanału; żadnych sekretów, cookies lub pełnych webhooków w nowym magazynie. Przed wysłaniem ponownie sprawdzić aktywność kanału/filtra i wersję konfiguracji miejsca docelowego (ID wersji niezależne od sekretów). Zmiana odbiorcy/endpointu nie przekierowuje dawnych zadań po cichu; zadanie wstrzymać lub anulować z czytelną przyczyną.
- Ograniczyć kolejkę i rozmiar intencji; nie usuwać cicho niewysłanych wpisów po przekroczeniu limitu. Ustalić jawne przechowywanie/porządkowanie zakończonych wpisów przed implementacją. Wyłączenie monitoringu hamuje nowe wysyłki, lecz zachowuje informacje o już rozpoczętych i przyjętych.

**Testy E:** restart między commit a enqueue, pomiędzy częściami i po przyjęciu przed zapisem ACK; kolejka pełna; jeden kanał poprawny/drugi błędny; zmiana opcji/konfiguracji, filtr usunięty lub wyłączony, uszkodzony stan intencji. Mockowane transporty, bez prawdziwych webhooków. Osobne regresje baseline/first_only/powrót i szablonów. Odbiór nie wymaga gwarancji exactly-once, której zewnętrzne usługi nie zapewniają.

## F. Budżety, UI i diagnostyka całej operacji

Projektować i testować od A, nie dodawać logów dopiero po zakończeniu implementacji.

- Reużyć `read_budget`, `browser_actions.checkpoint`, `BrowserRuntime`, `RefreshControl` i pojedynczy worker. Jeden aktywny budżet obejmuje nawigację, obie próby, obserwacje i paginację; oczekiwanie na ręczne logowanie/zgodę liczyć osobno. Nie zerować aktywnego kosztu po każdym wznowieniu SSO. Obecne wartości 15 s/1800 s traktować jako bazę, zmiany uzasadniać pomiarami.
- Każda obserwacja/akcja ma lokalny timeout ograniczony pozostałym budżetem i checkpointy. Bez globalnego `networkidle`, nieograniczonego `evaluate` i ponawiania niepewnego „Dalej”. Kliknięcie może być zakończone niepewnie; odbudowa od pierwszej strony nadal należy do jednego właściciela retry.
- Podczas dużej listy/promptu/logowania obsługiwać Stop i polecenia okna. Stop przed commit nie publikuje wyniku; zamknięcie przeglądarki korzysta z istniejącej ograniczonej ścieżki odtworzenia. Nie włączać rendererów dashboardu/SSO dla klasycznych list tylko z powodu tej przebudowy.
- Przenosić `operation_id`, `read_id`, attempt, generację monitoringu i commit/event/job ID przez wszystkie etapy. Unikać identyfikowania wyłącznie indeksem filtra, który zmienia się po reorder. W logach stosować bezpieczny alias/losowy ID, nie URL, nazwę filtra, numer INC lub wartości komórek.
- Zdarzenia: żądanie/rozpoznanie kontekstu, obserwacja i etap strony, kompletność, discard/retry, oczekiwanie/wznowienie, start/wynik commit/migracji/odzyskania, publikacja lub odrzucenie starego UI, przyjęcie/wynik kanału, koniec całej operacji. Rejestrować czasy aktywne/oczekiwania, zakresy/liczniki, limity, pierwszą przyczynę i końcowy wynik.
- Zaktualizować allowlisty i testy faktycznie zapisywanych pól. Nie logować polli ani treści wiadomości, adresatów, ścieżek profilu i wartości formularzy; brak sekretów sprawdzać syntetycznymi znacznikami również przy wyjątku i awarii rotacji. Awaria loggera nie zmienia wyniku czytnika/zapisu.
- UI rozróżnia co najmniej: aktualizacja, oczekiwanie na użytkownika, niepotwierdzony/niepełny odczyt, brak dostępu, błąd zapisu i problem kanału. Ostatni dobry wynik pozostaje z niezmienioną datą sukcesu. Awaria wysyłki nie oznacza błędu odczytu; `pagination_complete` nie oznacza ukończenia całego filtra.

**Odbiór F:** w teście blokowanych/opóźnionych działań Stop i polecenie Pokaż są obsługiwane w kontrolowanych punktach bez czekania na pełny 15-sekundowy prompt. Zmierzyć realne opóźnienia; nie obiecywać przerwania zablokowanego wywołania Win32 lub awarii procesu w dowolnej milisekundzie. Nie spowalniać ukrytego odczytu przez przywracanie widoczności.

## G. Macierz odbioru końcowego

| Zakres | Automatycznie | Rzeczywista strona |
| --- | --- | --- |
| Każdy typ INC/REQ/RITM/SCTASK | Dodatni/zero, minimum pól i dot-walk, złe typy/linki, query/ACL/widok | Dodatni i pusty wynik, poprawne pola/linki, osobny profil |
| Paginacja | 1/20/21/100/101, krótki koniec, >1000, restore, skip/overlap, metadata/pager | Pełny wielostronicowy odczyt każdego typu, także duże REQ/RITM do końca; 20 i 100 jeśli dostępne |
| Zmiana strony | Przebudowa DOM, zmiana schematu/total/query/sort, opóźnienia, niepewna akcja | Świeża nawigacja i ponowny odczyt; bez edycji zgłoszeń |
| Sesja/ukrycie | Auth w połowie, timeout/Stop/zamknięcie, generacje | Widoczne i całkowicie ukryte; natywne próbki widoczności/fokusu, naturalne wygaśnięcie jeśli dostępne |
| Stan | Baseline/powrót/first_only, awarie commit, migracja i restart procesu | Kontrolowany profil danych testowych, bez modyfikowania historii użytkownika |
| Kanały | Kolejki/ACK/partial/uncertain, restart i zmiana opcji | Rzeczywista wysyłka wyłącznie na osobne polecenie; nie jest warunkiem regresji z mockami |
| UI/diagnostyka | Stare zdarzenia, reorder/disable/clear, duże zbiory, korelacja/sekrety/rotacja | Responsywność podczas dużego odczytu i poleceń przeglądarki |

Uruchomić regresję zakresową po każdym etapie, pełny zestaw po domknięciu B–F. Tk/Playwright można izolować modułami jak w audycie. W raporcie podać dokładną wersję/fingerprint, liczbę zaliczonych/pominiętych, czasy, sposób izolacji i ograniczenia. Zmieniające się dane porównywać z uwzględnieniem czasu; kompletność nie oznacza transakcyjnego snapshotu bazy z jednej chwili.

**Warunek zakończenia źródeł:** F1–F12 mają wskazaną poprawkę i dowód albo jawną, zaakceptowaną granicę; brak niewyjaśnionych regresji, utraty danych i niepewnego wyniku przedstawionego jako sukces. Nie zaliczać pełnej dużej listy na podstawie jej trzech stron. Brak dostępu lub scenariusza rzeczywistego odnotować i pozostawić warunek odbioru otwarty.

## Dokumentacja i przekazanie

- Uzupełnić kontrakt, ADR dla tożsamości/kompletności oraz stanu/doręczeń, raport weryfikacji i instrukcję odzyskiwania danych. Decyzje 005/004 rozszerzać lub zastępować nowym ADR z odnośnikami, zachowując powód historyczny; nie zmieniać ich po cichu.
- Architektura opisuje wyłącznie faktycznie wdrożone zachowanie. Ten plan prowadzi checklistę etapów i pozostałych testów; po odbiorze trafi do `completed/`. Audyt zachowuje historię ustaleń, a nie jest nadpisywany wynikiem późniejszej poprawki.
- Przed EXE osobno sprawdzić migrację na kopii danych i uruchomienie z nowym magazynem. Build/release wymagają odrębnego polecenia; nie publikować danych użytkownika, logów ani kopii migracyjnych.

### Decyzje do zamknięcia podczas wdrożenia

To punkty kontrolne, nie powód do pytania użytkownika o każdą czynność: rzeczywiste równoważności query i empty bez tabeli (A/B); aliasy REQ/RITM bez zmiany znaczenia (C); backend i trwałość po pomiarze (D); ponawianie znanych odmów, wiek/limit intencji i postępowanie po zmianie celu (E). Jeśli wybór zmienia zachowanie widoczne dla użytkownika lub wymaga nieautoryzowanej wysyłki/zmiany danych, przedstawić konkretny wariant do uzgodnienia. Do tego czasu stosować wynik niepotwierdzony/wstrzymany, bez cichego resetu lub ponawiania.

## Uzupełnienie po audycie stanu i ustawień

[Audyt S1–S6](../analyses/stan-i-ustawienia-audyt.md) rozszerza istniejące etapy.

- **D/F:** snapshot ustawień i rewizja filtra odczytywane jako spójna całość. Zweryfikować rewizję i Stop na granicy commit, razem z zapisem. Zachować tożsamość przy zmianie kolejności. W testach wymusić wyłącz/włącz między walidacją a zapisem oraz awarię zapisu ustawień.
- **E:** intencja trwała od commit, ale wysyłka przed pierwszym POST ponownie sprawdza Stop, filtr i wersję celu. Uzgodnić los oczekujących zadań przy Stop, zmianie kanału i zamknięciu aplikacji. Nie przekierowywać starych alertów automatycznie. Sprawdzić zakończenie nadawców, odmowę i niepewność poszczególnych części.
- **F/G:** filtrować opóźnione zdarzenia według generacji monitoringu i rewizji, również dla statusów i zakończeń. W testach wymusić zmianę kolejności, późny wynik po Stop i restarcie oraz późną odpowiedź kanału. Logować decyzję i przyczynę bez danych zgłoszeń i adresów.

Próby uzupełniające S2–S6 potwierdziły przyjęcie starego snapshotu po wyłącz/włącz, różne momenty wyboru celu alertu oraz brak informacji o częściowym doręczeniu. Rollback przełącznika i zachowanie poprzedniego CONFIG po błędzie zastąpienia pliku przeszły próby. Zachować te dwa przypadki jako regresję. Wstrzyknięte stare zdarzenie fazy potwierdza brak bariery w odbiorcy; odbiór ma dodatkowo sprawdzić rzeczywisty cykl Stop → start z kontrolowanym opóźnieniem.

## Rozpoczęcie implementacji — 3 listopada 2026

Potwierdzono na zalogowanej stronie INC tabelę w ramce gsft_main, typ i ID listy, atrybut query oraz zakres 1–10 przy rozmiarze strony 10. W źródłach odrzucono obcy typ rekordu (F3), odrzucono komunikat pustki bez powiązanej tabeli (F2) i zmapowano request_state na state w REQ (część F8). Stage RITM pozostaje odrębnym polem. Powód odrzucenia typu jest dozwolony w diagnostyce paginacji.

Przeszły cztery próby zakresowe: zły typ, komunikat pustki bez tabeli, poprawny pusty wynik i paginacja 20/100. Przeszło osiem testów istniejącego stanu filtrów. Odbiór rzeczywistych odczytów po zmianach, pozostałe walidacje i etapy C–G pozostają otwarte.

## Dalsze wdrożenie — 3 listopada 2026

- **B/C:** jawne zapytanie jest porównywane z warunkami tabeli od pierwszej strony, z zachowaniem OR i NQ. Na żywym REQ po przejściu dalej potwierdzono usunięcie końcowego EQ przez ServiceNow; porównanie ignoruje wyłącznie końcowe dyrektywy EQ i sortowania, a osobne metadane sortowania nadal identyfikują przebieg. Jawny widok jest sprawdzany na adresie ramki. Link do rekordu wymaga jednego 32-znakowego sys_id i zachowuje tylko dozwolone parametry widoku. Rozpoznana tabela klasyczna bez metadanych nie jest automatycznie traktowana jako kompletna; anonimowy wariant zgodności nadal wymaga rozstrzygnięcia. Zmiana kluczy lub etykiet kolumn odrzuca próbę, ponowienie korzysta z nowego bufora. REQ zachowuje dotychczasowy klucz szablonów i otrzymuje kanoniczną wartość stanu.
- **D:** magazyn historii i obecności działa w jednej transakcji SQLite. Próba 20 tys. wierszy uzasadniła wybór względem prototypu JSON. Stare pliki są źródłem pierwszego wczytania, a po udanym przełączeniu pozostają kopią. Potwierdzono rollback między zapisem obu zbiorów i zachowanie obecności po czyszczeniu historii. Nie wykonano migracji na danych użytkownika. [Decyzja 011](../decisions/011-transakcyjny-stan-filtrow.md).
- **F:** rezultaty i profile kolumn publikowane po commicie, zdarzenia wyników niosą rewizję filtra i generację monitoringu. Kontrola Stop i rewizji występuje również przed zatwierdzeniem transakcji. Stronicowanie i podoperacje przeglądarki dzielą budżet jednej próby odczytu wraz z retry. Diagnostyka łączy odczyt z wynikiem zapisu.
- **E:** nadawcy zgłaszają przyjęcie do kolejki i liczbę przyjętych części przy częściowej awarii. Przed każdą częścią automatycznego alertu sprawdzają zapisane ustawienia, docelowy adres, szablon oraz Stop i rewizję filtra. Nadal do wykonania trwałe intencje, niezależna wersja konfiguracji celu i trwały zapis rezultatu kanału.
- Oczekiwanie na potwierdzenie dużej listy jest poza budżetem aktywnym, a wznowienie po SSO zachowuje pozostały czas. Otwarte pozostają pomiary tych granic, asynchroniczne zapisy historii z Tk, awarie i zatrzymanie procesu oraz pełny odbiór G. Zmiany pozostają w źródłach.

### Wyniki odbioru częściowego

- 86 testów zakresowych w jednym przebiegu, w tym paginacja, kontekst i stan, ochrona danych, kanały, budżety, duże listy i diagnostyka. Dodatkowe próby uruchamiano osobno dla zmiany widoku, syntetycznych REQ/RITM bez opisu, zmiany trasy wysyłki i Stop wewnątrz transakcji.
- W osobnym testowym Chromium rzeczywiste odczyty ukryte: INC 530 rekordów na 27 stronach i SCTASK 3 rekordy na 1 stronie. Pierwsze próby REQ/RITM wykryły różnicę końcowego EQ. Po korekcie pełne przebiegi zakończyły się dla REQ (2251 rekordów na 113 stronach, 494 s) i RITM (1518 rekordów na 76 stronach, 222 s). W obu próbach brak widoczności i fokusu w próbkach okna. Próby wykonywano na migawkach kodu z odpowiednich etapów, więc nie stanowią końcowego odbioru wszystkich zmian aplikacji.
- Zapisowe próby migracji były syntetyczne i obejmowały osobny proces, zachowanie plików źródłowych, wymuszoną awarię między tabelami i anulowanie przed zatwierdzeniem. Testy transportów korzystały z atrap.

### Odbiór na aktualnym kodzie — 3 listopada 2026

- W ukrytym testowym Chromium SCTASK zakończył odczyt 2 rekordów na 1 stronie, INC 532 rekordów na 27 stronach, RITM 1519 rekordów na 76 stronach. Próbki nie wykazały widocznego okna ani przejęcia fokusu. Kontrola odcisku potwierdziła brak zmian w źródłach w trakcie testu.
- REQ dwukrotnie zmienił łączną liczbę wyników w trakcie odczytu, na stronach 55 i 84. Po pierwszej zmianie czytnik rozpoczął od pierwszej strony, po drugiej zakończył odczyt bez zwrócenia częściowego wyniku. Wynik pełnego odczytu REQ na tej wersji wymaga powtórki.
- Osobny przebieg 37 testów stanu filtrów, trwałego zapisu i kanałów przeszedł. Przypadki restartu, zmiany odbiorcy i częściowej wysyłki używały lokalnej bazy oraz atrap transportu. W połączonym przebiegu 81 testów wystąpił jeden timeout testu Teams po ostrzeżeniu Tkinter. Moduł Teams uruchomiony osobno przeszedł wszystkie 10 testów.
- Migracja kopii danych projektu zachowała 933 wpisy historii i stan 9 filtrów.

Powtórka samego REQ na niezmienionych źródłach znów wykryła zmianę listy, tym razem na stronach 30 i 26. Żadna próba nie zwróciła częściowego wyniku.

### Zamknięcie odbioru G

- Historyczna lista zamkniętych REQ z jednego dnia: pełny odczyt 120 rekordów na 6 stronach w 10,3 s. W próbkach Chromium pozostawało ukryte i nie przejmowało fokusu. Odcisk źródeł był identyczny jak w próbach INC, SCTASK i RITM.
- Wspólny przebieg interfejsu i Teams zakończył się wynikiem 23/23. Pełny zakresowy zestaw odbiorczy zakończył się wynikiem 81/81. Poprzedni timeout Teams nie powtórzył się, jego przyczyna nie została potwierdzona.
