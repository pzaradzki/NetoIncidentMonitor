# Liczniki zgłoszeń na liście filtrów

Pod nazwą każdego filtra wyświetlić liczbę zgłoszeń z ostatniej poprawnej listy bieżących zgłoszeń oraz w nawiasie liczbę zgłoszeń z tej listy, których użytkownik jeszcze nie wyświetlił w tym filtrze.

Przykład `357 (3)` oznacza 357 bieżących zgłoszeń, w tym 3 niewyświetlone. Jeżeli dwa z tych trzech wypadną z listy przed otwarciem filtra, wynik zmieni się na `355 (1)`. Po wyświetleniu pozostałych bieżących zgłoszeń zostanie `355`. Przy zerze niewyświetlonych nawias znika. Przed pierwszym udanym odczytem widnieje `—`, a po potwierdzonym pustym wyniku `0`.

## 1. Rozpoznanie i ustalenia

- [x] Ustalono źródło aktualnych liczb. `App.drain()` przyjmuje zweryfikowany wynik filtra i zapisuje go w `snapshots`. `update_counts()` liczy obecnie zgłoszenia dla wybranego filtra na karcie bieżących zgłoszeń. [Odbiór wyniku](../../../neto_incident_monitor/app.py#L2573) · [Licznik widoku](../../../neto_incident_monitor/app.py#L1162)
- [x] Znaleziono punkty wejścia do obsługi wyświetlenia. Lista boczna odróżnia zaznaczenie wiersza od aktywacji widoku, a duża tabela kończy ładowanie w osobnym callbacku. [Lista filtrów](../../../neto_incident_monitor/widgets.py#L763) · [Zmiana widoku](../../../neto_incident_monitor/ui.py#L269) · [Koniec ładowania](../../../neto_incident_monitor/table_loading.py#L173)
- [x] Sprawdzono istniejącą decyzję o usunięciu dawnego stanu przeczytania. Nowy licznik dotyczy wyświetlenia bieżącej listy filtra. [Decyzja 012](../../decyzje/012-usuniecie-stanu-przeczytania.md)
- [x] Użytkownik potwierdził liczenie od nowa po restarcie. Pierwszy przyjęty wynik filtra, którego użytkownik jeszcze nie otworzył, liczy wszystkie obecne zgłoszenia jako niewyświetlone.
- [x] Użytkownik potwierdził ponowne liczenie zgłoszenia po powrocie z potwierdzonej nieobecności. Zgłoszenie obecne w dwóch filtrach rozlicza się dla każdego z nich osobno.

## 2. Liczniki i stan filtra

- [x] Wyprowadzić liczbę wszystkich zgłoszeń z ostatniego przyjętego wyniku każdego filtra. Rozróżnić brak wyniku, potwierdzone zero i zachowany wynik po błędzie odświeżenia. [Kontrakt odczytów](../../kontrakty/kolejka-i-trwalosc.md#operacje-i-warunki-zatwierdzenia) Rozróżnienie potwierdza test pierwszego wyniku, zera i błędu odświeżenia.
- [x] Powiązać lokalny stan wyświetleń z tożsamością filtra. Sprawdzić, że zmiana nazwy lub kolejności zachowuje właściwy stan, a usunięcie filtra lub zmiana warunków listy oczyszcza stan poprzedniego wyniku. Uzgodnić zachowanie po włączeniu, wyłączeniu i ponownym ręcznym odczycie. Zachowanie potwierdzono po zmianie nazwy, adresu i kolejności. Przełączenie harmonogramu zachowuje migawkę i licznik. Udany ręczny odczyt wyłączonego filtra przyjmuje nową migawkę. [Zmiana kolejności i mapowanie](../../../neto_incident_monitor/app.py#L809) · [Test przełącznika](../../../tests/test_filter_card_counts.py)
- [x] Przy przyjęciu pełnego wyniku usunąć ze stanu zgłoszenia spoza bieżącej listy. Liczyć niewyświetlone wyłącznie spośród zgłoszeń w nowym wyniku. Zachować dotychczasowe zasady historii, obecności, powiadomień i odrzucania nieaktualnych wyników. Testy obejmują wypadające i powracające zgłoszenia oraz ten sam numer w dwóch filtrach. Stan dotyczy wyłącznie widoku.
- [x] Aktualizować kartę filtra przy zmianie wartości licznika. Korzystać z istniejącej kolejki zdarzeń i odświeżania listy w Tk. Sprawdzić, czy seria odczytów nie powoduje zbędnego przerysowywania. Aktualizacja zmienia wyłącznie dwa elementy tekstowe wskazanej karty. Identyczna para liczb nie powoduje zmiany.

## 3. Potwierdzenie wyświetlenia

- [x] Powiązać potwierdzenie z widoczną zakładką **Bieżące zgłoszenia** danego filtra i aktualną migawką. Wejście myszą lub klawiaturą zalicza całą gotową listę, także wiersze poza obszarem przewijania. Historia, Dashboard, zminimalizowane okno i zaznaczenie ustawione przez aplikację same nie zaliczają wyświetlenia. Pokryto kliknięcie, klawiaturę, Historię, Dashboard, ukrycie i przywrócenie okna oraz samo zaznaczenie z kodu.
- [x] Obsłużyć wynik odświeżenia w już otwartym filtrze. Zaliczyć go po wyświetleniu aktualnej tabeli. Gdy użytkownik przełączył filtr lub zakładkę przed ukończeniem, pozostawić zgłoszenia niewyświetlone. Nowy wynik aktywnego widoku trafia do licznika po zakończeniu wyświetlania.
- [x] Dla dużych tabel sprawdzać zakończenie właściwego ładowania. Przetestować anulowanie, przerwane ładowanie i nadejście nowszego wyniku podczas wyświetlania. [Porcjowanie tabel](../../../neto_incident_monitor/table_loading.py) Anulowany starszy zestaw i jego callback nie zaliczają wyświetlenia. Zmiana zakładki oraz zastąpienie migawki są w testach.
- [x] Sprawdzić przeciąganie, przełącznik aktywności i zmianę zaznaczenia przy przebudowie listy. Gest służący zmianie ustawienia lub kolejności nie powinien sam potwierdzać wyświetlenia. Kliknięcie wywołuje aktywację przy zwolnieniu przycisku. Przeciągnięcie i przełącznik nie zaliczają wizyty.

## 4. Wygląd karty

- [x] Umieścić licznik pod nazwą. Pokazać całkowitą liczbę zwykłym tekstem, a dodatnią wartość w nawiasie kolorem akcentu. Zachować czytelność również bez koloru. Na podglądzie potwierdzono format 357 (3), zwykłe zero i kreskę przed wynikiem.
- [x] Rozmieścić licznik, status kolejki, ikony powiadomień i przełącznik tak, aby mieściły się na karcie. Sprawdzić długą nazwę, wąski pasek boczny oraz stan normalny, wybrany, wyłączony i aktualizowany. [Rysowanie kart](../../../neto_incident_monitor/widgets.py#L801) Sprawdzono kartę o szerokości 203 px przy pasku bocznym 235 px przy obu skalach Tk. Status zachowuje pełny tekst.
- [x] Zweryfikować, że zmiana układu karty zachowuje trafianie myszą, obsługę klawiatury, przeciąganie i przewijanie listy. [Istniejące testy kolejności](../../../tests/test_filter_reorder.py) Istniejące testy przewijania, przeciągania i ikon przeszły po zmianie układu.

## 5. Testy i odbiór

- [x] Sprawdzić na danych syntetycznych pierwszy odczyt, pokazanie i ukrycie nawiasu, zniknięcie dwóch z trzech niewyświetlonych zgłoszeń oraz ponowne pojawienie się zgłoszenia. Uwzględnić to samo zgłoszenie w dwóch filtrach i błąd odświeżenia. Testy pokrywają również skrócenie nawiasu z 3 do 1 i odrzucenie nieaktualnego wyniku.
- [x] Sprawdzić aktywację myszą i klawiaturą, otwarcie Historii oraz zmianę filtra w trakcie wczytywania. Potwierdzić wybrany wariant zachowania po restarcie. Sprawdzono także świeżą instancję z tą samą konfiguracją i tą samą ścieżką historii.
- [x] Użyć istniejącej diagnostyki do rejestrowania istotnych zmian stanu licznika i odrzucenia spóźnionego potwierdzenia. Zapisywać tylko zbiorcze liczniki i stałe kategorie przyczyn, z identyfikatorem operacji tam, gdzie już jest dostępny. Sprawdzić ochronę numerów zgłoszeń, treści oraz definicji filtrów. [Kontrakt diagnostyki](../../kontrakty/diagnostyka-logowania.md) Test rzeczywistych rekordów loggera potwierdził zbiorcze dane i brak treści zgłoszeń.
- [x] Sprawdzić wygląd w izolowanym oknie Windows przy skali 100% i 125%. Uruchomić testy zakresowe i regresję Windows. Zapisać wyniki oraz przyczyny ewentualnych pominięć. [Runner regresji](../../../tools/run_regression.py)
- [x] Zapisać przyjęte zachowanie w dokumentacji. Uzupełnić decyzję 012 o odnośnik do nowej decyzji w sprawie wyświetlenia listy i zaktualizować indeks po odbiorze.

## Wynik odbioru

- Natywne okno Tk w Windows sprawdzono na danych syntetycznych przy skali 100% i 125%. Karta o szerokości 203 px mieści maksymalny licznik `1000 (1000)`, ikony i pełny status kolejki. Po korekcie odstępu licznik znajduje się bliżej nazwy, a pigułka jest wyśrodkowana względem wysokości karty. Na wąskiej karcie z widoczną pigułką ikony mają mniejszy rozmiar i mieszczą się nad nią. Korektę objęło 30 testów zakresowych.
- Zestaw zakresowy zaliczył 71 testów. Pełna regresja objęła 572 testy. W pierwszym przebiegu zaliczono 570, jeden pominięto z powodu braku obsługi dowiązań symbolicznych, a jedyny błąd wystąpił w izolowanym teście sortowania. Po uzupełnieniu jego konfiguracji oba testy sortowania przeszły. [Testy licznika](../../../tests/test_filter_card_counts.py) · [Testy sortowania](../../../tests/test_sorting.py)
- Trzy testy aktywacji okien przeszły w pierwszej regresji i w próbach na pulpicie Windows po przerwanym ponowieniu w ograniczonym środowisku. Test pasywnego pokazywania Chromium przeszedł w pierwszej regresji. Runner pominął go w powtórce, gdy Windows nie przyznał oknu testowemu pierwszego planu. Łącznie pełny przebieg i ponowienia potwierdziły 571 zaliczonych testów. [Testy sesji](../../../tests/test_shared_session.py) · [Test okna Chromium](../../../tests/test_browser_window.py)
- Zasady liczenia opisano w decyzji 046, architekturze oraz kontraktach kolejki i diagnostyki. Odbiór dotyczy uruchomienia ze źródeł na danych syntetycznych. [Decyzja 046](../../decyzje/046-liczniki-zgloszen-w-filtrach.md)

## Aktualizowanie checkboxów

Oznaczać krok jako `[x]` po zweryfikowaniu wyniku. Zapisać przy nim ustalenie albo odnośnik do testu, pomiaru lub raportu. Przy częściowym wyniku zostawić `[ ]` i podać brakujący scenariusz. Po odbiorze przenieść plan do `zakonczone/` i poprawić odnośniki w indeksie.
