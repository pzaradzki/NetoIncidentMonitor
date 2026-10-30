# Logowanie i diagnostyka

## Zasady działania

- Chromium korzysta z osobnego lokalnego profilu aplikacji. Nie kopiuje poświadczeń z innych przeglądarek.
- Automatyzacja działa wyłącznie na stronach HTTPS obsługiwanych serwerów ADEO IdP.
- Przy wyłączonym automatycznym logowaniu ręczny formularz jest przywoływany bez dodatkowego opóźnienia. Przy włączonym automatycznym logowaniu aplikacja daje 5 sekund na autouzupełnienie od gotowości widocznego, edytowalnego i niezasłoniętego pola hasła, także po wyborze zapamiętanego konta. Potem przywołuje przeglądarkę, ale nie blokuje automatyzacji. Późniejsze autouzupełnienie może zostać użyte, dopóki użytkownik nie przejmie formularza. Wpisanie, wklejenie lub ręczne zatwierdzenie nadal oddaje kontrolę użytkownikowi. Gdy gotowego pola nie rozpoznano, pozostaje awaryjny limit przywołania po 20 sekundach.
- Skrypt obserwujący ręczną edycję formularza jest instalowany przed nawigacją, także dla nowych dokumentów i ramek. Nie pobiera treści wpisywanych wartości.
- Wpisywanie lub wklejanie danych oddaje kontrolę użytkownikowi do końca bieżącej próby logowania. Ochrona działa również po wyborze zapamiętanego konta i podczas oczekiwania na automatyczne kliknięcie.
- Ręczne kliknięcie linku/przycisku logowania jest również wykrywane. Informacja o oddaniu kontroli pozostaje w pamięci aplikacji po nawigacji, więc nie znika razem z dokumentem. Dwie aktywacje podczas jednej automatycznej próby nie powodują podwójnego wysłania.
- Wymiana pola hasła unieważnia zgodę wynikającą z wcześniejszego wyboru konta. Aplikacja przechodzi wtedy do ręcznej obsługi zamiast używać stanu poprzedniego formularza.
- Wypełnione pole bez potwierdzenia autouzupełnienia nie jest samodzielnym dowodem zapamiętania hasła. Po automatycznym wyborze jednego konta można zatwierdzić formularz, jeśli nie wykryto ręcznej edycji.
- Wiele kont, wiele pól hasła, MFA lub błąd formularza wymagają ręcznej obsługi. Formularz w osobnym oknie otwartym przez kartę monitoringu jest pokazywany użytkownikowi; automatyzacja nie wybiera tam konta.
- Ponowienie kliknięcia logowania jest dozwolone tylko po potwierdzeniu, że poprzednia próba nie wywołała akcji. Niejednoznaczny wynik nie powoduje ponownego wysłania. Limit wynosi trzy próby.
- Przywracanie ukrytego okna ma trzy próby oddzielone co najmniej dwiema sekundami. Po potwierdzeniu widoczności aplikacja respektuje późniejsze zminimalizowanie okna. Jeśli przywrócenie nie zostało potwierdzone, użytkownik otrzymuje komunikat w aplikacji.
- Początkowy błąd sieci ma ograniczone ponowienia. Jeśli wolna nawigacja pozostawiła stronę HTTPS, aplikacja sprawdza jej stan zamiast przerywać rozpoczęte logowanie.
- Sesję można potwierdzić przez bezpieczny znacznik zalogowanego użytkownika ServiceNow, niezależnie od rekordów pierwszego filtra. Sprawdzenie zwraca tylko wartość logiczną, bez identyfikatora użytkownika. Gdy znacznik jest niedostępny, pozostaje potwierdzenie przez rzeczywiście załadowaną listę. Brak obu potwierdzeń przez 180 sekund kończy oczekiwanie czytelnym błędem. Ten limit nie ogranicza czasu ręcznego logowania ani MFA.
- Dashboard wykrywa utratę sesji, korzysta z tej samej procedury logowania co filtry i ponawia przerwaną sekcję jeden raz.
- Aktualizacja dashboardu rozpoczyna się jednym pełnym otwarciem SLA. Wstrzymane i Wnioski są odczytywane przez przełączenie zakładek w tym samym załadowanym obszarze. Jeśli odpowiednia zakładka jest już aktywna, dodatkowe kliknięcie jest pomijane. Inny dashboard lub lista wymagają pełnego otwarcia; nieudane przełączenie ma najwyżej jedną próbę awaryjnego przeładowania. Strona SSO nie jest zastępowana taką nawigacją.
- Zamknięcie osobnego okna logowania bez potwierdzonej sesji zatrzymuje monitoring z wyjaśnieniem. Potwierdzona sesja w nadal otwartym oknie pozwala wznowić pracę w głównej karcie.
- Nawigacja ma pojedyncze oczekiwanie na rozpoczęcie ograniczone do jednej sekundy, a dalsze ładowanie i oczekiwanie na kontrolki odbywa się w krótkich odcinkach ze sprawdzeniem przycisku Zatrzymaj. Nawigacja nie jest ponawiana przy każdym krótkim przekroczeniu czasu. Automatyczne kliknięcie logowania ma limit pięciu sekund; gotowość przycisku jest wcześniej sprawdzana krótkimi próbami bez wysłania formularza. Gotowość kontrolek dashboardu jest sprawdzana próbami bez rzeczywistego kliknięcia, co 500 ms, do 30–60 sekund. Właściwe działanie na gotowej kontrolce ma limit pięciu sekund. Już dostarczonego żądania logowania nie można cofnąć.
- Po zamknięciu Chromium przerwy przed restartami wynoszą 2, 4 i 8 sekund. Czwarta awaria/zamknięcie w oknie 60 sekund zatrzymuje automatyczne restarty i pokazuje komunikat. Po spokojniejszym okresie budżet prób się odnawia.

