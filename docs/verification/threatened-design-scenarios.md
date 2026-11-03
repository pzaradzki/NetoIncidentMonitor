# Zagrożenia — weryfikacja syntetycznego projektu

2 listopada 2026. **Bez implementacji produktu.** [Plan](../plans/lista-zagrozonych-i-powiadomienia.md), [scenariusze i instrukcja](../fixtures/threatened/README.md).

Przygotowano 32 scenariusze / 60 kroków. Wszystkie przeszły przez izolowany model referencyjny. Oczekiwane wyniki są zapisane w fixture, nie wyliczane przez model podczas testu. Trzy kontrolowane mutacje modelu zostały wykryte: pominięcie pierwszego powiadomienia, usuwanie historii po pustym odczycie i ignorowanie błędu zatwierdzenia.

Sprawdzony zakres projektu:

- Pierwsze wykrycie, brak powtórzeń przy kolejnych odczytach/zmianie wartości lub kategorii, potwierdzone zniknięcie i ponowne pojawienie.
- Jedna pozycja historii na INC, pierwsze/ostatnie wykrycie i licznik pojawień; zachowanie po restarcie przez serializację JSON.
- Wiele SLA jednego INC: spójna para czas/procent, najbliższy termin także po przekroczeniu, stabilny remis, brak zgadywania przy nieznanym terminie.
- Błąd, partial, anulowanie, oczekiwanie na logowanie/ładowanie i timeout nie zmieniają obecności. Wstrzyknięta odmowa zatwierdzenia nie publikuje stanu ani zamiaru powiadomienia.
- Abstrakcyjne strony 1/25/26 rekordów, luka zakresu, zmiana total, brak końcowej strony, powtórzony SLA i rozbieżność zakres/liczba wierszy. Kompletność sprawdzana przed deduplikacją INC.
- Symulacja nie zanieczyszcza trwałej obecności/historii i nie tworzy zamiaru rzeczywistej wysyłki.

**Granice:** to sprawdzenie reguł projektowych, nie test aplikacji. Nie testowano rzeczywistego zapisu/awarii dysku, transportów, logów, parserów wartości, linków, DOM lub pagera. JSON round-trip nie dowodzi trwałości przy utracie zasilania. Wstrzyknięty wynik błędu nie testuje rozpoznawania tego błędu na stronie. Strony 25/26 są syntetyczne; nie potwierdzają realnego sposobu paginacji `NOW-LIST`.

Etap B jest przygotowany częściowo: scenariusze reguł są gotowe, ale mapping rzeczywistych wierszy i odbiór adaptera czekają na etap A. Przy wdrożeniu te same przypadki należy uruchomić przeciw kodowi aplikacji, zamiast uznawać wyniki modelu za testy produktu. Pełny zestaw regresji aplikacji nie był potrzebny do tej zmiany materiałów projektowych; nie budowano EXE ani ZIP.
