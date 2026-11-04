# 016 — Rozpakowywanie długich adresów list

Data: 4 listopada 2026. Status: przyjęta, wdrożona w źródłach.

## Decyzja

Adres `/now/nav/ui/classic/params/target/` rozpakowujemy raz, a parametry wewnętrznego celu parsujemy i kodujemy ponownie jako parametry bezpośredniej listy. Dołączamy parametry spoza zakodowanego celu, bez utraty widoku lub numeru wiersza. Sprzeczne wartości powtórzonego parametru `sysparm_*` są błędem; identyczne pary w opakowanym adresie są deduplikowane.

## Powód

ServiceNow przyjmuje długi adres „Dyżur 1L” i skraca go do `__tinyId__`. Poprzedni normalizator dekodował `locationNOT%20LIKESTORE` do surowej spacji, po czym sam odrzucał wynik. Błąd dotyczył dodawania adresu, niezależnie od [aliasu daty](015-rownowaznosc-dat-filtrow.md) podczas odczytu.

## Realizacja i ograniczenia

Rozszerzono istniejący `normalize_list_url`. `parse_qsl` i `urlencode(quote_via=quote)` zachowują wartości parametrów, a końcowa kontrola nadal wymaga HTTPS, właściwego hosta i dozwolonej listy. Nie dekodujemy rekurencyjnie. Poprawnie zagnieżdżone kodowanie zachowuje znaki `+`, `%`, `&`, `=`, Unicode i spacje. Niedozwolone znaki są sprawdzane także po rozpakowaniu parametrów.

Nowy opakowany adres zapisujemy jako bezpośredni. Dotychczasowe adresy bezpośrednie zachowują zapis, bo identyfikują historię i stan. Skróty nadal mają dotychczasową ścieżkę rozwiązywania. Diagnostyka walidacji zapisuje wyłącznie rodzaj adresu, wynik i stałą kategorię błędu. [Kontrakt](../kontrakty/kontrakt-odczytu-list.md).