## Zmiana ustawień podczas monitoringu

Trzy preferencje są przekazywane do wątku monitoringu przez zabezpieczoną blokadą kopię wartości. Wątek roboczy nie odczytuje zmiennych Tk, a interfejs nie wywołuje metod Playwright.

- Wyłączenie automatycznego logowania blokuje kolejne automatyczne działania. Polecenie już wysłane do przeglądarki może się zakończyć; nie jest powtarzane.
- Włączenie automatycznego logowania pozwala rozpocząć je w bieżącym oczekiwaniu, jeżeli użytkownik nie przejął formularza i nie wystąpiła przyczyna wymagająca ręcznej obsługi. Samo przełączenie opcji nie zeruje blokady ani liczników wysłania.
- Ukrywanie i minimalizacja zmieniają się podczas pracy. Całkowite ukrywanie ma pierwszeństwo nad minimalizacją.
- W czasie ręcznego logowania zmiany sposobu ukrywania są odroczone do potwierdzenia sesji. Polecenie Pokaż z zasobnika nadal umożliwia przywrócenie okna.
- Przełączenia preferencji i odroczenie ukrywania trafiają do diagnostyki jako flagi logiczne.

## Logi

W wersji EXE pliki znajdują się w `%LOCALAPPDATA%\NetoIncidentMonitor`:

- `login-diagnostics.jsonl` — szczegółowe zdarzenia logowania; rotacja 2 MB i trzy archiwa;
- `monitor.log` — ogólny przebieg aplikacji i stałe komunikaty błędów; również z rotacją.

Każdy wpis diagnostyki zawiera czas UTC, identyfikator próby `session`, identyfikator uruchomienia przeglądarki `trace`, numer `sequence`, czas od początku próby i kod `event`. Wspólny `trace` łączy początkową nawigację, logowanie i odczyty dashboardu. Dedupikacja ogranicza identyczne powtarzające się wpisy do jednego na 10 sekund.

Przechowywane są wyłącznie dozwolone pola i wartości: liczby kontrolek, flagi obecności/autouzupełnienia/ręcznej edycji, typ etapu, numer próby, status HTTP, kategoria błędu sieciowego oraz znormalizowany typ wyjątku. Nazwy kategorii stron to `adeo_identity`, `servicenow` i `other`; adres nie jest zapisywany.

Pole `error_category` rozróżnia m.in. zajęty profil (`profile_locked`), brak Chromium (`browser_missing`), przekroczenie czasu (`timeout`), zmianę dokumentu podczas odczytu (`document_changed`), niejednoznaczną kontrolkę (`ambiguous_locator`) oraz problemy DNS, połączenia i certyfikatu. Klasyfikacja analizuje wyjątek wyłącznie w pamięci i zapisuje stały kod.

Diagnostyka nie zapisuje loginów, haseł, wartości pól, treści HTML, tekstu strony, cookies, nagłówków HTTP, tokenów SSO, adresów SSO ani zrzutów formularza. Nieznane pola i dowolne teksty są odrzucane przez listę dozwolonych wartości. Komunikaty wyjątków przeglądarki nie są dodawane do logów odczytu/logowania. Formatowanie wyjątków w `monitor.log` zachowuje typ oraz lokalizacje błędu bez komunikatu wyjątku i bez treści linii źródłowych.

Surowe wyjście konsoli bibliotek jest pomijane; log odnotowuje tylko jego wystąpienie i liczbę znaków. Dzięki temu tekst wyjątku wypisany przez bibliotekę na stderr nie omija zabezpieczeń. Nieobsłużone wyjątki wątków są przechwytywane osobno i zapisywane przez bezpieczny formatter.

