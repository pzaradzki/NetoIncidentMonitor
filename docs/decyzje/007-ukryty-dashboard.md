# 007 — Renderowanie ukrytego dashboardu

Data: 1 listopada 2026. **Status: przyjęta; wdrożona w źródłach, odbiór D5 zakończony, bez nowego EXE.**

**Aktualizacja** — mechanizm renderowania analityki zastąpiony w źródłach przez [033](033-odczyty-analityki-przez-api.md).

**Decyzja:** podczas ukrytego odczytu analityki `BrowserRuntime` zarządza jednym `HiddenRendering` w istniejącym workerze. Lokalny DevTools podtrzymuje renderowanie (`Page.startScreencast`, JPEG jakość 0, maks. 1×1, co 60. klatkę); ramki są jedynie potwierdzane i odrzucane. Nie tworzymy drugiego czytnika, wątku Playwright ani właściciela ponowień.

**Powód:** [badania A–C](../archiwum/analizy/ukryte-chromium-rozwiazanie.md) wykazały ograniczenie klatek przy ukryciu. Prototyp przeszedł 40/40 odczytów oraz 4/4 po minimalizacji; mediana mieściła się w przyjętym progu. Nie jest to gwarancja dla każdej przyszłej wersji Chromium.

**Realizacja:** start wymaga dodatniego potwierdzenia sesji i docelowego originu/ścieżki/ID dashboardu, ale nie gotowej kontrolki daty. `dashboard_read` obejmuje każdą próbę sekcji i sprząta w `finally`. Wyjście z kontekstu, logowanie, Stop i zamknięcie celu kończą mechanizm. Nowa strona otrzymuje osobny stan. Błąd startu/ACK jest jawny i nie uruchamia dodatkowych ponowień; nie pokazujemy okna automatycznie wbrew opcji ukrywania. Dotychczasowe odzyskiwanie zamkniętej przeglądarki pozostaje zachowane.

Ręczne „Pokaż/Ukryj” jest respektowane także dla dashboardu; nadpisanie pozostaje do kolejnego jawnego polecenia, zmiany opcji widoczności lub nowego logowania. Ręczne logowanie ma pierwszeństwo i fokus. Sama minimalizacja bez ukrywania zachowuje widoczny odczyt analityki. Po odczycie mechanizm jest wyłączany także podczas bezczynnego ukrycia.

Niezależna poprawka kategorii potwierdza spóźniony stan po dokładnie rozpoznanym błędzie `check`, bez ponownego kliknięcia i w pozostałym budżecie do 500 ms. Brak zaznaczenia, stan pośredni i inne wyjątki pozostają błędami. To rozszerzenie [006](006-odczyt-sekcji-dashboardu.md), nie zastąpienie jej kontraktu.

**Diagnostyka i granice:** tylko stałe przyczyny, korelacja odczytu, czasy i liczniki techniczne; bez obrazów, treści strony i sekretów. API jest eksperymentalne. Niesprawne DevTools nie oznacza sukcesu ani sztucznych zer; poprzedni poprawny wynik pozostaje. Ręczne pokazanie umożliwia nowy widoczny odczyt. Weryfikacja wdrożenia: [osobny raport](../weryfikacja/odbior-ukrytego-dashboardu.md); build i publikacja są oddzielnymi zadaniami.

**Rozszerzenie 2 listopada:** historyczne wyłączenie uwierzytelniania rozszerza odrębna [009](009-renderowanie-ukrytego-logowania.md), za zgodą użytkownika i po pomiarach na prawdziwym formularzu. Wspólny lifecycle pozostaje; zakresy zaufania i warunki startu analityki oraz logowania są odrębne. Pozostała część 007 nie jest zastępowana.
