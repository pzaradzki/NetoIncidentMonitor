# Dokumentacja Neto Incident Monitor

Stan bieżących źródeł opisuje [architektura](architektura.md). Status paczek lokalnych i wydań publicznych prowadzi [indeks wersji](wersje/README.md).

| Cel | Dokument |
| --- | --- |
| Zmiana kodu: najpierw stan systemu | [Architektura](architektura.md) → właściwa [decyzja](decyzje/README.md) → [plan i pozostałe prace](plany/README.md) |
| Dokładne zasady działania | [Kontrakty](kontrakty/README.md) odczytów, kolejki, trwałości, logowania i diagnostyki |
| Migracja odczytów ServiceNow | [REST API w zalogowanej sesji Chromium](servicenow-api-sesja-przegladarki.md) |
| Co rzeczywiście sprawdzono | [Raporty weryfikacji](weryfikacja/README.md) |
| Skąd wzięły się rozwiązania | [Analizy i eksperymenty](archiwum/analizy/README.md) w archiwum oraz [rozpoznanie SMTP](analizy/README.md) |
| Zmiany wersji i status paczki | [Wersje](wersje/README.md) |
| Budowa i odbiór paczki Windows | [Instrukcja budowy EXE](budowa-exe.md) |
| Materiały historyczne i zastąpione opisy | [Archiwum](archiwum/README.md) |

Bieżący stan opisują architektura i kontrakty, decyzje wyjaśniają wybory, a indeks planów wskazuje pozostałe zadania. Zakończone plany i raporty zachowują datę, zakres oraz ograniczenia swoich pomiarów; starszy zapis „bez EXE” nie unieważnia późniejszego buildu.

Zasady pracy opisuje [AGENTS.md](../AGENTS.md). Dokumentacja nie stanowi polecenia wykonania planu. Raporty techniczne przechowujemy w ignorowanych katalogach projektu, a logi aplikacji w lokalnym katalogu użytkownika. [Ścieżki diagnostyki](kontrakty/diagnostyka-logowania.md)
