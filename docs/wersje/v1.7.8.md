# Neto Incident Monitor v1.7.8

Wydanie zawiera zmiany od wersji **1.7.7**: usprawnienia logowania, odczytu dashboardu i sterowania oknem Chromium oraz dokładniejszą diagnostykę.

## Logowanie i odzyskiwanie sesji

- Poprawiono wybór pojedynczego zapamiętanego konta ADEO. Aplikacja czeka na gotowość kafelka konta i przycisku logowania, zamiast zużywać próby podczas ich ładowania lub chwilowego zasłonięcia.
- Wzmocniono rozpoznawanie autouzupełnienia hasła i ochronę przed podwójnym zatwierdzeniem formularza. Ponowienie następuje wyłącznie po potwierdzeniu, że poprzednie kliknięcie nie zostało dostarczone; wynik niejednoznaczny wymaga ręcznej obsługi.
- Rozpoczęcie ręcznego wpisywania, wklejania lub zatwierdzenia formularza oddaje kontrolę użytkownikowi. Ochrona pozostaje aktywna po przekierowaniu, zmianie dokumentu i przełączeniu ustawienia automatycznego logowania.
- Poprawiono obsługę formularzy w ramkach i powiązanych oknach logowania, wielu zapamiętanych kont, MFA, zmiany formularza oraz błędów logowania. Przypadki wymagające decyzji użytkownika przechodzą do ręcznej obsługi.
- Potrzeba ręcznego logowania lub MFA uruchamia przywołanie właściwej karty i okna Chromium. Przywracanie ma ograniczoną liczbę prób; po potwierdzonym pokazaniu aplikacja respektuje późniejsze zminimalizowanie okna przez użytkownika. W razie niepowodzenia wskazuje możliwość użycia polecenia „Pokaż przeglądarkę”.
- Sesja jest sprawdzana niezależnie od zawartości pierwszego filtra, również gdy lista jest pusta. Wolne przekierowanie SSO nie jest zastępowane kolejnym otwarciem strony.
- Wygaśnięcie sesji podczas odczytu dashboardu uruchamia ponowne logowanie i jedną próbę wznowienia przerwanej sekcji. Ręczne logowanie i MFA nie mają limitu czasu przeznaczonego na potwierdzenie dostępu do listy.
- Dodano ograniczone ponowienia początkowego połączenia i czytelniejsze zakończenie pracy po zamknięciu okna logowania bez potwierdzonej sesji.
- Ograniczono pętlę restartów po zamknięciach lub awariach Chromium: odstępy wynoszą 2, 4 i 8 sekund, a czwarte zdarzenie w ciągu 60 sekund zatrzymuje restarty z komunikatem.

## Widoczność przeglądarki i ustawienia podczas pracy

- Podczas logowania i odczytu dashboardu Chromium pozostaje widoczne i niezminimalizowane, aby umożliwić renderowanie danych ServiceNow. Dotyczy to również ręcznej aktualizacji dashboardu.
- Automatyczne pokazywanie przeglądarki używa trybu bez aktywacji i umieszcza okno za istniejącymi oknami. Ręczne logowanie oraz jawne polecenie „Pokaż przeglądarkę” przywołują okno do użytkownika.
- Ukrywanie lub minimalizacja zgodne z preferencjami wracają przy sprawdzaniu filtrów. Polecenie ukrycia podczas logowania lub odczytu dashboardu jest odraczane.
- Automatyczne logowanie, minimalizację i całkowite ukrywanie można przełączać podczas monitoringu. Zmiany są przekazywane bezpiecznie do wątku obsługującego przeglądarkę; wyłączenie automatycznego logowania blokuje następne działania, bez powtarzania już wysłanych żądań.
- Skrócono pojedyncze oczekiwania podczas nawigacji, obsługi kontrolek i przechodzenia między stronami filtrów. Przycisk „Zatrzymaj” oraz zmiany ustawień są sprawdzane pomiędzy etapami pracy.

## Dashboard

