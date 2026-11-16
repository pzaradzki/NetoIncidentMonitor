# Definicja filtra ServiceNow bez otwierania klasycznej listy

Badanie w instancji ADEO wykonano 15 listopada 2026 r. Rozwiązanie sprawdzono w odrębnych, zalogowanych sesjach zwykłego użytkownika. Na dostarczonym skrócie `__tinyId__` prototyp pobrał kompletną definicję filtra INC w dwóch żądaniach ze strony SOW. Licznik nawigacji na klasyczną listę w trakcie tych dwóch żądań wyniósł zero. Klasyczną listę otwarto później do porównania. Poniższe próby i propozycje opisują stan badania przed wdrożeniem.

Wdrożenie rozdzieliło zapis zapytania i współdzielony układ, dodało walidację pól oraz usunęło czytnik DOM. Odbiór na jednym zwykłym koncie ADEO objął cztery domyślne układy, nazwany widok REQ, skrót INC i po jednym rekordzie każdego typu. Nieznany widok zwracał układ zapasowy mimo HTTP 200. Table API mogło pominąć błędne pole warunku. RITM zwrócił kompletny rekord z pominięciem jednej wartości `cat_item.workflow`, która jest teraz oznaczana jako niedostępna. Aktualne granice obsługi zapisano w [kontrakcie list](../kontrakty/kontrakt-odczytu-list.md) i [decyzji 037](../decyzje/037-definicje-filtrow-bez-dom.md).

## Wyniki rzeczywistych prób

| Próba | Wynik |
| --- | --- |
| Table API `GET /api/now/table/sys_tiny_url` ograniczone do dostarczonego identyfikatora | HTTP 200 i pusta tablica. W tym samym koncie skrót działał w nawigacji. Przyczyna pustej odpowiedzi pozostaje nieustalona. |
| `GET` pod adresem skrótu | HTTP 200 i HTML. Pełny cel jest w `window.__initialRoutePayload` pod `params.target`. Skrót w odpowiedzi był identyczny z żądanym, a `wasTinyURLResolved` miało wartość logiczną `true`. |
| `POST /xmlhttp.do` dla ustalonej tabeli i widoku | HTTP 200 i XML. Odczyt zwrócił spersonalizowane 14 kolumn, wszystkie przed otwarciem klasycznej listy. |
| Porównanie z klasyczną listą | Tabela `incident`, parametr widoku i `sysparm_query` zgadzały się z adresem ramki. Efektywny widok to `default`, a klient klasycznej listy nie zgłaszał dodatkowego stałego warunku. Wszystkie 14 technicznych nazw i etykiet zgadzało się w tej samej kolejności. |
| Warunki i sortowanie | Efektywny warunek tabeli różnił się zapisem znanego aliasu daty z [decyzji 015](../decyzje/015-rownowaznosc-dat-filtrow.md). `compare_list_conditions()` zwróciło `known_alias`. Teksty wyjściowe dla Table API różniły się literalnie, a dyrektywy `ORDERBY` po zastosowaniu `api_query()` były identyczne. |

