# Naprawa filtra „Dyżur 1L”

4 listopada 2026. Zakończono implementację i rzeczywisty odbiór źródeł oraz lokalnego EXE. Publikacji nie wykonywano.

- [x] Potwierdzić różnicę między żądaniem a tabelą na rzeczywistej stronie, także po zmianie strony.
- [x] Rozpoznać wyłącznie potwierdzony alias daty, z zachowaniem pozostałych warunków i tożsamości filtra.
- [x] Dodać ograniczoną diagnostykę zgodności bez zapytań i danych zgłoszeń.
- [x] Sprawdzić oba kierunki aliasu i paginację z OR/NQ oraz odrzucanie rzeczywistych zmian.
- [x] Zweryfikować zachowanie historii po błędzie, dalszy odczyt filtrów, Stop, utratę sesji i bezpieczeństwo diagnostyki.
- [x] Uruchomić izolowaną regresję zakresową — 75 testów.
- [x] Dwukrotnie odczytać rzeczywisty filtr ze źródeł i następnie filtr kontrolny.
- [x] Przebudować lokalny EXE i wykonać dwa pełne cykle na osobnych danych, bez powiadomień.
- [x] Zaktualizować architekturę, decyzję i kontrakt.

Dowody i granice: [kontrakt list](../../kontrakty/kontrakt-odczytu-list.md), [decyzja 015](../../decyzje/015-rownowaznosc-dat-filtrow.md). Przebudowa obejmuje bieżące źródła, także wcześniejsze niewydane zmiany. Numer wersji pozostawiono bez zmiany; istniejący ZIP nie jest nową paczką tego buildu.
