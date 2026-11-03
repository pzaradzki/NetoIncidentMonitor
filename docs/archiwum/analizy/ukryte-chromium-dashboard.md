# Odczyt dashboardu przy stale ukrytym Chromium

Data: 1 listopada 2026, **17:03–17:25 Europe/Warsaw**, łącznie z ręcznym logowaniem. **Analiza i 32 próby zakończone, bez zmian kodu aplikacji.**

**Wniosek:** w obecnej implementacji nie można wyłączyć wymuszonego pokazywania Chromium dla całego dashboardu i zachować sprawności odczytu. Na ukrytym oknie działają liczniki zagrożeń, ale wszystkie 15 prób SLA/Wstrzymanych/Wniosków kończy się błędem gotowości kontrolek. To nie dowodzi fundamentalnej niemożliwości odczytu w tle; odrzuca prostą zmianę samej polityki widoczności przy obecnym czytniku. Nie wdrażać jej na podstawie tych wyników.

## Cel i metoda

Sprawdzić, czy można respektować opcję całkowitego ukrywania Chromium również podczas odczytu dashboardu, bez utraty poprawności lub szybkości. Logowanie ręczne pozostaje odrębnym przypadkiem wymagającym pokazania okna.

Test używa rzeczywistych czytników oraz `run_section`, dokładnie obecnych opcji `browser_launch_options()`, Chromium **153.0.8010.12** i osobnego tymczasowego profilu. Nie kopiuje profilu działającej aplikacji. Jedyna zmienna eksperymentu to widoczność testowego okna; nie dodano flag uruchomienia ani alternatywnego czytnika. Wariant widoczny przywraca nieminizowane okno bez wymuszania pierwszego planu, jak bieżąca polityka aplikacji. Wariant ukryty używa tego samego `BrowserWindow.hide()`, co aplikacja, i nie uruchamia `BrowserRuntime`, który obecnie wymuszałby pokazanie okna.

Plan: trzy serie widoczne i trzy ukryte w kolejności V–H–H–V–H–V, następnie ukrycie po minimalizacji i restart testowej przeglądarki z ponownym odczytem na ukrytym oknie. Każda seria obejmuje zagrożenia, SLA, Wstrzymane i Wnioski. Dodatkowo 65 s bezczynności przy ukryciu oraz odczyt innego miesiąca. Przywrócić pierwotny okres po teście.

Przyjęcie wyniku: kompletny zestaw właściwej sekcji i kontekstu, brak ręcznej interwencji, liczba prób oraz porównanie czasów poszczególnych etapów. Czasów prób zakończonych błędem nie traktujemy jako poprawnego pomiaru szybkości odczytu. Przy sukcesach orientacyjny próg praktycznej różnicy to większa z wartości 15% lub 2 s; trzy powtórzenia nie są dowodem statystycznej równoważności.

Widoczność Windows jest próbkowana podczas odczytu, oddzielnie od widoczności elementów DOM. Wyniki biznesowe pozostają wyłącznie w pamięci procesu; do pliku trafiają liczba gotowych kafelków, wynik, czasy, bezpieczne przyczyny i informacja o zgodności kolejnych zestawów. Odcisk źródeł przed i po teście sprawdza brak zmian aplikacji.

Lokalne artefakty, poza paczką i repozytorium: `data/hidden-dashboard-study/results.json`, `actionability.json`, `actionability-navigation.json`; skrypty pomocnicze w `data/`. Raport nie zawiera danych zgłoszeń, poświadczeń ani profilu.

## Potwierdzone mechanizmy

