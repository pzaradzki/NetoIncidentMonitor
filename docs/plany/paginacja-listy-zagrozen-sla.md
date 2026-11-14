# Paginacja listy zagrożeń SLA

**Zastąpione w źródłach.** Paginację listy zagrożeń obsługuje REST. Odbiór na rzeczywistym wyniku wielostronicowym jest odnotowany w [planie migracji](zakonczone/dashboard-servicenow-api.md). Poniższe kroki dokumentują wcześniejszą propozycję dla DOM.

- [ ] Na rzeczywistej liście ServiceNow z co najmniej dwiema stronami potwierdzić zachowanie przycisku „Następna strona”, zmianę zakresu oraz stabilność identyfikatorów SLA.
- [ ] Dodać odczyt kolejnych stron do bieżącego czytnika. Zweryfikować ciągłość zakresów, stałą liczbę wyników, unikatowość SLA i zgodność z licznikami kategorii przed zapisem.
- [ ] Sprawdzić błędy przejścia, zmianę danych w trakcie odczytu, wygaśnięcie sesji i anulowanie. Odebrać pełny odczyt na rzeczywistej liście w ukrytym Chromium.

Do czasu odbioru wielostronicowy wynik zachowuje poprzednią listę i historię. Powiadomienia powstają wyłącznie po potwierdzeniu kompletnego odczytu.
