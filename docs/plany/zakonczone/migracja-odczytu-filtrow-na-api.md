# Migracja odczytu filtrów ServiceNow na REST API

**Status — zakończony w źródłach 15 listopada 2026. Szczegółowy odbiór na ServiceNow celowo pominięty.** Zakres obejmuje listy INC, REQ, RITM i SCTASK, niezależnie od tego, czy filtr dodano ręcznie, zaimportowano z Ulubionych, czy zapisano w starszej wersji. Wszystkie wejścia do odczytu rekordów korzystają z Table API. Aktualizuj checkboxy po zakończonej i sprawdzonej serii zmian. Pod krokiem zapisz wynik, a przy przerwanej pracy odnotuj pozostałe czynności.

Punkty odniesienia: [kontrakt list](../../kontrakty/kontrakt-odczytu-list.md), [transport w sesji Chromium](../../servicenow-api-sesja-przegladarki.md), [zmiany filtrów podczas monitoringu](../../decyzje/027-zmiany-filtrow-podczas-monitoringu.md) i [transakcja historii i obecności](../../decyzje/011-transakcyjny-stan-filtrow.md).

## Docelowy przebieg aktualizacji

1. Zadanie odbiera bieżącą rewizję filtra i sprawdza lokalną definicję. Kompletna i aktualna definicja pozwala od razu wykonać odczyt REST na wspólnej sesji.
2. Jeżeli brakuje definicji lub jej części, aplikacja wykorzystuje wiarygodne dane z adresu i zapisu. Tylko po pozostałe metadane otwiera listę na jednej karcie roboczej. Odczytuje warunki, tabelę, widok i nagłówki bez zbierania wierszy i bez przechodzenia na kolejne strony listy.
3. Gdy definicja jest kompletna, musi zostać zapisana dla aktualnej konfiguracji filtra. W ramach tego samego zlecenia aplikacja pobiera rekordy przez API, także podczas pierwszej aktualizacji. Zapisana definicja pozostaje dostępna po restarcie oraz po przejściowym błędzie odczytu API.
4. Aplikacja zatwierdza tylko kompletną listę. Jeśli nie może przygotować definicji, zapisać jej albo dokończyć odczytu, pokazuje przyczynę i zachowuje ostatni poprawny wynik.

## 1. Potwierdzenie kontraktu na ServiceNow

Użytkownik zrezygnował ze szczegółowego odbioru. Poniższe próby na instancji ServiceNow pozostają pominięte i są poza kryteriami zamknięcia. Rozbieżności wykryte w codziennym użyciu będą rozpatrywane na bieżąco.

- **Pominięto w szczegółowym odbiorze** porównanie rekordów, liczebności i wartości kolumn w INC, REQ, RITM i SCTASK, w tym przy różnych uprawnieniach.
- **Pominięto w szczegółowym odbiorze** porównanie złożonych, długich i względnych warunków, wartości dynamicznych, skrótów, odwołań przez kropkę i niestandardowych widoków na docelowej instancji.
- **Pominięto w szczegółowym odbiorze** pomiary czasu i kompletności odpowiedzi bliskiej 1000 rekordów oraz próby krótkiej lub pustej odpowiedzi z dodatnim licznikiem przy ograniczonym dostępie.
- **Potwierdzono w codziennym użyciu** obsługę przekroczenia limitu. Użytkownik potwierdził zachowanie po poprawce z automatycznym wyłączeniem filtra.

## 2. Definicja filtra i trwały zapis

