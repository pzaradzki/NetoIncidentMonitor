# 013. Reset lokalnych danych monitora

**Status** — wdrożone w źródłach.

**Decyzja.** Reset jest osobnym, potwierdzanym trybem zamykania. Usuwa lokalne dane i sesję Chromium, po czym użytkownik uruchamia aplikację ponownie.

**Powód.** Monitor, przeglądarka, nadawcy i logi mogą nadal trzymać uchwyty do danych w trakcie zamykania. Blokada instancji zapobiega równoczesnemu startowi podczas usuwania.

**Realizacja i ograniczenia.** Znacznik obok katalogu danych utrwala żądanie. Po zatrzymaniu zapisów dane są przenoszone na tym samym woluminie do katalogu przejściowego i usuwane. Wydanie EXE ma dedykowany katalog, a uruchomienie ze źródeł korzysta z listy nazw plików wykonawczych. Po przerwaniu reset zostaje wznowiony przed otwarciem logów i danych. Błąd usuwania wymaga ponowienia albo zamknięcia. Zdarzenia przed zwolnieniem uchwytów korzystają z istniejącego logu, który jest częścią resetu.

Reset usuwa również wpis autostartu właściwy dla EXE albo źródeł. Błąd zapisu w rejestrze pozostawia znacznik do ponowienia.
