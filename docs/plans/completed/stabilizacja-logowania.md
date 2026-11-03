# Stabilizacja logowania i ukrytego SSO

> Zakończony plan i historia wdrożenia, nie bieżąca lista zadań. Aktualny status, lokalny build 1.8.0 i pozostałe sprawdzenia: [indeks planów](../README.md). Zapisy o braku EXE dotyczą ówczesnego etapu.

Plan z 1 listopada; stan wdrożenia: 2 listopada 2026. **A–F zakończone w źródłach, z jawnymi granicami weryfikacji rzeczywistego SSO. Bez EXE, zmiany wersji, commita i publikacji.** Użytkownik zlecił całość jednym ciągiem; pomoc potrzebna tylko dla rzeczywistej ingerencji użytkownika.

Podstawa: [audyt L1–L10](../../analyses/stabilizacja-logowania-analiza.md), [badania B](../../analyses/logowanie-ukryte-chromium-badania.md), [architektura](../../architecture.md), decyzje [004](../../decisions/004-bezpieczna-diagnostyka.md), [008](../../decisions/008-obserwacja-logowania.md), [009](../../decisions/009-renderowanie-ukrytego-logowania.md). Wyniki i ograniczenia: [raport odbioru](../../verification/login-stabilization-verification.md). Historyczne checkpoints zastępuje to podsumowanie; dowody badawcze pozostają w analizach.

## Kontrakt użytkownika

- Auto+hide: automatyczna faza ukryta; pokazanie/fokus tylko przy potrzebie człowieka lub jawnym „Pokaż”. Auto off: widoczne ręczne logowanie. Minimalizacja nie jest pełnym ukryciem.
- Wiele profili oznacza wiele kont SSO. Użytkownik wybiera; potem prawdziwy autofill może wznowić automat. Wpisywanie/wklejanie, ręczne wysłanie i MFA oddają formularz użytkownikowi.
- Monitoring pozostaje aktywny podczas oczekiwania/bezpiecznego odzyskiwania. Dostarczonego, niepewnego lub odrzuconego hasła nie wysyłamy ponownie. Nie odtwarzamy starego URL SSO. Stop kończy oczekiwanie; zamknięte Chromium ma dotychczasowy ograniczony restart.
- Nie odczytujemy poświadczeń, magazynu haseł, cookies, treści odpowiedzi ani pełnych URL SSO. Bez resetowania profilu, obchodzenia MFA/TLS, nowych workerów lub przenoszenia okna poza ekran. Renderowanie 1×1 ma świadomą zgodę i granice 009.

## Etapy i wynik

| Etap | Wdrożenie i kryterium | Stan |
| --- | --- | --- |
| A — obserwacja | Jeden kontrakt authentication/logout/unknown/target/session; konflikty ramek i własnych popupów wykluczają sesję. Run/trace/read/action, generacja, przyczyny i bezpieczny zapis/rotacja. | Wdrożone; inspekcja aktualnego IdP i testy strukturalne/diagnostyczne. |
| B — ukryta gotowość | Zbadano wariant bez obrazów, nowszy silnik, alpha=0 i ograniczone renderowanie. Wybrano 009 po 24/24 prawdziwych ukrytych trial kontra 0/24 bez wsparcia. | Wdrożone; natywny pipeline i 10-minutowa próba syntetyczna. Ograniczenia pierwszego HWND i pełnego SSO opisane w raporcie. |
| C — akcje i własność | Osobne potrzebna pomoc/własność/wysłanie; epoka komponentu, potwierdzony autofill, ponowna kontrola przed akcją, ledger dostarczenia i retry tylko po udowodnionym braku akcji. | Wdrożone; wybór wielu kont, późny autofill, ręczne wpisywanie/Enter, podmiana DOM i niepewny POST pokryte testami. |
| D — odzyskiwanie | Dodatnia sesja bez collect; bezpieczny GET przy logout/sieci/braku postępu; backoff 5/15/60/300 s. Własne popupy, zamknięcie, DNS/TLS, Stop; niepewny POST nie jest ponawiany. | Wdrożone; błędy i wygasanie symulowane, rzeczywisty sukces oraz zachowana sesja sprawdzone oddzielnie. |
| E — runtime/UI | Wspólna polityka auto/hide/minimize/override, renderer kończy się przed pokazaniem manual, ograniczone próby przywrócenia okna i brak ponownego odbierania fokusu po pokazaniu. | Wdrożone; macierz preferencji, natywne opcje/Stop i sprzątanie. Fokus zależy także od uprawnień Windows. |
| F — odbiór | Pełna regresja, testy braku sekretów i awarii zapisu, raport rozdzielający realny IdP od fixture, aktualizacja architektury/decyzji/planu. | Zakończone: 388 testów, 387 OK / 1 skip; natywny Stop 0,312 s. Wyniki realne i ograniczenia w raporcie. Build osobno. |

