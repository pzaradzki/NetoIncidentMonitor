# 008 — Wspólne rozpoznawanie stanu logowania

1 listopada 2026; aktualizacja 2 listopada. **Status: przyjęta; wspólny kontrakt wdrożony w źródłach.**

**Decyzja:** `login_observation.py` zwraca jeden kontrakt: `authentication`, `logout`, `unknown`, `target` albo `session`. Korzystają z niego oba publiczne sprawdzenia w `authentication.py` oraz diagnostyka. Moduł wyłącznie obserwuje — nie zarządza akcjami, retry ani widocznością.

**Powód:** dodatni `g_user` w jednej ramce nie może przykryć formularza w innej, wylogowania, niedokończonego własnego popupu ani nieudanej obserwacji. `target` oznacza właściwe pochodzenie bez dowodu sesji; `unknown` nie pozwala uznać sesji za gotową.

**Realizacja:** strukturalne liczby/booleany z ramek, ścisłe HTTPS/443 bez danych użytkownika w adresie, pierwsza bezpieczna klasyfikacja błędu, generacja dokumentu i alias powierzchni. Log zapisuje zmianę stanu, dowód i korelację. Wartości pól, identyfikator użytkownika, treść komunikatu oraz URL nie opuszczają strony.

**Granice:** ta decyzja dotyczy obserwacji. Akcje, epoki komponentów i odzyskiwanie realizują istniejące `AutomaticLogin/wait_for_login`, opisane w [architekturze](../architektura.md). Rozpoznanie standardowego pola kodu/alertu jest testem strukturalnym, nie dowodem obsługi wszystkich rzeczywistych wariantów MFA. Ukryte renderowanie logowania ma odrębną, świadomie rozszerzoną granicę [009](009-renderowanie-ukrytego-logowania.md); [007](007-ukryty-dashboard.md) pozostaje kontraktem analityki. Zakres weryfikacji: [raport](../weryfikacja/odbior-stabilizacji-logowania.md).
