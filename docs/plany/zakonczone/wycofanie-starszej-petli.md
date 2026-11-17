# Wycofanie starszej pętli monitoringu

## Zmiany w źródłach

- `App` zawsze tworzy `SharedSession`. Usunięto parametr wyboru trybu, `App.monitor()`, `_monitor_browser()`, `RefreshControl` i osobne kolejki dashboardu oraz zagrożeń SLA. Czytniki dashboardu i zagrożeń dostają jawne żądanie i sygnał anulowania. Widoki pokazują pracę na podstawie zdarzeń wspólnej kolejki. [Punkt wejścia](../../../neto_incident_monitor/app.py) · [Kolejka](../../../neto_incident_monitor/monitoring.py) · [Decyzja 025](../../decyzje/025-wspolna-sesja-servicenow.md)
- Przeniesiono przypadki okresu dashboardu, zagrożeń SLA, aktywnego filtra i statusów na wspólną sesję. Próby obejmują ręczny odczyt po Stop, zastąpienie symulacji wynikiem odczytu, odrzucenie spóźnionych zdarzeń i ponowne połączenie po awarii. Usunięto próby dotyczące wyłącznie starej pętli, w tym dawnego automatycznego otwierania Chromium. [Okres](../../../tests/test_dashboard_period.py) · [Zagrożenia](../../../tests/test_threatened.py) · [Aktywny filtr](../../../tests/test_filter_views.py) · [Statusy](../../../tests/test_activity_status.py) · [Ponowne połączenie](../../../tests/test_shared_session.py)
- Harmonogram, zapis migawek i alertów oraz migracje danych podlegają nadal wspólnemu kontraktowi. [Kolejka i trwałość](../../kontrakty/kolejka-i-trwalosc.md)

## Weryfikacja

Przed usunięciem starszej pętli pełna regresja na pulpicie Windows objęła 547 testów w 71 modułach. Zaliczono 546. Próbę przekierowania przez dowiązanie symboliczne pominięto ze względu na uprawnienia środowiska.

Po usunięciu pętli pełna sekwencyjna regresja Windows objęła 535 testów w 71 modułach. Zaliczono 533, bez niepowodzeń. Środowisko nie pozwoliło utworzyć dowiązania symbolicznego. Windows nie przyznał fokusu oknu testowemu potrzebnemu do weryfikacji przywracania Chromium, także w osobnej próbie. Test zapisu zaszyfrowanej konfiguracji zgłosił błąd w przebiegu równoległym, a przeszedł w izolacji i w pełnym przebiegu sekwencyjnym. Próby uruchomiono na izolowanych danych syntetycznych. Odbiór na instancji ADEO pozostaje osobny.
