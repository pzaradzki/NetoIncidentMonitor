# Plany i pozostałe prace

Stan: **2 listopada 2026, lokalne 1.8.0**. Plany stabilizacji i poprawkę wyboru okresu zakończono w źródłach. Poprawka wyboru okresu oraz wspólnego timestampu pełnego odczytu nie są jeszcze zawarte w EXE 1.8.0. EXE 1.8.0 przeszedł offline test interfejsu/Chromium i kontrolę zgodności modułów; pełny rzeczywisty przebieg z nowego EXE to osobna weryfikacja. Bez nowego ZIP-a i publikacji.

## Pozostałe tematy

- Wyjaśnić lukę diagnostyki cyklu 1.8.1 opisaną w raporcie wersji.

- [Obsługa kodu PingID](obsluga-pingid-mfa.md) — pomiar bazowy, poprawka rozpoznawania i odbiór na rzeczywistym ServiceNow.

- Sprawdzić nowy EXE w zwykłej pracy, w tym świeże logowanie przy naturalnym wygaśnięciu sesji. Nie wymuszać błędnych haseł, blokad, MFA lub czyszczenia profilu dla statystyki.
- [Paginacja listy zagrożeń SLA](paginacja-listy-zagrozen-sla.md) jest osobnym otwartym zadaniem.
- Potencjalny kanał e-mail: [rozpoznanie SMTP](../analyses/powiadomienia-email-smtp.md) — jednorazowa wysyłka i dostarczenie potwierdzone; brak zatwierdzonego planu implementacji, konieczna weryfikacja zasad relay i innych komputerów.
- ZIP i publikacja GitHub dopiero na odrębne polecenie; istniejący ZIP nie odpowiada lokalnej wersji 1.8.0.

W ramach wcześniejszego buildu 1.8.0 zakończono [ochronę okresu podczas aktualizacji](completed/zmiana-okresu-podczas-aktualizacji-dashboardu.md): 130 testów zakresowych zaliczonych; poprawka weszła do lokalnego EXE 1.8.1.

## Zakończone plany

| Plan | Wynik / dowody |
| --- | --- |
| [Okres dashboardu](completed/zmiana-okresu-podczas-aktualizacji-dashboardu.md) | Blokada przez cały cykl żądania, zgodność ID/okresu i diagnostyka; 130 testów zakresowych, bez nowego EXE |
| [Paginacja list](completed/stabilizacja-paginacji.md) | Cztery etapy; inspekcja rzeczywistej listy dla 20 i 100 rekordów na stronie |
| [Dashboard](completed/stabilizacja-dashboardu.md) | A–F; [raport](../verification/dashboard-stabilization-verification.md) |
| [Incydenty zagrożone](completed/stabilizacja-odczytu-zagrozen-sla.md) | A–E; wspólny czytnik, [raport](../verification/dashboard-stabilization-verification.md); bez powiadomień |
| [Ukryty dashboard](completed/odczyt-dashboardu-w-ukrytym-chromium.md) | Badania A–C i wdrożenie D1–D5; [raport](../verification/hidden-dashboard-verification.md) |
| [Logowanie i ukryte SSO](completed/stabilizacja-logowania.md) | A–F; [raport](../verification/login-stabilization-verification.md), z jawnymi ograniczeniami realnego SSO |

Bieżące zachowanie: [architektura](../architecture.md) i [kontrakty](../contracts/README.md). Lokalny build: [1.8.0](../releases/v1.8.0.md).

## Utrzymanie

Nowy plan twórz tutaj; podaj cel, zakres, dowody, etapy, testy i kryteria ukończenia. Dokumentacja nie jest zgodą na wdrożenie. Weryfikuj aktualność z kodem i stroną. Po istotnym etapie zapisz wynik i braki; po zakończeniu przenieś plan do `completed/`, popraw odnośniki i zaktualizuj ten indeks. Nie kopiuj do niego całej historii ani wyników każdego przebiegu.

## Przygotowany projekt

[Stabilizacja odczytu filtrów INC/REQ/RITM/SCTASK](stabilizacja-odczytu-filtrow.md) — szczegółowy plan A–G na podstawie [audytu](../analyses/filtry-odczyt-audyt.md): kontrakt celu i kompletności, schematy, migracja/spójność stanu, intencje powiadomień, budżety/diagnostyka i odbiór. Odbiór zakresowy G zamknięty (81/81), z ograniczeniem dla zmieniającej się aktywnej listy REQ. Lokalny EXE 1.8.1 przeszedł test offline i cykl pracy potwierdzony przez użytkownika. [Wynik odbioru i otwarte próby](../releases/v1.8.1.md).

[Lista zagrożonych incydentów i powiadomienia](lista-zagrozonych-i-powiadomienia.md) jest wdrożona dla pojedynczej strony. Otwarty pozostaje odbiór tego zakresu.
