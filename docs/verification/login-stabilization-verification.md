# Odbiór stabilizacji logowania A–F

> Raport dotyczy wskazanej w nim serii źródeł i pomiarów. Późniejszy lokalny build EXE 1.8.0 opisano [osobno](../releases/v1.8.0.md); nie zastępuje on prób rzeczywistego SSO.

2 listopada 2026. Źródła **1.7.17**, bez przebudowy EXE, zmiany wersji, commita, push lub publikacji. Końcowy zestaw testów jest rozliczany poniżej; nie jest to certyfikacja dowolnej przyszłej strony SSO.

## Zakres wdrożenia

Wspólna obserwacja sesji i popupów, automat akcji z ledgerem dostarczenia, rozdzielenie potrzebnej pomocy od własności formularza, prawdziwy sygnał autofill, ukryte renderowanie 009, widoczność/fokus i ograniczone odzyskiwanie. Kod nie pobiera pierwszego filtra do potwierdzenia sesji. Nie powiela workera ani harmonogramu.

Auto+hide pozostaje ukryte podczas bezpiecznej fazy automatycznej. Auto off, rozpoznane MFA/ingerencja, nieznany wymagający obsługi formularz lub awaria renderowania oddają widoczne okno użytkownikowi. Sam wybór konta pozwala potem kontynuować przy potwierdzonym autofill; pisanie/wklejenie/Enter lub ręczne wysłanie blokuje automat do potwierdzenia sesji. Zwykła edycja dashboardu i ukryte formularze przekierowania SAML nie przejmują własności logowania.

Wysłanie dostarczone lub niepewne jest zachowywane przez przekierowanie, podmianę DOM i zmianę opcji. Bezpieczny GET przy logout/sieci/braku postępu nie nadpisuje ręcznej ani nierozstrzygniętej próby. Stop zwalnia renderer i obserwatory. Zajęty profil/permanentna awaria startu mają ograniczone istniejące odzyskiwanie, bez usuwania danych.

## Regresja końcowych źródeł

**388 testów: 387 zaliczonych, 1 pominięty; 0 błędów i porażek.** Regresja wykonana w dwóch częściach. Pierwsza ma 332 zakończone przypadki: 331 OK i 1 pominięty. Po omyłkowym przerwaniu procesu dokładnie pozostałe 56 ID przeszło w 48,861 s, bez zmiany źródeł. Automatyczne rozliczenie potwierdziło identyczny odcisk źródeł i pokrycie wszystkich 388 ID bez braków/powtórzeń; `data/login-stabilization-final-summary.json`.

Pominięcie dotyczy pasywnego przywracania fokusu: Windows nie przyznał fokusowi testowej aplikacji warunków wiarygodnego pomiaru. Nie pominięto ochrony ręcznego wpisywania ani wysyłania. Natywne testy ukrytego pipeline/Stop/opcji wykonały się.

Runner laboratoryjny izoluje katalog diagnostyki i finalizuje cykle Tk na głównym wątku. Wcześniejszy pełny przebieg miał błąd finalizacji `Tcl_AsyncDelete`; nie ukryto go zmianą produkcyjnej polityki GC ani wyłączeniem asercji. Poprzedni poprawny zestaw 378 testów nie zastępuje końcowych 388. Ukierunkowane 59 testów ostatniej zmiany guardów również przeszło.

Lokalne dowody (ignorowany `data/`, nie do wydania): `login-stabilization-verified-full-tests.log`, `login-final-prefix-status.json`, `login-stabilization-remaining-tests.log`, `login-stabilization-remaining-summary.json`. Odcisk 54 plików aplikacji (launcher i moduły): **542b21e02c3f9017c9ffe16e99d0b16f11a8e32bb42fea1812daa24f350df48b**. Algorytm: SHA256 sumy kolejnych posortowanych względnych ścieżek POSIX + NUL + bajty pliku + NUL; indywidualne sumy w `login-stabilization-source-manifest.json`.

## Próby rzeczywiste a syntetyczne

