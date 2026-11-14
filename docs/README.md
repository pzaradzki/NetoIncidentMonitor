# Dokumentacja Neto Incident Monitor

Ostatnie wydanie odnotowane w projekcie to [1.11.2](wersje/v1.11.2.md). Bieżące źródła obejmują też migrację dashboardu i Incydentów zagrożonych SLA na REST. [Architektura](architektura.md)

| Cel | Dokument |
| --- | --- |
| Zmiana kodu: najpierw stan systemu | [Architektura](architektura.md) → właściwa [decyzja](decyzje/README.md) → [plan i pozostałe prace](plany/README.md) |
| Dokładne zasady działania | [Kontrakty](kontrakty/README.md): odczyt sekcji, logowanie i diagnostyka |
| Migracja odczytów ServiceNow | [REST API w zalogowanej sesji Chromium](servicenow-api-sesja-przegladarki.md) |
| Co rzeczywiście sprawdzono | [Raporty weryfikacji](weryfikacja/README.md) |
| Skąd wzięły się rozwiązania | [Analizy i eksperymenty](archiwum/analizy/README.md) w archiwum oraz [rozpoznanie SMTP](analizy/README.md) |
| Zmiany wersji i status paczki | [Wersje](wersje/README.md) |
| Materiały historyczne i zastąpione opisy | [Archiwum](archiwum/README.md) |

Bieżący stan opisują architektura i kontrakty, decyzje wyjaśniają wybory, a indeks planów wskazuje pozostałe zadania. Zakończone plany i raporty zachowują datę, zakres oraz ograniczenia swoich pomiarów; starszy zapis „bez EXE” nie unieważnia późniejszego buildu.

Zasady pracy: [AGENTS.md](../AGENTS.md). Dokumentacja nie stanowi polecenia wykonania planu. Nie umieszczaj tutaj logów, profili, danych zgłoszeń ani sekretów; wyniki techniczne pozostają w lokalnym ignorowanym `data/`.
