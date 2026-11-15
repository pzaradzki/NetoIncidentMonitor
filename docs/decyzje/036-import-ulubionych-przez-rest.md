# 036 — Import Ulubionych przez API nawigatora

15 listopada 2026. **Status.** Przyjęta i wdrożona w źródłach.

**Decyzja.** Import Ulubionych używa `GET /api/now/ui/navigator/favorites` na karcie należącej do `SharedSession`.

**Powód.** W ADEO Table API dla `sys_ui_bookmark` zwróciło pustą tablicę przy liczniku 37, także z limitem obejmującym cały deklarowany zakres. Odczyt nawigatora na zwykłym koncie zwrócił wszystkie 37 pozycji z menu. Zgodne były nazwy, adresy i identyfikatory oraz zestaw 34 obsługiwanych filtrów.

**Realizacja.** Wspólny transport wysyła jeden odczyt bez parametrów w aktywnej sesji. Czytnik przekazuje pełne drzewo do klasyfikacji po walidacji grup, pozycji i ograniczeń. Podgląd oraz jawne zatwierdzenie zapisu zachowują kontrakt [022](022-import-ulubionych-na-zadanie.md). Źródło danych zastępuje czytnik menu z 022 i mechanizmy rozmiaru strony z [023](023-naturalne-logowanie-importu.md). Własność karty i kolejki określa [025](025-wspolna-sesja-servicenow.md).

**Ograniczenia.** To wewnętrzna trasa produktu. Próby obejmowały instancję ADEO z istniejącymi zakładkami i grupami na zwykłym koncie. Zachowanie pustej odpowiedzi sprawdzamy także syntetycznie. Po aktualizacji ServiceNow należy porównać wynik z menu. [Kontrakt](../kontrakty/kontrakt-importu-ulubionych.md)
