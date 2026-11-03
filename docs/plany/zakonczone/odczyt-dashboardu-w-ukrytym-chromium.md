# Plan: pełny odczyt dashboardu w ukrytym Chromium

> Zakończony plan i historia wdrożenia, nie bieżąca lista zadań. Aktualny status, lokalny build 1.8.0 i pozostałe sprawdzenia: [indeks planów](../README.md). Zapisy o braku EXE dotyczą ówczesnego etapu.

Data: **1 listopada 2026**. **Status: etapy badawcze A–C zakończone; prototyp spełnia kryteria głównej serii, z ograniczeniami opisanymi w raporcie. D1–D5 wdrożone i odebrane w źródłach; pełna regresja 338 testów (1 pominięty), główna seria 44/44 i końcowe 8/8 odczytów. EXE/ZIP nie są objęte zleceniem.**

Cel: znaleźć i potwierdzić sposób odczytu wszystkich sekcji przy respektowaniu opcji ukrywania, bez pogorszenia poprawności i istotnego spowolnienia. Ręczne logowanie nadal wymaga pokazania okna.

Podstawa: [analiza 32 prób](../../archiwum/analizy/ukryte-chromium-dashboard.md), [architektura](../../architektura.md), [kontrakt](../../kontrakty/kontrakt-odczytu-dashboardu.md) i [decyzja 006](../../decyzje/006-odczyt-sekcji-dashboardu.md). Zagrożenia działały na ukrytym oknie; wszystkie 15 ukrytych prób SLA/Wstrzymanych/Wniosków kończyło się w `ready_control`. Był to stan przed badaniem A–C; późniejsze pomiary powiązały blokadę z ograniczonym renderowaniem klatek. Szczegóły i granice dowodu opisuje raport rozwiązania.

## Zasady eksperymentu

- Najpierw testy pomocnicze w osobnym tymczasowym profilu, bez zmian aplikacji, jej ustawień i przeglądarki działającego monitora. Użytkownik obsługuje logowanie; po testach przywracamy pierwotny okres i zmienione wybory, o ile można je bezpiecznie odtworzyć.
- Aktualny DOM sprawdzamy w przeglądarce Codex. Kontrolowane porównanie widoczności wykonujemy na Chromium uruchomionym dokładnie jak w aplikacji. To różne role narzędzi, nie porównywalne zegary pomiarowe.
- Jedna zmienna na próbę: widoczność, sposób interakcji lub konkretna opcja uruchomienia. Bez równoległych czytników, przesuwania okna poza ekrany i dodawania wielu flag naraz.
- Zachowujemy kompletność sekcji, potwierdzanie dat/kategorii, ochronę poprzednich danych i wspólny budżet odzyskiwania. Nie uznajemy wydłużenia timeoutów ani wyłączenia kontroli gotowości za rozwiązanie.
- Najpierw krótki test jednej kontrolki; pełna seria dopiero dla obiecującego wariantu. Utrwalony błąd tego samego rodzaju kończy dany wariant — bez kolejnych kilkunastu minut identycznych timeoutów.

## A. Ustalić dokładną przyczynę

- [x] Ponownie sprawdzić datę, popover i `Zastosuj` w kategoriach na aktualnej stronie. W Codex potwierdzono pojedynczy `DIV[role=button]` daty w `PAR-FILTER-PILL-VARIANT`, natywny przycisk kategorii w `NOW-BUTTON-BARE` oraz opóźnione pojawienie się pojedynczego panelu daty. Przyczyna ukrytego blokowania nadal wymaga pomiaru.
- [x] Rozszerzyć **wyłącznie skrypt eksperymentalny** o obserwację krótkich prób kliknięcia, zanim wspólne oczekiwanie utraci szczegóły timeoutu. Korzystać z istniejącego `readiness_facts`; nie zapisywać surowych błędów Playwright.
- [x] Zebrać przed próbą, przy pierwszym niepowodzeniu i po pokazaniu okna: obecność/włączenie kontrolki, geometrię i jej zmiany, pozycję w obszarze strony, trafianie zdarzeń w cel, widoczność dokumentu, fokus, lokalne ładowanie i ograniczony licznik klatek animacji. Wynik trafiania zdarzeń zapisywać jako kod, bez HTML lub etykiet innych elementów.
- [x] W tej samej sesji wykonać ukryte → widoczne → ukryte oraz próbę kontrolną widoczną. Przed każdą interakcją odtworzyć ten sam kontekst i stan formularza; nie porównywać już otwartego popovera z zamkniętym.
- [x] Sprawdzić osobno wpływ krótkiego `trial=True` (obecnie do 500 ms), przewijania i podmiany elementów. Dłuższa pojedyncza próba może służyć diagnozie, ale nie oznacza zgody na zwiększenie limitów aplikacji.