## Macierz wyjątków i zakres dowodów

| Sytuacja | Ochrona i sposób weryfikacji |
| --- | --- |
| MFA/kod/push/CAPTCHA/zmiana hasła/zgoda | Rozpoznane struktury → widoczna obsługa użytkownika; obce/systemowe okna nie są automatyzowane. Standardowe kontrolki i alerty testowane syntetycznie; nie udajemy rzeczywistej próby każdego dostawcy. |
| DNS/VPN/offline/5xx przed logowaniem | Klasyfikacja i odroczony GET, stan oczekiwania zamiast zakończenia; testy z kontrolowanymi błędami. |
| Sieć/DOM/redirect po zatwierdzeniu | Zachowany ledger, brak kolejnego POST i brak pochopnego pokazania po samej zmianie originu; testy wyścigów i niepewnego wyniku. |
| TLS/proxy/odrzucenie hasła/blokada konta | Bez obejścia i automatycznego powtarzania hasła, przekazanie użytkownikowi. Wyłącznie syntetyczne błędy; bez celowego blokowania rzeczywistego konta. |
| Usunięte cookies/hasło, pusty profil, zablokowany menedżer | Stan strony rozstrzyga: aktywna sesja wystarcza; pusty gotowy formularz ma 5 s na autofill, potem pomoc. Nie czytamy magazynu ani nie wnioskujemy o jego zawartości; strukturalne fixture. |
| Zmiany danych/opcji podczas logowania | Nowy dokument/formularz sprawdzany ponownie, wysłanie nigdy nie jest zerowane zmianą preferencji. Testy opcji i podmiany DOM. |
| Wiele kont/ręczny wybór/autofill | Wąskie przekazanie wyboru; bez zgadywania tożsamości i kliknięcia usunięcia. Fixture wielu kont; realne jedno konto i prawdziwy autofill sprawdzone osobno. |
| Zamknięcie popupu/Chromium, awaria lub zajęty profil | Własność przez opener, świeża sesja zamiast starej ramki, ograniczony restart; bez kasowania danych. Testy zamknięcia, budżetu restartu i klasyfikacji błędów startu. |
| Logout/wygasły SAML/nowy nieznany ekran | Osobne stany; bezpieczne odzyskiwanie lub widoczne oczekiwanie do Stop. Nie przypisujemy przyczyny historycznemu realnemu logout bez dowodu. |
| Błąd diagnostyki/rotacji | Funkcja trwa; brak surowej treści/sekretów także na stderr, jedno ostrzeżenie i odroczona próba IO. Testy rzeczywistego handlera i syntetycznych sekretów. |

## Granice czasu

Zegary są zabezpieczeniami: poll 100 ms, trial i właściwe kliknięcie po maks. 500 ms, 5 s na autofill gotowego pustego pola, najwyżej 3 udowodnione niedostarczone próby. Po 30 s bez rozstrzygnięcia wysłania wymagamy pomocy; po 180 s bez postępu nie udajemy sukcesu. Żaden termin nie jest dowodem braku zapisanego hasła ani pozwoleniem na kolejny POST. Przywrócenie manualnego okna: najwyżej 3 próby co 2 s. Stop jest kooperacyjny, nie gwarantuje twardego limitu przy zawieszonym procesie renderera.

## Profil i następne działania

Osobny, przygotowany przez użytkownika profil `%LOCALAPPDATA%/NetoIncidentMonitorTests/login-stability/browser-profile` zachowany i zamknięty po próbach. Nie uruchamiać dwóch instancji jednocześnie, nie kopiować i nie odczytywać plików poświadczeń/cookies, nie dołączać do wydania. Skrypty i wyniki lokalne pozostają w ignorowanym `data/`.

Po odbiorze źródeł: osobno zlecony build/test EXE. Przy następnym naturalnym wygaśnięciu sesji warto ponowić pełny świeży przebieg końcowego kodu; cache SSO nie zastępuje takiej próby. Nie wymuszać złych haseł, wylogowania, MFA lub czyszczenia profilu tylko dla statystyki. Nowa wersja Chromium/IdP albo nowy ekran wymaga ponownej inspekcji i regresji. Nie ma gwarancji niezawodności dla dowolnej przyszłej zmiany serwisu.
