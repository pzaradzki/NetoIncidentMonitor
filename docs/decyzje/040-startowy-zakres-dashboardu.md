# 040 — Pobranie brakującego zakresu dashboardu po zalogowaniu

**Status.** Wdrożona w źródłach. Uzupełnia [decyzję o kolejności aktualizacji](018-kolejnosc-aktualizacji.md) i zastępuje domyślne listy z paczki `1.12.0-experimental.2`.

**Decyzja.** Paczka zawiera parametry zapytań SLA. Obie listy identyfikatorów przechowuje profil użytkownika. Brak kompletu uruchamia jedno zlecenie `dashboard_scope` po potwierdzeniu logowania. Komplet zapisany lokalnie wystarcza do odczytu.

**Powód.** Świeży profil powinien działać po zalogowaniu bez kopiowania plików. Wykorzystanie tej samej kolejki zapobiega przejęciu karty przez dashboard, gdy czytnik zakresu korzysta z widoku ServiceNow.

**Realizacja.** Po próbach układów INC, REQ, RITM i SCTASK aplikacja wykonuje istniejący odczyt zakresu na wspólnej karcie. Zapis atomowy dotyczy obu list. Ręczne zlecenie łączy się z oczekującym odczytem tego samego zakresu. Po odzyskaniu sesji sprawdzane jest konto, dla którego przyjęto zlecenie.

**Ograniczenia.** Błąd pozwala kontynuować pracę filtrów i zagrożeń. Dashboard zachowuje ostatnie dane. Ręczne ponowienie jest dostępne w ustawieniach, a kolejna próba automatyczna następuje po ponownym uruchomieniu, jeśli profil wciąż nie ma kompletu.
