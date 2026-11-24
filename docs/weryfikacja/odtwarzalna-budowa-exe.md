# Odbiór etapu 4. Odtwarzalna budowa EXE

## Wejścia i izolacja

Importer zweryfikował 27 zatwierdzonych definicji. Wszystkie osiem eksportowanych pól ma te same wartości i typy co wejście poprzedniej specyfikacji i plik w paczce 1.12.0-experimental.4. Próba oddzielnego lokalnego importu zachowała syntetyczne listy z istniejącego profilu. Eksport parametrów paczki odrzucił próbę zastąpienia istniejącego pliku. [Manifest](../../scripts/build-inputs.json) · [Odbiór definicji](../plany/zakonczone/nowe-kafelki-dashboardu-sla.md)

Do prób użyto 16 kół pobranych z PyPI i instalowanych w dwóch świeżych środowiskach przy włączonej weryfikacji sum. Pobieranie binariów z serwera Playwright wielokrotnie przekroczyło limit czasu. Odbiór wykonano z jawnym `-BrowserCache`. Zawartość Chromium 1243 i FFmpeg 1011 zgadzała się z poprzednią paczką i przeszła kontrolę skrótów zarówno przed skopiowaniem, jak i po pakowaniu. [Instrukcja](../budowa-exe.md)

Próba bez pliku parametrów zwróciła `dashboard_unavailable`, a próba z poprawnym składniowo plikiem o innej sumie zwróciła `dashboard_digest`. Obie zakończyły się kodem 1 podczas sprawdzania wejść. Testy syntetyczne potwierdziły też odrzucenie nadmiarowych i powtórzonych pól, niepełnej konfiguracji, niezgodnych metadanych i uszkodzonej zawartości przeglądarki. [Testy wejść](../../tests/test_package_inputs.py)

## Dwie budowy

Obie próby wykonano na Windows x64, z osobnymi, czystymi checkoutami lokalnego commitu odbiorowego `48cdca630e8002caef0193732aac3af44dc27d41`. Każdy checkout miał osobne środowisko Python, katalog binariów i ścieżkę wyniku. Obie paczki zawierają 1441 plików, a ich sumy SHA-256 są identyczne.

```text
2954593654071f6debae177efa9977228d15238e86a006563db77b547f0d12c8
```

Raporty budowy wskazują ten sam commit, pakiety, rewizje i skróty wejść. Czasy na tym stanowisku wyniosły odpowiednio 100,81 s i 100,83 s. Manifesty i ZIP-y zapisano lokalnie w `build/s4/final-a` i `build/s4/final-b`. Wersja zapisana w źródłach kandydata to `1.12.0-experimental.3`.

W obu ZIP-ach sprawdzono CRC, listę i sumy plików z wykazu budowy. Po rozpakowaniu ponownie policzono SHA-256 wszystkich 1441 plików. Wyniki odpowiadały wykazom i były identyczne między budowami. Wykazy obejmują m.in. EXE, zasoby, biblioteki, binaria przeglądarki i osadzony plik parametrów. Kontrola wykluczyła arkusz, ustawienia użytkownika, bazy, historię, cache dashboardu, logi i profile Chromium. Lokalny wynik porównania znajduje się w `build/s4/acceptance.json`.

## Próby offline

Każde rozpakowane EXE uruchomiono dwa razy z osobnym `LOCALAPPDATA`. Wszystkie cztery próby zakończyły się sukcesem. Pusty profil korzystał z wbudowanych parametrów, a test potwierdził brak list zakresu. Profil z danymi syntetycznymi zachował obie listy i potwierdził pierwszeństwo lokalnej nazwy grupy. Przeprowadzone próby potwierdziły start Tk, walidację konfiguracji i testową stronę w dołączonym Chromium 153.0.8010.12 z kartą w trybie offline. Profil testowy nie wymagał dostępu do współdzielonego katalogu binariów. [Próba offline](../../tools/package_smoke.py)

Rewizje i zawartość binariów odpowiadają paczce 1.12.0-experimental.4. Kod działania sesji pozostał ten sam, więc warunkowy odbiór zmienionego Chromium na ADEO nie miał zastosowania. Raport opisuje budowę i próby offline na danych syntetycznych.

## Regresja Windows

Próba zakresowa zaliczyła 44 z 45 testów. W pełnej regresji commitu odbiorowego zaliczono 555 z 560 testów. Trzy nie przeszły, dwa pominięto, a Tk nie zgłosiło błędów callbacków. Pominięto próbę dowiązania symbolicznego w resecie oraz test pasywnego pokazywania Chromium, gdy Windows nie przyznał pierwszego planu oknu testowemu.

Trzy niepowodzenia dotyczyły odsłonięcia monitora, aktywacji Tk po ukryciu Chromium i fokusu dialogu zapisu hasła. Powtórzenie każdego testu osobno na commicie odbiorowym i na niezmienionym masterze `1e68c31` dało takie same niepowodzenia na tych samych asercjach fokusu. Narzędzie pulpitu dwukrotnie zgłosiło `failed to activate captured window` także dla osobnego okna kontrolnego. Odbiór budowy i cztery próby offline zakończyły się poprawnie, a natywna aktywacja pozostaje ograniczeniem weryfikacji na tym pulpicie. [Testy sesji](../../tests/test_shared_session.py) · [Runner regresji](../../tools/run_regression.py)

Końcowy przebieg zapisano w `build/s4/regression-full.json`. Wyniki powtórzeń są w `build/s4/native-retry.json` i `build/s4/baseline-results/native-retry.json`. [Zakończony plan](../plany/zakonczone/odtwarzalna-budowa-exe.md)

**Ponowienie na aktywnym pulpicie.** Trzy wcześniejsze niepowodzenia fokusu ponowiono osobno na źródłach etapu 4 z tym samym przypiętym środowiskiem. Wszystkie trzy testy zaliczono, w tym odsłonięcie i ponowną aktywację monitora, fokus Tk po ukryciu Chromium oraz fokus dialogu zapisu hasła. Wynik zapisano lokalnie w `build/e5-focus-d17a1719/native-retry.json`.
