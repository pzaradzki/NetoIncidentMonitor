# Komunikaty o błędnych warunkach filtrów

**Status.** Wdrożono w źródłach. Odbiór zakończono na syntetycznych danych w Windows.

## Cel i zakres

W istniejącej belce **Błąd odczytu** pokaż użytkownikowi, który warunek sprawdzić w kreatorze filtrów ServiceNow. Reguła ma objąć wykrywane błędy warunków w filtrach INC, SCTASK, REQ i RITM. Użytkownik dostaje wskazówkę dla pierwszego błędu zgłoszonego przez dotychczasową walidację i może ponowić odczyt po poprawieniu filtra.

Zakres obejmuje prezentację i przekazanie kontekstu błędu. Adres, zapytanie wysyłane do REST, akceptowane operatory, kolejność walidacji i zasady zapisu danych zachowują dotychczasowe znaczenie. Przykładowy zapis `assigned_to=` pozostaje odrzucony przez bieżącą regułę. [Kontrakt odczytu list](../../kontrakty/kontrakt-odczytu-list.md) · [Decyzja 038](../../decyzje/038-walidacja-warunkow-filtrow.md) · [Decyzja 039](../../decyzje/039-statusy-widokow-i-kolejki.md)

## Treść belki

| Rozpoznany przypadek | Treść pod nagłówkiem |
| --- | --- |
| Błąd warunku i dostępna etykieta pola | Sprawdź warunek dla pola „Przypisany do” w ServiceNow. Upewnij się, że wybrano właściwy operator i uzupełniono wartość, jeśli jest wymagana. |
| Błąd warunku i dostępna wyłącznie nazwa techniczna | Sprawdź warunek dla pola „assigned_to” w ServiceNow. Upewnij się, że wybrano właściwy operator i uzupełniono wartość, jeśli jest wymagana. |
| Wykryty błąd warunków bez pola, które można wskazać | Sprawdź warunki filtra w ServiceNow, w szczególności wybrane operatory i wymagane wartości. |

Etykieta zależy od pola i dostępnych metadanych. W komunikacie użytkownik widzi słowo „operator”, zgodne z wyborem na liście w ServiceNow. Gdy istnieje poprzedni udany odczyt, belka dołącza dotychczasową informację o zachowaniu jego wyniku i pokazuje jego metadane. [Stan odczytu](../../../neto_incident_monitor/read_status.py) · [Belka](../../../neto_incident_monitor/read_status_ui.py)

## 1. Przekazanie rozpoznanego błędu

- [x] Zidentyfikować miejsca, które dziś zgłaszają pomyłkę w warunku. Uwzględnić błędy składni i brak wymaganej wartości w `parse_query()` oraz brak pola, niepoprawną ścieżkę, niedopasowanie typu i nieobsługiwany operator w `ConditionValidator`. [Walidator](../../../neto_incident_monitor/filter_conditions.py)
- [x] Dodać do błędu warunku opcjonalny, strukturalny kontekst dla UI. Obejmuje rozpoznaną ścieżkę pola, jeśli jest jednoznaczna, oraz tabelę i widok, jeśli zostały rozpoznane z adresu. Zachować dotychczasowe `reason` i `retryable`. Kontekst warunku pozwoli rozróżnić błąd pola od innych problemów używających tego samego kodu. [Typ błędu](../../../neto_incident_monitor/dashboard_context.py) · [Rozpoznanie adresu](../../../neto_incident_monitor/filter_metadata.py)
- [x] Dołączyć kontekst przy odrzuceniu już rozpoznanego warunku. Dla porównania dwóch pól wskazać pole warunku, które użytkownik może znaleźć w kreatorze. Dla nieczytelnego fragmentu albo jawnie nieobsługiwanej dyrektywy użyć wariantu ogólnego. Zachować kolejność kontroli i moment zakończenia odczytu.
- [x] Rozróżnić przypadki zmiennych katalogowych. Błąd samego warunku może wskazać znaną etykietę zmiennej, a bez niej korzysta z treści ogólnej. Odmowa pobrania metadanych, niedostępna sesja i uszkodzona odpowiedź serwera zachowują komunikaty odpowiadające faktycznej przyczynie. Techniczny identyfikator zmiennej pozostaje poza treścią belki. [Walidacja zmiennych](../../../neto_incident_monitor/filter_conditions.py)

