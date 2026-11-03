# Zmiana okresu podczas aktualizacji dashboardu

2 listopada 2026, źródła i lokalny EXE 1.8.0. **Status: wdrożone i zweryfikowane w źródłach; EXE 1.8.0 nie został przebudowany.** Podstawa: [architektura](../../architektura.md), [kontrakt sekcji](../../kontrakty/kontrakt-odczytu-dashboardu.md), decyzje [001](../../decyzje/001-watki-i-kolejki.md), [003](../../decyzje/003-poprawnosc-i-aktualnosc.md) i [006](../../decyzje/006-odczyt-sekcji-dashboardu.md).

## Potwierdzony problem

1. `dashboard_ui.py: request` zapisuje `(request_id, year, month)` do kolejki. Worker `App.read_dashboard_request` odczytuje ten niezmienny okres; nie pobiera wartości zmiennych Tk podczas pracy.
2. Obie listy okresu pozostają `readonly`, co blokuje wpisywanie, ale pozwala wybierać. `App.update_refresh_controls` blokuje przyciski aktualizacji, lecz nie miesiąc/rok.
3. `period_changed` zwiększa `panel.request_id`, ukrywa postęp i oznacza wszystkie trzy sekcje jako nieaktualne. Nie anuluje pracy przeglądarki i nie zleca nowego odczytu.
4. Worker kończy poprzednie żądanie, ale `apply_result`, statusy i postęp odrzucają jego stary ID. Poprawny odczyt może więc nie trafić do kafelków ani cache. Dotyczy także Wstrzymanych i Wniosków, choć te sekcje nie zależą od miesiąca SLA.
5. Zdarzenie końca `dashboard_updating=False` nie ma ID. Może zakończyć wskaźnik aktywności pomimo odrzucenia właściwych wyników. Koordynator nadal zwalnia rezerwację po pracy; nie potwierdzono trwałego zakleszczenia lub wyjątku ServiceNow wywołanego samym wyborem daty.

**Reprodukcja offline:** rzeczywiste kontrolki Tk i `App.read_dashboard_request`, syntetyczne poprawne odczyty sekcji oraz tymczasowy cache. Oddzielnie miesiąc i rok: ID 1→2 podczas SLA, worker pozostaje przy 2026/10; wszystkie 4 późniejsze zdarzenia wyniku odrzucone, kafelki i cache zachowują stare wartości, 3 statusy „Dane nieaktualne”, postęp ukryty, kolejka nowego żądania pusta. Dowód lokalny: `data/dashboard-period-race-analysis.json`; skrypt `data/analyze_dashboard_period_race.py`. Nie zmieniono kodu aplikacji ani danych użytkownika.

Jeżeli SLA zdążyło zostać zaakceptowane przed wyborem, jego wynik może już być zapisany; odrzucane będą dopiero późniejsze zdarzenia. To wniosek z kolejności obsługi, nie osobny pomiar rzeczywistego serwisu. Powrót wyboru A→B→A też nie przywraca starego ID. Nie ma dowodu, że worker miesza miesiące w jednym odczycie — główny błąd polega na utracie zgodności UI z nadal aktywnym żądaniem.

Nie badano ponownie DOM ServiceNow: reprodukcja dotyczy lokalnego UI, nie zmiany selektorów ani filtrów na stronie. Nie przypisujemy tej przyczyny każdemu możliwemu komunikatowi „Błąd odczytu”.

## Przyjęte rozwiązanie

**Zablokować wybór miesiąca i roku od przyjęcia żądania dashboardu do jego ostatecznego zakończenia.** To obejmuje kolejkę, oczekiwanie na logowanie, ponowienie i odtworzenie Chromium, nie dopiero moment rozpoczęcia SLA. Po zakończeniu użytkownik wybiera inny okres i klika Aktualizuj. Nie dodawać automatycznego anulowania, drugiego workera ani kolejki wszystkich kolejnych zmian.

Kontrolki są `disabled` podczas tego żądania, po zwolnieniu wracają do `readonly`. Sama aktualizacja filtra/zagrożeń bez zleconego dashboardu nie musi blokować dat. Dotychczasowa wspólna blokada przycisków aktualizacji pozostaje. Przełączenie widoku nie kończy żądania ani nie zwalnia blokady.

## Etapy wdrożenia

1. **Jeden cykl życia żądania.** Wykorzystać istniejące `RefreshControl`, kolejkę i główny wątek Tk. Przechować aktywny ID oraz zamrożony okres; rozróżnić wybór kontrolek, okres żądania i okres wyświetlonego poprawnego SLA. Zdarzenia rozpoczęcia/zakończenia muszą zawierać ID, żeby spóźniony koniec starszej próby nie zwalniał nowej. Logikę dostępności kontrolek skupić w jednym miejscu, zamiast niezależnych zmian stanu w callbackach.
2. **Blokada i dodatkowa ochrona.** Zablokować obie listy synchronicznie przy kolejkowaniu (start monitoringu, Aktualizuj i Sprawdź teraz). Podczas aktywnego żądania callback zmiany okresu nie może zwiększyć ID, schować postępu ani oznaczyć wyników jako nieaktualnych; odrzucona programowa zmiana przywraca zamrożony wybór. Zwalniać dopiero dla pasującego końca albo rzeczywistego zakończenia monitoringu; restart zachowujący żądanie zachowuje blokadę. Obsłużyć wyjątek przed wejściem do workera, aby nie zostawić kontrolki zablokowanej.
3. **Zgodność wyników i komunikatów.** Zachować ochronę przed starym ID; SLA dodatkowo weryfikować wobec okresu aktywnego żądania. Nigdy nie podpisywać starych kafelków nowym wyborem. Zmiana dat w bezczynności dotyczy SLA, nie unieważnia sama z siebie Wstrzymanych/Wniosków; informacja wskazuje wybrany i nadal wyświetlany okres. Kolejne Aktualizuj nadal odczytuje standardowe trzy sekcje. Nie usuwać poprawnego cache i nie zmieniać jego schematu bez potrzeby.
4. **Diagnostyka, regresja i dokumentacja.** Rozszerzyć wspólną allowlistę i korelację o stałe zdarzenia przyjęcia/zakończenia żądania, blokady/odblokowania, odrzuconej zmiany okresu i odrzuconego wyniku (powody: stary ID/niezgodny okres). Zapisać ID, bezpieczne year/month, stan oraz wynik; bez treści strony, URL, danych zgłoszeń i wpisu na każdy poll. Awaria logu nie może zmienić blokady lub przyjęcia wyniku. Po odbiorze zaktualizować kontrakt, instrukcję i plan; decyzję przekrojową zapisać dopiero po przyjęciu rozwiązania.

