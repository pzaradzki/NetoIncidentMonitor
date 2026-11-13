# 025 — Wspólna sesja ServiceNow i kolejka odczytów

12 listopada 2026. **Status: przyjęta, wdrożona w źródłach.** Wyniki i zakres odbioru są w [planie](../plany/wspolna-sesja-servicenow.md).

Regułę ukrycia Chromium po potwierdzeniu sesji w przypadku ręcznego wpisania hasła przy włączonym autologowaniu zastępuje [decyzja 026](026-potwierdzenie-zapisu-poswiadczen.md).

Zapis odstępów dla działającego harmonogramu i sposób liczenia nowego terminu opisuje [decyzja 030](030-odstepy-podczas-monitoringu.md).

**Decyzja.** Wejście aplikacji tworzy jeden wątek Playwright i jedną kartę roboczą. Chromium jest widoczne podczas pierwszego logowania. Po potwierdzeniu sesji i natywnego ukrycia okna Tk udostępnia główny widok. Akcje **Otwórz w SNOW** pozostają w domyślnej przeglądarce. Po awarii procesu dostępne jest świadome ponowne połączenie, ponieważ bazowy restart Chromium nie gwarantuje ukrycia.

**Powód.** Logowanie i sesja mają działać niezależnie od harmonogramu. Jeden właściciel karty zapobiega kolizjom nawigacji i profilu, a kolejka pozwala wykonać odczyt ręczny lub import także przy zatrzymanym monitoringu.

**Realizacja.** `SharedSession` jest właścicielem Chromium. Ręczne zlecenia mają utrwalony zakres i współdzielą czytniki z cyklem monitoringu. Pełna aktualizacja scala zgodne oczekujące odczyty. Import oddaje kartę po odczycie i pokazuje podgląd w Tk. `Schedule` budzi wątek po zmianie pracy lub terminie, a zagrożenia mają następny termin 60 s od końca próby.

**Granice.** Zastępuje [022](022-import-ulubionych-na-zadanie.md) w zakresie osobnego procesu i wyłączności importu oraz [023](023-naturalne-logowanie-importu.md) w zakresie osobnej karty. Zachowuje tymczasowy rozmiar menu z 023, kontrakt odczytu i jawny zapis z 022. Pozostają zakresy `HiddenRendering` dashboardu i ponownego logowania. Karta robocza należy do aplikacji, a przejściowe okno wymagane przez SSO należy do przebiegu logowania i jest zamykane przed wznowieniem odczytów.
