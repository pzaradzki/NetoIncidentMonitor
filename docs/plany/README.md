# Plany i pozostałe prace

Według [indeksu wersji](../wersje/README.md) ostatnia odnotowana paczka lokalna to [1.12.0-experimental.3](../wersje/v1.12.0-experimental.3.md), a ostatnie odnotowane wydanie publiczne to [1.11.2](../wersje/v1.11.2.md).

## Pozostałe tematy

- [Pobranie brakujących list agentów i lokalizacji po logowaniu](startowy-odczyt-zakresu-dashboardu.md) jest wdrożone w źródłach i lokalnej paczce. Pozostaje rzeczywisty odbiór na ADEO.
- Ustalić retencję outbox i lokalizację logów uruchomień ze źródeł. Pomiary opóźnień Tk odłożono do osobnej pracy. [Wyniki audytu](zakonczone/naprawy-audytu.md)
- Wrócić do luki diagnostycznej, jeśli powtórzy się po pełnym cyklu i normalnym zamknięciu. [Opis obserwacji](../wersje/v1.8.1.md)
- Potencjalny kanał e-mail. Potwierdzono pojedynczą wysyłkę i dostarczenie. Otwarte są zasady relay i działanie na innych komputerach. [Rozpoznanie SMTP](../analizy/powiadomienia-email-smtp.md)

## Zakończone plany