| Próba | Wynik i granice |
| --- | --- |
| Aktualny IdP w Codex | Potwierdzone konto LI, osobne usuwanie, password/current-password, CSS autofill oraz A#signOnButton. Wyłącznie struktura i booleany; użytkownik obsługiwał poświadczenia. |
| Prawdziwa gotowość w natywnym Chromium | Dwa uruchomienia po trzy serie: widoczne 24/24, ukryte zwykłe 0/24, ukryte wspierane 24/24; mediana obu sprawnych 31 ms. To porównanie gotowości, nie czasu całego SSO. Statyczny realny formularz nie dostarczył klatek w krótkich seriach; ich 1×1 potwierdzono wcześniej wyłącznie na syntetycznej animacji. |
| Pełne automatyczne konto → prawdziwy autofill → zatwierdzenie → sesja | 14,2 s; jedno wybranie konta i jedno zatwierdzenie. Wykryto krótkie błędne żądanie pokazania po zmianie originu między snapshotem a krokiem. Poprawione z testem braku ponownego POST; tej próby nie oznaczamy jako bezbłędnego ukrytego pełnego cyklu końcowego kodu. |
| Końcowa rzeczywista zachowana sesja | 2,8 s, session_ready=True, ukrycie przed celem i po sukcesie, 0 próbek widoczności/foreground, renderer zakończony. Bez wysyłania formularza. Cache SSO nie jest kolejnym świeżym logowaniem. |
| Natywny syntetyczny pipeline | Przejścia dokumentów konto → hasło → sesja, dokładnie jeden POST wyboru i jeden POST hasła, ukrycie i sprzątanie. Autofill jawnie mockowany; nie nazywamy go prawdziwym zapisanym hasłem. |
| 10 minut ukrycia | 600,2 s, 2244 próbki: brak WS_VISIBLE/foreground; 599 klatek/599 ACK. Potem coordinator kończy z jednym syntetycznym POST i wyłączonym rendererem. Dotyczy technicznego oczekiwania na syntetycznym komponencie, nie prawdziwego 10-minutowego MFA. Odcisk wcześniejszej wersji w lokalnym wyniku; późniejsze zmiany dotyczyły m.in. własności, widoczności i diagnostyki, więc nie jest to 10 min całego końcowego kodu. |
| Stop/żywe ustawienia | Natywne testy: brak wysłania po Stop, wyłączony renderer, auto off pokazuje, po pisaniu auto on nie przejmuje formularza. Osobny końcowy pomiar oczekiwania: **0,312 s**, 0 POST, okno ukryte, renderer zakończony (`login-final-stop-measurement.json`). Nie jest gwarancją dla zawieszonego renderera. |
| Wyjątki i ochrona danych | Syntetyczne MFA/CAPTCHA/alerty, nieznany origin, wiele kont, błędy sieci/TLS, podmiany DOM, niepewny POST, logout, obce/nested popupy, zamknięcie/restart i błędy diagnostyki. Brak celowych błędnych haseł, kasowania cookies lub blokowania rzeczywistego konta. |

Realne wyniki lokalne: `login-live-integrated-first-success-results.json`, `login-live-integrated-results.json`; soak: `login-stabilization-soak-results.json`. [Szczegółowe wcześniejsze pomiary](../analyses/logowanie-ukryte-chromium-badania.md).

## Diagnostyka i ograniczenia

- Run/trace/read/action i generacja; bezpieczne stany, powody, próby, dostarczenie, czasy, widoczność i foreground. Zmiany oraz okresowe podsumowania zamiast każdego poll. Logowanie dopisuje i rotuje; login-diagnostics: 2 MB + 3 archiwa.
- Allowlista działa przed zapisem. Nie eksportujemy wartości loginu/hasła, cookies, tokenów, pełnych adresów SSO, DOM ani payloadów klatek auth. Testy syntetycznych sekretów obejmują wyjątki/callbacki, rotację i stderr.
- Awaria handlera: jedno stałe ostrzeżenie, brak surowego rekordu/wyjątku, ponowna próba IO po 30 s i komunikat przywrócenia. W czasie niedostępności rekordy mogą zostać utracone; brak zapisu nie zatrzymuje logowania.
- Eksperymentalne DevTools może zmienić zachowanie po aktualizacji Chromium. Nie ma twardej gwarancji braku pojedynczego mignięcia ikony przed utworzeniem pierwszego HWND; pomiary dotyczą własnego rozpoznanego okna. Windows może odmówić przyznania fokusu.
- Nie przetestowano na rzeczywistym koncie wszystkich wariantów MFA, systemowego WebAuthn, błędnego hasła, blokady, usuwania cookies/hasła ani rzeczywistego wygaśnięcia po długim monitoringu. Mają strukturalne testy i zachowawczy fallback, nie deklarację pełnego pokrycia realnego serwisu.
- Przy następnym naturalnym wygaśnięciu sesji powtórzyć pełny świeży cykl końcowego kodu. Nowy EXE i jego test wymagają osobnego zlecenia. Profil testowy zachowany; nie zawiera go repozytorium ani pakiet.
