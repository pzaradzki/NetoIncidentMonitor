# Wskazówki do pracy nad Neto Incident Monitor

## Pamięć projektu

- Przed zmianą przeczytaj [architekturę](docs/architecture.md), powiązane [decyzje](docs/decisions/README.md) i właściwy [plan](docs/plans/README.md). Czytaj materiały dotyczące zadania, nie całą historię.
- Wykorzystuj lub rozszerzaj istniejące mechanizmy. Uzasadnij tworzenie alternatywy, szczególnie dla odczytu strony, ponowień, harmonogramu, diagnostyki, statusów i zapisu.
- Weryfikuj dokumentację z kodem i rzeczywistą stroną; poprawiaj rozbieżności. Rozróżniaj stan wdrożony, plan i hipotezę. Dokumentacja nie stanowi zgody na wdrożenie.
- Istotną zmianę kończ z odpowiednimi testami i aktualizacją dokumentacji: architektura opisuje stan, decyzja — wybór i powód, plan — pozostałe prace.
- Zapisuj decyzje przekrojowe lub trudne do odtworzenia z kodu, nie drobiazgi. Format: status, decyzja, powód, realizacja i ograniczenia. Zmianę decyzji zapisz jako nową; poprzednią oznacz jako zastąpioną i połącz odnośnikami, zachowując uzasadnienie.

## ServiceNow: obserwacja → potwierdzenie → implementacja → weryfikacja

Przed zmianą integracji UI sprawdź aktualną stronę w przeglądarce Codex. Nie zgaduj DOM ani selektorów ze zrzutu, nazwy lub wcześniejszej wersji strony.

1. Przeczytaj kod, określ cel i otwórz właściwą stronę obsługiwanymi narzędziami. Logowanie przekaż użytkownikowi; nie odczytuj jego poświadczeń.
2. Zbadaj DOM, role dostępności, komponenty, ramki i Shadow DOM. Rozróżnij tytuł, wartość, ładowanie i element klikany.
3. Sprawdź zachowania istotne dla zadania: pierwsze wejście, zakładki, filtry, daty, odświeżanie i przewijanie; uwzględnij leniwe renderowanie i podmianę DOM.
4. Potwierdź jednoznaczność selektora i odróżnianie gotowej wartości, zera, placeholdera oraz braku danych. Dopiero potem implementuj; testy oprzyj na obserwacji, także dla opóźnień, przebudowy DOM i wygaśnięcia sesji.
5. Po zmianie zweryfikuj działanie na stronie, jeśli dostęp i zakres zadania na to pozwalają. Wyniki rzeczywistej strony oddziel od testów lokalnych.

Gdy dostęp jest niemożliwy, wskaż brak weryfikacji i przyczynę; oddziel fakty od założeń. Kontynuuj niezależną analizę kodu, plan lub testy, ale nie przedstawiaj selektorów jako sprawdzonych. Poproś o dostęp dopiero, gdy jest niezbędny.

## Zakres i ochrona danych

- Sama analiza strony nie upoważnia do edycji zgłoszeń, zapisania konfiguracji dashboardu, wysyłania wiadomości ani innych działań biznesowych. Przy zleceniu wyłącznie analizy/planu nie zmieniaj aplikacji, nie buduj i nie publikuj.
- Nie zakłócaj przeglądarki działającego monitora. Uwzględnij zapamiętywanie dat/filtrów; po testach przywróć poprzedni stan, gdy to możliwe.
- Nie zapisuj w kodzie, testach, dokumentacji ani logach loginów, haseł, tokenów, cookies, nagłówków uwierzytelniania, danych profilu przeglądarki ani pełnych adresów SSO z parametrami.
- Nie kopiuj do repozytorium pełnego HTML, odpowiedzi sieciowych ani danych zgłoszeń. Testuj minimalną, zanonimizowaną strukturę z danymi syntetycznymi. Logi nie mogą zawierać tych treści ani wartości formularzy; używaj bezpiecznej klasyfikacji wyjątków i tracebacków. Samo późniejsze maskowanie sekretów nie wystarcza.

## Diagnostyka jest częścią każdej zmiany funkcjonalnej

- Planuj ją razem z funkcją/poprawką. Korzystaj ze wspólnego logowania i korelacji; nie twórz niespójnych loggerów. Sam „Błąd odczytu” lub typ wyjątku nie wystarcza: log ma wyjaśniać działanie, etap, oczekiwany i zaobserwowany stan oraz wynik.
- Rejestruj start, istotne etapy, koniec i czasy; rozróżniaj sukces, wynik częściowy, błąd, anulowanie i oczekiwanie na użytkownika. Zapisuj limity, numery/przyczyny ponowień, działania naprawcze i ich wyniki; odróżniaj problem naprawiony od końcowej awarii.
- Wiąż zdarzenia identyfikatorem uruchomienia i, zależnie od potrzeby, operacji/odczytu/próby. Nie wyprowadzaj identyfikatorów z poświadczeń. Dodawaj bezpieczny kontekst: np. zakres i rozmiar strony, licznik rekordów, stan widżetu, kategorię błędu.
- Dopuszczaj wyłącznie świadomie wybrane pola i stałe kategorie; preferuj aliasy celów zamiast pełnych URL. Aktualizuj zdarzenia i listy dozwolonych wartości przy zmianie funkcji; sprawdzaj, czy pola faktycznie są zapisywane.
- Stosuj spójne kody, pola strukturalne i poziomy ważności oraz zrozumiałe komunikaty UI. Loguj zmiany stanów i okresowe podsumowania zamiast każdego odpytywania; zachowuj pierwszą przyczynę i końcowy wynik. Ogranicz obciążenie UI, dysku i przeglądarki.
- Awaria diagnostyki nie może przerywać funkcji ani maskować pierwotnego błędu. Sygnalizuj ją bezpiecznie, bez rekurencji i zalewania wpisami.
- Przed ukończeniem sprawdź przydatność diagnostyki, korelację, kompletność pól i ochronę danych. Dla logowania i istotnych błędów testuj brak syntetycznych sekretów w logach; uwzględniaj ponowienie, anulowanie i awarię zapisu, jeśli dotyczą zmiany.

## Uruchomienia i przechowywanie logów

- Dopisuj do logów przy restarcie; nie zeruj ich. Start oznacz czasem, wersją i unikalnym ID uruchomienia, powiąż późniejsze operacje. Przy normalnym zamknięciu zapisz zakończenie; jego brak może wskazywać przerwanie.
- Stosuj rotację według rozmiaru i ograniczoną liczbę archiwów, zachowując historię sprzed restartu po błędzie.
- Logi trzymaj w lokalnym katalogu danych użytkownika; nie dołączaj ich do repozytorium, EXE/ZIP ani wydania GitHub.
