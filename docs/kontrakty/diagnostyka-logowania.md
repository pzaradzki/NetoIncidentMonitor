# Logowanie i diagnostyka

Stan: **2 listopada 2026, 1.8.0**. Bieżący kontrakt; zastępuje [wcześniejszy opis](../archiwum/diagnostyka-logowania-przed-1.8.0.md). Mapa modułów: [architektura](../architektura.md).

## Logowanie

- `SharedSession` wywołuje na swoim wątku `browser_login` i pomocnicze operacje z `browser_actions`. Tk odbiera zdarzenia o gotowości sesji, ręcznym logowaniu i potwierdzeniu zapisu hasła. [Podział modułów](../decyzje/042-granice-app-i-sesji.md)
- Jeden snapshot rozróżnia `authentication`, `logout`, `unknown`, `target` i `session`. Potwierdzenie sesji wymaga dodatniego dowodu we właściwym kontekście bez konfliktu formularza, ramek lub własnego popupu; nie pobiera pierwszej listy. [008](../decyzje/008-obserwacja-logowania.md).
- Automatyczne akcje i wsparcie renderowania dopuszczają tylko rozpoznane HTTPS `idpb2e.adeo.com:443`, bez userinfo. Nieznany formularz jest przekazywany użytkownikowi, nie automatyzowany przez zgadywanie selektorów.
- Jedno konto może być wybrane automatycznie; wiele kont wybiera użytkownik. Sam wybór nie oznacza ręcznej własności późniejszego formularza i nie zastępuje potwierdzenia CSS autofill. Pisanie/wklejenie, ręczne wysłanie, MFA i odrzucenie danych mają pierwszeństwo.
- Gotowe puste pole otrzymuje 5 s na autofill, potem okno jest udostępniane użytkownikowi. Późny autofill może wznowić automat przed ręcznym przejęciem. To nie jest odczyt magazynu haseł ani dowód braku zapisanego wpisu.
- Przed akcją ponownie sprawdzane są ustawienia, origin, formularz i ingerencja. Trial i właściwe kliknięcie są ograniczone do 500 ms. Co najwyżej 3 próby; ponowienie wyłącznie po potwierdzonym braku dostarczenia. Dostarczony lub niepewny POST nie jest ponawiany przy zmianie dokumentu/opcji.
- Auto+hide pozostaje ukryte. Auto off, potrzebna ręczna obsługa, błąd mechanizmu lub jawne „Pokaż” udostępniają okno. Po potwierdzonym pokazaniu nie ma pętli odbierania fokusu. Wsparcie [009](../decyzje/009-renderowanie-ukrytego-logowania.md) kończy się przed ręcznym pokazaniem; nie zapisuje ani nie dekoduje payloadu klatek auth.
- Logout, sieć i brak postępu mają ograniczone odzyskiwanie zwykłego celu GET, z odstępami 5/15/60/300 s. Nie odtwarzamy URL SSO ani nie nadpisujemy ręcznej/niepewnej próby. Monitoring oczekuje do odzyskania albo Stop. Zamknięty popup nie jest sam w sobie sukcesem lub poleceniem zatrzymania.
- Po zamknięciu Chromium sesja zgłasza problem i czeka na świadome ponowne połączenie. Profil zostaje zachowany. Zawieszenie procesu renderera może opóźnić kooperacyjny Stop. [Decyzja 025](../decyzje/025-wspolna-sesja-servicenow.md)

## Diagnostyka

EXE zapisuje logi w `%LOCALAPPDATA%/NetoIncidentMonitor`. Źródła używają `%LOCALAPPDATA%/NetoIncidentMonitor-SourceLogs/<id-kopii>`. `monitor.log` i `login-diagnostics.jsonl` dopisują przy restarcie i rotują (2 MB, 3 archiwa). Logi pozostają poza pakietami. [Decyzja 045](../decyzje/045-logi-uruchomien-ze-zrodel.md)

