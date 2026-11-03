# Odbiór stabilizacji dashboardu i zagrożeń

> Raport dotyczy wskazanej w nim serii źródeł i pomiarów. Późniejszy lokalny build EXE 1.8.0 opisano [osobno](../releases/v1.8.0.md); nie zastępuje on prób rzeczywistego SSO.

1 listopada 2026. Zakres: źródła aplikacji 1.7.17; bez zmiany wersji, EXE, ZIP, commita i publikacji. Realizuje oba [plany](../plans/README.md).

## Wdrożone zabezpieczenia

- Jeden lokalny czytnik dla czterech sekcji: tytuł, liczba, lokalne ładowanie, kompletność i końcowe potwierdzenie kontekstu. Brak zależności od obcych wykresów i metadanych przycisku.
- Jawna kontrola dashboardu, zakładki, miesiąca SLA i wszystkich wymaganych kategorii. Osobne zatwierdzanie kategorii, odświeżenie z obserwacją lub bezpieczne odtworzenie dokumentu. Obsługa leniwych kart i opóźnionego popovera daty.
- Jeden właściciel odzyskiwania: najwyżej dwie próby w aktywnym budżecie 60 s, z rezerwą na drugą próbę i osobnym rozliczaniem ręcznego logowania. Anulowanie, utrata sesji i zamknięcie przeglądarki pozostają odrębnymi ścieżkami.
- Osobne kompletne wyniki, daty i próby sekcji w cache schematu 2. Zachowanie poprzednich wartości po błędzie; migracja bez wymyślania historycznych dat. WJRUW wyłącznie z jednego zestawu SLA.
- Rozszerzona korelacja i bezpieczne pomiary etapów, kontekstu, ponowień, zapisu i spóźnień harmonogramu. Brak poświadczeń, tokenów, HTML, treści zgłoszeń i biznesowych wartości liczników w diagnostyce.

## Rzeczywista strona ServiceNow

Inspekcja w przeglądarce Codex potwierdziła lokalną strukturę kart, kontrolki dat i kategorii, ładowanie po przewinięciu oraz sześć linków zagrożeń. Wszystkie prowadzą do filtrów `task_sla_list.do` zgodnych z aplikacją. Nie potwierdzono, że suma kategorii oznacza unikalne incydenty; aplikacja jej tak nie interpretuje.

Następnie uruchomiono rzeczywiste czytniki Python/Playwright w oddzielnym testowym Chromium, z ręcznym logowaniem użytkownika i tymczasowym profilem. Wcześniejsze serie ujawniły wyścigi podczas podmiany elementów DOM: między sprawdzeniem obecności a odczytem atrybutu/położenia. Poprawiono obserwacje stanu i tolerowanie podmiany podczas przygotowania kart, dodając regresję.

Końcowa seria: **9/9 poprawnych odczytów**, bez odzyskiwania w drugiej próbie:

| Próba | Sekcja | Czas pełnego odczytu |
| --- | --- | --- |
| Po zalogowaniu | Zagrożenia — komplet 6 | 6,469 s |
| Pierwsza | SLA — komplet 11 | 12,125 s |
| Pierwsza | Wstrzymane — komplet 2 | 4,531 s |
| Pierwsza | Wnioski — komplet 4 | 5,437 s |
| Ponowna | SLA | 15,250 s |
| Ponowna | Wstrzymane | 4,516 s |
| Ponowna | Wnioski | 5,047 s |
| Zmiana miesiąca | SLA | 16,781 s |
| Przywrócenie okresu | SLA | 17,313 s |

Potwierdzono przywrócenie pierwotnego okresu. Nie kopiowano profilu działającego monitora ani danych zgłoszeń. Pomiary inspekcji Codex i pełnego silnika mają różny zakres; nie służą jako porównywalny benchmark przyspieszenia.

## Testy automatyczne

Testy obejmują m.in. opóźnione wartości i loadery, dodatkowy nieskończenie ładowany wykres, Shadow DOM, podmianę kontrolek, leniwe kategorie, zmieniony próg zagrożenia, niejednoznaczne karty, zły kontekst, zmianę daty, budżet z ponowieniem, logowanie poza budżetem, opóźnione zakończenie przerwanej nawigacji, Stop, częściowe/stare wyniki, migrację i błąd zapisu cache oraz brak syntetycznych sekretów w logach.

Pełna regresja: **52 moduły, 315 testów — 314 zaliczonych, 1 pominięty**, bez niepowodzeń (`data/stabilization-full-tests-final.log`). Pominięto istniejący pomiar fokusu Windows, ponieważ system nie przyznał testowej aplikacji pierwszego planu.

Końcowe testy czytnika, nawigacji, żądań, cache i odzyskiwania: **35 testów zaliczonych** (`data/dashboard-final-regression.log`), w tym dodatkowy przypadek podmiany kontrolek dodany po rozpoczęciu pełnego przebiegu. Test opóźnionego zakończenia nawigacji: moduł odzyskiwania **5/5**. Moduły pełnej regresji uruchamiano w osobnych procesach ze względu na współistnienie Tk i Playwright. `git diff --check`: bez błędów; dwa wcześniejsze pliki testów mają ostrzeżenie konwersji LF/CRLF.

## Granice odbioru i następny krok

To weryfikacja źródeł i integracji UI, nie nowego EXE. Budowa i test gotowego EXE wymagają osobnego polecenia zgodnie z zakresem użytkownika. Nie dodano powiadomień o zagrożeniach ani równoległego pobierania.

UI nie udostępnia transakcyjnego znacznika wersji całego dashboardu. Lokalna gotowość, kontekst i obserwacja odświeżenia ograniczają ryzyko, lecz nie dowodzą atomowego stanu bazy. Budżet jest kooperacyjny; nie przerywa procesu Chromium zablokowanego poza obsługą Playwright. Dziewięć sukcesów nie gwarantuje dostępności ServiceNow ani odporności na przyszłą przebudowę raportów.
