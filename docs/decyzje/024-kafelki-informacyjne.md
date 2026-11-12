# 024 — Kafelki informacyjne dashboardu i zagrożeń SLA

11 listopada 2026. **Status: przyjęta i wdrożona w źródłach.** Zastępuje [014](014-linki-dashboardu-na-zadanie.md).

**Decyzja.** Kafelki dashboardu i zagrożeń SLA wyświetlają wyniki i zachowują animację najechania. Kursor ma postać strzałki. Kliknięcie i aktywacja klawiaturą są wyłączone.

**Powód.** Usunięcie otwierania list z kafelków eliminuje dodatkowe żądanie przeglądarki i tymczasową kartę dashboardu. Upraszcza to planowaną pracę na jednej karcie, ponieważ kliknięcie nie musi przerywać odczytu ani zmieniać kolejności zadań.

**Realizacja i ograniczenia.** Wspólny `AnimatedMetricTile` obsługuje animację najechania. Usunięto ustalanie linków i powiązane zdarzenia diagnostyczne. Przyciski „Otwórz w SNOW” są osobnymi akcjami paneli. Zmiana obejmuje interfejs Neto i usunięcie ścieżki nawigacji. [Kontrakt dashboardu i zagrożeń](../kontrakty/kontrakt-odczytu-dashboardu.md).