- Aktualizacja korzysta z już załadowanego obszaru dashboardu i przełącza jego zakładki, ograniczając pełne przeładowania. Aktywna zakładka nie jest ponownie klikana; nieudane przełączenie ma ograniczoną próbę awaryjnego otwarcia.
- Poprawiono oczekiwanie na gotowość kontrolki okresu i filtrów oraz rozpoznawanie chwilowo zasłoniętych lub jeszcze nieaktywnych przycisków.
- Sekcja **Wnioski L1** sprawdza wybór wszystkich agentów L1 i w razie potrzeby zatwierdza go przyciskiem „Zastosuj”.
- Liczniki wniosków są odczytywane bezpośrednio z wartości widżetów. Gotowe dane nie muszą czekać na aktywność przycisku kafelka ani na zakończenie ładowania niezwiązanych wykresów.
- We wszystkich trzech sekcjach — **Dashboard SLA**, **Wstrzymane L1** i **Wnioski L1** — dodano przewijanie kontenerów widżetów do widocznego obszaru przed odczytem. Rozwiązuje to przypadek, w którym ServiceNow inicjalizuje kafelki dopiero po ich pojawieniu się na ekranie.
- Wnioski L1 mają ograniczony czas oczekiwania na komplet czterech stabilnych liczników i najwyżej jedno ponowienie po przeładowaniu. Niepełny wynik jest oznaczany jako błąd odczytu; brakujące wartości nie są zastępowane zerami ani traktowane jako pełny sukces.
- Dodano pasek postępu pod tytułem aplikacji. Postęp wynika z zakończonych kroków odczytu i nie osiąga 100% przed poprawnym zakończeniem całej aktualizacji. Po osiągnięciu 100% pasek znika po 3 sekundach; niepełny odczyt ma oznaczenie ostrzegawcze.
- Pasek uwzględnia ponowne logowanie, zatrzymanie monitoringu, zmianę okresu i rozpoczęcie kolejnej aktualizacji, aby spóźnione zdarzenia poprzedniej próby nie zmieniały bieżącego widoku.

## Diagnostyka i ochrona danych

- Rozbudowano `login-diagnostics.jsonl` o etapy nawigacji, gotowość formularzy, próby kliknięć, przejęcie ręczne, odzyskiwanie sesji, widoczność przeglądarki i konkretne operacje dashboardu wraz z czasem ich wykonania.
- Wspólny identyfikator przebiegu, numer zdarzenia i czas od początku próby ułatwiają powiązanie logowania z późniejszym odczytem. Kategorie błędów rozróżniają m.in. sieć, certyfikat, zajęty profil, brak przeglądarki, zmianę dokumentu i przekroczenie czasu.
- Diagnostyka stosuje listę dozwolonych pól i wartości. Nie zapisuje loginów, haseł, wartości formularzy, tokenów SSO, cookies, adresów SSO, kodu HTML ani zrzutów formularza.
- Zabezpieczono również ogólny log, wyjątki wątków i przechwycone wyjście bibliotek przed zapisywaniem surowych komunikatów mogących zawierać dane logowania. Logi mają rotację.
- Rozszerzono testy formularzy, sesji, sterowania oknem, odczytu dashboardu, postępu i ochrony logów.

## Uruchomienie

Rozpakuj **cały ZIP** i uruchom `Neto Incident Monitor.exe`, pozostawiając obok dołączony folder `_internal`. Aplikacja używa własnego lokalnego profilu Chromium; nie kopiuje haseł z przeglądarki użytkownika.

## Weryfikacja wydania

Przeszły 244 testy aplikacji. Natywny test pomiaru pasywnego fokusu został pominięty, ponieważ Windows nie przekazał pierwszego planu testowemu oknu; ten przypadek wymaga sprawdzenia w warunkach użytkownika. Potwierdzono uruchomienie gotowego EXE v1.7.8, interfejsu i dołączonego Chromium. Przed publikacją sprawdzana jest zgodność modułów paczki ze źródłami commita oraz integralność i zgodność plików ZIP-a z katalogiem aplikacji.
