# Interwał odczytu incydentów zagrożonych

W **Ustawieniach → Monitorowanie** dodać pole **Incydenty zagrożone SLA** obok interwałów INC, zgłoszeń katalogowych i Dashboardu SLA. Domyślne **60 s** zachowa obecne zachowanie profili bez nowego ustawienia.

## 1. Stan obecny i zasada wykonania

- [x] Sprawdzono, że `SharedSession.finish_threatened_read()` wyznacza dziś kolejny termin po 60 s od zakończenia próby, a `next_part()` wybiera odczyt dopiero po zwolnieniu wspólnej karty ServiceNow. [Sesja](../../../neto_incident_monitor/shared_session.py) · [Kontrakt kolejki](../../kontrakty/kolejka-i-trwalosc.md#kolejka-i-anulowanie)
- [x] Sprawdzono wspólny zapis trzech interwałów oraz terminy przechowywane już w `MonitorCycle`. Te mechanizmy obejmą czwarte pole. [Ustawienia](../../../neto_incident_monitor/settings_ui.py) · [Decyzja o cyklu dashboardu](../../decyzje/047-cykliczne-odswiezanie-dashboardu.md)
- [x] Użytkownik potwierdził zasadę odbioru. Gdy termin upłynie podczas innego odczytu, zagrożenia czekają na **zakończenie całej bieżącej operacji na karcie**. Jeśli w tym czasie minie kilka interwałów, po zwolnieniu karty przypada jedna zaległa próba.

## 2. Ustawienia i zapis

- [x] Dodać pole z jednostką **sekund** przez istniejące `interval_field()`. Włączyć je do tej samej instancji `ScheduleIntervalAutosave` i zapisu przy zamknięciu ustawień. Test ustawień potwierdził edycję i wspólny zapis podczas zamykania okna.
- [x] Dodać `threatened_interval` do wspólnego odczytu i zapisu konfiguracji. Starsze profile bez tego klucza przyjmują 60 s. Użyć obecnej walidacji pełnych sekund z minimum 15 s. [Zapis interwałów](../../../neto_incident_monitor/app.py) Sprawdzono wartość domyślną 60 s i odrzucenie 14 s.
- [x] Przekazać nową wartość do aktywnego cyklu po udanym zapisie. Po błędnej wartości lub odmowie zapisu stosować poprzedni interwał i wyświetlić istniejący komunikat ustawień. Odmowa zapisu zachowała aktywny cykl i poprzednią konfigurację.

## 3. Termin we wspólnej sesji

- [x] Włączyć `threatened` do istniejących terminów `MonitorCycle` i użyć `schedule_next()`, wspólnego przeliczania interwałów oraz istniejącego oczekiwania na najbliższy termin. Przenieść konsumentów `threatened_next_read`, w tym diagnostykę, na ten sam termin i usunąć osobne odliczanie z `SharedSession`. Testy korzystają z terminu w `MonitorCycle`, także przy oczekiwaniu sesji.
- [x] Zachować wybór pracy przez `SharedSession.next_part()`. Odczyt zagrożeń może wejść między filtrami, po zakończeniu bieżącego filtra. Po starcie zachować obecne pierwszeństwo zaległych zagrożeń oraz kolejność dashboard → zagrożenia → filtry przy starcie i **Sprawdź teraz**. [Kolejność i anulowanie](../../kontrakty/kolejka-i-trwalosc.md#kolejka-i-anulowanie) Testy potwierdziły kolejność między dashboardem, zagrożeniami i filtrami.
- [x] Wyznaczać kolejny termin względem końca próby zagrożeń, także po błędzie, po **Aktualizuj** i po części zagrożeń w **Sprawdź teraz**. Dalsza praca innych modułów może opóźnić wykonanie, a zakończenie tej pracy nie rozpoczyna odliczania od nowa. Po udanym odczycie odpowiadającym oczekującemu zleceniu ręcznemu wykorzystać dotychczasowe scalanie w `ReadQueue`. [Kolejka ręczna](../../../neto_incident_monitor/monitoring.py) Sprawdzono koniec próby po błędzie, po odczycie ręcznym i przed końcem pozostałych części pełnego odczytu.
- [x] Po zapisaniu interwału podczas oczekiwania przeliczyć termin względem końca ostatniej próby. Zaakceptować nowy interwał po trwającym odczycie zagrożeń i zastosować go od zakończenia tej próby. Zegar testowy pokazał oba przeliczenia terminu.
- [x] Przy Stop zatrzymać cykl, zachować oczekujące zlecenia ręczne i przypisać zakończenie odczytu wyłącznie do właściwego cyklu. Przy ponownym połączeniu zachować obsługę przerwanego żądania i jego status. Utrzymać istniejący sygnał `threatened_finished` oraz zapis migawek, historii i powiadomień. [Odczyt zagrożeń](../../../neto_incident_monitor/threatened_read.py) Sprawdzono zakończenie starego cyklu, ręczne zlecenie po Stop i zwolnienie żądania po utracie karty.

## 4. Diagnostyka i odbiór

- [x] Rozszerzyć wspólne zdarzenie `schedule_interval_change` o interwał zagrożeń. W `threatened_schedule` zachować spóźnienie, przyczynę oczekiwania i korelację z odczytem. Potwierdzić diagnostykę po zmianie ustawienia, udanym odczycie, błędzie i anulowaniu. [Kontrakt diagnostyki](../../kontrakty/diagnostyka-logowania.md) Testy potwierdziły pola interwału, zwłokę, wspólne ID oraz rozróżnienie błędu i anulowania.
- [x] W ustawieniach sprawdzić domyślne 60 s w starym profilu, zmianę wartości podczas monitoringu, ponowne uruchomienie aplikacji oraz brak zmiany terminu po błędzie walidacji lub zapisu. Na starym profilu odtworzył się domyślny interwał 60 s, a po zapisie i ponownym uruchomieniu wczytało się 45 s. [Test zapisu interwałów](../../../tests/test_shared_session.py)
- [x] Na kontrolowanym zegarze sprawdzić termin przed odczytem, po zakończeniu próby oraz po zmianie interwału w trakcie oczekiwania i aktywnego odczytu. [Testy harmonogramu](../../../tests/test_refresh_requests.py)
- [x] Przekroczyć termin w trakcie długiego odczytu dashboardu i w trakcie filtra. W obu próbach potwierdzić, że zagrożenia ruszają dopiero po zakończeniu operacji, a kolejka wykonuje jeden zaległy odczyt mimo upływu kilku interwałów. Sprawdzić też jednoczesny termin dashboardu i zagrożeń. [Testy kolejności](../../../tests/test_update_order.py)
- [x] Sprawdzić ręczne i zbiorcze odświeżenie, błąd odczytu, Stop przy zajętej karcie i ponowne połączenie. Potwierdzić, że odrzucona lub anulowana próba zachowuje ostatnią przyjętą migawkę. [Testy sesji](../../../tests/test_shared_session.py) · [Testy zapisu zagrożeń](../../../tests/test_threatened_details.py)
- [x] Uruchomić testy zakresowe i regresję Windows. Zapisać wyniki z izolowanego okna ustawień i przebiegów na danych syntetycznych.
- [x] Po wdrożeniu zaktualizować architekturę, kontrakt kolejki i opis diagnostyki. Przenieść odebrany plan do `zakonczone/` i poprawić indeks. Oznaczać każdy krok po potwierdzeniu wyniku oraz dopisywać dowód lub przyczynę oczekiwania.

## Wynik odbioru

- Ustawienia zachowały domyślne 60 s dla starego profilu. Po zapisie i ponownym uruchomieniu aplikacja odczytała 45 s wraz z trzema poprzednimi interwałami. Test okna potwierdził wspólny zapis podczas monitoringu i zachowanie poprzedniej konfiguracji po błędzie zapisu.
- Zegar testowy potwierdził pojedynczy zaległy odczyt po zakończeniu dashboardu lub filtra, termin liczony od końca próby zagrożeń i zastosowanie zapisanego interwału. Próby objęły też ręczne odświeżenie, pełne odświeżenie, Stop oraz utratę i odzyskanie karty na danych syntetycznych. [Testy terminów](../../../tests/test_refresh_requests.py) · [Testy cyklu odczytu](../../../tests/test_threatened.py)
- Przeszło 68 testów zakresowych. W pełnej regresji Windows zaliczono 585 z 586 testów, bez błędów testów i callbacków Tk. Jeden test resetu pominięto z powodu niedostępnej funkcji tworzenia dowiązań symbolicznych.