- [x] **Oddzielić rozpoznawanie listy od pobierania rekordów.**
  - [x] Rozszerzyć istniejące `list_definition` o wersję, powiązanie z adresem i instancją filtra oraz mapowanie stabilnych kluczy kolumn aplikacji na zweryfikowane pola ServiceNow. Zachować tabelę, pełne zapytanie, widok i etykiety. Puste, potwierdzone zapytanie traktować jako osobny stan od nieustalonego zapytania. Brak pola oznaczony jako „Nie rozpoznano pola” w podglądzie nie jest potwierdzonym mapowaniem API.
  - [x] Ponownie wykorzystać metadane zapisane przez **ⓘ**. Brakujące elementy uzupełniać przy pierwszym odczycie po aktualizacji. Stary zapis lub profil kolumn przyjąć tylko w zakresie informacji, których źródło i zgodność da się potwierdzić. Migracja ma działać na istniejących danych bez zmiany zapisanych układów.
  - [x] Wydzielić z bieżącego czytnika odczyt tożsamości tabeli, zapytania i nagłówków. Zbierać wyłącznie metadane, również na potwierdzonej pustej liście. Zachować normalizację adresu i sprawdzanie kontekstu listy. Przy ustalaniu technicznych nazw wykorzystać wiarygodne atrybuty, a nierozpoznane obowiązkowe pola opisać w komunikacie. Nie zmieniać preferencji liczby wierszy.
  - [x] Zapisywać definicję atomowo w konfiguracji filtra. Przed zapisem sprawdzić aktualną rewizję, instancję i adres. Uzgodnić przekazanie wyniku zapisu pomiędzy właścicielem konfiguracji i wątkiem sesji. Błąd zapisu wstrzymuje pierwszy odczyt API i pozwala ponowić próbę. Zachować inne ustawienia zapisane w trakcie rozpoznawania.
    Próby lokalne potwierdziły odczyt metadanych z pustej listy Chromium, przejście do REST na jednej karcie, kolejność zapisu i odczytu oraz zachowanie poprzedniej definicji przy błędzie zapisu. Zapis sprzed wersjonowania służy do podglądu, a mapowanie potrzebne do odczytu jest zbierane przy pierwszej aktualizacji.
  - [x] Zmiana znormalizowanego linku ma unieważnić tylko powiązaną definicję i pracę na starej rewizji. Pokazać nieaktywny przycisk **ⓘ** do ponownego zapisu. Uwzględnić stary wynik po edycji, usunięciu, ponownym dodaniu tego samego adresu lub restarcie Chromium. Sama zmiana nazwy i układu kolumn w aplikacji nie unieważnia definicji.
  - [x] Rozwiązać zmianę układu po stronie SNOW przez jawną akcję **Odśwież definicję z SNOW** na tej samej kolejce. Odczyty z działającą definicją nie mają okresowo sprawdzać DOM. Nową definicję zapisać dopiero po jej sprawdzeniu. Zestaw i układ aktualnych kolumn zachować w zakresie wspólnych kluczy.

## 3. Odczyt REST i kompletność

- [x] **Pobrać pełną migawkę przez wspólny transport.**
  - [x] Rozszerzyć istniejący transport o dozwolone ścieżki Table API dla czterech tabel. Zachować tę samą kartę, origin ServiceNow i odzyskiwanie sesji. Stosować wyłącznie odczytowe żądania, istniejące budżety i anulowanie. Przy gotowej definicji standardowa aktualizacja nie otwiera listy. W razie potrzeby kontekstu sesji wraca na SOW.
  - [x] Budować `sysparm_fields` ze wszystkich pól wykrytych w widoku ServiceNow. Zachować pola ukryte lokalnie dla historii, szablonów i późniejszego pokazania kolumny. Dodać `sys_id`, numer i surową datę utworzenia INC potrzebną do obliczenia wieku. Zachowano również wartość `state` dla istniejących szablonów REQ.
  - [x] Zmapować odpowiedź do bieżącego modelu rekordów i kluczy kolumn. Zachować czytelne etykiety, prawidłową strefę czasu, typ rekordu i poprawne odnośniki do INC, REQ, RITM i SCTASK. Odnośnik zbudować ze zweryfikowanej tabeli i identyfikatora.
  - [x] Rozdzielić błędy definicji, niezgodność schematu, brak dostępu, problem sieciowy lub ograniczenie liczby żądań oraz utratę sesji. Przy problemie przejściowym użyć istniejącego limitu ponowień. Przy trwałym błędzie zachować poprzednie dane i pokazać przyczynę.
    Kod pobiera wszystkie pola ze zweryfikowanego widoku, w tym lokalnie ukryte. Wymaga licznika zgodnego z liczbą zwróconych wierszy. Zachowanie licznika i ACL na docelowej instancji objęto decyzją o pominięciu szczegółowego odbioru. Próba HTTP 401 potwierdza jedno odzyskanie sesji z ponowieniem żądania. Ponowna odpowiedź 401 kończy zlecenie bez zatwierdzenia migawki.

