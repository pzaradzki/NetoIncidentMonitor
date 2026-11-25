# 047 — Cykliczne odświeżanie dashboardu

**Status.** Wdrożono w źródłach. Zastępuje zasady automatycznego dashboardu z [decyzji 018](018-kolejnosc-aktualizacji.md), zachowując jej uzasadnienie kolejności startu i pełnej aktualizacji.

**Decyzja.** Dashboard ma własny interwał monitoringu. Domyślna wartość to 60 s i można ją zapisać w ustawieniach obok interwałów INC oraz zgłoszeń katalogowych. Stare profile bez ustawionego interwału przyjmują 60 s. Pierwszy termin jest gotowy przy starcie monitoringu po przygotowaniu potrzebnego zakresu. Dalej licznik czasu biegnie od zakończenia próby dashboardu, w tym odczytu ręcznego i części dashboardowej pełnej aktualizacji.

**Powód.** Dashboard odświeża się podczas monitoringu, a odczyt ręczny przesuwa kolejny termin. Jedna karta i wspólny harmonogram zachowują kolejność pracy także przy długiej aktualizacji filtra lub ponownym logowaniu.

**Realizacja.** `MonitorCycle` wyznacza terminy, `SharedSession` wybiera pracę na granicy operacji, a `ReadQueue` rozpoznaje zgodne ręczne zlecenie po okresie. Tk przygotowuje i blokuje miesiąc oraz rok na czas żądania. Stop anuluje odczyt cykliczny. Zamówiony ręczny odczyt można nadal wykonać, jeśli cykliczny nie dostarczył zgodnego wyniku. [Sesja](../../neto_incident_monitor/shared_session.py) · [Kolejka](../../neto_incident_monitor/monitoring.py) · [Okres dashboardu](010-cykl-zycia-zadania-dashboardu.md)

**Ograniczenia.** Interwał wyznacza najwcześniejszy termin po ostatniej próbie. Wolna karta, priorytet zagrożeń i odnowienie sesji mogą go opóźnić. Po opóźnieniu sesja obsługuje jeden zaległy odczyt. Zmianę zapisuje wspólny mechanizm interwałów, a Stop kończy odliczanie. [Plan i odbiór](../plany/zakonczone/cykliczne-odswiezanie-dashboardu.md)
