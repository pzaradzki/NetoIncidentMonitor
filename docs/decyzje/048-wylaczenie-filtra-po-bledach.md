# 048 — Wyłączenie filtra po błędach odczytu

**Status.** Wdrożono w źródłach.

**Decyzja.** Trzy kolejne odczyty listy zakończone błędem uruchamiają zapis wyłączenia danego filtra w harmonogramie. Udany pełny odczyt zeruje licznik jego rewizji. Wyłączony filtr zachowuje poprzedni wynik i można go odczytać ręcznie. Powrót do harmonogramu wymaga włączenia przełącznika.

**Powód.** Wcześniej trzeci błąd wyświetlał komunikat, a harmonogram dalej zlecał odczyty filtra. Zapis wyłączenia ogranicza powtarzające się błędy i pozwala dokończyć odczyty innych filtrów.

**Realizacja.** `Health` liczy końcowe błędy odczytu włączonej listy. Po progu wątek sesji zleca Tk zapis istniejącego ustawienia `enabled` i czeka na zakończenie zapisu. Tk sprawdza rewizję, generację i anulowanie. Po udanym zapisie aktualizuje przełącznik, unieważnia starsze zlecenia i podaje nazwę filtra w komunikacie. Zdarzenia zapisu `filter_config_change` z przyczyną `disable_failures` mają ten sam identyfikator odczytu co błąd kończący serię. [Obsługa w App](../../neto_incident_monitor/app.py) · [Kolejka i trwałość](../kontrakty/kolejka-i-trwalosc.md#kolejka-i-anulowanie)

**Ograniczenia.** Ponowienie techniczne jest częścią jednego odczytu. Anulowanie, obsługa logowania, osobne odświeżenie definicji lub układu i ręczny odczyt wyłączonego filtra są poza licznikiem. Przekroczenie limitu rekordów korzysta z odrębnego progu i wspólnego zapisu wyłączenia. Gdy zapis się nie powiedzie, filtr pozostaje w harmonogramie, a kolejna seria trzech błędów może zlecić ponowny zapis. [Decyzja 035](035-limit-odczytu-filtrow.md) · [Testy statusów](../../tests/test_view_status.py)

**Odbiór.** Syntetyczne odczyty potwierdziły reset serii po sukcesie, zapis wyłączenia i pominięcie filtra w kolejce, zachowanie wyniku oraz ręczne ponowienie. Sprawdzono też nieaktualne żądania i odmowę zapisu. Regresja z ponowieniem 48 prób potwierdziła 592 zaliczenia z 594. Dwa pominięcia wynikały z ograniczeń Windows dotyczących fokusu okna i dowiązań symbolicznych. Raporty w `build/filter-auto-disable-regression.json` i `build/filter-auto-disable-recheck.json`.
