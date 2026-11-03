# 010 — Okres należy do żądania dashboardu

2 listopada 2026. **Status: przyjęta; wdrożona w źródłach; 130 testów zakresowych zaliczonych.** Rozszerza [001](001-watki-i-kolejki.md), [003](003-poprawnosc-i-aktualnosc.md) i [006](006-odczyt-sekcji-dashboardu.md), nie zastępuje ich.

**Decyzja:** główny wątek przechowuje aktywne `(request_id, year, month)` od przyjęcia żądania do jego końcowego zdarzenia. Wybór miesiąca i roku jest wtedy wyłączony; guard zmiennych przywraca okres także po programowej zmianie. Worker nadal używa istniejącej kolejki i zamrożonego okresu, bez odczytów Tk.

**Powód:** wcześniej zmiana wyboru zwiększała ID widoku, choć odczyt trwał dalej. Poprawne wyniki i postęp były odrzucane, a nowy odczyt nie powstawał. Samo wyłączenie przycisku Aktualizuj nie chroniło kontrolek okresu.

**Realizacja:** rozpoczęcie, ponowienie po zamknięciu Chromium i koniec zawierają ID oraz okres. Tylko pasujący koniec, końcowy Stop lub błąd kolejkowania/uruchomienia zwalnia blokadę. Restart zachowuje to samo żądanie i blokadę. Wynik z obcym ID, innym okresem albo już zakończonej transakcji nie zmienia cache. `RefreshControl` nadal rezerwuje cały zakres aktualizacji; blokada okresu dotyczy tylko żądania dashboardu, nie samych filtrów lub zagrożeń.

W bezczynności wybór nowego okresu oznacza jako nieaktualne wyłącznie SLA i nie podpisuje starych danych nowym miesiącem. Wstrzymane/Wnioski zachowują swój stan. Nie wprowadzono anulowania odczytu zmianą dat, automatycznego kolejnego żądania, nowego workera ani nowego schematu cache.

**Diagnostyka i granice:** wspólne zdarzenia przyjęcia/zakończenia, blokady, odrzuconego wyboru i wyniku; stałe przyczyny oraz ID/rok/miesiąc, bez danych strony. To lokalna synchronizacja UI, bez zmiany interakcji ServiceNow. Wyniki i ograniczenia: [plan](../plany/zakonczone/zmiana-okresu-podczas-aktualizacji-dashboardu.md). EXE 1.8.0 pozostaje wcześniejszym buildem, bez tej poprawki.