### Przydatne zdarzenia

| Zdarzenie | Znaczenie |
| --- | --- |
| `initial_navigation_attempt`, `initial_navigation_error` | Otwarcie strony i wynik nieudanej próby |
| `navigation`, `document_response`, `document_failed` | Przekierowanie, status HTTP lub kategoria awarii sieci |
| `page_state` | Bezpieczny stan formularza i automatyzacji |
| `account_click_attempt`, `account_clicked`, `account_click_error` | Próba wyboru konta i jej wynik |
| `account_waiting_ready` | Oczekiwanie na gotowość kafelka bez zużywania prób; stały kod `readiness_reason`, bez tekstu strony |
| `submit_waiting_ready` | Przycisk zatwierdzenia jeszcze nie przyjmuje kliknięcia; oczekiwanie nie zużywa prób wysłania formularza |
| `blocked` | Powód oddania kontroli użytkownikowi |
| `submit_attempt`, `submit_clicked`, `submit_error` | Próba zatwierdzenia i potwierdzone lub niejednoznaczne dostarczenie |
| `submit_retry_scheduled`, `submit_retry_cancelled` | Decyzja o ponowieniu lub jego anulowaniu |
| `manual_login_show_attempt`, `manual_login_show_retry` | Próba przywrócenia okna, jeszcze bez potwierdzenia |
| `manual_login_shown`, `manual_login_show_failed` | Potwierdzona widoczność albo wyczerpanie prób |
| `authentication_popup` | Logowanie przeniosło się do osobnego okna |
| `authentication_popup_closed` | Okno logowania zostało zamknięte |
| `session_confirmed` | Potwierdzono zalogowanie niezależnie od rekordów filtra |
| `browser_options_changed`, `visibility_deferred` | Zmiana preferencji lub odroczenie ukrywania na czas ręcznego logowania |
| `browser_activity` | Etap `login`, `dashboard` lub `filters`; logowanie i dashboard wymagają widocznego okna, a filtry stosują aktualne ustawienia widoczności |
| `browser_restart_delay`, `browser_restart_limited` | Przerwa przed restartem albo wyczerpanie budżetu restartów |
| `login_complete`, `login_cancelled`, `target_unavailable` | Wynik oczekiwania na sesję/listę |
| `dashboard_operation` | Konkretny etap odczytu: nawigacja, okres, pola dat, wybór kategorii, zastosowanie filtrów lub odczyt wartości |
| `dashboard_navigation` | Wykorzystanie już załadowanego dashboardu (`reused: true`) albo pełne otwarcie strony (`reused: false`) |
| `dashboard_scores_attempt`, `dashboard_scores_retry`, `dashboard_scores_error` | Pierwszy odczyt Wnioski L1 i maksymalnie jedno ponowienie po przeładowaniu karty |
| `dashboard_widgets_activated` | Liczba kontenerów widżetów przewiniętych do widocznego obszaru; bez ich treści i położenia |
| `dashboard_tile_state`, `dashboard_tile_missing` | Stała nazwa jednego z czterech kafelków Wnioski L1 i kod stanu: gotowy, brak, niejednoznaczny, nieprawidłowa liczba lub niedostępny; bez wartości kafelka i tekstu strony |
| `section_read_partial` | Odczyt nie zawiera kompletu danych; nie jest zapisywany jako `section_read_complete` |
| `session_expired`, `section_read_attempt`, `section_read_complete`, `section_read_error` | Odzyskiwanie sesji i ponowienie sekcji dashboardu |

## Testy

Chromium jest pokazywane automatycznie bez aktywowania okna i umieszczane za istniejącymi oknami. Startuje zminimalizowane, po czym natywny kontroler przywraca je pasywnie przed logowaniem. Przy pierwszym pokazaniu i przywróceniu ukrytego/zminimalizowanego okna kontroler przez maksymalnie sekundę chroni poprzedni fokus przed opóźnioną aktywacją przez proces naszego Chromium. Inne aplikacje nie są objęte tą ochroną. Nie zmienia globalnych ustawień blokady fokusu Windows; tymczasowe połączenie obsługi wejścia jest zawsze odłączane w `finally`. Zwykłe ponowne sprawdzenie już widocznego okna nie czeka. Jawne polecenie Pokaż przeglądarkę nadal aktywuje okno, a wykryta potrzeba ręcznego logowania lub MFA również przywołuje właściwą kartę lub okno na pierwszy plan. Po potwierdzonym przywołaniu aplikacja nie ponawia fokusowania, jeśli użytkownik sam zminimalizuje przeglądarkę.