## 2. Ustalenie nazwy pola

- [x] Odczytać etykietę po dokładnej ścieżce technicznej z już dostępnego układu dla bieżącej tabeli, widoku, konta i języka. Można użyć etykiety tej samej ścieżki z zapisanego układu domyślnego tej samej tabeli i konta, jeśli w układzie wybranego widoku jej brakuje. [Zapis układów](../../../neto_incident_monitor/filter_layouts.py) · [Sesja i układy](../../../neto_incident_monitor/shared_session.py)
- [x] Obsłużyć błąd wcześniejszy niż pobranie układu, filtr z widokiem bez tej kolumny i brak zapisanych etykiet. Wtedy użyć rozpoznanej technicznej nazwy pola zgodnej ze składnią ścieżki. Etykieta pola końcowego innej ścieżki nie jest dowodem poprawnego dopasowania.
- [x] Użyć wariantu ogólnego, gdy nie ma bezpiecznej nazwy. Przy formatowaniu ograniczyć treść do nazwy lub etykiety pola. Wykorzystać dostępne dane w pamięci lub zapisany układ, bez zlecania dodatkowego odczytu ServiceNow w celu zbudowania komunikatu.

## 3. Belka, ponowienie i diagnostyka

- [x] Dodać dwa szablony treści w jednym miejscu warstwy prezentacji odczytu filtrów. Użyć rozpoznanego kontekstu po odrzuceniu warunku. Dla nieprawidłowego adresu, błędu skrótu, widoku, logowania, sieci, limitu oraz zapisu wybrać dotychczasowe komunikaty na podstawie istniejącej klasyfikacji. [Katalog dotychczasowych komunikatów](../../../neto_incident_monitor/analytics_api.py) · [Obsługa odczytu](../../../neto_incident_monitor/app.py)
- [x] Przekazać tekst istniejącą ścieżką `filter_activity` → `filter_error` → `ReadStatus` → `ReadStatusBar`. Zachować sprawdzanie rewizji filtra i generacji sesji. Użyć tego samego formatowania w istniejącym komunikacie akcji odświeżania definicji, jeśli zgłosi ten sam błąd warunku. [App](../../../neto_incident_monitor/app.py) · [Belka odczytu](../../../neto_incident_monitor/read_status_ui.py)
- [x] Zachować nagłówek **Błąd odczytu**, akcję **Ponów odczyt** oraz ostatni poprawny wynik po błędzie. Potwierdzić, że poprawny odczyt usuwa komunikat i że zdarzenie z wcześniejszej rewizji, poprzedniego konta albo anulowanej próby nie nadpisuje bieżącego stanu.
- [x] Utrzymać dotychczasową korelację startu, rozpoznania definicji, błędu i zakończenia próby. Sprawdzić, że diagnostyka nadal zapisuje etap i bezpieczną kategorię, a sformatowana treść UI, nazwa pola, wartość warunku, pełny adres i kontekst sesji nie trafiają do logów. [Diagnostyka](../../../neto_incident_monitor/login_diagnostics.py)

## 4. Testy i odbiór

