# 021 — Gotowość i potwierdzenie kontekstu dashboardu

Data: 5 listopada 2026. **Status: przyjęta; wdrożona w źródłach i głównej lokalnej paczce EXE 1.9.3.**

**Aktualizacja** — zatwierdzanie kontrolek strony zastąpione w źródłach przez [033](033-odczyty-analityki-przez-api.md).

**Decyzja:** zmiana okresu czeka na gotowość przycisku Zastosuj, wysyła jedno kliknięcie i obserwuje oczekiwany okres oraz zamknięcie panelu. Anulowanie jest dopuszczalne, gdy żądany okres jest już zatwierdzony. Chwilowo wyłączony przycisk nie oznacza braku zmiany. Po zatwierdzeniu kategorii wspólna obserwacja wymaga jednocześnie zaznaczenia checkboxa i braku stanu pośredniego.

**Powód:** rzeczywisty ServiceNow wykazał opóźnioną aktywację Zastosuj mimo poprawnych dat. Dawna gałąź Anuluj mogła wycofać zmianę i czekać na nieosiągalny okres. Osobna końcowa kontrola stanu pośredniego miała nieponawiany timeout 300 ms. Ten drugi przypadek odtworzono syntetycznie, nie na rzeczywistej stronie. Log historycznej awarii nie dowodzi dokładnego miejsca obu usterek.

**Realizacja:** istniejące read_control/ready_control/wait_control, świeżo rozwiązywane lokatory i rozdzielone etapy period_ready, commit_period, period_confirm oraz category_apply/category_confirm. Walidacja wartości i aria-invalid nie dopuszcza niepoprawnych pól. Ponawia się obserwację, nigdy niepewnie dostarczone kliknięcie. Zachowane zasady [006](006-odczyt-sekcji-dashboardu.md) i [019](019-odzyskiwanie-sesji-sekcji.md): wspólne 60 s, pierwsza próba 39 s, jedno ponowienie techniczne i jedno odzyskanie sesji. Bez zmian selektorów, schematów i publicznych sygnatur.

**Ograniczenia:** nie zapewnia dostępności ServiceNow; nie zwiększa budżetów. Rzeczywiste próby w przeglądarce Codex są odbiorem zachowania strony, nie wykonaniem czytnika EXE ani wymuszonym testem utraty SSO. [Plan i wyniki](../plany/zakonczone/zatwierdzanie-kontekstu-dashboardu.md).
