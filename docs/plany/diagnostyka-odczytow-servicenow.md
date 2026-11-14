# Diagnostyka błędów odczytu list i dashboardu ServiceNow

Uzgodniono 13 listopada 2026. Wdrożenie odłożono. Zakres obejmuje stałe podsumowania dla list INC, REQ, RITM i SCTASK oraz sekcji dashboardu SLA, Wstrzymane L1 i Wnioski L1. `monitor.log` ma wystarczyć do pierwszej diagnozy, a `login-diagnostics.jsonl` zachowa szczegóły prób i obserwacji. Tryb debugowania i eksport logów odłożono do osobnego zadania. [Zasady diagnostyki](../decyzje/004-bezpieczna-diagnostyka.md), [kontrakt list](../kontrakty/kontrakt-odczytu-list.md), [kontrakt dashboardu](../kontrakty/kontrakt-odczytu-dashboardu.md).

## Potwierdzone ustalenia

- W logach z 13 listopada wszystkie cztery końcowe błędy filtrów to `row_count_mismatch` na pierwszej stronie. Metadane wskazywały 10 albo 20 oczekiwanych wierszy, a licznik rozpoznanych wierszy wynosił 0 także po ponowieniu. Kod liczy wiersz dopiero po znalezieniu widocznego linku z numerem w rozpoznanej kolumnie. Samo 0 nie wskazuje, na którym etapie zabrakło danych.
- Na żywych listach INC, REQ, RITM i SCTASK potwierdzono klasyczną tabelę, metadane zakresu i wiersze rekordów `tbody tr.list_row`. Ogólny licznik wierszy z komórkami danych zwracał 101 przy 100 rekordach. Na pustej liście INC zwracał 1 przy zakresie `1–0` i zerze rekordów. Na drugiej stronie INC potwierdzono zakres `101–200`.
- Na dashboardzie potwierdzono kontrolkę okresu, panel `now-popover-panel`, kontrolki kategorii w Shadow DOM i wartości widżetów powiązane z nagłówkami. Po zmianie zakładki część elementów pojawiała się z opóźnieniem. Po załadowaniu rozpoznano 11 z 11 wartości SLA, 2 z 2 Wstrzymanych i 5 z 5 Wniosków. W logu kolegi pięć odczytów SLA zakończyło się przy otwieraniu okresu, wyborze kategorii **Status** lub przygotowaniu widżetów. Konkretnej awarii z jego środowiska nie udało się odtworzyć podczas obserwacji strony.

## Etapy wdrożenia

Po każdym wykonanym i sprawdzonym kroku zaznacz jego checkbox i dopisz wynik weryfikacji. Przy przerwaniu pracy zostaw checkbox otwarty i dopisz stan oraz następną czynność. Zaznacz etap po ukończeniu jego kroków.

- [ ] **1. Zapis planu i wspólne podsumowania**
  - [x] Zapisz plan w `docs/plany` i dodaj go do indeksu.
    - Plan zawiera ustalenia z kodu, obu logów i obserwacji strony. Odnośnik znajduje się w sekcji pozostałych prac.
  - [ ] Użyj istniejącego mechanizmu diagnostyki i rotacji. Zapisuj jedno podsumowanie końcowego błędu na odczyt filtra lub sekcję dashboardu. Powiąż je z JSONL przez `run_id` i `read_id`, a dla dashboardu także `request_id` i sekcję. Podaj pierwszą i końcową przyczynę, liczbę prób, czas i wynik.
  - [ ] Odnotuj udane ponowienie jako odzyskanie. Rozróżnij anulowanie, zmianę filtra, oczekiwanie na logowanie, błąd odczytu i błąd zapisu.

- [ ] **2. Rozpoznawanie przyczyn błędów list**
  - [ ] W istniejącej obserwacji właściwej tabeli zbierz liczby kandydatów na rekordy, widocznych wierszy, wierszy z rozpoznanym numerem i rekordów zwróconych przez kolektor. Uwzględnij obecność i widoczność nagłówka **Numer**, `aria-busy` oraz oczekiwany zakres. Użyj `.list_row` jako dowodu diagnostycznego dla klasycznych list. Jeśli znacznika nie da się potwierdzić, oznacz licznik jako niedostępny.
  - [ ] Przy odrzuceniu strony użyj ostatniego wiarygodnego stanu z tej samej próby i strony. Rozróżnij brak właściwej tabeli, niejednoznaczny wybór, brak metadanych, brak widocznych wierszy, brak nagłówka lub linków z numerami i różnicę między licznikiem tabeli a wynikiem kolektora. Zachowaj `row_count_mismatch` jako przyczynę główną i dopisz zaobserwowane liczby.
  - [ ] Uwzględnij typ listy, indeks filtra oraz wynik próby ustawienia 100 wierszy, także gdy zakończyła się przed potwierdzeniem rozmiaru.
  - [ ] Zweryfikuj dotychczasowe kryteria kompletności, budżety i ponowienia. Potwierdź, że poprawne zero wymaga pozytywnego dowodu, po błędzie zachowana jest ostatnia poprawna lista z czasem i historią, a wynik częściowy nie trafia do kolejki alertów.

- [ ] **3. Rozpoznawanie przyczyn błędów dashboardu**
  - [ ] Oprzyj podsumowanie o istniejące zdarzenia REST. Podaj sekcję, alias celu, ostatnie żądanie, próbę, kod HTTP, czas, pozostały budżet oraz wynik zapisu migawki. [Decyzja 032](../decyzje/032-odczyty-analityki-przez-api.md)
  - [ ] Rozróżnij potwierdzone zero, odmowę dostępu, wadliwy schemat i niepełną paginację zagrożeń. Zachowaj pierwszą przyczynę i końcowy wynik po ponowieniu.

- [ ] **4. Odbiór i dokumentacja**
  - [ ] Przetestuj syntetycznie zakres 20 przy zerze rozpoznanych wierszy, brak nagłówka, ukryte wiersze, wiersze bez linku, dodatkowy wiersz techniczny, poprawną pustkę i ponowienie od pierwszej strony.
  - [ ] Dla dashboardu i zagrożeń sprawdź błąd HTTP, zły schemat, niepełną odpowiedź i wyczerpanie budżetu. Sprawdź także Stop, utratę sesji i awarię zapisu logu.
  - [ ] Na Windows z izolowanymi danymi potwierdź, że `monitor.log` rozróżnia wymienione przypadki, a identyfikatory prowadzą do właściwej próby w JSONL.
  - [ ] Wykonaj odczytowy odbiór na ServiceNow w osobnym profilu, także przy ukrytym Chromium. Zapisz wyniki lokalne i obserwacje rzeczywiste, zaktualizuj kontrakty odczytu i architekturę.

## Ochrona danych i granice

Do logów trafiają wyłącznie dozwolone kody, liczniki, flagi, czasy i techniczne identyfikatory. Diagnostyka pomija treść zgłoszeń, nazwy filtrów użytkownika, pełne adresy, warunki zapytań, wartości kafelków, HTML i dane logowania. Pomiary obejmują REST dla analityki i DOM dla zwykłych list.
