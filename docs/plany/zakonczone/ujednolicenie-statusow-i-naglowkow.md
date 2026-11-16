# Ujednolicenie statusów i nagłówków widoków

**Stan** Wdrożone w źródłach. Odbiór lokalny zakończony 16 listopada 2026. 522 testy zaliczone, 2 pominięte.

## Docelowy wygląd

1. **Nagłówek aplikacji.** Pigułka obok „Incident Monitor” pokazuje stan monitoringu, np. „Monitoring aktywny” lub „Monitoring zatrzymany”. Ręczny odczyt przy zatrzymanym monitoringu jest widoczny jako bieżąca praca.
2. **Nagłówek widoku filtra.** Tytuł po lewej, a przyciski **ⓘ**, **Konfiguruj**, **Kolumny**, **Aktualizuj** i **Otwórz w SNOW** w tym samym wierszu po prawej, bezpośrednio pod przyciskami sterowania monitoringiem. Wysokość, wyrównanie i odstępy odpowiadają nagłówkom Dashboardu SLA i Incydentów zagrożonych SLA. Zakładki „Bieżące zgłoszenia” i „Historia zgłoszeń” zostają w osobnym wierszu niżej. Usuwamy licznik „Następna aktualizacja INC / SCTASK/REQ/RITM” i powtórzoną pigułkę monitoringu przy nazwie filtra.
3. **Belka widoku.** Pod tabelą filtra, dashboardem lub widokiem zagrożeń znajduje się stały wiersz poza przewijanym obszarem. Od lewej wyświetla trzy pola **Status**, **Ostatni udany odczyt** i **Czas zapytania**. Przełączanie między danymi bieżącymi a historią filtra zachowuje te same metadane odczytu. Belka zastępuje dawne opisy, w tym „Odczytano liczniki i listę zagrożeń”. Wybrany okres SLA i pigułki poszczególnych sekcji dashboardu pozostają widoczne.
4. **Dolna belka aplikacji.** Po lewej, pod panelem bocznym, pokazuje stan połączenia z ServiceNow i potrzebną akcję logowania. Po prawej, pod głównym panelem, wskazuje bieżącą pracę, np. „Aktualizuje filtr «Wnioski»”, „Importuje Ulubione” albo „Oczekuje na logowanie”. Po zakończeniu pracy pole się czyści, chyba że użytkownik ma jeszcze komunikat wymagający uwagi. Usuwamy globalną „Ostatnią aktualizację” i utrzymujące się „zakończono”.
5. **Pigułki przy pozycjach panelu bocznego.** Ujednolicamy „W kolejce” i „Aktualizuje” dla filtra, Dashboardu SLA i zagrożeń. Pigułka odzwierciedla przyjęte żądanie lub trwający odczyt. Sam przyszły termin w harmonogramie nie zajmuje miejsca w kolejce widocznej w UI.

## Znaczenie pól belki widoku

| Zdarzenie | Status | Ostatni udany odczyt i Czas zapytania |
| --- | --- | --- |
| Widok bez odczytu | Brak odczytu | `—` w obu polach |
| Pełny, zaakceptowany wynik, również z zerem rekordów | Odczyt udany | Data i godzina oraz łączny czas żądań po dane przypisanych do wyniku |
| Dashboard z poprawnym wynikiem części sekcji | Odczyt częściowy | Metadane ostatniego pełnego wyniku dla aktualnego okresu, jeśli istnieją |
| Błąd lub niekompletny wynik | Błąd odczytu | Metadane ostatniego pełnego wyniku właściwego dla widoku, jeśli istnieją |
| Anulowanie | Zachowany poprzedni status odczytu | Zachowane metadane. Bieżąca praca znika po obsłużeniu anulowania |

„Czas zapytania” oznacza sumę czasów pomyślnych żądań REST po dane, których odpowiedzi złożyły się na pełny wynik. Pomiar pomija kolejkę, logowanie, rozpoznawanie definicji i układu kolumn filtra, odrzucone próby oraz lokalne przetwarzanie, renderowanie i zapis. Jeśli wynik pochodzi ze starszego cache bez wiarygodnego pomiaru, pole czasu pokazuje `—`. Status odczytu opisuje wynik, a informacja o danych przywróconych z cache lub wymagających odświeżenia nadal może pojawić się w odpowiedniej pigułce.

## Etapy wdrożenia

