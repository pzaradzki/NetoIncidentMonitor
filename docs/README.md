# Dokumentacja Neto Incident Monitor

Stan: **2 listopada 2026, lokalna wersja 1.8.0**. EXE zbudowany i sprawdzony offline; bez nowego ZIP-a i publikacji na GitHubie. Późniejsza poprawka okresu dashboardu jest w źródłach i wymaga jeszcze przebudowy EXE.

| Cel | Dokument |
| --- | --- |
| Obsługa aplikacji | [Instrukcja użytkownika](user-guide.md) |
| Zmiana kodu: najpierw stan systemu | [Architektura](architecture.md) → właściwa [decyzja](decisions/README.md) → [plan i pozostałe prace](plans/README.md) |
| Dokładne zasady działania | [Kontrakty](contracts/README.md): odczyt sekcji, logowanie i diagnostyka |
| Co rzeczywiście sprawdzono | [Raporty weryfikacji](verification/README.md) |
| Skąd wzięły się rozwiązania | [Analizy i eksperymenty](analyses/README.md) — historyczne dowody, nie aktualne instrukcje wdrożenia |
| Zmiany wersji i status paczki | [Wersje](releases/README.md) |
| Dawne, zastąpione opisy | [Archiwum](archive/README.md) |

Bieżący stan opisują architektura i kontrakty, decyzje wyjaśniają wybory, a indeks planów wskazuje pozostałe zadania. Zakończone plany i raporty zachowują datę, zakres oraz ograniczenia swoich pomiarów; starszy zapis „bez EXE” nie unieważnia późniejszego buildu.

Zasady pracy: [AGENTS.md](../AGENTS.md). Dokumentacja nie stanowi polecenia wykonania planu. Nie umieszczaj tutaj logów, profili, danych zgłoszeń ani sekretów; wyniki techniczne pozostają w lokalnym ignorowanym `data/`.
