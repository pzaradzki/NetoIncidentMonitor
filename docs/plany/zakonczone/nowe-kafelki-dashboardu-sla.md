# Trzy nowe kafelki Dashboardu SLA

**Status** — wdrożono w źródłach i zaktualizowano lokalną konfigurację. Zweryfikowano wiersze 33–35 zakładki **Kafelki ServiceNow** lokalnego arkusza `data/dashboard-api-kafelki.xlsx`. Aggregate API w ADEO potwierdziło odpowiedzi HTTP 200 dla wszystkich trzech zapytań na wskazanych niżej tabelach.

| Wiersz | Sekcja i kafelek | Tabela i zakres | Wartość w arkuszu |
| --- | --- | --- | --- |
| 33 | Dashboard SLA · **Nieprzypisane zgłoszenia** | `task_sla`, wybrany miesiąc i rok, wspólna lista lokalizacji, puste przypisanie | 0 przed korektą filtra |
| 34 | Dashboard SLA · **Zagubione zgłoszenia** | `incident`, stan bieżący, grupy o prefiksie `LMPL-L1` z dwiema zapisanymi grupami wykluczonymi | 0 |
| 35 | Wstrzymane L1 · **L1 bez aktualizacji > 7 dni** | `incident`, stan bieżący, wspólna lista agentów, grupa znana z konfiguracji SLA, stany 2 i 3, ostatnia aktualizacja ponad 7 dni temu, brak incydentu nadrzędnego | 7 |

**Budżet odczytu** — 11 agregacji w pełnym przebiegu bez ponowień. Trzy dodatkowe liczniki pobieramy trzema zapytaniami. Obecna agregacja miesięczna zwraca grupy według priorytetu i przekroczenia, więc nie daje danych potrzebnych do wyliczenia nowych kafelków. Odczyt Wstrzymanych L1 obejmuje zarówno `incident_metric`, jak i `incident`. Wnioski L1 nadal korzystają z pięciu dotychczasowych agregacji.

**Odbiór ADEO** — w jednym oknie i na jednej karcie Aggregate API zwróciło 0 nieprzypisanych za październik 2026, 5 za listopad 2026, 1 zagubione oraz 9 bez aktualizacji. Table API potwierdziło październikowe 0 i bieżący 1. Kontrolne żądania Table API z limitem 1 dla listopada i licznika bez aktualizacji zwróciły HTTP 400. Te dwie wartości potwierdzono w Aggregate API. Próba otwarcia dashboardu w przeglądarce Codex wymagała ponownego logowania, więc nie porównano ich bezpośrednio z widżetami. Wartości stanu bieżącego w arkuszu pochodzą z wcześniejszego odczytu.

**Regresja lokalna** — 80 testów izolowanych zaliczonych. Osobno 29 testów współdzielonej sesji zakończyło się bez nieudanych asercji. Tk wypisywało ostrzeżenia podczas zamykania okien testowych, które odnotowano także w pełnym przebiegu modułu uruchomionym przez izolowany runner. Importer sprawdził 27 definicji i zachował zestaw 46 agentów oraz 104 lokalizacji bez zmian.

## 1. Definicje i budżet zapytań

- [x] **Potwierdzić warunki i źródło każdego nowego licznika.**
  - [x] Sprawdzono etykiety, sekcje, okresy, wartości referencyjne oraz kompletność i brak formuł w wierszach 33–35. Porównano listy agentów i lokalizacji z dotychczasową definicją miesięczną.
  - [x] Porównano zapytania z istniejącymi agregacjami. Każdy nowy kafelek dostanie osobne zapytanie z zachowaniem dotychczasowych agregacji. Zagubione zgłoszenia obejmują stany 1, 2 i 3 oraz puste przypisanie. Kafelek L1 bez aktualizacji liczy rekordy według `sys_updated_on`, podczas gdy istniejące kafelki Wstrzymanych liczą metryki według `mi_start`.
  - [x] Uzgodniono korektę filtra **Nieprzypisane zgłoszenia**. Przy budowaniu zapytania pominąć klauzulę `task.assigned_toIN` z wiersza 33. Zachować `task.assigned_toISEMPTY`, `active=true`, `task.active=true` oraz pozostałe warunki tego wiersza. W walidatorze arkusza uwzględnić zarówno pierwotną definicję, jak i wariant po usunięciu tej klauzuli.

## 2. Odczyt REST i konfiguracja

