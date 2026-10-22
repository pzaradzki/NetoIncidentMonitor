# Niestandardowe powiadomienia dla filtrów

Status: zaimplementowano wspólną bibliotekę nazwanych, dwupoziomowych szablonów w konfiguracji kanałów filtra (22.10.2026).

## Aktualna obsługa

W ustawieniach filtra otwórz zębatkę przy Teams lub Google Chat i wybierz nazwany szablon. Biblioteka jest wspólna dla wszystkich filtrów i obu kanałów; każdy filtr i kanał wybiera szablon niezależnie. Dodaj/Edytuj otwiera osobny edytor z nazwą, a Usuń wymaga potwierdzenia. Standardowy blokuje edycję i usunięcie. Usunięcie własnego szablonu przełącza jego użycia na Standardowy. Windows zachowuje standardowy format. Globalne przełączniki pozostają nadrzędne; pusty webhook korzysta z adresu globalnego.

Szablon wiadomości obsługuje `{filtr}`, `{liczba}` i `{lista incydentów}`. Szablon elementu listy jest powtarzany dla każdego INC/SCTASK i obsługuje identyfikatory wszystkich kolumn wykrytych na liście tego filtra. Selektor pokazuje etykietę i stabilny identyfikator kolumny, np. `Krótki opis [short_description]`; przycisk wstawia `{short_description}`. Zmiana etykiety nie zmienia znaczenia zmiennej. Kolumny nie muszą być widoczne w tabeli aplikacji.

Podgląd w edytorze i test używają danych przykładowych. Test wysyła wiadomość w tle na wskazany lub globalny webhook. „Zapisz szablon” i „Zastosuj” zatwierdzają szkice; dopiero „Zapisz” w oknie filtra zapisuje konfigurację oraz bibliotekę razem. Anulowanie zachowuje wcześniejsze ustawienia. Dotychczasowe własne formaty migrują do nazwanych szablonów; nazwy są unikalne, a powiązania korzystają ze stabilnych identyfikatorów.

Brakujące wartości i niedostępne kolumny są zastępowane pustym tekstem; separatory wpisane w szablonie pozostają. Edytor ostrzega o niedostępnych kolumnach. Numery są linkowane wyłącznie do zweryfikowanych adresów rekordów ServiceNow; dane nie mogą wstrzykiwać znaczników ani wzmianek. Szablony są zwykłym tekstem, bez wykonywania wyrażeń. Oba kanały dzielą duże wiadomości.

Poniżej zachowano wcześniejsze notatki projektowe; aktualne zachowanie opisuje ta sekcja.

## Zakres uzgodniony z użytkownikiem

- Osobna konfiguracja niestandardowego powiadomienia dla każdego filtra.
- W oknie „Ustawienia filtra” nowy wpis „Skonfiguruj niestandardowe powiadomienie”, przycisk „Konfiguruj” i przełącznik aktywacji.
- Konfiguracja pozwala wybrać informacje zawarte w wiadomości oraz ich kolejność.
- Dostępne są wszystkie rozpoznane kolumny konkretnej listy ServiceNow, a nie tylko obecny stały zestaw pól INC/SCTASK lub kolumny widoczne w tabeli aplikacji.
- Pierwszy poprawny odczyt filtra jest wymagany do rozpoznania dostępnych kolumn. Trzeba odczytywać zarówno nagłówki, jak i wartości wybranych pól.
- Możliwość wpisania osobnego webhooka dla danego filtra.

## Zaproponowane zachowanie do potwierdzenia przed implementacją

- Wyłączenie niestandardowego powiadomienia przywraca standardowy format i trasowanie, zachowując konfigurację filtra.
- Lista pól zawiera zaznaczenia i przyciski przesuwania w górę oraz w dół. Podgląd wiadomości aktualizuje się na bieżąco.
- Pole numeru zachowuje hiperłącze w obsługujących je kanałach.
- Kanał własnego webhooka jest wybierany jawnie: Google Chat albo Microsoft Teams. Własny webhook zastępuje globalny dla tego filtra i kanału, bez podwójnego wysyłania.
- Puste pole webhooka oznacza użycie globalnego adresu kanału.
- Globalne przełączniki kanałów pozostają nadrzędne. Format niestandardowy stosowany jest we wszystkich aktywnych kanałach, natomiast własny webhook tylko w wybranym kanale.
- Przycisk „Wyślij test” umożliwia sprawdzenie konfiguracji. Zapis i anulowanie powinny mieć jednoznaczny zakres; anulowanie nie może zmienić aktywnej konfiguracji.
- Brakujące wartości są pomijane bez zbędnych separatorów.

## Rozpoznawanie kolumn

- Przed pierwszym poprawnym odczytem komunikat: „Uruchom monitoring tego filtra, aby pobrać dostępne pola”.
- Zapamiętywanie identyfikatorów i nazw kolumn osobno dla każdego adresu filtra, także między uruchomieniami.
- Kolejne poprawne odczyty aktualizują dostępne pola. Błąd odczytu nie powinien zerować zapamiętanego schematu.
- Wybrane pole, które przestało występować na liście, pozostaje zapisane jako niedostępne i jest pomijane przy wysyłce.
- Zakres obejmuje kolumny obecne na monitorowanej liście. Odczytywanie pól dopiero ze szczegółów rekordu nie jest częścią tej propozycji.
- Rodzaj INC/SCTASK rozpoznawany automatycznie. Selektor rodzaju w wizualizacji służył wyłącznie demonstracji.

## Kwestie techniczne do rozstrzygnięcia

- Stabilne identyfikatory kolumn, powtarzające się nazwy nagłówków, wartości referencyjne i puste listy.
- Odczyt i przechowywanie dynamicznych wartości w wynikach, historii i zdarzeniach powiadomień, z migracją dotychczasowych danych.
- Zachowanie ustawień przy zmianie adresu filtra, dostępności pól i zmianach kanałów globalnych.
- Wariant dla własnych webhooków kilku kanałów jednocześnie, format separatorów i ewentualne ustawienia osobno dla kanałów nie zostały jeszcze uzgodnione.
- Webhooki wprowadzane przez użytkownika zapisywać jako konfigurację użytkownika. Nie umieszczać ich na stałe w kodzie, testach, dokumentacji ani pakietach dystrybucyjnych.

## Wznowienie prac

Utworzyć nową gałąź z aktualnego `master`. Poprzednia gałąź `codex/custom-filter-notifications` została przeznaczona do usunięcia; nie zawierała implementacji tej funkcji. Nie przywracać starej historii sprzed czyszczenia webhooka.

Istniejący prototyp był wyłącznie interaktywną propozycją interfejsu, bez wysyłania danych i bez zmian w aplikacji. Przy wznowieniu należy potwierdzić zasady trasowania i globalnego włączania kanałów przed implementacją.
