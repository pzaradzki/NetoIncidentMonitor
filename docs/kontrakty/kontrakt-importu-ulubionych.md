# Kontrakt importu Ulubionych ServiceNow

## Źródło

**Importuj z ServiceNow** zleca `GET /api/now/ui/navigator/favorites` bez parametrów. Użytkownika określa aktywna sesja na karcie `SharedSession`. Trasa jest jawnie dozwolona w `analytics_api.py`. Przy gotowym kontekście do odczytu wystarcza jeden GET. Brak kontekstu może wymagać otwarcia SOW na tej samej karcie.

## Odpowiedź i kompletność

- HTTP 200 z tablicą `result.favorites`. Tablica może być pusta. Brak tablicy, błędny JSON lub odpowiedź HTTP z błędem oznaczają nieudany odczyt.
- Każda pozycja i grupa mają tekstowe `id` i `title`. Pozycja ma tekstowy, niepusty `url`. Grupa zawiera tablicę `favorites` i może być pusta. Dodatkowe pola, takie jak ikony, są pomijane.
- Czytnik zachowuje kolejność serwera i ścieżki grup. Powtórzony `id`, niejednoznaczna struktura, sygnał paginacji (`Link` z `rel=next` lub `X-Total-Count`), ponad 1000 węzłów łącznie lub zagnieżdżenie ponad 8 grup kończą próbę bez częściowego wyniku.
- Podgląd klasyfikuje otrzymane adresy przez obecny walidator. Zachowuje adresy INC, REQ, RITM i SCTASK, w tym rozpoznawane skróty. Cele nieobsługiwane pozostają w podglądzie jako niedostępne do importu.

## Kolejka i zapis

- Jeden import obejmuje zlecenie i podgląd do jego zamknięcia. Karta jest dostępna dla następnych odczytów po pobraniu danych. **Stop** dotyczy monitoringu, a anulowanie importu dotyczy jego własnego zlecenia.
- Wspólny mechanizm ponowień stosuje budżet 30 sekund aktywnej pracy, osobno mierzy logowanie i może raz ponowić błąd przejściowy oraz raz odzyskać sesję. `403` i `429` kończą próbę. Zamknięcie Chromium podczas importu kończy to zlecenie, a ponowne połączenie pozostaje dostępne dla dalszej pracy sesji.
- Przed zapisem podgląd ponownie sprawdza konfigurację i duplikaty. Potwierdzone nowe filtry są zapisywane razem jako wyłączone, z wyłączonymi powiadomieniami. Anulowanie i nieudany zapis zachowują dotychczasową konfigurację.
- Diagnostyka wiąże odczyt z `import_id` i numerem zlecenia. Zapisuje status HTTP, liczbę grup i zakładek, czasy oraz stałe kategorie wyniku. Treści zakładek i dane sesji pozostają poza logami.

Trasa nawigatora jest wewnętrzna dla ServiceNow. Po aktualizacji platformy porównaj podgląd z menu na zwykłym koncie. Ustalony zakres próby w ADEO opisuje [decyzja 036](../decyzje/036-import-ulubionych-przez-rest.md).