- [x] Na syntetycznym adresie listy INC odtworzyć brak wartości w warunku `assigned_to`. Sprawdzić błąd na etapie definicji, poprawny wariant z etykietą i brak żądania Table API o zgłoszenia. W osobnym przypadku sprawdzić prawidłowy operator **Jest puste**.
- [x] Sprawdzić inne pola i typy błędów. Pokryć nierozpoznane pole lub część ścieżki, brak argumentu dla innego pola, nieobsługiwany operator, błędny warunek po `OR` lub `NQ` oraz dwa błędne warunki w jednym filtrze. Objąć co najmniej filtr incydentów i filtr katalogowy. Test potwierdza sposób wskazania pierwszego wykrytego błędu. [Testy metadanych i walidacji](../../../tests/test_filter_metadata.py)
- [x] Pokryć brak układu, brak etykiety, etykietę z właściwego układu, inną tabelę lub konto i niedający się rozpoznać warunek. Sprawdzić zamianę etykiety na nazwę techniczną albo komunikat ogólny bez dodatkowych żądań.
- [x] Sprawdzić na syntetycznej sesji ręczny i cykliczny odczyt, przełączanie dwóch filtrów, spóźnione zdarzenie po edycji lub zmianie sesji i ponowienie zakończone sukcesem. Porównać przypadki błędu przed pierwszą migawką i po udanym odczycie. [Testy statusów](../../../tests/test_view_status.py) · [Testy odczytu REST](../../../tests/test_filter_api.py)
- [x] Sprawdzić zachowanie po błędach autoryzacji, transportu i metadanych oraz po anulowaniu. Potwierdzić zgodność kodów, ponowień i logów. Użyć syntetycznego znacznika w argumencie, etykiecie lub URL i sprawdzić, że nie ma go w żadnym zapisie diagnostycznym.
- [x] Obejrzeć belkę w izolowanym oknie Tk przy minimalnej szerokości i przy skalach 100% oraz 125%. Sprawdzić zawijanie długiej etykiety, widoczność przycisku oraz rozróżnienie błędu od komunikatu o ostatnim udanym odczycie. Uruchomić zestaw zakresowy i regresję Windows. [Runner regresji](../../../tools/run_regression.py)

## 5. Dokumentacja i zamknięcie planu

- [x] Uzupełnić kontrakt odczytu list o warianty komunikatu, źródło etykiety i dane przeznaczone wyłącznie dla belki. Dodać w architekturze odnośnik do miejsca, w którym powstaje komunikat, jeśli zmieni się punkt wejścia dla prezentacji statusu.
- [x] Zapisać wyniki lokalne i przyczyny pominięć. Odbiór dotyczy lokalnej walidacji oraz prezentacji. Ewentualną próbę na ADEO odnotować osobno, jeśli zostanie wykonana.
- [x] Oznaczać checkbox po wykonaniu kroku i zweryfikowaniu wyniku. Po odbiorze przenieść plan do `zakonczone/` i zaktualizować [indeks planów](../README.md).

## Wynik odbioru

- Adres z pustym argumentem zakończył się przed wysłaniem żądania o zgłoszenia. Belka pokazała etykietę z zapisanego układu. Próby objęły również nazwę techniczną pola, wariant ogólny, błędy ścieżek i operatorów oraz etykietę zmiennej katalogowej.
- Odczyt ręczny, cykliczny i odświeżanie definicji użyły tej samej treści. Po nieudanym odczycie belka zachowała metadane ostatniego sukcesu. Zdarzenia ze starej rewizji i generacji układu zostały odrzucone. Poprawny odczyt usunął komunikat.
- Logi powiązały rozpoznanie definicji z błędem i końcem próby. Zawierały etap i kategorię błędu. Test nie wykrył w logach syntetycznej wartości, pełnego adresu ani treści przeznaczonej dla belki.
- W syntetycznym oknie Tk sprawdzono skalę 100% oraz 125% przy minimalnej szerokości. Długa etykieta zawinęła się, przycisk pozostał widoczny, a informacja o poprzednim wyniku mieściła się pod komunikatem.
- Przeszły wszystkie 83 testy z ośmiu modułów zakresowych w pełnej regresji. Łącznie zaliczono 589 z 591. Pominięto próbę pierwszego planu okna Chromium i próbę dowiązania symbolicznego ze względu na warunki Windows. Pojedyncze ponowienie testu fokusu również zakończyło się pominięciem. Raporty w `build/filter-condition-regression.json` i `build/filter-condition-focus-retry.json`.