- [x] **Włączyć nowe wartości do istniejącego odczytu dashboardu.**
  - [x] Rozszerzono adaptery, generatory i walidator arkusza. Importer dodaje do konfiguracji drugą wykluczoną grupę i zachowuje wcześniej zapisane listy zakresu. Wczytano nową konfigurację lokalną.
  - [x] Rozszerzono kontrakty SLA i Wstrzymanych L1. Nowe wartości przechodzą przez istniejący odczyt sekcji, zdarzenia oraz kolejkę. Próba ADEO potwierdziła zapytania dla dwóch okresów na jednej karcie.
  - [x] Nowe liczniki mają osobne numery w swoich sekcjach. Test ponowienia potwierdził ponowienie wyłącznie nieudanego licznika oraz zachowanie numerów i pomiarów pozostałych zapytań.

## 3. Widok, cache i statusy

- [x] **Pokazać nowe kafelki w stylu istniejących sekcji.**
  - [x] Uzgodniono układ **Dashboardu SLA** na siatce pięciu równych kolumn. W pierwszym rzędzie od lewej **Liczba zgłoszeń** zajmuje dwie kolumny, a **Nieprzypisane zgłoszenia**, **Zagubione zgłoszenia** i **WJRUW** zajmują po jednej. W drugim rzędzie są **Zgłoszenia P1–P5**, a w trzecim **Przekroczone P1–P5**. W obu rzędach priorytety rosną od lewej do prawej.
  - [x] Uzgodniono jeden rząd trzech równych kafelków w sekcji **Wstrzymane L1**. Od lewej **Wstrzymane L1 >14 dni**, **Wstrzymane L1 >7 dni**, **L1 bez aktualizacji > 7 dni**.
  - [x] Wdrożono uzgodnioną siatkę z `AnimatedMetricTile`. **Nieprzypisane zgłoszenia** i **Zagubione zgłoszenia** mają kolor kafelka **Liczba zgłoszeń**. Usunięto podpis zakresu z kafelka **Zagubione zgłoszenia**.
  - [x] Odczyt starszego cache zachowuje poprzednie liczby i pokazuje `—` na nowych kafelkach. Starsze dane pozostają widoczne również po zapisie cache przez inną sekcję. Nie ustanawiają pełnego odczytu rozszerzonego dashboardu.
  - [x] Testy potwierdziły obsługę zera, błąd sekcji z zachowaniem poprzedniej migawki, metadane belki i wynik WJRUW dla niezmienionej podstawy grupowania.

## 4. Regresja i odbiór

- [x] **Sprawdzić wyniki oraz wpływ na działanie aplikacji.**
  - [x] Regresja objęła warunki, dwa zakresy kalendarzowe, wspólne listy ID, 11 wywołań, poprawne zero, ponowienie i migrację cache.
  - [x] W Windows sprawdzono kolejność, kolumny i ich rzeczywiste szerokości w Tk dla wąskiego widoku przy skalach 100% i 125%. Testy okresu potwierdziły zachowanie widoku podczas odświeżania.
  - [x] W ADEO sprawdzono trzy zapytania aplikacji oraz niezależne porównania, które obsłużył Table API. Wyniki i granice weryfikacji zapisano powyżej i w [kontrakcie dashboardu](../../kontrakty/kontrakt-odczytu-dashboardu.md). Regresja potwierdziła niezmienione obliczenia wcześniejszych liczników dla identycznych danych.

Późniejsze dopasowanie wysokości potwierdziło widoczność wszystkich 22 kafelków o jednakowej wysokości w zmaksymalizowanym oknie i na pełnym ekranie 1920 × 1080 przy skali Tk 100% i 125%. Przy zmniejszeniu okna test potwierdził przewijanie do ostatniego rzędu i jego wyłączenie po powiększeniu okna. Zestaw 69 testów zakresowych przeszedł na danych syntetycznych. [Test zmiany rozmiaru](../../../tests/test_dashboard_snapshots.py)

Przy wdrażaniu cyklu dashboardu regresja wykryła naprzemienne zmiany wysokości i widoczności paska przewijania przy pośredniej szerokości okna. Zawijanie tytułów oblicza się teraz na podstawie szerokości obszaru z rezerwą na pasek. Po poprawce przeszły testy zwijania listy filtrów i ponowione próby Full HD. [Układ dashboardu](../../../neto_incident_monitor/dashboard_ui.py) · [Test listy filtrów](../../../tests/test_filter_reorder.py)