| Plan | Wynik / dowody |
| --- | --- |
| [Wycofanie starszej pętli monitoringu](zakonczone/wycofanie-starszej-petli.md) | Wdrożono w źródłach. Dashboard, zagrożenia SLA i filtry korzystają ze wspólnej sesji. W pełnej regresji Windows zaliczono 533 testy, a 2 pominięto. |
| Okres dashboardu w `SharedSession` | Testy obejmują blokadę od zakolejkowania, ponowienie logowania, ponowne połączenie, spóźnione zdarzenia i Stop. Poprawiono odblokowanie odczytu automatycznego po zamknięciu Chromium. Pełna powtórzona regresja objęła 547 testów, z czego 546 zaliczono i jeden pominięto. [Testy okresu](../../tests/test_dashboard_period.py) |
| Harmonogram zagrożeń SLA w `SharedSession` | Sprawdzono pojedynczy zaległy odczyt po dashboardzie i między filtrami, termin 60 s od zakończenia sukcesu, błędu lub ręcznej próby oraz Stop. Poprawiono zapis przyczyny opóźnienia i sprawdzono korelację w JSONL. Zaliczone 55 prób zakresowych na danych syntetycznych. [Testy harmonogramu](../../tests/test_refresh_requests.py) |
| Kolejność odczytów w `SharedSession` | Testy startu cyklu i pełnego ręcznego odświeżenia ćwiczą normalne akcje `App`, kolejkę sesji i zapis migawek. Potwierdzono pominięcie wyłączonego dashboardu przy starcie, odczyt włączonych filtrów oraz kontynuację po błędzie sekcji. Regresja zakresowa na syntetycznych danych zaliczyła 76 testów. [Testy kolejności](../../tests/test_update_order.py) |
| Regresja dialogu zapytania i wspólnej sesji | Na pulpicie Windows zaliczono 112 prób z syntetycznymi danymi, w tym obie natywne próby startu Chromium i zapisu hasła. Podgląd zamyka się bez błędu Tcl, a dwie próby odzyskiwania dashboardu używają `SharedSession`. [Testy sesji](../../tests/test_shared_session.py) · [Testy odzyskiwania](../../tests/test_section_login_recovery.py) |
| [Restart po pierwszym zapisie zagrożeń SLA](../kontrakty/kolejka-i-trwalosc.md#lokalne-dane-i-migracja) | Naprawiono w źródłach. Regresja sprawdza kontrolę startową i zachowanie migawki z licznikiem oraz oczekującego alertu przed pierwszym zapisem filtra i po nim. [Test](../../tests/test_threatened_details.py) |
| [Trzy nowe kafelki Dashboardu SLA](zakonczone/nowe-kafelki-dashboardu-sla.md) | Wdrożono w źródłach. Trzy liczniki potwierdzone w Aggregate API ADEO, 80 izolowanych testów zaliczonych. |
| [Ujednolicenie statusów i nagłówków widoków](zakonczone/ujednolicenie-statusow-i-naglowkow.md) | Wdrożono w źródłach. Tk na Windows przy skali 100% i 125%, 522 testy zaliczone i 2 pominięte. |
| [Walidacja zmiennych katalogowych i złożonych warunków filtrów ServiceNow](zakonczone/walidacja-warunkow-filtrow-servicenow.md) | ADEO: Wnioski, SCTASK i RITM z progiem 4 dni, jedna sesja. 516 zaliczonych testów, 2 pominięte. |
| [Definicje filtrów ServiceNow bez otwierania klasycznej listy](zakonczone/definicje-filtrow-bez-klasycznej-listy.md) | ADEO: cztery typy list, skrót INC i widok nazwany REQ. 509 zaliczonych testów, 1 pominięty. |
| [Migracja importu Ulubionych ServiceNow na REST API](zakonczone/migracja-importu-ulubionych-na-api.md) | ADEO: 37 zakładek zgodnych z menu, w tym 34 obsługiwane filtry. 506 zaliczonych testów, 2 pominięte. |
| [Migracja odczytu filtrów ServiceNow na REST API](zakonczone/migracja-odczytu-filtrow-na-api.md) | 515 zaliczonych testów, 2 pominięte. Usunięto czytnik wierszy i paginację DOM. Szczegółowy odbiór na ServiceNow celowo pominięto. |
| [Wspólna sesja ServiceNow, jedna karta i kolejka operacji](zakonczone/wspolna-sesja-servicenow.md) | Pozostałe próby odbiorowe zaliczone według potwierdzenia użytkownika z 14 listopada 2026. |
| [Dashboard i Incydenty zagrożone SLA przez REST API](zakonczone/dashboard-servicenow-api.md) | Zgodność potwierdzona przez użytkownika. 538 testów zaliczonych, 1 pominięty. |
| [Paginacja listy zagrożeń przez DOM](zakonczone/paginacja-listy-zagrozen-sla.md) | Plan zastąpiony przez paginację REST. |
| [Wydanie 1.11.2](zakonczone/wydanie-1.11.2.md) | Opublikowano. 599 zaliczonych testów, 2 pominięcia, dwie próby offline i zgodność publicznie pobranego ZIP-a. |
| [Lokalne wydanie 1.11.1](zakonczone/wydanie-1.11.1-lokalne.md) | 81 testów, zgodność 1444 plików i dwie próby offline. Kopia 1.11.0 zachowana. |
| [Lokalne wydanie 1.11.0](zakonczone/wydanie-1.11.0-lokalne.md) | 19 testów, zgodność 1444 plików ZIP i dwie próby offline. Kopia 1.10.0 zachowana. |
| [Odzyskanie zmian po wydaniu 1.10.0](zakonczone/odzyskanie-zmian-po-v1.10.0.md) | Odtworzono 38 plików. Użytkownik potwierdził przywrócenie monitora jednym kliknięciem na pasku zadań. |
| [Wydanie 1.10.0](zakonczone/wydanie-1.10.0.md) | Opublikowano. Regresja 585 testów, 2 pominięcia. Potwierdzono zgodność EXE ze źródłami i SHA-256 pobranego ZIP-a. |
| [Import ulubionych ServiceNow](zakonczone/import-ulubionych-servicenow.md) | Wdrożone w źródłach: 555 testów, 2 pominięcia, bez błędów; DOM sprawdzony na ServiceNow. Pełny rzeczywisty odbiór użytkowy pozostaje osobny; bez nowego EXE. |
| [Wydanie 1.9.4](zakonczone/wydanie-1.9.4.md) | Opublikowano: 523 testy (2 pominięcia), build i offline smoke, zgodność tagu i SHA-256 ponownie pobranego ZIP-a. |
| [Zatwierdzanie okresu i filtrów](zakonczone/zatwierdzanie-kontekstu-dashboardu.md) | Lokalne EXE 1.9.3: 523 testy, 2 pominięcia, build i oba smoke OK; poprzednia paczka zachowana, bez publikacji. |
| [Wydanie 1.9.3](zakonczone/wydanie-1.9.3.md) | Opublikowano: 514 testów (2 pominięcia), build i offline smoke; zgodność tagu oraz SHA-256 pobranego ZIP-a. |
| [Synchronizacja statusów](zakonczone/synchronizacja-statusow-dashboardu.md) | Lokalne EXE 1.9.2: 514 testów (2 pominięcia), build i oba smoke OK; bez publikacji. |
| [Wydanie 1.9.2](zakonczone/wydanie-1.9.2.md) | Opublikowano: 505 testów (2 pominięcia), build i offline smoke, zgodność tagu oraz pobranego ZIP-a; bez odrzuconego eksperymentu. |
| [Odzyskiwanie dashboardu](zakonczone/odzyskiwanie-dashboardu-po-utracie-sesji.md) | 505 testów (2 pominięcia), kandydat i główne EXE 1.9.1 sprawdzone offline; bez nowej publikacji. |
| [Wydanie 1.9.1](zakonczone/wydanie-1.9.1.md) | Opublikowano: 495 testów (2 pominięcia), build i offline smoke, zgodność tagu oraz SHA-256 pobranego ZIP-a. |
| [Ukrycie autostartu Windows](zakonczone/ukrycie-autostartu-windows.md) | Przełącznik ukryty; mechanizm zachowany, domyślnie wyłączony; lokalny build i smoke OK. |
| [Kolejność aktualizacji](zakonczone/kolejnosc-aktualizacji.md) | Dashboard → zagrożenia → filtry; 493 testy (2 pominięcia), lokalny build i offline smoke; główna paczka zaktualizowana, bez publikacji. |
| [Naprawy audytu technicznego](zakonczone/naprawy-audytu.md) | A01–A06/A09 naprawione, A10 częściowo; końcowe 486 testów (2 pominięcia), pięć osobnych buildów i prób offline. Naprawy opublikowano później w [1.9.1](zakonczone/wydanie-1.9.1.md). |
| [Wydanie 1.9.0](zakonczone/wydanie-1.9.0.md) | 465 testów (463 zaliczone, 2 pominięte), kontrola ZIP i rozpakowanego EXE, publikacja i zgodność pobranej paczki. |
| [Obsługa długich adresów list](zakonczone/obsluga-dlugich-adresow-list.md) | 66 testów, rzeczywiste dodanie filtra, zapis i odczyty po restarcie przebudowanego EXE na osobnych danych. |
| [Naprawa filtra „Dyżur 1L”](zakonczone/naprawa-filtra-dyzur-1l.md) | Potwierdzony alias daty, 75 testów i rzeczywisty odbiór źródeł oraz przebudowanego EXE na osobnych danych. |
| [Diagnostyka przed wydaniem 1.8.1](zakonczone/diagnostyka-przed-wydaniem-1.8.1.md) | Cztery poprawki testów, pełna regresja i publikacja ZIP-a |
| [Lista zagrożeń SLA i powiadomienia](zakonczone/lista-zagrozonych-i-powiadomienia.md) | Odbiór jednej strony w ukrytym Chromium. Dwa rzeczywiste rekordy, zapis historii, testowa kolejka bez duplikatu i potwierdzony zapis diagnostyki. |
| [Obsługa kodu PingID](zakonczone/obsluga-pingid-mfa.md) | Rzeczywista próba odsłonięcia ukrytego okna i powrotu do sesji. Użytkownik potwierdził pojawienie się okna także w EXE 1.8.1. |
| [Stabilizacja odczytu filtrów](zakonczone/stabilizacja-odczytu-filtrow.md) | Odbiór zakresowy G 81/81. Zmienna aktywna lista REQ odrzucana przy zmianie liczebności. [Odbiór EXE 1.8.1](../wersje/v1.8.1.md) |
| [Okres dashboardu](zakonczone/zmiana-okresu-podczas-aktualizacji-dashboardu.md) | Blokada przez cały cykl żądania, zgodność ID/okresu i diagnostyka; 130 testów zakresowych, poprawka w EXE 1.8.1 |
| [Paginacja list](zakonczone/stabilizacja-paginacji.md) | Cztery etapy; inspekcja rzeczywistej listy dla 20 i 100 rekordów na stronie |
| [Dashboard](zakonczone/stabilizacja-dashboardu.md) | A–F; [raport](../weryfikacja/odbior-stabilizacji-dashboardu.md) |
| [Incydenty zagrożone](zakonczone/stabilizacja-odczytu-zagrozen-sla.md) | A–E; wspólny czytnik, [raport](../weryfikacja/odbior-stabilizacji-dashboardu.md); bez powiadomień |
| [Ukryty dashboard](zakonczone/odczyt-dashboardu-w-ukrytym-chromium.md) | Badania A–C i wdrożenie D1–D5; [raport](../weryfikacja/odbior-ukrytego-dashboardu.md) |
| [Płynność listy wielu filtrów](zakonczone/plynnosc-listy-filtrow.md) | Poprawka źródeł po 1.9.4. |
| [Logowanie i ukryte SSO](zakonczone/stabilizacja-logowania.md) | A–F; [raport](../weryfikacja/odbior-stabilizacji-logowania.md), z jawnymi ograniczeniami realnego SSO |


## Utrzymanie

Nowy plan twórz tutaj; podaj cel, zakres, dowody, etapy, testy i kryteria ukończenia. Dokumentacja nie jest zgodą na wdrożenie. Weryfikuj aktualność z kodem i stroną. Po istotnym etapie zapisz wynik i braki; po zakończeniu przenieś plan do `zakonczone/`, popraw odnośniki i zaktualizuj ten indeks. Nie kopiuj do niego całej historii ani wyników każdego przebiegu. Przy publikacji twórz nowy ZIP i sprawdzaj jego zgodność ze źródłami.