Gotowość przycisku zatwierdzenia jest sprawdzana próbnie w odcinkach do 500 ms, bez wysyłania formularza i bez zużywania trzech prób kliknięcia. Rzeczywiste kliknięcie ma limit 5 sekund i nie czeka na zakończenie nawigacji. Przed nim ponownie sprawdzane są ręczna obsługa, ustawienie automatycznego logowania, tożsamość dokumentu i pola hasła oraz ewentualne spóźnione dostarczenie poprzedniego kliknięcia. Nieznany wynik dostarczenia nadal wyklucza ponowne wysłanie.

Wnioski L1 przed odczytem weryfikują wybór wszystkich agentów i w razie potrzeby zatwierdzają go przyciskiem Zastosuj. Odczyt czeka do 60 sekund na komplet czterech liczbowych kafelków, brak widocznego komunikatu ładowania i stabilność danych przez sekundę. Po niepełnym odczycie karta jest przeładowywana raz, ponownie weryfikowany jest filtr agentów i wykonywany drugi odczyt. Anulowanie i wygaśnięcie sesji trafiają do dotychczasowej obsługi zatrzymania/logowania, zamiast wywoływać kolejne ponowienia kafelków.

Liczba jest odczytywana bezpośrednio z `now-score-basic .now-score-value` wewnątrz karty odnalezionej po dokładnym nagłówku. Interaktywność i etykieta przycisku nie są warunkiem odczytu. Diagnostyka zapisuje stałe źródło `score_source` (`widget_value`, `button`, `none`) i flagę `button_available`, bez liczby ani tekstu strony. Komunikat ładowania, `aria-busy` i pasek ładowania są sprawdzane wewnątrz odpowiedniego kafelka, więc inne wykresy nie blokują kompletu gotowych liczników. Starszy, płaski układ nadal może korzystać z odczytu przycisku.

Przy pierwszym przejściu między kartami ServiceNow potrafi pozostawić widżety poza ekranem bez nagłówków i liczników, aż znajdą się w widocznym obszarze. Wspólny etap `prepare_widgets` działa we wszystkich trzech sekcjach: Dashboard SLA, Wstrzymane L1 i Wnioski L1. Po ustawieniu okresu i kategorii danej sekcji przewija kontenery `.grid-stack-item-content` według położenia na stronie. Nie wymaga jeszcze istnienia nagłówków. Po każdym przewinięciu oddaje 100 ms na obsługę widoczności i renderowanie, a pomiędzy kontenerami sprawdza zatrzymanie oraz sesję. Odczyt liczb i kontrola stabilności następują po tej inicjalizacji.

Testy automatyczne używają lokalnie przechwytywanych formularzy w Chromium i danych zastępczych. Nie łączą się z rzeczywistym SSO i nie wykorzystują kont użytkowników.

Zestaw obejmuje ręczną edycję przed pierwszym sprawdzeniem, po wyborze konta i w trakcie kliknięcia, zachowanie ręcznego przycisku po rezygnacji automatyzacji, ograniczenia ponowień, MFA, wiele kont, przywracanie prawdziwego okna Windows, zamknięcie przeglądarki, błędy pierwszej nawigacji, anulowanie, logowanie w ramce, wykrywanie powiązanego okna, odzyskanie sesji dashboardu oraz brak danych zastępczych poświadczeń w obu formatach logów.

Przed wydaniem warto dodatkowo wykonać testy na rzeczywistym koncie ADEO:

1. Świeży profil: pokazać formularz, zalogować się ręcznie i sprawdzić wznowienie odczytu.
2. Profil z zapamiętanym kontem: uruchomić monitoring z ukrytym Chromium i potwierdzić automatyczne przejście do listy.
3. Podczas logowania ręcznie rozpocząć wpisywanie hasła; aplikacja ma pozostawić zatwierdzenie użytkownikowi.
4. Wywołać MFA, zmianę hasła lub wybór kilku kont i sprawdzić pokazanie właściwego okna.
5. Zminimalizować już pokazane okno; aplikacja nie powinna uporczywie przywracać go ponownie.
6. Wygasić sesję podczas aktualizacji dashboardu i sprawdzić wznowienie tej samej sekcji po logowaniu.
7. Przerwać sieć, zamknąć Chromium i użyć przycisku Zatrzymaj; sprawdzić komunikaty oraz zakończenie/ponowienie zgodne z wybraną akcją.
8. Przejrzeć logi i upewnić się, że zawierają etapy oraz wyniki, bez wartości formularzy i adresów SSO.

Te scenariusze rzeczywistego SSO zależą od polityk konta, MFA i stanu profilu; testy lokalne ich nie zastępują.
