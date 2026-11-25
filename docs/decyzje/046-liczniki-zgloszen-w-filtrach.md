# 046. Liczniki bieżących i niewyświetlonych zgłoszeń

**Status.** Wdrożono w źródłach. [Plan i odbiór](../plany/zakonczone/liczniki-zgloszen-na-liscie-filtrow.md)

**Decyzja.** Karta filtra pokazuje liczbę zgłoszeń w ostatnim przyjętym wyniku. Dodatnia liczba w nawiasie to zgłoszenia z tego wyniku niewyświetlone w bieżącym uruchomieniu. `—` oznacza brak przyjętego wyniku, a `0` potwierdzoną pustą listę.

**Powód.** Użytkownik może ocenić wielkość bieżącej listy i zauważyć nowe zgłoszenia przed otwarciem filtra. Liczenie według aktualnej listy pozwala odejmować zgłoszenia, które wypadły przed wyświetleniem.

**Realizacja.** Tk utrzymuje stan osobno dla każdego filtra. Użytkownik zalicza cały aktualnie wyświetlony zestaw przez wejście do zakładki bieżących zgłoszeń. Otwarte i widoczne bieżące zgłoszenia zaliczają kolejny wynik po jego wyświetleniu. Wczytywanie porcjowane musi się zakończyć dla tej samej migawki. Zgłoszenie powracające po potwierdzonej nieobecności jest ponownie liczone w nawiasie do chwili wyświetlenia listy. [Obsługa widoku](../../neto_incident_monitor/app.py#L1205) · [Karty filtrów](../../neto_incident_monitor/widgets.py#L709)

**Ograniczenia.** Stan działa w pamięci i zaczyna się od nowa po restarcie. Dawne pola przeczytania pozostają poza mechanizmem, a historia i powiadomienia nadal korzystają z osobnych zasad obecności. [Decyzja 012](012-usuniecie-stanu-przeczytania.md) · [Kontrakt kolejki i trwałości](../kontrakty/kolejka-i-trwalosc.md)
