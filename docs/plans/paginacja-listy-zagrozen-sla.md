# Paginacja listy zagrożeń SLA

**Otwarte.** Zadanie wydzielone z [planu listy zagrożeń i powiadomień](lista-zagrozonych-i-powiadomienia.md).

- [ ] Na rzeczywistej liście ServiceNow z co najmniej dwiema stronami potwierdzić zachowanie przycisku „Następna strona”, zmianę zakresu oraz stabilność identyfikatorów SLA.
- [ ] Dodać odczyt kolejnych stron do bieżącego czytnika. Zweryfikować ciągłość zakresów, stałą liczbę wyników, unikatowość SLA i zgodność z licznikami kategorii przed zapisem.
- [ ] Sprawdzić błędy przejścia, zmianę danych w trakcie odczytu, wygaśnięcie sesji i anulowanie. Odebrać pełny odczyt na rzeczywistej liście w ukrytym Chromium.

Do czasu odbioru wielostronicowy wynik zachowuje poprzednią listę i historię. Powiadomienia powstają wyłącznie po potwierdzeniu kompletnego odczytu.