- [x] **1. Ustalenie źródeł stanów i ich zakresu**
  - [x] Rozpisać, które zdarzenia aplikacji, sesji i kolejki sterują każdą pigułką, belką oraz dostępnością przycisków. Ustalić, gdzie pokazać dotychczasowe komunikaty o problemach z odczytem, zapisem i importem, aby zachować informacje potrzebne użytkownikowi.
  - [x] Użyć istniejących zdarzeń i identyfikatorów. Dla filtra powiązać wynik z identyfikatorem i aktualną rewizją konfiguracji, dla Dashboardu SLA z okresem i żądaniem, a dla zagrożeń z wynikiem obejmującym liczniki i listę.
  - [x] Zdefiniować jedną reprezentację wyniku odczytu używaną w trzech widokach. Uwzględnić brak odczytu, poprawne zero, część sekcji dashboardu, błąd, anulowanie oraz brak czasu w starszych danych.
  - Wynik. Wspólny `ReadStatus` przeszedł próby zmiany widoku, błędu po sukcesie, przyjętego zera i odrzucenia wyniku zakończonego żądania.

- [x] **2. Przekazanie godziny odczytu i czasu żądań do UI**
  - [x] Wykorzystać pomiar monotoniczny we wspólnej ścieżce REST. Przekazywać czas w metadanych bieżącego wyniku przez istniejące zdarzenia. Zachować diagnostykę poszczególnych prób i korelację z żądaniem.
  - [x] Zsumować czasy odpowiedzi użytych przez filtr, dashboard i zagrożenia, w tym kolejne strony listy zagrożeń. Zatwierdzać godzinę i czas razem z kompletnym wynikiem. Zmiana metadanych, sortowania, kolumn lub historii filtra sama nie odświeża tych pól.
  - [x] Powiązać pełny wynik dashboardu z wybranym miesiącem i rokiem. Obecny cache przechowuje niezależne migawki sekcji oraz jedną datę pełnego sukcesu. Przy zmianie okresu lub wczytaniu starszego zapisu pokazywać metadane wyłącznie wtedy, gdy można przypisać je do tego okresu. Obsłużyć starszy zapis bez błędu i bez wymyślania brakujących wartości.
  - [x] Sprawdzić zachowanie po restarcie. Powiązać metadane z odtworzonym wynikiem tam, gdzie widok wczytuje zapisane dane. Historia filtra sama nie potwierdza odtworzenia jego bieżącej listy.
  - Wynik. Kontrolowane czasy oraz pomiar w lokalnym Chromium przeszły próby. Cache dashboardu wiąże pełny odczyt z okresem, a zagrożenia zapisują liczniki i czas z listą w jednej transakcji. Sprawdzono ponowne otwarcie pustego wyniku.

- [x] **3. Przebudowa nagłówków i dodanie belki widoku**
  - [x] Przenieść pięć przycisków filtra do prawej części wiersza tytułu. Użyć wspólnych parametrów wyrównania z dashboardem i zagrożeniami. Zachować działanie skrótów, kolejność fokusu, wyłączanie przycisków podczas pracy i osobny wiersz zakładek.
  - [x] Usunąć wyświetlanie odliczania harmonogramu i lokalną pigułkę fazy monitoringu z widoku filtra. Usunąć kod licznika UI po sprawdzeniu jego powiązań z zegarem harmonogramu i pozostałymi odświeżeniami interfejsu.
  - [x] Zbudować wspólną belkę trzech pól. Umieścić ją poza obszarem przewijania danych i przed dolną belką aplikacji. Przenieść użyteczne szczegóły błędów do właściwego widoku lub komunikatu wymagającego uwagi. Usunąć zdublowane informacje o sukcesie i czasie.
  - [x] Dopracować układ na minimalnej szerokości okna, z długą nazwą filtra i przy przesuniętej szerokości panelu bocznego. Tytuł może się skrócić, a komplet przycisków ma pozostać dostępny.
  - Wynik. Tk na Windows potwierdziło geometrię belek i dostępność przycisków z długim tytułem w minimalnym oknie przy skali 100% i 125%.

