# 022 — Import ulubionych w sesji na żądanie

6 listopada 2026. **Status: zastąpiona przez [025](025-wspolna-sesja-servicenow.md) w zakresie osobnego wątku, karty i wyłączności importu.** Kontrakt odczytu i zatwierdzania opisany niżej zachowuje zastosowanie.

**Uaktualnienie:** [023](023-naturalne-logowanie-importu.md) zastąpiła wymuszanie rozmiaru przez całą sesję i bezwarunkowe tworzenie nowej karty. Poniższy opis zachowuje historyczne uzasadnienie.

**Decyzja:** jednorazowy import menu Ulubione jest dostępny po zatrzymaniu monitoringu. Import i monitoring współdzielą mechanizm otwierania profilu, input guard, BrowserRuntime i cleanup, ale nie działają równocześnie. Wątek importu nie wywołuje startu monitoringu, historii ani nadawców. Własna karta SOW ma kontrolowany rozmiar 751×884; istniejące karty nie są nawigowane. Okno importu otrzymuje zdarzenia przez prywatną kolejkę z import_id.

**Powód:** istniejący start zapisuje ustawienia i uruchamia odczyty; użycie go do importu miałoby niezamierzone skutki. Drugie równoległe użycie profilu grozi kolizją. To rozszerzenie zasady jednego właściciela Playwright z [001](001-watki-i-kolejki.md), bez zmiany harmonogramu monitoringu.

**Realizacja:** browser_session współdzieli minimalny setup i cleanup; favorites_worker posiada zasoby i publikuje wynik po zakończeniu sesji. Tk czeka też na zakończenie wątku. Rezerwacja trwa przez podgląd do zapisu lub zamknięcia. Import nie zmienia zapisanych preferencji widoczności; jego przeglądarka jest widoczna.

Czytnik favorites_reader zbiera jeden rozpoznany korzeń przez otwarte Shadow DOM. Wymaga pustego wyszukiwania, pełnej struktury i trzech identycznych migawek co 200 ms. Wyniki wyszukiwania hide-scroll, nieznane dzieci, niepełne zakresy grup i głębsze zagnieżdżenia nie są akceptowane jako pełny wynik. Pustka bez potwierdzonego komunikatu jest błędem. Brak nawigacji do każdego linku; dotychczasowe limity dashboardu są nietknięte.

Budżet 30 s obejmuje wszystkie próby, z wyłączeniem oczekiwania na logowanie. Jedno ponowienie techniczne i jedno odzyskanie logowania, maksymalnie trzy przebiegi. Niepewne kliknięcia nie są powtarzane na tym samym dokumencie. Zamknięcie Chromium kończy import, zamiast restartować monitoring.

Wybrane wpisy przechodzą istniejącą normalizację adresów i deduplikację, są dopisywane jednym zapisem jako wyłączone, z wyłączonymi trzema kanałami powiadomień. Nie zmienia się schemat; grupa i ID źródła istnieją tylko w pamięci podglądu. Odmowa zapisu wycofuje zmianę pamięci. Zmiana konfiguracji na dysku blokuje nadpisanie. Bez synchronizacji z późniejszymi zmianami ServiceNow.

**Uzupełnienie po odbiorze użytkowym, 6 listopada:** href menu bez początkowego `/` jest interpretowany względem katalogu głównego tenanta, nie ścieżki SOW. Wcześniejsze użycie adresu strony jako bazy błędnie oznaczało listy jako nieobsługiwane. Zapytanie pozostaje niezmienione, a wynik nadal musi przejść dotychczasowy walidator tenanta i typu listy.

**Ograniczenia:** zakres to menu udostępnione bieżącemu kontu, nie wszystkie rekordy backendu. Bez niezależnego licznika nie można udowodnić kompletności niewidocznej odpowiedzi serwera. Nieznana wirtualizacja bez sygnałów w DOM nie jest certyfikowana; nie dodano spekulatywnego scrollowania. Skróty są zachowane bez otwierania każdego celu. [Analiza](../analizy/import-ulubionych-servicenow.md), [odbiór i pozostałe granice](../plany/zakonczone/import-ulubionych-servicenow.md).
