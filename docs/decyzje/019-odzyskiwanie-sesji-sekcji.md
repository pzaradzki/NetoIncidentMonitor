# 019 — Niezależne odzyskanie sesji i ponowienie odczytu sekcji

Data: 5 listopada 2026. **Status: przyjęta; wdrożona w źródłach i lokalnym EXE; testy automatyczne i offline zakończone.**

**Decyzja:** wspólny runner sekcji dopuszcza jedno ponowienie po retryowalnym błędzie odczytu oraz jedno odzyskanie uwierzytelnienia, niezależnie od ich kolejności. Najwyżej trzy wywołania czytnika na sekcję. Zastępuje wyłącznie ograniczenie dwóch łącznych prób z [006](006-odczyt-sekcji-dashboardu.md); pozostałe zasady 006 obowiązują.

**Powód:** w EXE 1.9.1 sekwencja timeout gotowości dokumentu → AuthenticationRequired kończyła dashboard bez wywołania odzyskiwania. Późniejszy sukces zagrożeń nie ponawiał dashboardu. Potwierdzono zdarzenia i reprodukcję lokalną; nie ustalono przyczyny ponownego żądania uwierzytelnienia przez ServiceNow.

**Realizacja:** jedynym właścicielem limitów pozostaje section_runner. Aktywny budżet nadal wynosi 60 s, pierwsza próba najwyżej 39 s. Czas callbacku odzyskiwania jest wyłączony z budżetu; nie otrzymuje się nowych 60 s. Wyczerpany budżet uniemożliwia następny odczyt lub rozpoczęcie logowania. Kolejne wywołania odtwarzają kontekst przez istniejący RECOVERY. Powtórne wymaganie uwierzytelnienia po odzyskaniu jest końcowym błędem; Stop przerywa oczekiwanie i dalsze czytanie.

Wznowienie zachowuje żądanie, okres i blokady dashboardu. Nie dodaje się ponownego pełnego żądania do kolejki. Cache nadal przyjmuje wyłącznie kompletny wynik sekcji. Zamknięcie Chromium zachowuje dotychczasowe ponowne zakolejkowanie tego samego żądania i restart.

**Diagnostyka:** section_login_recovery_start/end, stała przyczyna authentication_required, numer próby, wynik i czas odzyskiwania; wspólna korelacja i istniejąca filtracja pól. Logowany sygnał session_expired oznacza zaobserwowaną potrzebę uwierzytelnienia, nie dowód przyczyny po stronie SSO.

**Ograniczenia:** bez zmian interakcji DOM, selektorów, sygnatur, schematów, zależności i numeru 1.9.1. Wyłącznie lokalne EXE, bez publikacji GitHub. Testy syntetyczne i offline nie stanowią nowego odbioru ServiceNow/SSO. [Plan i wyniki](../plany/zakonczone/odzyskiwanie-dashboardu-po-utracie-sesji.md).

Późniejsze zlecenie publikacji stabilnej poprawki opisuje [wydanie 1.9.2](../plany/zakonczone/wydanie-1.9.2.md). Powyższy brak publikacji dotyczy pierwotnego etapu lokalnego.