### Duże listy

Podczas odbioru filtr rozwiązanych i zamkniętych INC obejmował ponad 80 tys. wpisów. Kopia zawężona do miesiąca miała 6 817 wpisów, a poprzedni wariant wielostronicowy zatrzymywał się na stronie 65 w obu próbach, mimo HTTP 200 i stałego licznika. Użytkownik ustalił limit 1000 i zawężanie warunków przez edycję filtra. [Decyzja 035](../../decyzje/035-limit-odczytu-filtrow.md)

- [x] **Obsłużyć filtry jednym żądaniem z limitem 1000.**
  - [x] Poprosić Table API o maksymalnie 1000 rekordów i licznik. Zatwierdzić wynik wyłącznie przy zgodności liczby wierszy, licznika i braku następnej strony.
  - [x] Przy przekroczeniu limitu zakończyć odczyt po pierwszej odpowiedzi. Wyłączyć filtr w harmonogramie, zapisać zmianę i potwierdzić ją monitem. W stopce pokazać nazwę filtra, liczebność i limit. Zachować ostatni poprawny wynik, historię, obecność i alerty.
  - [x] Sprawdzić lokalnie 0, 1000, 1001, 6817 i 80000, brakujące wiersze, sygnał następnej strony, duplikaty, odzyskanie sesji, zrozumiały komunikat i brak zapisu niepełnego wyniku.
    Przeszło 108 testów obejmujących transport, kolejkę, widok filtra w Tk, lokalny Chromium, diagnostykę i transakcje SQLite. Próba wyłączenia potwierdziła trwały zapis, usunięcie filtra z harmonogramu, krótki tekst w stopce, zachowanie poprzedniej migawki, obsługę błędu zapisu i odrzucenie spóźnionego zdarzenia.

## 4. Kolejka, historia i diagnostyka

- [x] **Przełączyć wszystkie wejścia filtra na ten sam przebieg.**
  - [x] Podłączyć harmonogram, **Aktualizuj** i **Sprawdź teraz** do przygotowania definicji i odczytu API w istniejącym zadaniu. Zachować kolejność względem dashboardu, zagrożeń i importu, dostępność ręcznego odczytu przy zatrzymanym monitoringu oraz zasady dla wyłączonego filtra.
  - [x] Pokazywać etapy ustalania definicji, odczytu, oczekiwania na logowanie i wynik. Zachować działanie **Stop**, anulowanie, zamykanie i odrzucanie spóźnionych zdarzeń. **Otwórz w SNOW** nadal otwiera stronę na żądanie użytkownika.
  - [x] Użyć istniejącej transakcji historii, obecności i kolejki alertów dopiero po walidacji pełnego odczytu. Migracja istniejącego filtra ma zachować obecność, historię i oczekujące powiadomienia. Dla rzeczywiście nowego filtra pierwszy udany odczyt ustanawia punkt odniesienia. Błąd lub niepełna odpowiedź nie mogą wywołać fałszywych zniknięć, powrotów ani duplikatów alertów.
  - [x] Rozszerzyć wspólne logowanie o wynik i czas rozpoznania, zapis definicji, alias tabeli, numer strony, liczebność, wynik walidacji, bezpieczny kod HTTP, ponowienia i wynik zatwierdzenia. Powiązać zdarzenia z żądaniem i próbą. Bez treści zapytań, identyfikatorów rekordów, odpowiedzi i danych sesji.
    Testy kolejki, historii i odzyskania sesji potwierdziły wspólne wykonanie. Próba błędnej strony sprawdziła korelację, liczniki i brak syntetycznego warunku w logach.