**Wynik etapu:** odtwarzalny przypadek i konkretny niespełniony warunek, z porównaniem przed/po pokazaniu. Jeśli przyczyny nie da się potwierdzić, zapisać brak dowodu i potrzebny pomiar; nie przechodzić od razu do przypadkowych poprawek.

## B. Porównać rozwiązania w prototypie poza aplikacją

- [x] Na podstawie etapu A wybrać najmniej inwazyjny wariant: poprawne przewinięcie/wybór właściwego elementu, oczekiwanie na rzeczywisty stan komponentu albo inna potwierdzona ścieżka jego obsługi.
- [x] Jeśli problem faktycznie dotyczy renderowania lub fokusu, przetestować pojedynczy mechanizm sterowania tym stanem w testowym Chromium. Sprawdzić natywną niewidoczność, brak przejmowania klawiatury i utrzymanie działania po nawigacji.
- [x] Inną ścieżkę ustawienia okresu/kategorii rozważyć tylko po zaobserwowaniu jej na stronie lub potwierdzeniu w dokumentacji. Nie zgadywać parametrów adresu, formatu stanu ani wewnętrznych endpointów. Nie pobierać poświadczeń ani nie poszerzać dostępu.
- [x] `force=True` lub sztuczne wysłanie zdarzenia traktować co najwyżej jako eksperyment rozdzielający przyczyny. Sam brak wyjątku nie oznacza poprawnej interakcji i nie kwalifikuje wariantu do wdrożenia.
- [x] Dla każdego wariantu potwierdzić faktyczny skutek: właściwy okres, zastosowanie wszystkich kategorii, odświeżenie i komplet właściwych liczników. Powtórzyć z zerami i niezmienionymi wartościami; nie wymagać zmiany samej liczby.

**Wynik etapu:** tabela wariantów — skutek, czas, ograniczenia i powód przyjęcia/odrzucenia. Jeżeli żaden nie przejdzie, pozostawić obecną politykę i opisać, czy potrzebna byłaby większa zmiana architektury. Tryb headless byłby osobnym wariantem z własnym testem logowania, nie dowodem dotyczącym obecnego ukrywania okna.

## C. Odbiór najlepszego wariantu

- [x] Naprzemienne serie widoczne/ukryte w tej samej konfiguracji: co najmniej 5 pełnych cykli na wariant, na dwóch uruchomieniach przeglądarki. Osobno oznaczyć pierwszy odczyt, rozgrzany cache i ręczne logowanie.
- [x] Objąć zagrożenia, SLA/WJRUW, Wstrzymane i Wnioski; ten sam i inny miesiąc, powrót do zakładki, leniwe karty, ukrycie od startu po uwierzytelnieniu oraz ukrycie po minimalizacji.
- [x] Sprawdzić odczyt po co najmniej 10 minutach ciągłego ukrycia, w tym po dłuższej bezczynności. Nie utożsamiać tego z testem wielogodzinnej pracy ani wszystkich komputerów.
- [x] Sprawdzić Stop, zamknięcie okna, utratę sesji i przekazanie do ręcznego logowania. Gdy nie da się bezpiecznie odtworzyć przypadku na żywym koncie, testować syntetycznie i wyraźnie oznaczyć brak weryfikacji rzeczywistej.
- [x] Potwierdzić, że ustawienie ukrywania jest respektowane podczas odczytu; okno może być pokazane przy ręcznym logowaniu. Próbki z takiego przekazania nie należą do czysto ukrytych pomiarów.

**Kryteria przyjęcia:**