- Aplikacja obecnie wymusza pokazanie nieminizowanego okna w aktywnościach `login` i `dashboard`; ukrywanie działa dla `filters` (`browser_policy.py`). Analiza nie zmienia tej polityki.
- Playwright już domyślnie dodaje `--disable-background-timer-throttling`, `--disable-backgrounding-occluded-windows` i `--disable-renderer-backgrounding`. Potwierdzono je w zainstalowanym `coreBundle.js`; aplikacja nie wyłącza tych domyślnych argumentów. Dwie flagi dopisane w poprzednim teście integracyjnym pokrywały się więc z domyślnymi — sama ich obecność nie wyjaśnia różnicy wyników.
- Widoczność DOM nie jest widocznością natywnego okna. Playwright wymaga ponadto stabilności, włączenia i trafiania zdarzeń w element. Stabilność sprawdza na kolejnych klatkach animacji. [Oficjalna dokumentacja](https://playwright.dev/python/docs/actionability).
- Chromium może ograniczać renderowanie i JavaScript dla zasłoniętych/ukrytych stron, lecz to możliwość mechanizmu, nie ustalona przyczyna tego konkretnego błędu. [Dokumentacja Chromium](https://chromium.googlesource.com/chromium/src/+/master/docs/windows_native_window_occlusion_tracking.md), [opis timerów Chrome](https://developer.chrome.com/blog/timer-throttling-in-chrome-88).
- Syntetyczny przycisk na tej samej konfiguracji przechodzi test kliknięcia także na ukrytym oknie, zarówno bez nawigacji, jak i po pełnej nawigacji. Osiem klatek animacji powstaje w około 106–114 ms. Nie potwierdzono więc ogólnego zatrzymania `requestAnimationFrame` przez samo ukrycie w tym środowisku.

## Wyniki

Trzy podstawowe serie w każdym wariancie; czasy to mediany pełnych poprawnych odczytów, zaokrąglone do 0,01 s:

| Sekcja | Okno widoczne | Okno stale ukryte |
| --- | --- | --- |
| Zagrożenia | 3/3 poprawne, **6,56 s** | 3/3 poprawne, **6,45 s** |
| SLA | 3/3 poprawne, **17,52 s** | **0/3**, każdy błąd po około 60 s |
| Wstrzymane L1 | 3/3 poprawne, **4,66 s** | **0/3**, każdy błąd po około 60 s |
| Wnioski L1 | 3/3 poprawne, **11,20 s** | **0/3**, każdy błąd po około 60 s |

Wynik obejmuje pierwszy i ponowny odczyt, zmianę miesiąca, 65 s bezczynności na ukrytym oknie oraz odzyskanie poprawnego działania po pokazaniu tej samej przeglądarki. Dwie następujące po sobie ukryte serie i przerwa między nimi nie zawierały pokazywania okna.

Dodatkowe przypadki:

- **Ukrycie po minimalizacji:** zagrożenia 1/1 w 4,66 s; SLA, Wstrzymane i Wnioski 0/3, z tym samym błędem gotowości.
- **Restart procesu:** ServiceNow wymagał ponownego logowania. Po ręcznym zalogowaniu i ponownym ukryciu zagrożenia zakończyły się sukcesem; czas całej próby 143,41 s zawiera oczekiwanie na użytkownika, a aktywnego odczytu około 6,59 s. Nie jest to czysto ukryty pomiar porównawczy. Następne trzy sekcje były sprawdzane wyłącznie na ukrytym oknie i wszystkie zakończyły się tym samym błędem.

Łącznie: **17 sukcesów i 15 błędów**. Wszystkie 12 prób widocznych zakończyło się sukcesem. Wszystkie 15 prób zwykłego dashboardu na ukrytym oknie zakończyło się błędem po 60,11–60,16 s, mimo ograniczonego ponowienia. Cztery czysto ukryte odczyty zagrożeń zakończyły się sukcesem; piąty przeszedł po pokazaniu okna do ręcznego logowania i ponownym ukryciu.

W 19 próbach bez ręcznej interwencji na ukrytym oknie zebrano **1565 próbek natywnej widoczności Windows: 0 widocznych, 0 brakujących okien**. Oddzielnie 65 próbek podczas bezczynności również potwierdziło ukrycie. Pierwszy odczyt po restarcie ma 3 próbki widocznego okna w trakcie obsługi logowania; nie zaliczono go do czysto ukrytych prób.

**Miejsce awarii:** SLA — `set_period → click_control → ready_control` przy otwieraniu daty; Wstrzymane i Wnioski — `ensure_all_categories → click_control → ready_control`, przy zatwierdzaniu kategorii. Nie był to timeout pobierania samych liczb. Po ponownym pokazaniu tego samego okna poprawne odczyty wracały bez przebudowy czy zmiany źródeł.

**Zakończenie:** po wszystkich pomiarach okno testowe pokazano wyłącznie do przywrócenia pierwotnego miesiąca. Przywrócenie potwierdzono, przeglądarkę i tymczasowy profil zamknięto. Odcisk wszystkich modułów aplikacji i launchera przed/po teście jest identyczny; nie zmieniono wersji ani istniejącego diffu źródeł. Nie budowano EXE/ZIP ani nie publikowano.

## Granice diagnozy

Odczyt liczby i przygotowanie interaktywnego filtra to różne operacje. Poprawny odczyt zagrożeń ani test prostego przycisku nie dowodzi gotowości wszystkich kontrolek ServiceNow.

Obecne `ready_control` przechwytuje krótkie timeouty Playwright, a na końcu zgłasza ogólny błąd gotowości. Z logu można wskazać etap, ale nie rozstrzygnąć, czy zawiodła stabilność, pozycja w obszarze widocznym, overlay czy inny warunek interakcji. Wymagałoby to osobnego pomiaru stanów rzeczywistej kontrolki lub dopuszczonej w przyszłości diagnostyki stałymi kodami `readiness_facts`, bez zapisywania pełnego tekstu błędu/DOM. W tej analizie nie dopisano takiej poprawki do aplikacji.

Podobny czas odczytu zagrożeń nie uzasadnia rozszerzenia wniosku na cały dashboard. Dla pozostałych sekcji nie ma poprawnych ukrytych pomiarów, z których można byłoby wyliczyć równoważność wydajności. Brak dowodu na fundamentalną niemożliwość pełnego odczytu w tle nie jest dowodem, że proponowana zmiana będzie bezpieczna i równie szybka.

Pomiary rozpoczynają się po ręcznym zalogowaniu; nie są testem ukrytego formularza automatycznego logowania ani autouzupełniania. Nie testowano wielogodzinnej pracy, blokady Windows, RDP ani innych komputerów. Nie wnioskujemy o równej wydajności z prostych testów renderowania.

## Co należałoby zbadać przed ewentualną zmianą

1. Dla rzeczywistego przycisku daty i kategorii zebrać bezpieczne stany: widoczność dokumentu, włączenie elementu, prostokąt i pozycję w obszarze strony, przesłonięcie oraz stałą kategorię nieudanej próby kliknięcia. Bez HTML, etykiet zawierających dane osób i surowych błędów Playwright.
2. Porównać te same kontrolki w tej samej sesji tuż przed i po pokazaniu okna; ustalić rzeczywistą przyczynę zamiast zakładać throttling.
3. Dopiero potem zaprojektować i osobno przetestować obsługę ukrytą. Nie uznawać usunięcia sprawdzania gotowości czy wymuszonego kliknięcia za rozwiązanie bez weryfikacji skutku operacji.
4. Powtórzyć pełny odczyt z miesiącem i kategoriami, restart, długie ukrycie oraz zachowanie po utracie sesji. Warunek odbioru: kompletne poprawne wyniki bez dodatkowych timeoutów i bez istotnego wzrostu czasów.

Powyższe są propozycjami kolejnej pracy, nie wdrożeniem. Obecna analiza nie zmienia zachowania aplikacji.

Szczegółowa kolejność badań i kryteria odbioru: [plan znalezienia rozwiązania](../../plany/zakonczone/odczyt-dashboardu-w-ukrytym-chromium.md).
