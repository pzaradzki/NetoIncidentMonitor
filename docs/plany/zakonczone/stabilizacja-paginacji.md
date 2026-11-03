# Stabilizacja paginacji list ServiceNow

> Zakończony plan i historia wdrożenia, nie bieżąca lista zadań. Aktualny status, lokalny build 1.8.0 i pozostałe sprawdzenia: [indeks planów](../README.md). Zapisy o braku EXE dotyczą ówczesnego etapu.

Data: 1 listopada 2026. Zmiany przygotowane w kodzie po wydaniu 1.7.17; bez budowania EXE i publikacji.

## Zakres czterech etapów

- [x] Powiązanie tabeli, jej kontenera, pagera i metadanych. Kolektor otrzymuje widok ograniczony do wybranej tabeli. Główna lista jest rozpoznawana po typie, `data-list_id` i identyfikatorze tabeli; niejednoznaczny wybór jest odrzucany.
- [x] Kontrola przejść: pierwszy wiersz, ostatni wiersz, rozmiar strony, liczba wyników, stan kontrolek oraz dane odczytane przed i po obserwacji. Odczyt wraca do pierwszej strony także wtedy, gdy ServiceNow zapamiętało inną pozycję.
- [x] Kontrola kompletności: ciągłość zakresów, liczba rekordów na stronie, unikalność numerów między stronami i zgodność całego zestawu z licznikiem listy. Wykryta zmiana filtra, sortowania, rozmiaru strony lub liczby wyników unieważnia próbę.
- [x] Ograniczone odzyskiwanie i diagnostyka: jedna ponowna próba całego odczytu, od pierwszego wiersza i z pustym buforem. Nie ponawiamy w miejscu kliknięcia o niepewnym wyniku.

## Zasady działania

- Paginowane listy muszą udostępniać jednoznaczne metadane pozwalające potwierdzić kompletność. Czekamy również na opóźnione pojawienie się pagera lub metadanych.
- Listy rzeczywiście pozbawione paginacji oraz potwierdzone puste wyniki zachowują osobne ścieżki obsługi. Nieznany pager nie jest uznawany za koniec listy.
- Domyślny czas oczekiwania na gotową stronę wynosi 15 s, a wspólny limit aktywnego odczytu i jego ponowienia 30 minut. Są to limity kontrolowane w punktach obserwacji; nie obiecują przerwania dowolnego zablokowanego wywołania biblioteki przeglądarki.
- Stop, zamknięcie przeglądarki, wygaśnięcie sesji i odmowa odczytu dużej listy nie uruchamiają ponowienia niespójnej paginacji. Obsługuje je dotychczasowa warstwa monitoringu.
- Zgoda na dużą listę nie jest ponownie wymagana w ramach ponowienia tego samego sprawdzenia.
- Historia, stan obecności i powiadomienia otrzymują wynik dopiero po zakończeniu całego poprawnego odczytu.
- Zdarzenia `pagination_*` trafiają do istniejącej, rotowanej diagnostyki. Zawierają identyfikatory korelacji, numer filtra/próby/strony, zakresy, liczniki, kategorie przyczyn i czasy etapów. Nie zapisują numerów ani treści zgłoszeń, adresów filtrów i danych uwierzytelniających.

## Weryfikacja na rzeczywistej stronie

W przeglądarce Codex sprawdzono strukturę listy TEST i powiązanie tabeli `incident_table` z jej kontenerem i kontrolkami. Następnie sprawdzono selektory i reguły ciągłości oraz kompletności podczas przejścia przez cały wynik:

| Rozmiar strony | Liczba stron | Ostatni zakres | Unikalne rekordy | Licznik ServiceNow |
| --- | --- | --- | --- | --- |
| 20 | 27 | 521–528 | 528 | 528 |
| 100 | 6 | 501–528 | 528 | 528 |

Po testach przywrócono pierwszą stronę i pierwotne ustawienie 20 wierszy. Nie edytowano zgłoszeń i nie eksportowano ich treści.

Ta weryfikacja dotyczy rzeczywistych elementów i reguł przechodzenia w przeglądarce Codex. Silnik Python jest weryfikowany osobno przez testy automatyczne na minimalnych stronach syntetycznych; nie należy utożsamiać tego z uruchomieniem nowego EXE na rzeczywistym koncie.

## Testy automatyczne

- `tests/test_list_context.py`: strony 20/100, obce listy i pagery, lista powiązana tego samego typu oraz niejednoznaczna lista główna.
- `tests/test_pagination_validation.py`: komplet danych, krótka ostatnia strona, zapamiętana pozycja, pominięcie/nakładanie stron, duplikaty, zmiana rozmiaru/licznika/filtra, opóźnione kontrolki i metadane, podmiana tabeli, pusty wynik, duża lista, anulowanie, wygaśnięcie sesji, ponowienie od początku, diagnostyka i syntetyczne sekrety.
- Istniejące testy paginacji, niezawodności, skrótów i dużych list zostały dostosowane do metadanych zaobserwowanych w rzeczywistym ServiceNow.
- [x] Końcowy pełny zestaw: 293 testy w 48 modułach — 292 zaliczone, 1 pominięty, bez błędów. Pominięto pomiar pasywnego fokusu, ponieważ Windows nie przyznał testowemu oknu pierwszego planu.
- Pełny zestaw wykonano modułami w osobnych procesach, po niestabilnym przebiegu we wspólnym procesie Tk/Playwright. Wynik tego przebiegu zapisano lokalnie w `data/pagination-isolated-tests.log`; pomocniczy skrypt uruchamiający to `data/run-pagination-regression.py`. Pliki diagnostyczne nie są materiałem do publikacji.

## Granice gwarancji

Kontrola zakresów, liczników i duplikatów wykrywa niespójności widoczne podczas paginacji. Nie tworzy transakcyjnej kopii bazy ServiceNow z jednej chwili. Zmiany danych, które nie zmieniają obserwowanych metadanych ani nie powodują wykrywalnego braku lub duplikatu, mogą pozostać niewidoczne. Przy wykrytej trwałej niestabilności wynik jest odrzucany zamiast zapisywania częściowej listy.

Stabilizacja nawigacji dashboardu zagrożeń po SSO i powiadomienia o zagrożeniach pozostają osobnymi zadaniami.