| Obszar | Wymaganie |
| --- | --- |
| Poprawność | Każda planowa próba zwraca komplet właściwej sekcji i kontekstu; brak sztucznych zer i mieszania prób. Zmiany liczników na żywym serwisie trzeba wyjaśnić, nie uznawać automatycznie za błąd. |
| Szybkość | Mediana każdej sekcji i całego cyklu nie gorsza od widocznej o więcej niż większa z wartości **15% lub 2 s**. Osobno porównać najwolniejsze próby i ponowienia; mediana nie może ukryć nowych timeoutów. To próg praktyczny, nie dowód statystycznej równoważności. |
| Niewidoczność | Brak pokazania testowego okna i kradzieży fokusu w fazie ukrytej; potwierdzenie natywnego stanu, nie tylko `document.visibilityState`. |
| Odzyskiwanie | Zachowane ograniczone ponowienie, obsługa Stop/logowania i poprzedni poprawny wynik po błędzie. |
| Diagnostyka | Korelacja próby/etapu, przyczyna oczekiwania i wynik; bez poświadczeń, tokenów, HTML, treści zgłoszeń i wartości biznesowych liczników. |

**Wynik etapu:** rekomendacja „wdrażać”, „odrzucić” albo „brakuje dowodów”, z liczbą prób i surowymi technicznymi pomiarami w lokalnym `data/`. Nie obiecywać jednakowej szybkości na każdym komputerze.

## D. Wdrożenie — zakończone w źródłach

Plan z 1 listopada 2026 opiera się na [wynikach A–C](../../archiwum/analizy/ukryte-chromium-rozwiazanie.md) i aktualnym kodzie. Wykonanie całego D1–D5 zostało zlecone 1 listopada 2026; etapy są realizowane kolejno, z kontrolą wyniku każdego etapu. EXE/ZIP i publikacja są osobnym zadaniem.

### Docelowe zachowanie

| Sytuacja | Zachowanie |
| --- | --- |
| Ukrywanie włączone, odczyt SLA/Wstrzymanych/Wniosków/zagrożeń | Okno pozostaje ukryte; podtrzymanie renderowania działa tylko podczas potrzebnego odczytu. |
| Ukrywanie wyłączone | Obecne widoczne odczyty bez dodatkowego mechanizmu. Sama opcja minimalizacji nadal nie wymusza minimalizowania dashboardu — ten wariant nie był przedmiotem odbioru. |
| Logowanie automatyczne lub ręczne | Zachować dotychczasową ścieżkę logowania; ręczne wymaga pokazania i fokusu. Mechanizm renderowania nie pracuje na stronie logowania. |
| Ręczne „Pokaż przeglądarkę” | Pokazać okno zgodnie z poleceniem, bez natychmiastowego ponownego ukrycia przez odpytywanie. Nadpisanie pozostaje ważne do kolejnego jawnego polecenia, zmiany opcji widoczności lub nowego logowania. |
| Zmiana ustawień podczas odczytu | Zastosować przy najbliższym bezpiecznym `tick`; nie przerywać dostarczonego kliknięcia, nie otwierać drugiego czytnika. Ręczne logowanie ma pierwszeństwo. |
| Stop, zamknięcie/odtworzenie strony lub Chromium | Zakończyć mechanizm i usunąć nasłuchy; nowa strona otrzymuje nowy stan, bez odwołań do starego celu. |
| Brak obsługi lub awaria DevTools | Zgłosić określoną przyczynę, zachować ostatni poprawny wynik i jego czas. Nie pokazywać okna automatycznie wbrew opcji ukrywania. Użytkownik może wybrać „Pokaż przeglądarkę” i ponowić widoczny odczyt. |

### D1. Mechanizm podtrzymania renderowania i jego cykl życia

- [x] Wydzielić mały komponent, np. `browser_rendering.py`, zarządzany przez `BrowserRuntime` w istniejącym workerze. Jeden aktywny mechanizm na stronę; start/stop idempotentne. Bez nowych wątków Playwright i bez kopiowania laboratoryjnego sterownika.
- [x] Przenieść wyłącznie sprawdzony wariant: lokalny `Page.startScreencast`, JPEG jakość 0, maksymalnie 1×1, co 60. klatkę. ACK bez dekodowania, przechowywania lub zapisywania obrazów; bez kolejki ramek i pracy w bezczynności między odczytami.
- [x] Uruchamiać po potwierdzeniu uwierzytelnienia i właściwego originu/ścieżki/ID dashboardu, ale **przed** oczekiwaniem gotowości kontrolek zależnych od klatek. Nie uzależniać startu od działającego już przycisku daty. Istniejąca nawigacja ma doprowadzić do celu także z listy lub strony po logowaniu.
- [x] Zatrzymywać przy wyjściu z dozwolonego kontekstu, żądaniu logowania, błędzie ACK, zamknięciu celu, Stop i końcu odczytu (`finally`). Sprzątanie nie może przykrywać pierwotnego błędu. Sprawdzić dostępność polecenia na Chromium dostarczanym z aplikacją.

