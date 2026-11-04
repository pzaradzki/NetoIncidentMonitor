# Dashboard → incydenty zagrożone → filtry

Status: zakończone w źródłach i głównej paczce lokalnej, 4 listopada 2026. Bez publikacji.

Cel: zmienić pierwszeństwo odczytów przy starcie i pełnej aktualizacji, zachowując niezależne zakresy, terminy zagrożeń, blokady i odzyskiwanie sesji. [Decyzja 018](../../decyzje/018-kolejnosc-aktualizacji.md).

- [x] Regresje nowej kolejności przed poprawką wykazały błędy w trzech scenariuszach starego zachowania.
- [x] Zamiana kolejności w istniejącym workerze i kontroli Stop między etapami; komunikaty zgodne z rzeczywistą kolejką dashboardu.
- [x] Testy rzeczywistej koordynacji z syntetycznymi wynikami: start/all, dashboard pominięty, błąd sekcji, Stop, zaległość bez duplikatu i diagnostyka `delay_reason=dashboard`.
- [x] Zakresowa regresja: 68 testów oraz wcześniejsze 34 testy zagrożeń/harmonogramu/okresu; bez błędów.
- [x] Pełna regresja: 493 testy, 491 zaliczonych, 2 pominięcia środowiskowe, bez niezaliczonych modułów i błędów callbacków Tk. Raport: `build/order-full-tests.json`.
- [x] Osobny build PyInstaller 6.22.3 do `dist/update-order/Neto Incident Monitor/`; offline smoke UI/Chromium i walidacji startu OK na tymczasowym LOCALAPPDATA (`build/order-smoke.json`). EXE był obecny po próbie.
- [x] Na polecenie użytkownika zastąpiono główną paczkę `dist/Neto Incident Monitor/` sprawdzonym pakietem, zweryfikowano zgodność SHA-256 EXE i usunięto osobny katalog `dist/update-order`. Ponowny offline smoke głównej paczki: UI, Chromium i walidacja startu OK (`build/order-main-smoke.json`), EXE obecny po próbie.

Sprawdzono składnię 135 plików Python/PYW, `pip check` i whitespace diff. Dwa pominięcia to odmowa fokusu testowemu oknu przez Windows i brak możliwości utworzenia symlinka w teście resetu. Pozostałe próby okna i resetu przeszły. Kontrola nazw plików paczki nie wykazała konfiguracji, historii, logów ani profilu użytkownika.

Nowe testy potwierdzają też faktyczny zapis opóźnienia zagrożeń spowodowanego dashboardem: wspólny zegar syntetyczny, `delay_reason=dashboard`, `lateness_ms`, jeden odczyt po przekroczeniu terminu. Bez nowych pól diagnostyki; istniejące identyfikatory i etapy pozostają używane.

Nie zmieniano DOM/selektorów ani nie wykonywano nowego odbioru ServiceNow/SSO. Bez zmian schematów, publicznych sygnatur, zależności i numeru wersji. Bez publikacji. Główna paczka dist została zaktualizowana na późniejsze polecenie użytkownika. Świadomy kompromis: zagrożenia czekają na dashboard, także jego ponowienia lub logowanie.
