# Badanie rozwiązania odczytu na ukrytym oknie

1 listopada 2026. **Etapy badawcze A–C zakończone. Rekomendacja: kontrolowane wdrożenie w osobnym etapie D. Wyłącznie skrypty eksperymentalne — bez zmian aplikacji.**

## Potwierdzony mechanizm blokady

Na aktualnej stronie kontrolka daty jest `DIV[role=button]` wewnątrz `PAR-FILTER-PILL-VARIANT`; `Zastosuj` jest natywnym przyciskiem w `NOW-BUTTON-BARE`. Potwierdzono to w Codex, a pomiary wykonano w osobnym Chromium uruchomionym jak aplikacja.

Po świeżej nawigacji przy ukryciu przyciski mają stałą geometrię, są włączone i znajdują się w obszarze strony. Dokument zgłasza `visibility=visible` i fokus (Playwright domyślnie emuluje fokus). Mimo tego liczba klatek animacji spada z 4 w około 40–65 ms do 0–2 w około 750 ms. Krótkie próby kliknięcia zatrzymują się na oczekiwaniu gotowości; ślad nie wskazuje odłączenia elementu, wyłączenia ani przechwycenia zdarzeń przez nakładkę.

Przy trzech świeżych ukrytych kontrolkach próby 500 ms zawiodły. Pojedyncza próba do 4 s przechodziła po około 1,36–1,84 s. Pokazanie tego samego okna przywracało cztery klatki i gotowość w 47–63 ms. To wyjaśnia, dlaczego ponawianie krótkiej kontroli od początku może wyczerpać budżet mimo obecności elementu. [Playwright potwierdza stabilność na kolejnych klatkach](https://playwright.dev/python/docs/actionability).

Sam prosty test syntetyczny nie odtwarzał ograniczenia klatek występującego w pełnym ServiceNow. Przejścia świeża nawigacja/ustalone ukrycie są ważniejsze od próby wykonanej natychmiast po schowaniu okna.

## Porównane warianty

| Wariant, ukryte okno | Data | Status — Zastosuj | Agent L1 — Zastosuj |
| --- | --- | --- | --- |
| Bez zmiany | Timeout 500 ms | Timeout 500 ms | Timeout 500 ms |
| Ponowne ustawienie emulacji fokusu | Timeout | Timeout | Timeout |
| Cykl życia strony `active` | Timeout | Timeout | Timeout |
| Podtrzymanie renderowania przez DevTools | Sukces 78 ms | Sukces 109 ms | Sukces 78 ms |
| Wariant z rzadszym przekazywaniem ramek | Sukces 109 ms | Sukces 62 ms | Sukces 63 ms |

Prototyp korzysta z lokalnego `Page.startScreencast`: maksymalnie **1 × 1 piksel**, JPEG z minimalną jakością, przekazywanie co 60. klatki. Odebrane dane są natychmiast potwierdzane; nie są dekodowane, oglądane, zapisywane ani wysyłane na zewnątrz. Zliczane są wyłącznie ramki i rozmiar transmisji lokalnej. To mechanizm utrzymania renderowania przy fizycznie ukrytym oknie, nie alternatywny parser ani wymuszone kliknięcie. Fokus i widoczność Windows są mierzone osobno.

Parametry i polecenia pochodzą z [oficjalnej definicji DevTools](https://raw.githubusercontent.com/ChromeDevTools/devtools-protocol/master/pdl/domains/Page.pdl). Jest to API eksperymentalne, wymagające sprawdzania obsługi i bezpiecznego zakończenia przy utracie sesji lub zamknięciu strony. Prototyp wyłącza mechanizm przy nawigacji głównego dokumentu poza ServiceNow. Odbiór musi również uwzględnić koszt CPU; brak widocznego okna nie oznacza braku renderowania.

## Pilot pełnego czytnika

Oryginalne funkcje odczytu, budżety, zwykłe kliknięcia i timeout 500 ms pozostają bez zmian. Skrypt eksperymentalny jedynie zarządza widocznością i sesją DevTools.

| Sekcja | Widoczny przed | Ukryty z prototypem | Widoczny po |
| --- | --- | --- | --- |
| Zagrożenia | 6,45 s | 6,14 s | 5,50 s |
| SLA/WJRUW | 15,67 s | 16,23 s | 16,77 s |
| Wstrzymane L1 | 4,63 s | 4,72 s | 4,89 s |
| Wnioski L1 | 11,50 s | 5,53 s | 4,97 s |
| Cały cykl | 38,31 s | 32,67 s | 33,16 s |

**12/12 odczytów poprawnych**, bez ponowień. Ukryty cykl nie miał żadnej próbki pokazania okna. Różnice Wniosków między kolejnymi próbami pokazują, że pojedynczy pilot nie wystarcza do oceny szybkości — odbiór C porównuje serie i czasy etapów.

## Odbiór C: wyniki głównej serii

Chromium 153.0.8010.12, ten sam komputer i sposób uruchomienia co aplikacja; osobny tymczasowy profil. Naprzemiennie wykonano 5 pełnych cykli widocznych i 5 ukrytych, w dwóch uruchomieniach przeglądarki, dla pierwotnego i poprzedniego miesiąca. Logowanie odbywało się przed pomiarem. Pełna seria nie korzystała z poprawki pól wyboru opisanej niżej.

| Sekcja | Mediana widoczny / ukryty | Maksimum widoczny / ukryty |
| --- | --- | --- |
| Zagrożenia | 6,17 / 6,00 s | 6,84 / 7,05 s |
| SLA/WJRUW | 16,78 / 15,52 s | 17,67 / 17,47 s |
| Wstrzymane L1 | 4,64 / 4,74 s | 4,99 / 4,92 s |
| Wnioski L1 | 11,73 / 5,20 s | 11,88 / 11,13 s |
| Cały cykl | 39,83 / 32,75 s | 41,03 / 37,59 s |

**40/40 odczytów poprawnych, zero ponowień i przekazań do logowania w mierzonych odczytach.** Każda sekcja i cały cykl spełniły próg: ukryty nie wolniejszy o więcej niż większa z wartości 15% lub 2 s. W 606 próbkach aktywnego ukrytego odczytu nie wykryto pokazania okna ani przejęcia fokusu. Pomiar próbkowany nie wyklucza zdarzenia krótszego od interwału próbkowania.

Różnicy Wniosków nie należy interpretować jako gwarantowanego przyspieszenia: widoczny wariant cztery razy użył ścieżki `document_fallback`, ukryty raz; pozostałe próby potwierdziły odświeżenie bez tej ścieżki. Zmienność strony i cache wpływa na czas. Kryterium to brak istotnego spowolnienia, nie obietnica przewagi wariantu ukrytego.

Dodatkowy cykl po minimalizacji i ukryciu: **4/4 poprawne odczyty**, 37,59 s łącznie, bez ponowień, pokazania okna i przejęcia fokusu (122 próbki). SLA zajęło w nim 19,52 s, czyli dłużej niż maksimum głównej serii. Ten pojedynczy przypadek nie zmienia porównania median; pokazuje, że czasy nadal są zmienne.

Przy domykaniu testów omyłkowo wystartowała dodatkowa seria restartująca przeglądarkę. Po ręcznym logowaniu jej bezpośrednie oczekiwanie na kontrolkę daty zakończyło się timeoutem; kolejna próba nie spełniła warunku wejścia mechanizmu — uwierzytelniony dashboard. Nie były to odczyty zaliczone do 40/40. Jawna nawigacja do właściwego dashboardu naprawiła przygotowanie testu, po czym wykonano opisany cykl po minimalizacji. Zachowano oba błędy w wynikach. Wniosek: sama obecność zalogowanej sesji nie potwierdza gotowości docelowego dashboardu; wdrożenie musi korzystać z istniejącego potwierdzania kontekstu i obsługi nawigacji.

### Długie ukrycie i zasoby

Okno pozostawało ukryte przez **609,66 s**, z 600 próbkami natywnej widoczności — wszystkie niewidoczne. Następny pełny odczyt wszystkich czterech sekcji oraz kolejny cykl widoczny przeszły. W bezczynności mechanizm nie przekazał żadnych ramek; przybliżony przyrost CPU własnych procesów Chromium wyniósł 5,88 s przez cały ten okres.

Mediana sumy przyrostów CPU na cykl wyniosła około 45,22 s dla widocznego i 38,88 s dla ukrytego. To czas procesora sumowany po procesach, nie procent obciążenia ani zużycie energii. Metoda pomija procesy zakończone pomiędzy próbkami; krótsza ścieżka odświeżania Wniosków także wpływa na wynik. Nie zastępuje to wielogodzinnego profilowania na innych komputerach.

### Odzyskiwanie i dodatkowy wyścig pól wyboru

- Rzeczywista strona: przywrócenie „Wybierz wszystko” i odczyt SLA oraz Wniosków; anulowanie aktywnego odczytu przez Stop w 141 ms.
- Strona syntetyczna bez poświadczeń: komplet zer każdej z czterech sekcji (WJRUW nie jest obliczany bez mianownika), zatrzymanie mechanizmu przed zewnętrznym logowaniem i przed stroną logowania ServiceNow, zamknięcie celu oraz bezpieczne sprzątanie. Dwa oczekiwane błędy sprzątania zamkniętego celu zostały przechwycone.
- 6 testów pomocniczego mechanizmu i 5 istniejących testów odzyskiwania sekcji przeszło. Nie jest to test nowego EXE ani całego procesu logowania na rzeczywistym koncie po wygaśnięciu sesji.

Pierwsza próba przywracania kategorii Wniosków ujawniła niezależny problem: `Locator.check` zgłasza brak zmiany, chociaż następująca zaraz po nim obserwacja potwierdza zaznaczenie. W dodatkowych 12 próbach stresowych wystąpiły 2 takie błędy — oba przy **widocznym** oknie. Ten problem nie wynika z ukrywania.

Prototyp obserwacyjnego potwierdzenia przechodzi 12/12 prób; w dwóch przypadkach potwierdził spóźniony stan **bez ponownego kliknięcia**. Przechwytuje wyłącznie dokładnie rozpoznany błąd braku zmiany po `check`, potwierdza stan w pozostałym budżecie do 500 ms i nadal respektuje Stop. Test syntetyczny z opóźnieniem 250 ms odtwarza błąd, potwierdza naprawienie jednym kliknięciem i wykazuje, że rzeczywisty brak zaznaczenia nadal kończy się błędem. Dopiero z tym prototypowym potwierdzeniem ponowiono przypadek przywrócenia kategorii Wniosków z sukcesem. Początkowy błąd zachowano w wynikach.

**Ta poprawka istnieje tylko w skrypcie eksperymentalnym**, jako podmiana `Locator.check` w pamięci w wybranych testach odporności. Przy wdrożeniu należy przenieść samą zasadę potwierdzania do wspólnej obsługi kategorii, bez globalnej podmiany Playwright i bez dodatkowego kliknięcia.

## Rekomendacja i granice wdrożenia

**Jest podstawa do wdrożenia wariantu podtrzymania renderowania jako kontrolowanej zmiany**, wraz z osobnym potwierdzaniem spóźnionego stanu pól wyboru. Dotychczasowe testy nie uzasadniają już twierdzenia, że pokazanie okna jest zawsze konieczne. Nie gwarantują jednak identycznej szybkości na każdym komputerze, przyszłej wersji Chromium ani zmienionym dashboardzie.

Etap D powinien obejmować:

1. Jeden właściciel sesji DevTools w istniejącym workerze, mechanizm wyłącznie na uwierzytelnionym dashboardzie, sprzątanie przy Stop, zamknięciu i nawigacji do logowania. Sprawdzanie dostępności eksperymentalnego API oraz bezpieczna reakcja na jego awarię; brak cichego uznawania odczytu za poprawny.
2. Respektowanie opcji ukrywania, ręcznego „Pokaż przeglądarkę” i zmian ustawień; zachowanie pokazania i fokusu przy ręcznym logowaniu. Tych zmian polityki prototyp nie wdraża.
3. Diagnostykę start/koniec/przyczyna zatrzymania/czas/błędy ACK bez obrazów i danych biznesowych; ograniczone koszty oraz dotychczasowy wspólny budżet odzyskiwania.
4. Regresje integracji i ponowną serię na rzeczywistej stronie, a następnie osobno zlecony build i test EXE.

Po zakończeniu przywrócono pierwotny miesiąc i zamknięto testowe okno wraz z tymczasowym profilem. Odciski źródeł sprzed i po badaniu są identyczne. Aplikacja, wersja i istniejący EXE pozostają bez zmian. Surowe techniczne wyniki są wyłącznie lokalnie w `data/hidden-control-lab/results.json`; nie dołączać ich do wydania. [Plan i kryteria odbioru](../../plany/zakonczone/odczyt-dashboardu-w-ukrytym-chromium.md).
