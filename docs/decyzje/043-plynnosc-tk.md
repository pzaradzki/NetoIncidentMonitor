# 043 — Płynność Tk

**Status.** Przyjęta i wdrożona w źródłach. [Pomiary i odbiór Windows](../weryfikacja/plynnosc-tk.md)

**Decyzja.** Tk zatwierdza wyniki dashboardu, a dedykowany wykonawca zapisuje cache. Pomiary fontu i zapis profilu kolumn pozostają w Tk. Pomiary dla dużej tabeli wykonują się w porcjach.

**Uzasadnienie.** Ponowienia zapisu zatrzymywały Tk nawet na 1,23 s i mogłyby opóźniać historię oraz retencję na wspólnym wykonawcy. W historii z 10 tys. wierszy dominował pomiar fontu. Zapis profilu zajmował zwykle 2–4 ms, więc pozostawiono go w dotychczasowej ścieżce ustawień.

**Realizacja.** Wykonawca cache zapisuje atomowo jedną migawkę naraz, przechowuje najwyżej jedną oczekującą i raportuje wynik z rewizją do Tk. Zamknięcie czeka na wynik, a reset odrzuca oczekującą migawkę przed usunięciem danych. Dopasowanie używa całego zestawu wierszy, czeka na wczytanie tabeli, a przed zastosowaniem wyniku sprawdza filtr, układ i szerokość. Zmiana widoku lub ręczna zmiana układu może anulować pomiar. [Kontrakt zapisu](../kontrakty/kolejka-i-trwalosc.md#zapis-cache-dashboardu) · [Kod dopasowania](../../neto_incident_monitor/dynamic_columns.py)

**Ograniczenia.** Wynik na ekranie może wyprzedzić zapis na dysku. Nagłe przerwanie procesu może utracić oczekującą migawkę. Budżet 6 ms dotyczy porcji pomiaru po pobraniu listy identyfikatorów wierszy. Pełne dopasowanie dużej tabeli może trwać dłużej, kiedy Tk obsługuje między porcjami inne zdarzenia.
