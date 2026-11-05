# Plany i pozostałe prace

Bieżąca wersja to [1.9.4](../wersje/v1.9.4.md).

## Pozostałe tematy




- [Etap napraw audytu](zakonczone/naprawy-audytu.md) zamknięto za zgodą użytkownika 4 listopada 2026 po testach automatycznych, offline i wstępnych testach użytkowych bez zgłoszonych problemów. Kolejne funkcjonalności można planować niezależnie. Pozostają decyzje o retencji outbox i lokalizacji logów źródłowych oraz pomiary opóźnień Tk. Naprawy włączono następnie do [wydania 1.9.1](zakonczone/wydanie-1.9.1.md) na osobne zlecenie.


- Wrócić do luki diagnostycznej, jeśli powtórzy się po pełnym cyklu i normalnym zamknięciu.
- [Paginacja listy zagrożeń SLA](paginacja-listy-zagrozen-sla.md) jest odłożona do czasu pojawienia się rzeczywistej listy z co najmniej dwiema stronami.
- Potencjalny kanał e-mail: [rozpoznanie SMTP](../analizy/powiadomienia-email-smtp.md) — jednorazowa wysyłka i dostarczenie potwierdzone; brak zatwierdzonego planu implementacji, konieczna weryfikacja zasad relay i innych komputerów.
- Przy publikacji kolejnych wersji tworzyć nowy ZIP i sprawdzać zgodność ze źródłami; nie używać starszego archiwum.

W ramach wcześniejszego buildu 1.8.0 zakończono [ochronę okresu podczas aktualizacji](zakonczone/zmiana-okresu-podczas-aktualizacji-dashboardu.md): 130 testów zakresowych zaliczonych; poprawka weszła do lokalnego EXE 1.8.1.

Zmiany w źródłach po 1.8.1 obejmują [usunięcie lokalnego stanu przeczytania](../decyzje/012-usuniecie-stanu-przeczytania.md).

Reset lokalnych danych wdrożono w źródłach. [Decyzja 013](../decyzje/013-reset-danych-aplikacji.md).

W źródłach monitor naprawia wpis autostartu po przeniesieniu i usuwa go przy resecie. [Architektura](../architektura.md).

## Zakończone plany

| Plan | Wynik / dowody |
| --- | --- |
| [Zatwierdzanie okresu i filtrów](zakonczone/zatwierdzanie-kontekstu-dashboardu.md) | Lokalne EXE 1.9.3: 523 testy, 2 pominięcia, build i oba smoke OK; poprzednia paczka zachowana, bez publikacji. |
| [Wydanie 1.9.3](zakonczone/wydanie-1.9.3.md) | Opublikowano: 514 testów (2 pominięcia), build i offline smoke; zgodność tagu oraz SHA-256 pobranego ZIP-a. |
| [Synchronizacja statusów](zakonczone/synchronizacja-statusow-dashboardu.md) | Lokalne EXE 1.9.2: 514 testów (2 pominięcia), build i oba smoke OK; bez publikacji. |
| [Wydanie 1.9.2](zakonczone/wydanie-1.9.2.md) | Opublikowano: 505 testów (2 pominięcia), build i offline smoke, zgodność tagu oraz pobranego ZIP-a; bez odrzuconego eksperymentu. |
| [Odzyskiwanie dashboardu](zakonczone/odzyskiwanie-dashboardu-po-utracie-sesji.md) | 505 testów (2 pominięcia), kandydat i główne EXE 1.9.1 sprawdzone offline; bez nowej publikacji. |
| [Wydanie 1.9.1](zakonczone/wydanie-1.9.1.md) | Opublikowano: 495 testów (2 pominięcia), build i offline smoke, zgodność tagu oraz SHA-256 pobranego ZIP-a. |
| [Ukrycie autostartu Windows](zakonczone/ukrycie-autostartu-windows.md) | Przełącznik ukryty; mechanizm zachowany, domyślnie wyłączony; lokalny build i smoke OK. |
| [Kolejność aktualizacji](zakonczone/kolejnosc-aktualizacji.md) | Dashboard → zagrożenia → filtry; 493 testy (2 pominięcia), lokalny build i offline smoke; główna paczka zaktualizowana, bez publikacji. |
| [Naprawy audytu technicznego](zakonczone/naprawy-audytu.md) | A01–A06/A09 naprawione, A10 częściowo; końcowe 486 testów (2 pominięcia), pięć osobnych buildów i prób offline, bez publikacji. |
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
| [Logowanie i ukryte SSO](zakonczone/stabilizacja-logowania.md) | A–F; [raport](../weryfikacja/odbior-stabilizacji-logowania.md), z jawnymi ograniczeniami realnego SSO |

Bieżące zachowanie: [architektura](../architektura.md) i [kontrakty](../kontrakty/README.md). Wydanie: [1.9.4](../wersje/v1.9.4.md).

Zakończono zmianę otwierania list dashboardu: wartości odświeżają się bez pozyskiwania linków, a pojedynczy cel jest potwierdzany po kliknięciu. Kafelki z cache również mają akcję, SLA zachowuje okres wyświetlonej migawki, a błąd pozwala ponowić kliknięcie. [Decyzja i ograniczenia](../decyzje/014-linki-dashboardu-na-zadanie.md), [lokalne i rzeczywiste próby](../kontrakty/kontrakt-odczytu-dashboardu.md). Funkcja jest częścią EXE 1.9.0.

## Utrzymanie

Nowy plan twórz tutaj; podaj cel, zakres, dowody, etapy, testy i kryteria ukończenia. Dokumentacja nie jest zgodą na wdrożenie. Weryfikuj aktualność z kodem i stroną. Po istotnym etapie zapisz wynik i braki; po zakończeniu przenieś plan do `zakonczone/`, popraw odnośniki i zaktualizuj ten indeks. Nie kopiuj do niego całej historii ani wyników każdego przebiegu.

Wnioski L1 mają pięć kafelków. Zapis czterech dawnych wartości jest pomijany przy starcie z zachowaniem pozostałych sekcji. Rzeczywiste odczyty i granice odbioru opisuje [kontrakt dashboardu](../kontrakty/kontrakt-odczytu-dashboardu.md).