Odrębna wcześniejsza próba z pełnym adresem INC potwierdziła dokładną zgodność jawnych warunków z klasyczną listą oraz zgodność 14 kolumn z `UIPage / getList`. Table API dla `sys_ui_list` zwróciło HTTP 403. Katalog `/api/now/ui/meta/incident` potwierdził etykiety, a kolejność i wybór kolumn potwierdził XML. [Dokumentacja Table API](https://www.servicenow.com/docs/r/api-reference/rest-apis/c_TableAPI.html) · [Dokumentacja GlideList2](https://www.servicenow.com/docs/r/api-reference/c_GlideList2API.html)

## Rozwinięcie skrótu

`GET` wysyłamy na dostarczony skrót w tej samej instancji, w kontekście zalogowanej karty. Skrót zwraca stronę nawigatora bez nagłówka `Location`. Pobranie tekstu tej odpowiedzi pozwala odczytać dane startowe przy zachowaniu bieżącego dokumentu SOW. [Skrócone adresy w ServiceNow](https://www.servicenow.com/docs/r/platform-user-interface/configure-user-experiences/t_EnableTinyURLSupport.html)

W badanym HTML były dwa przypisania `window.__initialRoutePayload`. Jedno miało postać `JSON.parse(...)` z cytowanym i escapowanym literałem JavaScript, drugie przypisywało pusty obiekt. Prototyp odczytał literał jako dane, zdekodował jego sekwencje ucieczki i zastosował parser JSON bez wykonywania skryptu strony. Przykład przedstawia syntetyczną treść po dekodowaniu literału.

```json
{
  "__tinyId__": "syntetyczny-identyfikator",
  "wasTinyURLResolved": true,
  "params": {
    "target": "incident_list.do?sysparm_query=active%3Dtrue%5Epriority%3D2&sysparm_view=default"
  }
}
```

Z wyniku wybieramy dokładnie jeden obiekt z identycznym `__tinyId__`, wartością logiczną `true` w `wasTinyURLResolved` i tekstowym `params.target`. Puste przypisanie pozostaje poza wynikiem. `params.target` był adresem względnym względem katalogu głównego instancji. Pole `encodedParams` zawierało zakodowane parametry nawigatora i do tej próby wystarczyło `params.target`.

Cel przechodzi obecne `normalize_list_url(..., allow_short=False)`, kontrolę dozwolonego hosta i tabeli oraz `unsupported_context()` i `api_query()`. Prototyp wymagał dokładnie jednego niepustego `sysparm_query`, maksymalnie jednego `sysparm_view` i pełnego rozwinięcia bez `sysparm_tiny`. To granica rozpoznania potwierdzona w tym badaniu. Właściwy parser powinien rozpoznawać sprawdzoną strukturę i czytać wyłącznie literały danych, z limitem odpowiedzi i bez przeszukiwania dowolnych wystąpień `sysparm_query`. W prototypie zaliczono 11 syntetycznych przypadków walidatora celu, w tym obcy host, inny identyfikator, wieloznaczny cel, cel nadal zawierający `sysparm_tiny`, pusty warunek, sprzeczne parametry i niedozwolony typ listy. [Normalizacja w kodzie](../../neto_incident_monitor/service_now_urls.py) · [Decyzja 016](../decyzje/016-normalizacja-adresow-list.md)

## Odczyt kolumn

Z SOW działa jeden `POST /xmlhttp.do` jako odczytowa operacja interfejsu `UIPage / getList`. Odczyt układu potrzebuje ustalonej tabeli i widoku. W próbie wystarczyły poniższe parametry formularza.

```text
sysparm_processor=AJAXXMLHttpAggregator
sysparm_scope=global
sysparm_aggregation_size=1
0.sysparm_processor=UIPage
0.sysparm_scope=global
0.sysparm_name=getList
0.sysparm_table=incident
0.sysparm_list_view=default
0.sysparm_list_parent=
0.sysparm_list_parent_id=
0.sysparm_list_relationship=
```

Z XML odczytujemy `choice_list_set/selected/choice` z odpowiedzi operacji `UIPage / getList`. Atrybut `value` określa pole techniczne, a `label` etykietę. Kolejność elementów to kolejność kolumn użytkownika. Układ zawierał oznaczenie `user_list`. W obu próbach tabela i widok wystarczyły do uzyskania spersonalizowanego układu. `getList` i format `__initialRoutePayload` są wewnętrznymi kontraktami używanymi przez interfejs tej instancji. [Dokumentacja GlideAjax](https://www.servicenow.com/docs/r/api-reference/c_GlideAjaxAPI.html)

Przy wdrożeniu XML powinien zachować istniejące klucze aplikacji, np. `caller_id` → `caller` i `sys_created_on` → `created`. Stabilne klucze są potrzebne lokalnym ustawieniom kolumn, historii i szablonom powiadomień po odświeżeniu definicji. Pole, etykieta i kolejność są potwierdzone. Równoważność pełnego mapowania `key` warto sprawdzić przed podmianą czytnika. [Aktualne mapowanie nagłówków](../../neto_incident_monitor/filter_definition.py) · [Kontrakt list](../kontrakty/kontrakt-odczytu-list.md)

## Ustalenia do przyszłego planu

- Wspólna karta i kolejka wystarczą. Przy brakującej definicji lub ręcznym odświeżeniu przez **ⓘ** skrót może przejść ścieżkę `GET skrótu → cel → odczyt układu → walidacja → atomowy zapis`. Pełny adres z potwierdzonym zakresem zaczyna od walidacji celu. Obecne odczyty rekordów, limit list, powiadomienia i częstotliwość harmonogramu mają nadal korzystać ze zapisanej definicji. [Decyzja 034](../decyzje/034-odczyt-filtrow-przez-rest.md) · [Decyzja 035](../decyzje/035-limit-odczytu-filtrow.md)
- Pierwotny skrót nadal identyfikuje zapisany filtr. Rozwinięty adres i definicję można zapisać istniejącymi polami `resolved_list_url` i `list_definition`. Zmiana adresu unieważnia oba pola. Nieudana próba ręcznego odświeżenia zachowuje ostatnią poprawną definicję zgodnie z kontraktem aplikacji.
- Zachowaj semantykę OR/NQ, sortowanie oraz wąski wyjątek dla sprawdzonego aliasu dat. Nieznany warunek, dodatkowy kontekst listy, wieloznaczna odpowiedź lub niepotwierdzony widok wymagają bieżącego rozpoznawania klasycznej listy albo czytelnego błędu według obecnych reguł. Brak rozpoznanych warunków nie może skutkować odczytem całej tabeli.
- Zachowaj wspólne odzyskiwanie sesji, anulowanie i ograniczony budżet czasu. Ogranicz nowe żądanie POST do potwierdzonej operacji odczytowej. W diagnostyce wystarczą etap, alias operacji, HTTP, liczba dopasowań i kolumn, powód wyboru ścieżki zapasowej oraz czas w korelacji istniejącego zlecenia. Pełne adresy, treść `sysparm_query`, HTML, XML i dane sesji pozostają poza logami.
- Przed wycofaniem odczytu DOM porównaj pełne i skrócone adresy dla INC, REQ, RITM i SCTASK, widoki nazwane, układ domyślny i spersonalizowany oraz pola odwołujące się do innej tabeli. Oddzielnie sprawdź puste jawne zapytanie, brak zapytania, wygaśnięcie skrótu, utratę sesji i zmianę personalizacji po ponownym rozpoznaniu. Odbiór powinien porównać warunki, sortowanie, tabelę, widok, kolejność, etykiety i klucze oraz potwierdzić zachowanie zapisanej konfiguracji po błędzie. Rzeczywisty dowód z tego badania dotyczy filtra INC, dostarczonego skrótu i widoku `default`.
