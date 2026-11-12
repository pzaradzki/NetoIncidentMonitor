# 014 — Linki dashboardu pobierane po kliknięciu

Data: 4 listopada 2026. Status: zastąpiona przez [024](024-kafelki-informacyjne.md). Poniżej zachowano pierwotne uzasadnienie i opis realizacji.

## Decyzja i powód

Odświeżanie dashboardu pobiera wartości, bez odwiedzania list odpowiadających kafelkom. Poprzednie pobieranie do 18 linków wydłużało odczyt i uzależniało klikalność kafelka od powodzenia dodatkowej nawigacji. Każdy kafelek z poprawnym wynikiem, także przywróconym z cache, otrzymuje akcję otwierania. WJRUW pozostaje lokalny i nieklikalny.

## Realizacja i ograniczenia

Kliknięcie kolejkuje pojedyncze żądanie do istniejącego workera Playwright i pokazuje „Otwieranie listy…” na kafelku oraz w komunikacie dashboardu. Dla SLA żądanie zawiera miesiąc wyświetlanej migawki, niezależnie od aktualnego wyboru kontrolek. Tymczasowa karta tej samej sesji potwierdza kontekst i cel listy. Nadal obowiązują walidacja hosta, tabeli i jawnych dat SLA oraz brak utrwalania zapytań na dysku.

Rozwiązanie wymaga działającego monitoringu. Żądanie czeka na wolny worker; jego wykonanie ma budżet 18 sekund. Jednocześnie obsługiwane jest jedno kliknięcie. Błąd pozwala kliknąć ponownie bez odświeżenia wartości. Stop anuluje oczekujące otwarcie, a spóźniona odpowiedź nie uruchamia przeglądarki. Liczebność bieżącej listy może różnić się od wcześniejszej migawki wskutek zmian w ServiceNow.

Kontrakt i dowody: [odczyt dashboardu](../kontrakty/kontrakt-odczytu-dashboardu.md).