- [x] **4. Ujednolicenie dolnej belki aplikacji i pigułek**
  - [x] Ustawić stan monitoringu przy tytule aplikacji. W dolnej belce wyrównać stan ServiceNow do panelu bocznego, a bieżącą pracę do głównego widoku. Zachować akcję pokazania okna logowania, gdy potrzebna jest interwencja.
  - [x] Sterować opisem aktywnej pracy bezpośrednio ze zdarzeń kolejki i sesji. Uwzględnić scalanie żądań, odczyt cykliczny i ręczny, import, ponowienie i oczekiwanie na logowanie. Usuwać opis po zakończeniu właściwej operacji. Odrzucać spóźnione zdarzenia, które mogłyby przesłonić nową pracę.
  - [x] Rozróżnić krótką informację o pracy od komunikatu wymagającego decyzji. Ten drugi zachować do rozwiązania problemu lub zamknięcia komunikatu, żeby następny odczyt go nie przykrył.
  - [x] Użyć istniejących stylów i krótkich etykiet pigułek. Ujednolicić oznaczenia pracy dla wszystkich trzech typów widoków i zachować pigułki pokazujące stan danych każdej sekcji dashboardu.
  - Wynik. Próba ze scaleniem żądań i ponownym logowaniem zachowała stan monitoringu, kolejność aktywnych opisów oraz osobne ostrzeżenie po opróżnieniu kolejki.

- [x] **5. Regresja i odbiór układu**
  - [x] Sprawdzić poprawny odczyt, poprawne zero, błąd po sukcesie, częściowy dashboard, anulowanie, restart ze starszym cache i odczyt po ponownym zalogowaniu. Sprawdzić obliczanie czasu na kontrolowanych opóźnieniach żądań.
  - [x] Sprawdzić szybkie przełączanie filtrów i zakładek, zmianę okresu dashboardu oraz edycję lub usunięcie filtra podczas odczytu. Potwierdzić, że spóźnione zdarzenia i wyniki z innego okresu nie zmieniają bieżącego widoku.
  - [x] Sprawdzić Start i Stop, ręczne odświeżanie przy zatrzymanym monitoringu, „Sprawdź teraz”, import, oczekiwanie na logowanie oraz pustą kolejkę. Potwierdzić dotychczasową kolejność odczytów, zakres operacji i dostępność przycisków.
  - [x] Sprawdzić układ Tk na Windows przy zmianie szerokości okna i skali 100% oraz 125%. Zweryfikować wyrównanie nagłówków, wspólne krawędzie belek, przewijanie, klawiaturę i brak uciętych akcji. Użyć danych testowych do prób stanów i odnotować zakres rzeczywistego odbioru.
  - [x] Sprawdzić, czy istniejąca diagnostyka pozwala powiązać zaakceptowanie lub odrzucenie wyniku z jego próbą i czasem. Sprawdzić także, czy błąd zapisu diagnostyki nie wpływa na UI i czy zdarzenia nie zawierają treści zgłoszeń ani danych logowania.
  - Wynik. Pełna regresja na oddzielnych danych uruchomiła 524 testy. Dwa pominięcia dotyczyły pasywnego pomiaru fokusu Windows i niedostępnego dowiązania symbolicznego. Tk i Chromium zweryfikowano z danymi syntetycznymi i przechwyconymi odpowiedziami testowymi. Odbiór nie obejmował połączenia z ADEO. Próba diagnostyki potwierdziła `api_data_ms` oraz odporność na błąd zapisu. Test monitora dodatkowo odizolowano od ustawień projektu po wykryciu, że wstępna próba mogła zapisać lokalne `data/config.json`.

- [x] **6. Dokumentacja po wdrożeniu**
  - [x] Zaktualizować architekturę i kontrakty odczytów o zakres i znaczenie pól. Zapisać nową decyzję o prezentacji statusów i powiązać ją z decyzją 020. Zachować zabezpieczenia identyfikatora żądania i okresu opisane w poprzedniej decyzji.
  - [x] Odnotować wyniki lokalne i zakres odbioru, uzupełnić checkboxy po zakończonych seriach zmian i po odbiorze przenieść plan do zakończonych. Build EXE i publikacja są poza zakresem.

## Punkty odniesienia

- [Architektura aplikacji](../../architektura.md)
- [Decyzja 039 o statusach odczytów i kolejki](../../decyzje/039-statusy-widokow-i-kolejki.md)
- [Decyzja 020 o aktywności dashboardu](../../decyzje/020-spojne-statusy-dashboardu.md)
- [Kontrakt odczytu dashboardu i zagrożeń](../../kontrakty/kontrakt-odczytu-dashboardu.md)
- [Kontrakt odczytu list ServiceNow](../../kontrakty/kontrakt-odczytu-list.md)
