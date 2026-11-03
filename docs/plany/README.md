# Plany i pozostałe prace

Bieżąca wersja lokalna to [1.8.1](../wersje/v1.8.1.md).

## Pozostałe tematy

- Wrócić do luki diagnostycznej, jeśli powtórzy się po pełnym cyklu i normalnym zamknięciu.
- [Paginacja listy zagrożeń SLA](paginacja-listy-zagrozen-sla.md) jest odłożona do czasu pojawienia się rzeczywistej listy z co najmniej dwiema stronami.
- Potencjalny kanał e-mail: [rozpoznanie SMTP](../analizy/powiadomienia-email-smtp.md) — jednorazowa wysyłka i dostarczenie potwierdzone; brak zatwierdzonego planu implementacji, konieczna weryfikacja zasad relay i innych komputerów.
- ZIP i publikacja GitHub dopiero na odrębne polecenie; poprzedni ZIP znajduje się w archiwum lokalnym.

W ramach wcześniejszego buildu 1.8.0 zakończono [ochronę okresu podczas aktualizacji](zakonczone/zmiana-okresu-podczas-aktualizacji-dashboardu.md): 130 testów zakresowych zaliczonych; poprawka weszła do lokalnego EXE 1.8.1.

## Zakończone plany

| Plan | Wynik / dowody |
| --- | --- |
| [Lista zagrożeń SLA i powiadomienia](zakonczone/lista-zagrozonych-i-powiadomienia.md) | Odbiór jednej strony w ukrytym Chromium. Dwa rzeczywiste rekordy, zapis historii, testowa kolejka bez duplikatu i potwierdzony zapis diagnostyki. |
| [Obsługa kodu PingID](zakonczone/obsluga-pingid-mfa.md) | Rzeczywista próba odsłonięcia ukrytego okna i powrotu do sesji. Użytkownik potwierdził pojawienie się okna także w EXE 1.8.1. |
| [Stabilizacja odczytu filtrów](zakonczone/stabilizacja-odczytu-filtrow.md) | Odbiór zakresowy G 81/81. Zmienna aktywna lista REQ odrzucana przy zmianie liczebności. [Odbiór EXE 1.8.1](../wersje/v1.8.1.md) |
| [Okres dashboardu](zakonczone/zmiana-okresu-podczas-aktualizacji-dashboardu.md) | Blokada przez cały cykl żądania, zgodność ID/okresu i diagnostyka; 130 testów zakresowych, poprawka w EXE 1.8.1 |
| [Paginacja list](zakonczone/stabilizacja-paginacji.md) | Cztery etapy; inspekcja rzeczywistej listy dla 20 i 100 rekordów na stronie |
| [Dashboard](zakonczone/stabilizacja-dashboardu.md) | A–F; [raport](../weryfikacja/odbior-stabilizacji-dashboardu.md) |
| [Incydenty zagrożone](zakonczone/stabilizacja-odczytu-zagrozen-sla.md) | A–E; wspólny czytnik, [raport](../weryfikacja/odbior-stabilizacji-dashboardu.md); bez powiadomień |
| [Ukryty dashboard](zakonczone/odczyt-dashboardu-w-ukrytym-chromium.md) | Badania A–C i wdrożenie D1–D5; [raport](../weryfikacja/odbior-ukrytego-dashboardu.md) |
| [Logowanie i ukryte SSO](zakonczone/stabilizacja-logowania.md) | A–F; [raport](../weryfikacja/odbior-stabilizacji-logowania.md), z jawnymi ograniczeniami realnego SSO |

Bieżące zachowanie: [architektura](../architektura.md) i [kontrakty](../kontrakty/README.md). Lokalny build: [1.8.1](../wersje/v1.8.1.md).

## Utrzymanie

Nowy plan twórz tutaj; podaj cel, zakres, dowody, etapy, testy i kryteria ukończenia. Dokumentacja nie jest zgodą na wdrożenie. Weryfikuj aktualność z kodem i stroną. Po istotnym etapie zapisz wynik i braki; po zakończeniu przenieś plan do `zakonczone/`, popraw odnośniki i zaktualizuj ten indeks. Nie kopiuj do niego całej historii ani wyników każdego przebiegu.
