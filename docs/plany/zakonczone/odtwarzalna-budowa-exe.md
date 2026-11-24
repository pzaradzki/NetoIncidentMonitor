# Etap 4. Odtwarzalna budowa EXE

Zbudować paczkę Windows x64 z czystego checkoutu wskazanego commitu, przy użyciu jawnych, wersjonowanych wejść. Rozpakowane EXE ma przejść próbę offline z izolowanym profilem. Odtwarzalność potwierdzą dwie niezależne budowy z tymi samymi wejściami, wersjami narzędzi i zgodną zawartością funkcjonalną paczki. Sumy SHA-256 posłużą do kontroli każdego ZIP-a i ustalenia przyczyn ewentualnych różnic między budowami. [Plan ogólny](../uporzadkowanie-architektury.md#etap-4-odtwarzalna-budowa-exe)

## 1. Stan wyjściowy

Rozpoznanie poniżej dotyczy stanu sprzed zmiany, z commitu `1e68c31`.

- [x] Ustalono źródło parametrów wbudowanych w EXE. Specyfikacja kompilowała 27 definicji z lokalnego `data/dashboard-api-kafelki.xlsx`, wybierała osiem pól i osadzała je w `defaults/dashboard-api.json`. Git ignoruje katalog `data/`. [Specyfikacja](<../../../scripts/Neto Incident Monitor.spec>) · [Reguły Git](../../../.gitignore)
- [x] Sprawdzono granicę między parametrami paczki a danymi użytkownika. W EXE lokalny JSON może nadpisać wartości domyślne. Po logowaniu aplikacja pobiera brakujące listy agentów i lokalizacji. Importer arkusza na potrzeby lokalne zapisuje także te listy. [Konfiguracja](../../../neto_incident_monitor/analytics_config.py) · [Importer](../../../tools/import_dashboard_api.py) · [Decyzja 040](../../decyzje/040-startowy-zakres-dashboardu.md)
- [x] Sprawdzono wejście do budowy. Skrypt używał istniejącego `.venv`, instalował zależności oraz Chromium i budował do domyślnego `dist/`. PyInstaller jest przypięty, a wymagania dopuszczały różne wersje Playwright, plyer i pystray. Katalogi Chromium oraz FFmpeg wybierała specyfikacja z metadanych zainstalowanego Playwright. [Skrypt](../../../scripts/build_exe.ps1) · [Wymagania aplikacji](../../../requirements.txt) · [Wymagania budowy](../../../requirements-build.txt)
- [x] Ustalono punkt odniesienia dla prób. Lokalny zestaw odczytany z `.venv` to Python 3.12.6 x64, pip 24.2, PyInstaller 6.22.3, hooks-contrib 2026.8 i Playwright 1.63.0. Jego metadane wskazują Chromium 153.0.8010.12, rewizję 1243, i FFmpeg, rewizję 1011. Wybór zestawu docelowego i zgodność z wynikiem kompilacji pozostają do potwierdzenia.
- [x] Rozpoznano istniejący odbiór paczki. `launcher.pyw --smoke-test <raport>` uruchamia Tk, sprawdza wbudowane parametry, walidację startową i uruchamia Chromium na syntetycznej stronie. Wydanie 1.11.2 dodatkowo porównano ze źródłami i sprawdzono po rozpakowaniu ZIP-a. [Launcher](../../../launcher.pyw) · [Próba offline](../../../tools/package_smoke.py) · [Przykład odbioru](wydanie-1.11.2.md)

## 2. Wersjonowane parametry dashboardu

- [x] Ustalić pochodzenie i zgodność 27 definicji. Importer zweryfikował obowiązujące warunki, a osiem pól odpowiada paczce 1.12.0-experimental.4. [Odbiór definicji](nowe-kafelki-dashboardu-sla.md) · [Importer](../../../tools/import_dashboard_api.py)
- [x] Sklasyfikować osiem pól. Wersja jest polem schematu. Pięć identyfikatorów definicji lub grup i dwie nazwy lub opisy stanowią metadane instancji. Ich wartości przechowujemy jako zewnętrzne wejście. Repozytorium zapisuje rewizję, SHA-256 oraz procedurę pozyskania. [Manifest](../../../scripts/build-inputs.json) · [Instrukcja](../../budowa-exe.md)
- [x] Wybrać kanoniczne wejście. JSON ma zamknięty zestaw ośmiu pól, klucze w stałej kolejności, kodowanie UTF-8 i końcowy LF. Źródłem są zatwierdzone definicje, a zmiana wymaga aktualizacji rewizji i SHA-256. [Decyzja 044](../../decyzje/044-odtwarzalna-budowa-exe.md)
- [x] Wyeksportować parametry z użyciem istniejącego importera. Wszystkie osiem pól i ich typy porównano z wejściem dotychczasowej specyfikacji oraz JSON-em poprzedniej paczki.
- [x] Zweryfikować listę dozwolonych pól i odrzucenie błędów. Testy odrzuciły starszą niepełną definicję, błędny format, złą sumę, powtórzone klucze oraz `assignees` i `locations`. [Test wejść](../../../tests/test_package_inputs.py)
- [x] Przełączyć specyfikację na jawne wejście z osadzaniem jako `defaults/dashboard-api.json`. Pierwsze budowy z czystych checkoutów przeszły bez katalogu `data/`. Próba bez pliku wejściowego zwróciła `dashboard_unavailable` przed utworzeniem środowiska. [Specyfikacja](<../../../scripts/Neto Incident Monitor.spec>)
- [x] Potwierdzić lokalny import i pierwszeństwo ustawień użytkownika. Import zachował istniejące syntetyczne listy. Odczyt rozpakowanego EXE sprawdzono z pustym profilem i z poprawnym lokalnym nadpisaniem. [Odbiór](../../weryfikacja/odtwarzalna-budowa-exe.md#próby-offline)

## 3. Narzędzia, budowa i raport

- [x] Ustalić wspierany zestaw Windows x64. Potwierdzono CPython 3.12.6, pip 24.2, Playwright 1.63.0, PyInstaller 6.22.3 i hooks-contrib 2026.8. [Manifest](../../../scripts/build-inputs.json) · [Wymagania budowy](../../../requirements-build.txt)
- [x] Utrwalić wersje i SHA-256 szesnastu kół bezpośrednich oraz pośrednich. Koła pobrano z PyPI. Instalacja z przypiętego katalogu i `pip check` przeszły w obu świeżych środowiskach.
- [x] Powiązać Chromium i FFmpeg z metadanymi Playwright i skrótami drzew plików. Katalogi binariów są zgodne z poprzednią paczką, a testy odrzucają brakujące pliki i niezgodne rewizje lub zawartość. [Testy](../../../tests/test_package_inputs.py)
- [x] Dostosować skrypt do jawnych wejść. Obie pierwsze budowy użyły własnego środowiska, katalogu przeglądarek oraz osobnych ścieżek wyników. [Skrypt](../../../scripts/build_exe.ps1)
- [x] Zweryfikować nieobsługiwany Python, niewłaściwą architekturę i niekompletne wejścia. Testy rozpoznają nieobsługiwany zestaw, a rzeczywista próba braku pliku kończy się kodem 1. Procedura ponowienia wymaga nowej ścieżki wyniku. [Instrukcja](../../budowa-exe.md#ponowienie-i-aktualizacja-wejść)
- [x] Zapisać raporty prób. Oba końcowe raporty zawierają commit, czystość checkoutu, wersje, skróty, etapy, czasy i wynik. Raporty niepełnych wejść zawierają stałą kategorię błędu. Raporty prób offline zapisują wyłącznie stany i nazwy nadpisanych pól. [Odbiór](../../weryfikacja/odtwarzalna-budowa-exe.md)
- [x] Sprawdzić nazwy archiwum i aplikacji oraz zawartość. W obu paczkach uzyskano takie same 1441 plików. Kontrola wykluczyła arkusz, profil, ustawienia użytkownika, bazy, cache, historię i logi. [Wynik](../../weryfikacja/odtwarzalna-budowa-exe.md#dwie-budowy)

## 4. Odbiór z czystego checkoutu

- [x] Uruchomić testy zakresowe. Zaliczone 44 z 45. Negatywne próby budowy zwróciły tylko etap i kategorię błędu. [Testy wejść](../../../tests/test_package_inputs.py) · [Analityka](../../../tests/test_analytics_api.py) · [Zakres](../../../tests/test_dashboard_scope.py)
- [x] Przygotować czysty checkout lokalnego commitu odbiorowego `48cdca6` w osobnym katalogu i zbudować pierwszego kandydata. Raport potwierdził czystość checkoutu i zgodność wejść.
- [x] Utworzyć ZIP, sprawdzić CRC oraz SHA-256 i rozpakować go w osobnym katalogu. Sprawdzono listę oraz sumy wszystkich 1441 plików z wykazem budowy.
- [x] Uruchomić rozpakowane EXE offline z pustym profilem. Potwierdzono start Tk, domyślne parametry, brak lokalnych list i użycie Chromium z paczki. [Próba offline](../../../tools/package_smoke.py)
- [x] Powtórzyć próbę rozpakowanego EXE z syntetycznymi listami. Potwierdzono obie listy i pierwszeństwo lokalnego nadpisania nazwy grupy.
- [x] Zbudować i porównać drugiego kandydata. Drugi czysty checkout i świeże środowisko dały identyczny SHA-256 ZIP-a oraz plików wypakowanych, przy tych samych wersjach i skrótach wejść. [Wynik](../../weryfikacja/odtwarzalna-budowa-exe.md#dwie-budowy)
- [x] Sprawdzić różnice i ponowić próbę offline na drugim kandydacie. Porównanie wykazało pełną zgodność. Obie próby offline drugiego EXE przeszły. [Odbiór](../../weryfikacja/odtwarzalna-budowa-exe.md#próby-offline)
- [x] Uruchomić i rozliczyć pełną regresję Windows. Zaliczone 555 z 560 testów, dwa pominięcia i trzy niepowodzenia fokusu powtórzone także na niezmienionym masterze. Zawartość Chromium i FFmpeg odpowiada poprzedniej paczce. [Wyniki i ograniczenia](../../weryfikacja/odtwarzalna-budowa-exe.md#regresja-windows)

## 5. Domknięcie

- [x] Zapisać i sprawdzić instrukcję budowy. Drugi przebieg skorzystał z opisanego źródła parametrów, przypiętych kół i zweryfikowanych binariów. [Instrukcja](../../budowa-exe.md)
- [x] Domknąć zapis decyzji i wyników. Zaktualizowano architekturę, opis REST i plan ogólny. [Decyzja 044](../../decyzje/044-odtwarzalna-budowa-exe.md) · [Raport odbioru](../../weryfikacja/odtwarzalna-budowa-exe.md)
- [x] Zamknąć checklistę po potwierdzeniu budów i prób offline. Plan przeniesiono do zakończonych, a odnośniki zaktualizowano w indeksach. Paczka służy jako lokalny kandydat odbiorowy.

## Aktualizowanie checkboxów

Oznaczać krok jako `[x]` po jego weryfikacji. Przy kroku zapisać wynik lub odnośnik do testu, decyzji albo raportu. Przy wyniku częściowym zostawić `[ ]` i dopisać konkretny brak. Przy kroku warunkowym, który nie ma zastosowania, zostawić `[ ]` z uzasadnieniem. Po każdej serii prób odnotować commit, zakres i wynik, żeby kolejna sesja mogła rozpocząć od pierwszej niezweryfikowanej czynności.