Dokładną ścieżkę bieżącej kopii źródeł wyświetla polecenie uruchomione w katalogu projektu.

```powershell
.\.venv\Scripts\python.exe -B -c "from neto_incident_monitor.runtime_paths import LOG_DIR; print(LOG_DIR)"
```

Korelacja: `run_id`, `trace`, `read_id`, `action_id`, `session`, `sequence`, generacja dokumentu. Zapisywane są wybrane stany, dowody, kategorie błędu, czasy, próby, dostarczenie i widoczność. Identyczne wpisy są ograniczane, zmiany stanów zachowywane. Typowe zdarzenia:

| Zdarzenia | Znaczenie |
| --- | --- |
| `login_state_changed`, `page_state` | Stan i strukturalne booleany, bez wartości pól |
| `account_click_attempt`, `account_clicked`, `account_awaiting_result` | Wybór konta i oczekiwanie na skutek |
| `submit_attempt`, `submit_clicked`, `submit_retry_cancelled` | Próba i kontrakt dostarczenia |
| `login_user_required`, `blocked` | Potrzebna pomoc lub trwałe przejęcie formularza |
| `manual_login_shown`, `manual_login_show_retry`, `manual_login_show_failed` | Wynik udostępnienia okna |
| `login_recovery`, `document_failed`, `document_response` | Odzyskiwanie i sklasyfikowany stan sieci |
| `rendering_start`, `rendering_stop`, `rendering_error` | Zakres renderowania, czas i liczniki techniczne |
| `session_confirmed`, `login_complete`, `login_cancelled` | Potwierdzenie i zakończenie przebiegu |
| `filter_card_count` | Zmiana licznika karty po przyjęciu wyniku lub wyświetleniu listy oraz odrzucenie spóźnionego potwierdzenia. Pola liczbowe mogą obejmować pozycję filtra, obie liczby z karty i czas od zakończenia wczytywania do potwierdzenia wyświetlenia. |
| `filter_config_change` | Zmiana konfiguracji filtra. Przy udanym przełączeniu harmonogramu zapis obejmuje pozycję filtra i liczbę zgłoszeń w zachowanej liście, jeśli filtr ma przyjęty wynik. |
| `dashboard_layout` | Przejście między widokiem mieszczącym wszystkie kafelki a przewijaniem. Zapisuje wysokość obszaru, wspólną wysokość kafelków oraz minimum wynikające z ich zawartości. |
| `dashboard_schedule` | Źródło, początek i wynik próby dashboardu. Dla cyklu obejmuje interwał, zwłokę względem terminu i rodzaj pracy poprzedzającej odczyt. ID odczytu łączy zdarzenie z sekcjami dashboardu. |
| `schedule_interval_change` | Walidacja, zapis i zastosowanie ustawienia interwału. Obejmuje zagrożenia SLA także przy zapisaniu zmiany w trakcie odczytu. |
| `threatened_schedule`, `threatened_read_finished` | Pierwsze zdarzenie zapisuje interwał, zwłokę i jej przyczynę dla odczytu po terminie. Drugie zapisuje wynik oraz czas próby, także po błędzie, anulowaniu lub utracie karty. ID odczytu łączy je ze zdarzeniami sekcji. |

Allowlista odrzuca dowolne teksty i nieznane pola przed zapisem. Bez loginów, haseł, cookies, tokenów, pełnych URL SSO, HTML, danych zgłoszeń i surowych wyjątków. Źródłem kodów/pól jest `login_diagnostics.py`, nie ta skrócona tabela. Awaria zapisu/rotacji diagnostyki nie przerywa funkcji: stałe ostrzeżenie raz, ponowienie IO po 30 s i sygnał przywrócenia; rekordy w czasie awarii mogą zostać utracone.

Zakres testów, pomiary rzeczywiste/syntetyczne i ograniczenia MFA/Windows: [raport odbioru](../weryfikacja/odbior-stabilizacji-logowania.md). Nie gwarantujemy obsługi dowolnej przyszłej zmiany SSO.
