# Badania niezawodności ukrytego logowania

> Dokument historyczny analizy/badań. Stan wdrożenia i końcowe dowody z 2 listopada: [raport odbioru](../../weryfikacja/odbior-stabilizacji-logowania.md). Poniższe ograniczenia dotyczą opisanej serii, nie zastępują aktualnej architektury.

2 listopada 2026. **Badania trwają; nie ma odbioru B ani wdrożenia C–F.** Kontynuacja [planu](../../plany/zakonczone/stabilizacja-logowania.md). Kod aplikacji i środowisko `.venv` pozostają bez zmian. Skrypty i wyniki robocze są wyłącznie w ignorowanym `data/`.

## Potwierdzone obserwacje

| Próba | Wynik i ograniczenie |
| --- | --- |
| Aktualna karta konta w Codex | Jedno `LI`, nazwa i usuwanie jako osobne elementy. Brak semantyki klawiaturowej samego konta; nie zakładać działania Enter. |
| Wybór konta w natywnym profilu: karta startowa i nowa | 24/24 krótkich trial gotowych również po ukryciu; dokument raportuje widoczność/fokus. Nie wykonano wyboru konta ani wysłania. |
| Formularz hasła po ręcznym wyborze, pole/przycisk/body | Widoczne 12/12 (15–47 ms), ukryte 0/12 (500–516 ms). Natywnie okno ukryte; `document.visibilityState` nadal visible i hasFocus true, lecz RAF w 750 ms daje 0–1 zamiast 4. Prostokąty kontrolek nie zmieniły się. Prawdziwe autofill potwierdzone. |
| Syntetyczne warianty motywu i aktywacji | 48/48 trial; samo ukrycie nie odtwarza degradacji każdej strony. Syntetyczny sukces nie zastępuje rzeczywistego SSO. |
| Kolejność wyłączenia/włączenia emulacji fokusu | Udało się odtworzyć degradację RAF także syntetycznie. Samo późniejsze true ani nowa sesja CDP jej nie naprawiły. Nie utożsamiać stanu JS visible z działającym renderowaniem. |
| DWM cloak | API odmówiło ustanowienia cloak (HRESULT access denied); bit cloak pozostał zerowy. Widocznych prób opisanych roboczą nazwą cloaked NIE zaliczać jako ukrytych. |
| Warstwowe okno alpha=0 | Syntetycznie szybkie zwykłe zaufane kliknięcia, również w wariancie wyłączającym natywne wejście i próbującym window.focus. Zachowane oddzielne wyniki. Brak jeszcze odbioru prawdziwego autofill, popupów, startu i kompletnego przywracania; nie wdrażać tego na podstawie samej próbki. |

Lokalne źródła wyników: `login-target-session-study-results.json`, `login-password-pipeline-results.json`, `login-hidden-factors-results.json`, `login-focus-order-results.json`, `login-cloak-fixture-results.json`, `login-transparent-fixture-results.json`, `login-disabled-transparent-fixture-results.json`.

## Sprawdzony trop: wersja silnika nie wystarcza