## 5. Wycofanie czytnika DOM

- [x] **Usunąć stare pobieranie rekordów.**
  - [x] Sprawdzić zależności poprzedniego czytnika i zachować porównanie warunków, wykrywanie tabeli oraz mapowanie nagłówków.
  - [x] Usunąć czytanie wierszy z DOM, obsługę stron i zmianę preferencji liczby wierszy. Oddzielne wyjątki sesji są w `read_errors.py`.
  - [x] Zastąpić testy starego czytnika próbami REST i odczytu metadanych. Zachować próby normalizacji, aliasu daty, bezpieczeństwa, logowania, skrótów, importu i historii. Uzupełnić dokumentację oraz odnośniki do poprzednich decyzji.

## 6. Weryfikacja i zamknięcie

### Odbiór na ServiceNow

Szczegółowy odbiór został celowo pominięty zgodnie z decyzją użytkownika. Pozostałe rozbieżności będą zgłaszane podczas normalnego użycia. Próby lokalne opisano osobno.

### Testy lokalne

Pełny zestaw lokalny przed ostatnimi doprecyzowaniami przeszedł bez błędów (548 uruchomionych, 2 pominięte). Po poprawkach zakres obejmujący kolejkę, Windows, sesję, filtry, Table API, limity i diagnostykę dał 103 poprawne wyniki. Zestaw 60 testów potwierdził również użycie zapisanej definicji po ponownym uruchomieniu, odrzucenie zmiany licznika i nakładających się stron oraz działanie wspólnych wyjątków po przeniesieniu ich poza poprzedni czytnik. Kolejne 30 testów objęło rozpoznawanie syntetycznego skrótu i jego widoku na jednej karcie. Próba pełnego zapisu przez SQLite potwierdziła, że niekompletna odpowiedź zachowuje poprzednią historię i obecność bez alertu, a pełna odpowiedź pozwala użyć ukrytej kolumny w szablonie Teams. Próba korzystała z atrapy Teams. Zakres świadomie pominiętych prób na rzeczywistej instancji opisano w sekcji 1.

- [x] **Ukończyć weryfikację lokalną.**
  - [x] Na danych syntetycznych sprawdzić start bez definicji i z kompletem, restart, osobne zapisy dla filtrów, edycję w kolejce i w trakcie pracy, błąd zapisu, skróty, odświeżenie definicji i pole pominięte przez API.
  - [x] Sprawdzić zero, limit 1000, niespójny licznik, niepełne metadane, brak uprawnień, awarię Chromium, utratę sesji, anulowanie i późny wynik. Potwierdzić brak zmian trwałego stanu i alertów po odrzuconej migawce oraz brak sekretów w diagnostyce.
  - [x] Na Windows sprawdzić Start, Stop, ręczne zlecenia, import, wspólną kartę i ukrycie Chromium. Potwierdzić pierwszą aktualizację z pozyskaniem samych metadanych oraz drugą i odczyt po restarcie bez otwierania widoku listy.
  - [x] Powtórzyć regresję po usunięciu starej ścieżki. Zamknąć plan po spełnieniu kryteriów. Przebudowa EXE i publikacja pozostają osobnym zadaniem.

Końcowa izolowana regresja Windows po usunięciu czytnika DOM objęła **69 modułów i 517 testów**. Zaliczyło 515, dwa pominięto z powodu braku gwarantowanego fokusu podczas jednej próby Windows oraz braku możliwości utworzenia dowiązania symbolicznego. Brak nieudanych modułów i błędów zdarzeń Tk. Mapowanie kolumn, ponowny start, wspólną kartę, odzyskiwanie sesji, import, kolejkę i ukrywanie Chromium zweryfikowano w lokalnych próbach zakresowych, w tym na syntetycznych stronach.
