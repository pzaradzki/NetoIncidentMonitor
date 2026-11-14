# Paginacja listy zagrożeń SLA

**Plan archiwalny, zastąpiony przez REST.** Wielostronicowy odczyt przez API sprawdzono na danych syntetycznych. Użytkownik potwierdził zgodność niepustej listy z ServiceNow. Wyniki opisuje [plan migracji](dashboard-servicenow-api.md).

Pierwotny plan zakładał klikanie przycisku „Następna strona” w interfejsie ServiceNow, kontrolę ciągłości zakresów i weryfikację kompletności listy przed zapisem. Aplikacja pobiera dziś kolejne strony przez REST i aktualizuje historię oraz powiadomienia po potwierdzeniu kompletnego odczytu.