## Testy i odbiór

- Miesiąc i rok: blokada już w kolejce, przy logowaniu, podczas każdej sekcji, ponowieniu i odtworzeniu przeglądarki; wybór myszą, klawiaturą i kółkiem. Odrzucona próba/programowy callback nie zmienia aktywnego ID, okresu ani paska postępu.
- Start automatyczny i Sprawdź teraz (w tym oczekiwanie za zagrożeniami) działają tak samo jak ręczne Aktualizuj. Przełączenie widoku nie odblokowuje okresu.
- Sukces, błąd sekcji, całego odczytu, anulowanie i końcowy Stop przywracają `readonly`; spóźnione zdarzenie innego ID nie odblokowuje nowego żądania. Ponowienie tego samego żądania nie zwalnia kontrolek przedwcześnie.
- W bezczynności nowy okres można wybrać i odczytać. Stare dane są podpisane swoim okresem; statusy sekcji bieżących i ich czasy nie są bezpodstawnie unieważniane. Cache, kompletny zestaw SLA i WJRUW pozostają spójne.
- Sprawdzić kolejności zdarzeń: zmiana przed startem workera; po zaakceptowaniu SLA; końcowy wynik czekający w kolejce; Stop→Start; A→B→A oraz wynik ze zgodnym ID, ale innym okresem.
- Sprawdzić zapis nowych pól diagnostyki, ograniczenie liczby wpisów, brak syntetycznych sekretów i odporność na awarię zapisu. Regresje snapshotów, cache, postępu, harmonogramu i wspólnego sterowania aktualizacją.

Kryterium: zero odrzuconych poprawnych wyników wyłącznie z powodu obsługi kontrolek, brak danych podpisanych obcym okresem, brak przedwczesnego/trwałego zablokowania UI. Po testach źródeł osobny build i test EXE na polecenie użytkownika. Jeśli implementacja dotknie interakcji ServiceNow, najpierw nowa inspekcja strony zgodnie z AGENTS.md; sama lokalna blokada nie wymaga zmiany czytnika.

## Odbiór — 2 listopada 2026

Wdrożono wszystkie cztery etapy. Panel przechowuje zamrożone ID/okres, blokuje kontrolki i chroni ich zmienne; zdarzenia workera mają identyfikator oraz okres, a restart zachowuje żądanie. Pasujący koniec/Stop/błąd kolejki/startu zwalnia blokadę. Odrzucane są stare ID, obcy okres i wyniki już zakończonej transakcji. Nowy wybór w bezczynności nie zmienia aktualności Wstrzymanych/Wniosków. Format zapisu cache i jego schemat pozostały bez zmian. [Decyzja 010](../../decyzje/010-cykl-zycia-zadania-dashboardu.md).

- **130 różnych testów zaliczonych, 0 błędów i pominięć w tym zakresie.** Regresja 18 modułów: 128 testów w 176,0 s; końcowy moduł okresu rozszerzono z 14 do 16 przypadków i ponowiono w 5,953 s. Razem 128−14+16=130 unikalnych przypadków. Nie jest to ponowienie całego zestawu aplikacji.
- Pokrycie: kontrolki myszy/klawiatury/kółka i programowe zmiany, kolejka/finalny wynik oczekujący na UI, pełny worker i cache, nowe okresy, ponowne logowanie, restart, Stop→nowe żądanie, spóźniony koniec, błędny okres przy zgodnym ID, duplikat po końcu, częściowy błąd, anulowanie, start/all i awaria kolejki/wątku/diagnostyki. Nowe pola i zdarzenia sprawdzono w rzeczywiście sformatowanych wpisach; allowlista odrzuca syntetyczne sekrety.
- Pierwsze próby testu startu i sprzątania wymagały poprawienia fixture: symulowany worker początkowo już działał, a anulowanie timerów usuwało callbacki należące do innych widżetów. Poprawiono izolację, nie poluzowano asercji aplikacji; wynik końcowy jest po tych korektach.
- Wyniki lokalne: `data/dashboard-period-regression-summary.json`, `data/period-regression-*.log`, `data/dashboard-period-final-tests.log`. `compileall` i `git diff --check` poprawne. Sprawdzono zmianę dokładnie trzech modułów względem buildu: app, dashboard_ui, login_diagnostics.
- Testy rzeczywistych kontrolek Tk/koordynatora, ale syntetycznych odczytów i tymczasowego cache; bez ponownej sesji ServiceNow, zmiany selektorów/DOM, danych użytkownika lub testu nowego EXE. Poprzedni plik EXE ma niezmieniony SHA256. Przebudowa i jej test wymagają osobnego zlecenia.
