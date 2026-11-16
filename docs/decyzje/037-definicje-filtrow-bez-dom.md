# 037 — Definicje filtrów bez otwierania klasycznej listy

**Status** — przyjęta i wdrożona w źródłach. Zastępuje część [decyzji 034](034-odczyt-filtrow-przez-rest.md) o ustalaniu i zapisie metadanych.

Potwierdzanie zmiennych katalogowych i złożonych operatorów rozszerza [decyzja 038](038-walidacja-warunkow-filtrow.md).

**Decyzja** — utrwalamy jawne zapytanie z sortowaniem, tabelę i widok przy filtrze. Współdzielimy układ kolumn między filtrami tego samego konta, tabeli i widoku. Przy zmianie linku tylko ten filtr traci zapis zapytania. Jeżeli nowy odczyt układu zawiedzie, odpowiedni ostatni poprawny układ pozostaje dostępny. Brak potwierdzenia zakresu przerywa operację przed pobraniem rekordów.

**Powód** — rekordy są już dostępne przez Table API. Oddzielne przechowywanie układów ogranicza liczbę odczytów, zachowuje personalizację i pozwala wycofać nawigację oraz renderowanie klasycznej listy. Lokalne ustawienia kolumn pozostają zapisane przy filtrze.

Przycisk **Aktualizuj** w podglądzie ustawień odświeża cztery domyślne układy jako jedno ręczne zadanie. Zadanie czeka na wspólną sesję, zachowuje zapisy poszczególnych tabel po częściowym błędzie i zatrzymuje się po zmianie konta.

**Realizacja i ograniczenia** — `SharedSession` kolejkuje odczyty po zalogowaniu. Pełny adres dostarcza jawny zakres, skrót wymaga odczytania danych startowych nawigatora, a nowe pola weryfikuje katalog metadanych tabel. `UIPage / getList` dostarcza układ. Porównanie z odpowiedzią zapasową pozwala odrzucić niepotwierdzony widok, nawet przy HTTP 200. Jawny widok w adresie określa intencję użytkownika. Niezadeklarowany widok oznacza `default` dla zweryfikowanych samodzielnych list. Oprogramowanie odrzuca kontekstowe adresy z dodatkowymi warunkami, których nie może udowodnić. Etykiety pochodzą z układu ServiceNow, także tam, gdzie nagłówek klasycznej listy stosuje inną etykietę odwołania. Zakres, koszt żądań i wynik odbioru opisują [kontrakt list](../kontrakty/kontrakt-odczytu-list.md) i [analiza](../analizy/definicja-filtrow-servicenow-bez-dom.md).
