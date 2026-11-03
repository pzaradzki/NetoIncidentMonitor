# Audyt stanu aplikacji podczas monitoringu

3 listopada 2026. Zakres obejmuje źródła, kolejki i zapis lokalny. Dwie kontrolowane próby uruchomiły aktualną metodę `App.drain` z syntetyczną kolejką i atrapą nadawcy. Pozostałe ustalenia pochodzą z przeglądu kodu. Nie uruchamiano ServiceNow ani rzeczywistej wysyłki.

| ID | Priorytet | Ustalenie i dowód |
| --- | --- | --- |
| S1 | Wysoki | **Potwierdzone testem.** Kolejka Stop → powiadomienie nadal przekazuje powiadomienie do `notify_filter`, gdy flaga Stop jest ustawiona. Próba zamknięcie → powiadomienie zostawia zdarzenie w kolejce po wyjściu z `drain`. To wzmacnia F5: zdarzenie interfejsu nie jest trwałą intencją. |
| S2 | Wysoki | **Ścieżka w kodzie.** Wyłączenie filtra po ostatnim sprawdzeniu `disabled_filter_urls` może zbiec się z zapisem historii i obecności. UI odrzuca snapshot dla wyłączonego filtra, ale worker może już zapisać wynik. Szybkie wyłącz/włącz może przyjąć zdarzenie ze starego odczytu, bo identyfikuje je URL i bieżący stan przełącznika. Przestawienie kolejności jest bezpieczniejsze dla zdarzeń z URL, ale istnieją też ścieżki z indeksem. |
| S3 | Wysoki | **Ścieżka w kodzie.** Preferencja `first_only` jest odczytywana przed zapisem, kanały i szablony przy obsłudze zdarzenia przez Tk, a nadawca zachowuje webhook i treść z momentu kolejkowania. Wyłączenie kanału lub zmiana adresu po kolejkowaniu nie wycofuje zadania. Zmiana adresu między wykryciem a kolejkowaniem może skierować wcześniejszy alert do nowego celu. Oba kanały potrzebują jawnej granicy obowiązywania ustawień. |
| S4 | Wysoki | **Ścieżka w kodzie.** Zamknięcie czeka na monitor, ale nadawcy Teams i Chat działają jako wątki daemon bez uzgodnionego zakończenia. Oczekujące zadania i reszta wiadomości dzielonej na części mogą przepaść. Status kanału nie odróżnia pewnego odrzucenia, częściowego przyjęcia i nieznanego wyniku. |
| S5 | Średni | **Ocena kodu.** Główne zapisy konfiguracji biegną przez Tk, a `secret_config` chroni pojedynczy zapis. Nie wykazano dwóch równoległych zapisów CONFIG. Ryzyko leży w różnych wersjach ustawień czytanych przez worker i w osobnych zapisach stanu/historii (F4), nie w potrzebie ogólnej blokady. Sprawdzić zapis ustawień, gdy otwarty edytor ma starszą kopię, oraz rollback po błędzie zapisu. |
| S6 | Średni | **Ocena kodu.** Dashboard i zagrożenia mają ID żądania. Ogólne zdarzenia fazy, statusu, odczytu i zakończenia nie mają wspólnej generacji monitoringu. Normalny start jest blokowany do zakończenia i nie potwierdzono awarii po szybkim restarcie. Test powinien sprawdzić opóźnione zdarzenia i odpowiedzi kanałów, szczególnie na granicy zamykania i odtwarzania Chromium. |

## Wnioski dla wdrożenia

Zachować podział z decyzji 001. Tk zatwierdza konfigurację, worker dostaje spójny snapshot opcji i identyfikator rewizji filtra, a wyniki niosą generację monitoringu i ID odczytu. Przy zapisie ponownie sprawdzić uprawnienie operacji do commit w tej samej granicy synchronizacji. Sama kontrola flagi przed zapisem pozostawia wyścig. Zmianę kolejności traktować jako zmianę prezentacji. Wyłączenie, zmiana celu i Stop unieważniają odpowiedni odczyt przed commit. Ostatni potwierdzony wynik pozostaje dostępny.

Proponowana polityka kanałów do uzgodnienia w etapie E: przed rozpoczęciem wysyłki ponownie sprawdzać uprawnienie i wersję kanału, zadania ze starym celem wstrzymać bez automatycznego przekierowania. Po rozpoczęciu POST nie można zapewnić cofnięcia. Zapisać wynik każdej części i pozostawić wynik niepewny do rozstrzygnięcia. Odróżnić Stop monitoringu od zamknięcia procesu i od ręcznego testu kanału.

Testy odbioru powinny używać barier i atrap, bez polegania na odstępach czasowych. Zatrzymać worker przed commit, przełączyć filtr i wznowić. Zmienić webhook przed i po zakolejkowaniu, zasymulować błąd drugiej części i zamknięcie podczas wysyłki. Sprawdzić rollback konfiguracji, odrzucenie opóźnionych zdarzeń oraz korelację bez sekretów. Do wyników odbioru włączyć logi przyczyn odrzucenia, anulowania i wstrzymania oraz wynik końcowy.

Wymagania włączono do [planu stabilizacji filtrów](../plans/stabilizacja-odczytu-filtrow.md). S1–S6 opisują dowody i ryzyka, a proponowana polityka stanowi część planu.

## Domknięcie prób lokalnych — 3 listopada 2026

Dziewięć kontrolowanych prób uzupełnia dwie wcześniejsze. Uruchomiono metody ze źródeł, podstawiając kolejki, zależności Tk i transporty. Zapis testowano na osobnym pliku z danymi syntetycznymi. Bez połączenia z ServiceNow i bez wysyłki.

- **S2.** Snapshot zakolejkowany przed wyłączeniem został przyjęty po ponownym włączeniu tego samego filtra. Próba odtwarza kolejność w kolejce Tk. Wyścig na granicy trwałego zapisu pozostaje wnioskiem z przeglądu kodu, a jego test z barierą jest warunkiem odbioru poprawki.
- **S3.** Obsługa alertu użyła aktualnego celu Teams. Po przyjęciu zadania do kolejki Teams i Chat zachowały wcześniejszy cel. Potwierdzono dwie różne granice konfiguracji. Wybór szablonu przy obsłudze alertu potwierdza kod.
- **S4.** W obu transportach pierwsza część została zaakceptowana przez atrapę, a druga zgłosiła błąd. Wynik całego zadania był błędem i nie zawierał informacji o już przyjętej części. Rzeczywistego przerwania procesu w trakcie HTTP nie symulowano; ograniczenie zamykania wynika z cyklu życia wątków.
- **S5.** Po wymuszonym błędzie zapisu przełącznik filtra wrócił do poprzedniej wartości. Osobna próba awarii zastąpienia pliku zachowała poprzedni plik bajt w bajt i usunęła plik tymczasowy. Przegląd nie wykazał równoległych zapisów tego samego CONFIG przez monitor i Tk.
- **S6.** Wstrzyknięte zdarzenie fazy z poprzedniego przebiegu zostało obsłużone. To potwierdza brak bariery w odbiorcy, ale nie dowodzi, że takie zdarzenie powstaje po zwykłym restarcie.

Sondę zachowano lokalnie w ignorowanym katalogu data. Zebrane dowody wystarczają do zamknięcia audytu przekrojowego. Testy współbieżności po poprawkach pozostają w etapach D–G planu. Kod aplikacji pozostał bez zmian.
