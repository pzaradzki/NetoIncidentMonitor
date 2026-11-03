# Logowanie i diagnostyka

Stan: **2 listopada 2026, 1.8.0**. Bieżący kontrakt; zastępuje [wcześniejszy opis](../archiwum/diagnostyka-logowania-przed-1.8.0.md). Mapa modułów: [architektura](../architektura.md).

## Logowanie

- Jeden snapshot rozróżnia `authentication`, `logout`, `unknown`, `target` i `session`. Potwierdzenie sesji wymaga dodatniego dowodu we właściwym kontekście bez konfliktu formularza, ramek lub własnego popupu; nie pobiera pierwszej listy. [008](../decyzje/008-obserwacja-logowania.md).
- Automatyczne akcje i wsparcie renderowania dopuszczają tylko rozpoznane HTTPS `idpb2e.adeo.com:443`, bez userinfo. Nieznany formularz jest przekazywany użytkownikowi, nie automatyzowany przez zgadywanie selektorów.
- Jedno konto może być wybrane automatycznie; wiele kont wybiera użytkownik. Sam wybór nie oznacza ręcznej własności późniejszego formularza i nie zastępuje potwierdzenia CSS autofill. Pisanie/wklejenie, ręczne wysłanie, MFA i odrzucenie danych mają pierwszeństwo.
- Gotowe puste pole otrzymuje 5 s na autofill, potem okno jest udostępniane użytkownikowi. Późny autofill może wznowić automat przed ręcznym przejęciem. To nie jest odczyt magazynu haseł ani dowód braku zapisanego wpisu.
- Przed akcją ponownie sprawdzane są ustawienia, origin, formularz i ingerencja. Trial i właściwe kliknięcie są ograniczone do 500 ms. Co najwyżej 3 próby; ponowienie wyłącznie po potwierdzonym braku dostarczenia. Dostarczony lub niepewny POST nie jest ponawiany przy zmianie dokumentu/opcji.
- Auto+hide pozostaje ukryte. Auto off, potrzebna ręczna obsługa, błąd mechanizmu lub jawne „Pokaż” udostępniają okno. Po potwierdzonym pokazaniu nie ma pętli odbierania fokusu. Wsparcie [009](../decyzje/009-renderowanie-ukrytego-logowania.md) kończy się przed ręcznym pokazaniem; nie zapisuje ani nie dekoduje payloadu klatek auth.
- Logout, sieć i brak postępu mają ograniczone odzyskiwanie zwykłego celu GET, z odstępami 5/15/60/300 s. Nie odtwarzamy URL SSO ani nie nadpisujemy ręcznej/niepewnej próby. Monitoring oczekuje do odzyskania albo Stop. Zamknięty popup nie jest sam w sobie sukcesem lub poleceniem zatrzymania.
- Zamknięcie Chromium korzysta z dotychczasowego budżetu restartów; nie kasujemy profilu. Permanentna awaria startu/profilu nie jest bezterminowo naprawiana. Zegary są zabezpieczeniami; zawieszenie procesu renderera może opóźnić kooperacyjny Stop.

## Diagnostyka

W EXE: `%LOCALAPPDATA%/NetoIncidentMonitor`; w źródłach: lokalny `data/`. `monitor.log` i `login-diagnostics.jsonl` dopisują przy restarcie i rotują (2 MB, 3 archiwa). Nie dołączać ich do pakietów.

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

Allowlista odrzuca dowolne teksty i nieznane pola przed zapisem. Bez loginów, haseł, cookies, tokenów, pełnych URL SSO, HTML, danych zgłoszeń i surowych wyjątków. Źródłem kodów/pól jest `login_diagnostics.py`, nie ta skrócona tabela. Awaria zapisu/rotacji diagnostyki nie przerywa funkcji: stałe ostrzeżenie raz, ponowienie IO po 30 s i sygnał przywrócenia; rekordy w czasie awarii mogą zostać utracone.

Zakres testów, pomiary rzeczywiste/syntetyczne i ograniczenia MFA/Windows: [raport odbioru](../weryfikacja/odbior-stabilizacji-logowania.md). Nie gwarantujemy obsługi dowolnej przyszłej zmiany SSO.
