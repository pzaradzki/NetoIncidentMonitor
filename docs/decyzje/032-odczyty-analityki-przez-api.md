# 032 — Dashboard i zagrożenia SLA przez REST API

**Status** — przyjęta i wdrożona w źródłach. Użytkownik potwierdził zgodność dashboardu i zagrożeń z ServiceNow, także dla niepustej listy.

**Decyzja** — kolejka i karta należą do `SharedSession`. Dwa niezależne zadania używają tego samego transportu REST. Dashboard pobiera agregacje. Zagrożenia pobierają komplet wierszy SLA, liczą je według kategorii i grupują według INC dla listy, historii i alertów. Konfiguracja lokalna powstaje z zatwierdzonego arkusza.

**Powód** — REST pozwala pobrać wartości i rekordy bez renderowania widżetów. Osobna migawka każdej sekcji dashboardu pozwala zachować ostatni poprawny wynik. Wymóg kompletnego zestawu zagrożeń chroni obecność, historię i powiadomienia przed częściowym odczytem.

**Realizacja i ograniczenia** — dashboard wykonuje osiem agregacji. Zagrożenia używają jednego wywołania Table API, gdy mieszczą się na jednej stronie. Odczyt zależy od uprawnień konta i zgodności filtrów, pól oraz metadanych instancji. Dashboard pokazuje stany sekcji bez paska postępu. Zastąpiono czytnik widżetów z [006](006-odczyt-sekcji-dashboardu.md), zakres renderowania analityki z [007](007-ukryty-dashboard.md) i zatwierdzanie kontrolek strony z [021](021-zatwierdzanie-kontekstu-dashboardu.md). [Plan i kryteria odbioru](../plany/zakonczone/dashboard-servicenow-api.md)
