# 039 — Statusy widoków, sesji i kolejki

**Status** Przyjęta i wdrożona w źródłach. Zastępuje sposób prezentacji opisany w [decyzji 020](020-spojne-statusy-dashboardu.md) i zachowuje jej ochronę cyklu żądania.

**Decyzja** Stan monitoringu jest przy tytule aplikacji. Dolna belka pokazuje sesję pod panelem bocznym i pracę kolejki pod głównym widokiem. Własna stała belka filtra, dashboardu i zagrożeń pokazuje wynik próby oraz godzinę i czas zapytań ostatniego pełnego odczytu. Pigułki w panelu bocznym odnoszą się do części rzeczywiście przyjętych lub wykonywanych.

**Powód** Operacja w tle może dotyczyć innego widoku, a utrata sesji lub ręczny odczyt może wystąpić przy zatrzymanym monitoringu. Zakończenie operacji usuwa opis pracy. Komunikat wymagający uwagi ma własne miejsce i można go zamknąć.

**Realizacja** `SharedSession` przekazuje początek i koniec aktywnej części kolejki. `ReadStatus` i `ReadStatusBar` wyświetlają wynik próby oddzielnie od metadanych kompletnego wyniku. Filtr używa rewizji, dashboard używa ID i okresu, a zagrożenia wymagają liczników i zatwierdzonej listy. Zakończone i spóźnione zdarzenia mają ochronę w istniejących ścieżkach UI. Cache dashboardu zapisuje okres i czas pełnego odczytu. Podsumowanie zagrożeń zapisuje się w tej samej transakcji SQLite co lista. Dla starszych danych bez wiarygodnych metadanych belka pokazuje kreskę.

**Czas zapytania** Suma pomiarów `performance.now()` od wysłania żądania REST do pobrania treści odpowiedzi użytej w wyniku. Odczyt metadanych, logowanie, kolejka, odrzucone próby, lokalne przetwarzanie i zapis są poza pomiarem. Pole diagnostyki `api_data_ms` jest liczbą i ma bezpieczny alias celu oraz istniejący kontekst odczytu. Pole `duration_ms` nadal opisuje czas istniejącego etapu lub operacji.

**Komunikaty pod danymi** Wiersz metadanych skraca etykietę czasu do „Dane z”, a dashboard używa „Pełny odczyt”. Rozwinięta belka pokazuje nagłówek, przyczynę i akcję w tym samym widoku. Ponowienie i edycja używają istniejących poleceń oraz ich dostępności. Odczyty, przyjęcie do kolejki i zapisy konfiguracji zachowują dotychczasową korelację w diagnostyce.

**Wspólna dolna belka** Jedna linia u góry rozciąga się pod oboma panelami. Stan sesji i „Aktywność” zajmują jeden wiersz na tle głównego okna. Wysokość wyznaczają tekst, widoczne przyciski i ewentualny komunikat wymagający uwagi. Treść korzysta z kolumn tego samego układu co panele, więc przesunięcie separatora zachowuje wyrównanie. Akcje logowania i ponownego połączenia są po prawej. Gdy kolejka nie pracuje, belka pokazuje oczekiwanie na odczyt lub brak zleceń.

**Ograniczenia** Po ponownym uruchomieniu historia filtra pozostaje dostępna, a belkę uzupełnia pierwszy zaakceptowany odczyt bieżącej listy. Dashboard nadal zachowuje trzy niezależne migawki. Wynik częściowy może pokazać świeższe dane sekcji przy zachowaniu godziny ostatniego pełnego odczytu.
