# Plany i pozostałe prace

Bieżąca wersja to [1.9.0](../wersje/v1.9.0.md).

## Pozostałe tematy


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

Bieżące zachowanie: [architektura](../architektura.md) i [kontrakty](../kontrakty/README.md). Wydanie: [1.9.0](../wersje/v1.9.0.md).

Zakończono zmianę otwierania list dashboardu: wartości odświeżają się bez pozyskiwania linków, a pojedynczy cel jest potwierdzany po kliknięciu. Kafelki z cache również mają akcję, SLA zachowuje okres wyświetlonej migawki, a błąd pozwala ponowić kliknięcie. [Decyzja i ograniczenia](../decyzje/014-linki-dashboardu-na-zadanie.md), [lokalne i rzeczywiste próby](../kontrakty/kontrakt-odczytu-dashboardu.md). Funkcja jest częścią EXE 1.9.0.

## Utrzymanie

Nowy plan twórz tutaj; podaj cel, zakres, dowody, etapy, testy i kryteria ukończenia. Dokumentacja nie jest zgodą na wdrożenie. Weryfikuj aktualność z kodem i stroną. Po istotnym etapie zapisz wynik i braki; po zakończeniu przenieś plan do `zakonczone/`, popraw odnośniki i zaktualizuj ten indeks. Nie kopiuj do niego całej historii ani wyników każdego przebiegu.

Wnioski L1 mają pięć kafelków. Zapis czterech dawnych wartości jest pomijany przy starcie z zachowaniem pozostałych sekcji. Rzeczywiste odczyty i granice odbioru opisuje [kontrakt dashboardu](../kontrakty/kontrakt-odczytu-dashboardu.md).