**Odbiór D1:** testy start/stop, nawigacji, awarii CDP/ACK i odłączenia strony; brak aktywnych nasłuchów po zakończeniu. Obsługa awarii nie dodaje własnej pętli ponowień.

### D2. Potwierdzanie opóźnionego zaznaczenia kategorii

- [x] Wspólną obsługę w `dashboard.py: ensure_all_categories` rozszerzyć o potwierdzenie stanu po dokładnie rozpoznanym błędzie `check` oznaczającym brak zmiany po kliknięciu. Nie przechwytywać w ten sposób innych wyjątków.
- [x] Obserwować zaznaczenie i brak stanu pośredniego, do 500 ms w pozostałym budżecie, z obsługą Stop i kontroli sesji. Nie klikać drugi raz; potwierdzenie dotyczy już dostarczonej akcji. Następnie zwykłe „Zastosuj” i dotychczasowa walidacja.
- [x] Przy braku potwierdzenia zachować rzeczywisty błąd i wspólne odzyskiwanie sekcji. Bez globalnej podmiany `Locator.check`, `force=True` i wydłużania budżetów.

**Odbiór D2:** stan natychmiastowy i opóźniony, prawdziwy brak zmiany, indeterminate, podmiana DOM, inny wyjątek, Stop i utrata sesji. Testy potwierdzają pojedyncze kliknięcie oraz rozróżnienie błędu naprawionego i końcowego.

### D3. Integracja z widocznością, odczytami i odzyskiwaniem

- [x] W `browser_policy.py` zastąpić bezwarunkowe pokazywanie dla aktywności `dashboard` polityką z powyższej tabeli. `login` nadal obsłużyć osobno. Sprawdzić obsługę poleceń zasobnika, w tym obecne odraczanie „Ukryj” poza filtrami.
- [x] W `app.py` podłączyć cykl życia komponentu do wszystkich wejść: start monitoringu, „Sprawdź teraz”, ręczna aktualizacja dashboardu/zagrożeń, harmonogram i wtrącenie zagrożeń między filtrami. Przejście do filtrów kończy mechanizm; nie zmienia terminów sprawdzania.
- [x] Zachować jednego właściciela odzyskiwania (`section_runner.py`), istniejący aktywny budżet 60 s i osobne oczekiwanie na logowanie. Po odzyskaniu odtworzyć kontekst, opcje widoczności i mechanizm dla aktualnej strony.
- [x] Zachować kompletność wyniku, WJRUW z jednego zestawu, poprzednie dane po błędzie, blokowanie przycisków i dotychczasowe statusy/postęp. Nie dodawać powiadomień o zagrożeniach ani równoległego odczytu.

**Odbiór D3:** macierz ukrywanie/minimalizacja/ręczne nadpisanie/logowanie; zmiany opcji w trakcie i między odczytami; zamknięcie i odtworzenie Chromium. Sprawdzić, że po błędzie CDP ręczne pokazanie umożliwia nowy widoczny odczyt bez restartu aplikacji.

### D4. Diagnostyka od pierwszego etapu

- [x] Już w D1–D3 dodawać zdarzenia do wspólnego `LoginDiagnostics`, jego list dozwolonych pól i korelacji uruchomienie/operacja/sekcja/próba. D4 jest przeglądem kompletności, nie odłożeniem logowania na koniec.
- [x] Rejestrować start, wynik, przyczynę zatrzymania/odmowy startu, czas, zmianę polityki widoczności, brak obsługi API, błąd ACK/sprzątania i naprawione opóźnione zaznaczenie. Przydatne pola: tryb, aktywność, kod przyczyny, liczba ramek/ACK i ich łączny rozmiar. Podsumowanie na koniec zamiast wpisu dla każdej ramki lub `tick`.
- [x] Nie zapisywać obrazów, danych ramek, HTML, pełnych URL, zawartości formularzy, liczników biznesowych ani sekretów. Testować brak syntetycznych poświadczeń/tokenów w zwykłych i błędnych ścieżkach oraz odporność na awarię samej diagnostyki.