Aplikacja używa Playwright 1.63.0 i Chromium 153.0.8010.12. W [kodzie tego Chromium](https://raw.githubusercontent.com/chromium/chromium/153.0.8010.12/content/browser/devtools/protocol/emulation_handler.cc) obsługa emulacji fokusu przy zmianie renderera różni się od [stabilnej wersji 156](https://raw.githubusercontent.com/chromium/chromium/156.0.8078.80/content/browser/devtools/protocol/emulation_handler.cc), która przenosi stan na nowy widget renderera. Była to **hipoteza przyczyny**; porównanie poniżej nie potwierdziło, że sama aktualizacja usuwa awarie. Diff nie stanowi dowodu przyczynowego. Zainstalowany Playwright włącza emulację domyślnie; [kontrola stabilności](https://github.com/microsoft/playwright/blob/main/packages/injected/src/injectedScript.ts) korzysta z kolejnych RAF.

Powstało odizolowane środowisko `data/login-engine-venv` z oficjalnym stabilnym Playwright 1.64.1 (PyPI), zalecającym Chromium 156.0.8078.4. Pobieranie silnika do `data/login-engine-browsers` nie zastępuje istniejącej przeglądarki ani profilu. Pobranie zalecanego Chromium zakończyło się pięcioma ECONNRESET; dodatkowa próba oficjalnego manifestu zakończyła się timeoutem. Nie wyłączano ochrony TLS. Do porównania użyto zainstalowanego Chrome 156.0.8078.76, zawsze z nowym tymczasowym profilem. Przygotowany profil 153 nie był migrowany ani kopiowany. Zwykły Chrome służy wyłącznie do badania, nie jest propozycją paczki wydania.

### Przejścia dokumentów i rzeczywiste akcje na fixture

Lokalnie przechwycone żądania, syntetyczny wybór konta → formularz → potwierdzenie. Zwykłe kliknięcia Playwright, maks. 1000 ms; bez force. Udane przejście miało dokładnie dwa syntetyczne POST, nieudane jedno; bez ponawiania wysłania. Widoczność natywna sprawdzana na każdym etapie.

| Playwright / silnik | Ukryte pełne przebiegi | Widoczne pełne przebiegi |
| --- | --- | --- |
| 1.63.0 / Chromium 153 | 2/3 | 3/3 |
| 1.63.0 / Chrome 156 | 2/3 | 3/3 |
| 1.64.1 / Chromium 153 | 8/10 | 10/10 |
| 1.64.1 / Chrome 156 | 8/10 | 10/10 |

To próby porównawcze, nie oszacowanie awaryjności użytkowników. **Żadna para wersji nie daje podstaw do wdrożenia ukrytej polityki.** Różnice brandu i polityk Chrome są dodatkowym ograniczeniem. Pierwsza wersja fixture używała przechwyconego HTTP 302 i nie dochodziła do kontrolek; została odrzucona. Wyniki w tabeli dotyczą poprawionych przejść JS i potwierdzonej kolejności czterech lokalnych celów. Pliki `data/login-engine-matrix-<playwright>-<engine>.json`.

## Granica bezpieczeństwa

Nie wysyłano prawdziwego formularza w tej serii badań. Prawdziwe dane i magazyny pozostają nieodczytane. Nie używano force, syntetycznego submit na rzeczywistym SSO, zrzutów formularza, zmian ochrony certyfikatów, headless ani przenoszenia okna poza monitory. Wynik trzeba jeszcze sprawdzić dla dostarczenia jednej akcji, Stop, ręcznego przejęcia, utraty strony/sieci i popupu. Pełnej bezawaryjności każdej przyszłej strony nie deklarować.


## Próba kandydatów na prawdziwym formularzu

`data/login-password-candidates-results.json`: zakończono 12 prób bez wysłania. Prawdziwy autofill dodatni. Zwykłe ukrycie, trial 500 ms: 0/2; jedna ciągła próba z limitem 3000 ms: 4/4, 1234–1781 ms. Całkowicie przezroczyste okno (alpha=0, wejście natywne wyłączone, NOACTIVATE/TOOLWINDOW): 2/2, 15–16 ms. Widoczne kontrolne 4/4, 16–47 ms. Wszystkie pomiary bez foreground. Nie jest to test jednego automatycznie dostarczonego prawdziwego logowania.

`data/login-alpha-lifecycle-results.json`: trzy osobne konteksty, po pięć syntetycznych przejść i przywróceń. 15/15, 63–141 ms, bez foreground; przywrócono zwykłe style i enabled=True. **Test popupu ujawnił brak domknięcia**: nowe okno było WS_VISIBLE, nieikonowe i bez alpha=0 przed wykonaniem callbacku Playwright. Dopiero callback stosował zabezpieczenia. Nie stwierdzono obrazu na ekranie pomiarem optycznym, ale taki stan nie pozwala zagwarantować braku odsłonięcia. Nie wdrażać alpha=0 jako rozwiązania pełnego ukrycia. Wynik `data/login-alpha-popup-results.json`.

## Kandydat wymagający świadomego rozszerzenia granicy renderowania

Dotychczasowy plan B i decyzja 007 wykluczają automatyczne przeniesienie screencastu na logowanie. Warianty bez obrazów zbadano; nie uzyskały pełnego odbioru. Osobno sprawdzono wyłącznie syntetyczny wariant `Page.startScreencast`, quality=0, maxWidth=1, maxHeight=1, everyNthFrame=60, ACK i natychmiastowe odrzucanie danych. To technicznie przetwarzanie obrazów, mimo braku czytelnego tekstu; nie opisywać jako rozwiązanie bez obrazów.

Pierwszy statyczny fixture zakończył 15/15 przejść, lecz nie wygenerował klatek — nie dowodził ich rozmiaru. Powtórka z animacją: trzy osobne konteksty, 15/15 zwykłych kliknięć/przejść, 78–110 ms; WS_VISIBLE=False przez akcje; 15 klatek łącznie, każda **1×1**, potwierdzone nagłówkami JPEG wyłącznie syntetycznych danych. Obrazy nie zostały zapisane. Wynik `data/login-synthetic-reduced-render-results.json`.

Użytkownik następnie wyraźnie dopuścił test na rzeczywistym SSO z odrzucaniem klatek w pamięci, bez dekodowania, zapisu, wyświetlania lub wysyłania do zewnętrznych usług. [Decyzja badawcza 009](../../decyzje/009-renderowanie-ukrytego-logowania.md); nie oznacza odbioru integracji ani pełnego B.

## Dwa rzeczywiste przebiegi po dopuszczeniu testu 1×1

Zachowany profil testowy, zwykły trial Playwright 500 ms na polu hasła i przycisku. Każde uruchomienie: trzy pary/serie widoczne → ukryte bez wsparcia → ukryte ze wsparciem. Łącznie 72 pomiary. Origin wsparcia ograniczony do zaobserwowanego HTTPS idpb2e.adeo.com:443, bez userinfo; nawigacja/zmiana zaufanego kontekstu, przejęcie użytkownika lub błąd ACK kończy próbę. Kod badawczy nie wysyłał formularza.

| Wariant | Przebieg 1 | Przebieg 2 | Mediana |
| --- | --- | --- | --- |
| Widoczny | 12/12 | 12/12 | 31 ms w obu |
| SW_HIDE bez wsparcia | 0/12 | 0/12 | timeout 500/507,5 ms |
| SW_HIDE + Page.startScreencast 1×1 | 12/12 | 12/12 | 31 ms w obu; zakres 0–47 ms |

Przy ukrytych pomiarach IsWindowVisible=False; prawdziwy CSS autofill dodatni. To dowód gotowości przy ustalonym ukryciu, nie samego wysłania, pełnego startu bez odsłonięcia ani fokusu (nie rejestrowano foreground w tej serii). Parametry 1×1 pozostawały stałe. Na statycznym prawdziwym formularzu **nie nadeszła żadna klatka** w tych krótkich oknach pomiaru; renderer był uruchomiony i zamknięty trzy razy w każdym przebiegu. Brak odebranych klatek nie gwarantuje, że nie powstaną przy innych zmianach/animacjach. Rozmiar zakodowanego obrazu potwierdzano wcześniej wyłącznie na syntetycznej animacji; na rzeczywistym SSO nie dekodowano danych.

Po drugim pomiarze najpierw wyłączono renderer, pokazano okno i użytkownik ręcznie dokończył logowanie. Obserwator aplikacji potwierdził session, a po 2 s ukrycia ponownie session. Profil zachowany, oba konteksty normalnie zamknięte. Wyniki: `data/login-real-reduced-render-da5e9bfc.json`, `data/login-real-reduced-render-53dda17f.json`.

### Sprzątanie wspólnego mechanizmu — osobne fixture natywne

`data/login-render-shared-lifecycle-results.json`: istniejący HiddenRendering na lokalnie przechwyconej stronie syntetycznej, z jawnym mockiem potwierdzonej sesji. 4/4 zakończone przypadki: zamknięcie guard (etykieta stop_requested), wyjście poza cel, zamknięcie karty, kontrolowana awaria ACK. Klient zakończony w każdym przypadku; błąd ACK ujawniony jako DashboardReadError, bez ponowienia. Przy nawigacji odnotowano jeden błąd sprzątania, przy zamknięciu karty dwa — nie maskowały wyniku. **To nie jest test przycisku Stop ani runtime logowania.** Tylko zachowanie wspólnego mechanizmu na fixture.

### Co nadal nie zostało odebrane

Nie ma jeszcze kompletnego B ani wdrożenia C–F. Kandydat rozwiązuje odtworzony problem gotowości; wymagane pozostają: integracja bez zmiany ochrony pojedynczego dostarczenia, pomiar Stop/żywych opcji, start i własne popupy, przypadki błędów oraz długie ukrycie. Automatycznego wysłania prawdziwego formularza w tej serii nie testowano; ręczny sukces go nie zastępuje. Kod aplikacji, .venv, EXE i wersja pozostają niezmienione. Te ograniczenia muszą wejść do odbioru wdrożenia, nie zniknąć w podsumowaniu sukcesu trial.