**Odbiór D4:** log wyjaśnia, czy przyczyną była nawigacja, gotowość kontrolki, DevTools, kategoria, logowanie czy anulowanie; błędy sprzątania nie zastępują pierwszej przyczyny.

### D5. Testy integracyjne i odbiór źródeł

- [x] Rozszerzyć istniejące testy widoczności, kontrolek, diagnostyki i odzyskiwania; testy nowego komponentu obejmują kontrakt zdarzeń CDP i sprzątanie. Uruchomić pełny zestaw testów aplikacji po integracji.
- [x] Przed odbiorem potwierdzić aktualną stronę w Codex. Na osobnym Chromium aplikacji powtórzyć minimum 5 pełnych cykli widocznych i 5 ukrytych, w dwóch uruchomieniach, z tym samym i innym miesiącem. Objąć wszystkie cztery sekcje, leniwe karty i zaznaczanie kategorii; zachować wszystkie nieudane próby.
- [x] Sprawdzić co najmniej 10 minut ciągłego ukrycia, odczyt po bezczynności/minimalizacji, opcje zmieniane podczas pracy i ręczne „Pokaż”. Zmierzyć natywną widoczność/fokus, czasy etapów, ponowienia i przybliżony koszt CPU; porównać z raportem A–C.
- [x] Sprawdzić rzeczywistą ścieżkę ręcznego logowania i powrotu do odczytu; wygaśnięcie sesji, zera, niezmienione wartości i wymuszone awarie testować kontrolowanie. Rozdzielić dowody rzeczywiste i syntetyczne. Przywrócić pierwotny okres/wybory i zamknąć wyłącznie testowe okno.
- [x] Odbiór: kompletne wyniki bez nowych timeoutów, brak pokazania/kradzieży fokusu w fazie ukrytej, działające Stop i logowanie, brak wycieków nasłuchów, zachowany poprzedni sukces po błędzie. Mediana każdej sekcji i cyklu nie gorsza niż widoczna o więcej niż **max(15%, 2 s)**; osobno ocenić maksima, ponowienia i CPU. Regresja zatrzymuje odbiór, nie jest naprawiana wydłużaniem timeoutów.
- [x] Dopiero po odbiorze zaktualizować architekturę i kontrakt oraz zapisać decyzję projektową z ograniczeniem do sprawdzonej wersji Chromium. Badań A–C nie przepisywać jako wyniku nowego kodu; dopisać osobny raport odbioru wdrożenia.

**Wynik D:** sprawdzone źródła i dokumentacja. Przy niespełnieniu kryteriów pozostawić problem opisany i wycofać nową politykę dla ukrytych odczytów, zachowując niezależną poprawkę potwierdzania kategorii, jeśli przechodzi testy. Nie ogłaszać gotowości EXE przed osobnym buildem i jego sprawdzeniem.

**Wynik A–C:** rekomendacja kontrolowanego wdrożenia D. Główna seria 40/40 odczytów poprawnych; dodatkowy cykl po minimalizacji 4/4. Próba ciągłego ukrycia trwała ponad 10 minut; mediana każdej sekcji i cyklu mieściła się w progu. Testy utraty sesji wykonano syntetycznie, nie przez unieważnianie konta użytkownika. Wykryto także niezależny wyścig zaznaczania kategorii; obserwacyjne potwierdzenie sprawdzono wyłącznie w prototypie. Pełne wyniki, błędy przygotowania dodatkowej serii i granice: [raport](../../archiwum/analizy/ukryte-chromium-rozwiazanie.md).

**Wynik D:** implementacja i odbiór źródeł zakończone. Szczegóły, warunki pomiarów, poprawka callbacków i ograniczenia: [raport wdrożenia](../../weryfikacja/odbior-ukrytego-dashboardu.md). Rzeczywiste odczyty po ostatniej poprawce zakończone; miesiąc przywrócony, własne sesje zamknięte, źródła niezmienione podczas odbioru. Bez zmiany wersji i budowy EXE. Następny krok wymaga osobnego polecenia: build i sprawdzenie EXE, ewentualnie późniejsze wydanie.
