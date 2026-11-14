# Wspólna sesja ServiceNow, jedna karta i kolejka operacji

**Status — zakończony 14 listopada 2026.** Użytkownik potwierdził pozytywny wynik pozostałych prób odbiorowych na Windows i rzeczywistym ServiceNow, w tym autologowania z zapisanym hasłem, odzyskania sesji z MFA i natywnej propozycji zapisu hasła w Chromium po ręcznym logowaniu ADEO.

**Ustalenie z 11 listopada 2026.** Chromium uruchamia się widoczne i pozostaje widoczne przez pierwsze logowanie. Przy włączonym autologowaniu aplikacja przeprowadza je w widocznym oknie. W razie wyłączonego autologowania, braku danych uzupełnionych przez Chromium albo potrzeby MFA użytkownik kończy logowanie w tym samym oknie. Po potwierdzeniu sesji aplikacja ukrywa Chromium i dopiero wtedy udostępnia główne okno zgodnie z preferencją startu zminimalizowanego. Kryterium braku mignięć obowiązuje od tego ukrycia.

**Uzupełnienie z 12 listopada 2026.** Jeśli przy włączonym autologowaniu użytkownik wpisał hasło ręcznie, po zalogowaniu wybiera **Zapisano** albo **Wyłącz autologowanie** przed ukryciem Chromium. Dotyczy to pierwszego logowania i odzyskiwania sesji. [Decyzja 026](../../decyzje/026-potwierdzenie-zapisu-poswiadczen.md).

Po każdym kroku zaktualizuj ten plik przed następnym krokiem. Zaznacz `[x]` po wykonaniu i sprawdzeniu. Zapisz wynik, a przy przerwanym kroku pozostaw `[ ]` i zapisz stan, przeszkodę oraz następną czynność. Etap zaznacz po ukończeniu wszystkich kroków. Po wznowieniu przeczytaj ostatnią notatkę i sprawdź bieżący diff.

- [x] **Stan wejściowy.** W źródłach usunięto otwieranie list z kafelków dashboardu i zagrożeń SLA. Zachowano animację najechania i strzałkę. Poprzednia regresja zakresowa objęła 61 zaliczonych testów.

- [x] **Etap 1. Zapis planu i potwierdzenie wykonalności**
  - [x] Zapisz plan, dodaj go do indeksu i odnotuj stan wejściowy. Zachowaj istniejące zmiany, w tym import Ulubionych.
    - 11 listopada 2026. `git status --short` pokazał istniejące zmiany kafelków, importu, listy filtrów i dokumentacji. Plan dodano obok nich, bez zmiany kodu aplikacji.
  - [x] Ustal regresję bazową. Sprawdź logowanie, harmonogram, ręczne odczyty, import i zamykanie z izolowanymi danymi. Zapisz wyniki i ograniczenia natywnych prób Windows i Chromium.
    - 11 listopada 2026. Regresja bazowa poza ograniczonym środowiskiem procesu, na izolowanych danych i lokalnych binariach Playwright, objęła 112 testów. Zaliczono 111, jeden pominięto z powodu niedostępnego tworzenia dowiązań symbolicznych, bez błędów. Obejmuje automat logowania, odzyskiwanie sekcji, autostart, harmonogram, ręczne aktualizacje, import i reset. W ograniczonym środowisku przechodzi zestaw 70 testów (jeden pominięty), a próby z Chromium i kluczem rejestru wymagały osobnego uruchomienia. Lokalny raport bazowy to `build/session-regression/verified-baseline.json`.
  - [x] Sprawdź na rzeczywistym ServiceNow w przeglądarce Codex cel SOW, dodatni dowód sesji, przekierowania i zachowanie MFA oraz ewentualne okna SSO. Użyj odrębnego profilu. Logowanie ręczne wykonuje użytkownik.
    - 12 listopada 2026. Osobna karta Codex przeszła od dostawcy logowania ADEO do strony głównej SOW. Po zalogowaniu istniała jedna karta i jeden nagłówek z jednym widocznym awatarem oraz jednym menu użytkownika. Sprawdzono hierarchię otwartego Shadow DOM. Wprowadzono strukturalny dowód sesji wyłącznie dla głównego dokumentu pod znaną ścieżką SOW. Zaliczone 14 testów obserwacji, w tym syntetyczne doładowanie nagłówka. W tej próbie nie odtworzono osobno przebiegu MFA ani otwierania okna SSO. Wynik późniejszego odbioru użytkownika zapisano w etapie 5.
  - [x] Ustal bazową widoczność i fokus Chromium od zimnego startu na Windows.
    - W czterech izolowanych próbach z syntetyczną stroną okno było widoczne przed zwróceniem kontekstu Playwright. Rozpiętość widocznych próbek wyniosła 140–203 ms w każdej próbie, a w trzech z czterech prób Chromium zostało oknem pierwszoplanowym. Przycisku Eksploratora nie mierzono bezpośrednio. Po konfiguracji runtime nie zaobserwowano widoczności ani fokusu. Pomiar wykonano lokalnym skryptem `build/session-regression/cold_probe.py` na odrębnym profilu. Uzgodniony widoczny start usuwa dotychczasową blokadę. Weryfikacja ukrywania po potwierdzeniu sesji należy do odbioru w etapie 5.

- [x] **Etap 2. Logowanie i cykl życia wspólnej sesji**
  - [x] Zachowaj blokadę pojedynczej instancji, wznowienie resetu i walidację danych przed Chromium. Wczytaj preferencje logowania przed głównym widokiem, zachowując domyślną wartość autologowania. Obsłuż start bez filtra.
    - Walidacja i reset nadal wyprzedzają utworzenie `App`. Test natywnego startu użył pustej konfiguracji i potwierdził ukrycie Chromium przed odsłonięciem Tk.
  - [x] Przenieś własność Playwright, profilu i jednej karty do wątku sesji aplikacji. Tk przekazuje polecenia i odbiera zdarzenia kolejką. Start i Stop sterują odczytami cyklicznymi. Zamknięcie anuluje pracę, zwalnia profil i przechodzi do istniejącej procedury zamknięcia lub resetu.
    - Test Tk z syntetycznym kontekstem potwierdził pojedyncze uruchomienie, tę samą kartę i ten sam wątek przy czterech rodzajach pracy oraz zamknięcie kontekstu. Regresja integracyjna objęła 67 testów, 66 zaliczono, a jeden pominięto z powodu braku uprawnień do dowiązań symbolicznych.
  - [x] Ogranicz regułę jednej karty do Chromium obsługiwanego przez aplikację. Jawne akcje **Otwórz w SNOW** i otwieranie zgłoszeń kieruj do domyślnej przeglądarki użytkownika, zgodnie z [decyzją o kafelkach](../../decyzje/024-kafelki-informacyjne.md).
    - Sprawdzono wejścia otwierające stronę przez domyślną przeglądarkę. Odczyt pustej listy i podgląd importu na ServiceNow użyły dokładnie jednej karty roboczej.
  - [x] Uruchom Chromium jako widoczne okno i pozostaw je widoczne do potwierdzenia pierwszej sesji.
    - Próba na rzeczywistym ServiceNow potwierdziła widoczne okno i przejście przez ekran ADEO w odrębnym profilu. Nawigacja logowania dopuszcza konkretny cel SOW bez stosowania walidatora adresów list.
  - [x] Potwierdź aktywną sesję istniejącym mechanizmem. Gdy potrzebne jest logowanie, użyj obecnego automatu w widocznym oknie albo przekaż obsługę użytkownikowi, jeśli autologowanie jest wyłączone lub potrzebna jest interwencja.
    - Potwierdzono ręczne logowanie i sesję na rzeczywistym SOW oraz zaliczono 14 testów obserwacji. Autologowanie z zapisanym hasłem i MFA objęto późniejszym odbiorem użytkownika.
  - [x] Zachowaj sygnał ręcznego wpisania hasła przez przekierowania i okna logowania.
    - Testy Chromium na syntetycznym formularzu potwierdziły przekazanie sygnału przez nawigację i z okna SSO do karty głównej. Zdarzenie programowe i pole kodu jednorazowego zostały pominięte. Do aplikacji trafia wyłącznie informacja o ręcznym wpisaniu hasła.
  - [x] Po potwierdzeniu sesji pokaż komunikat przy włączonym autologowaniu. Utrzymaj Chromium widoczne do wyboru **Zapisano** lub **Wyłącz autologowanie**. Zapisz zmianę preferencji przed wznowieniem pracy.
    - Na Windows próba z Tk i Chromium potwierdziła blokadę startu i wstrzymanie odczytów do wyboru po ponownym logowaniu. Obie akcje ukryły Chromium. Błąd zapisu preferencji pozostawił komunikat otwarty, a ponowienie zapisało zmianę.
  - [x] Sprawdź na syntetycznym logowaniu pierwszy start, odzyskanie sesji, obsługę obu przycisków i zakończenie pracy podczas oczekiwania.
    - Zaliczone 126 z 127 testów w osobnych procesach z izolowanymi danymi. Pominięta próba pasywnego pokazywania okna nie otrzymała fokusu od Windows. Potwierdzono też pominięcie komunikatu przy wyłączonym autologowaniu, anulowanie oczekiwania przy zamknięciu i korelację wyniku z logowaniem bez danych formularza. Raport `build/session-regression/password-save.json`.
  - [x] Wyśrodkuj komunikat zapisu poświadczeń i przekaż mu fokus po wyświetleniu przy starcie oraz odzyskiwaniu sesji.
    - Test z rzeczywistymi oknami Windows i syntetycznym logowaniem potwierdził położenie komunikatu, okno pierwszoplanowe i fokus Tk w obu przebiegach. Chromium pozostało widoczne do wyboru, a wynik aktywacji zapisano w diagnostyce logowania.
  - [x] Po potwierdzeniu sesji ukryj Chromium, a następnie udostępnij główne okno z uwzględnieniem preferencji startu zminimalizowanego.
    - Po rzeczywistym logowaniu natywna kontrola potwierdziła ukryte Chromium przed uruchomieniem odczytów. Oba zlecenia użyły jednej karty, bez ponownego uruchamiania procesu.
  - [x] Przekaż fokus głównemu oknu po pierwszym logowaniu przy starcie w trybie widocznym.
    - Na Windows z syntetyczną sesją SOW przed poprawką okno Tk było widoczne, ale okno pierwszoplanowe należało do innej aplikacji. Po poprawce potwierdzono ukrycie Chromium, własność pierwszoplanowego okna i fokus klawiatury w Tk. Test objął też pominięcie aktywacji przy starcie zminimalizowanym i ponownym potwierdzeniu sesji. Zaliczone 28 testów. Jedną próbę pasywnego pokazania Chromium pominięto, ponieważ Windows nie przyznał fokusu jej oknu początkowemu.
    - Późniejsza poprawka potwierdza fokus klawiatury po aktywacji i przekazuje go także po odzyskaniu sesji wymagającym pierwszoplanowego okna logowania. Test z natywnymi oknami i syntetycznym logowaniem objął start oraz powrót z komunikatu zapisu poświadczeń. Sprawdzono też start zminimalizowany i odzyskanie sesji w tle.
  - [x] Rozdziel aktywację, fokus klawiatury i odsłonięcie głównego okna. Sprawdź także przywracanie z paska zadań.
    - Bazowy test startu na Windows przeszedł. W próbie z zasłaniającym oknem „zawsze na wierzchu” Windows i Tk potwierdzały fokus mimo zasłonięcia monitora. Po poprawce osobna próba potwierdziła odsłonięcie po logowaniu, cofnięcie podniesienia po utracie aktywności i odsłonięcie po natywnym przywróceniu.
    - Odbiór został przerwany po utracie 38 plików. Po odtworzeniu źródeł z 14 oryginalnych poprawek zaliczono 9/9 testów obejmujących natywne odsłonięcie i przywrócenie, ukrycie Chromium, komunikat poświadczeń oraz diagnostykę.
    - 12 listopada 2026 użytkownik potwierdził ręczny test przywrócenia okna jednym kliknięciem na pasku zadań. [Plan i wyniki odzyskania](odzyskanie-zmian-po-v1.10.0.md).
  - [x] Uruchamiaj monitoring po zalogowaniu, gdy jest włączona opcja **Uruchom monitoring przy starcie aplikacji** i jest co najmniej jeden włączony filtr. Zachowaj kolejność pierwszego cyklu **dashboard → zagrożenia → filtry**. Uwzględnij dashboard w tym cyklu, gdy włączono jego automatyczne odświeżanie. Przy zatrzymanym monitoringu ręczne odczyty działają zgodnie z etapem 3. [Kolejność odczytów](../../decyzje/018-kolejnosc-aktualizacji.md).
    - Test Tk sprawdził blokadę autostartu przed sesją, ustawienie włączone i wyłączone oraz brak aktywnego filtra. Zaliczył też pierwszy cykl, Stop i kolejny odczyt ręczny na tej samej karcie.
  - [x] Przy awarii startu Chromium albo niedostępności ServiceNow pokaż małe okno z akcjami **Spróbuj ponownie** i **Zamknij**.
    - Komunikat i działanie zamknięcia potwierdzono podczas pierwszej próby z błędem nawigacji. Następnie poprawiono nawigację do SOW i potwierdzono rzeczywiste logowanie.
  - [x] Po pierwszym logowaniu utrzymuj Chromium ukryte podczas bezczynności, odczytów i importu. Wycofaj przełączniki widoczności i minimalizacji Chromium. Starsza konfiguracja wczytuje się bez migracji. Automatyczne odzyskiwanie sesji przebiega w tle. Gdy potrzebna jest interwencja użytkownika, pokaż Chromium i udostępnij akcję **Pokaż okno logowania**. Po potwierdzeniu sesji ponownie ukryj okno przed wznowieniem pracy.
    - Potwierdzono natywne ukrycie w teście oraz w odczycie i imporcie na rzeczywistym ServiceNow. Regresja ukrytego logowania obejmuje przejście do ręcznej interwencji na stronach syntetycznych.
  - [x] Zachowaj `BrowserRuntime`, `HiddenRendering` i zabezpieczenia logowania. Używaj ukrytego renderowania w dotychczasowych zakresach pracy w tle. Sprzątaj zakres renderowania przy zmianie operacji, anulowaniu, błędzie i zamknięciu.
    - Przeszły testy ukrytego renderowania. Rzeczywista próba potwierdziła zakończenie zakresu renderowania SOW i przywrócenie viewportu po imporcie.
  - [x] Sprawdzaj sesję przed operacjami i reaguj na jej utratę w trakcie. Wznawiaj ważne żądania po potwierdzeniu sesji w ich dotychczasowym budżecie.
    - Przeszły testy odzyskiwania sesji i budżetów sekcji. Filtr przenosi pozostały budżet do następnego odczytu. Import zachowuje oddzielny budżet odczytu.
  - [x] Po awarii procesu Chromium zastosuj ograniczony automatyczny restart, jeśli w próbie na Windows można go wykonać bez mignięcia i przejęcia fokusu. Jeśli próba tego nie potwierdzi, wstrzymaj odczyty i pokaż w głównym oknie akcję **Połącz ponownie**. Ta akcja rozpoczyna widoczne ponowne połączenie. Po potwierdzeniu sesji ukryj Chromium i wznów nadal ważne żądania.
    - Bazowe próby uruchamiania wykazały widoczność i możliwe przejęcie fokusu, więc zastosowano **Połącz ponownie**. Test awarii potwierdził, że kolejny start jest możliwy dopiero po jawnej akcji.
  - [x] Rejestruj w istniejącej diagnostyce przyczynę pokazania Chromium i wynik ponownego ukrycia. Powiąż te zdarzenia z próbą logowania i bieżącą operacją.
    - Próby rzeczywiste potwierdziły zdarzenia widocznego uruchomienia oraz ukrycia po zalogowaniu. Nowe pola diagnostyczne są ograniczone listą dozwolonych wartości.

- [x] **Etap 3. Wspólne wykonanie odczytów, kolejka i harmonogram**
  - [x] Wydziel wykonanie dashboardu, zagrożeń i pojedynczego filtra na przekazanej karcie. Współdziel czytniki cyklu i odczytu ręcznego. Zachowaj walidację, budżety, kontekst okresu, historię, cache i zasady powiadomień.
    - Wydzielono odczyt pojedynczego filtra, a dashboard i zagrożenia przyjmują jawne żądanie oraz sygnał anulowania. Regresja dotychczasowego wykonania zaliczyła 31 testów harmonogramu, odzyskiwania sesji i transakcji filtrów. Podłączenie nowych wejść do tych samych metod jest następnym krokiem.
  - [x] Podłącz **Aktualizuj filtr**, **Aktualizuj dashboard**, **Aktualizuj zagrożenia** i **Sprawdź teraz** do wspólnej kolejki, również przy zatrzymanym monitoringu. Utrwal ID i zakres. Blokuj okres dashboardu do pasującego końca. Sprawdzaj aktualność filtra i wymagaj włączenia przy odczycie cyklicznym lub zbiorczym. Odrzucaj spóźnione wyniki zakończonych lub anulowanych żądań.
    - Test Tk potwierdził ręczny pełny odczyt z wyłączonym cyklem oraz porządek sekcji. Zakres filtra identyfikuje URL i rewizja, a dashboard zachowuje wybrany okres i dotychczasową walidację ID.
  - [x] Dopuść ręczny odczyt pojedynczego filtra wyłączonego z harmonogramu.
    - Test Tk potwierdził aktywny przycisk, wykonanie zlecenia, wynik w tabeli i historii, brak filtra w harmonogramie i pełnej aktualizacji oraz oznaczenie wyniku w diagnostyce. Zaliczone 48 testów zakresowych.
  - [x] Sprawdzaj rozmiar klasycznej listy przed odczytem i ustaw 100 wierszy, gdy metadane wskazują inną wartość.
    - Inspekcja Codex potwierdziła `rows_per_page` i opcję menu we wszystkich czterech typach list. Zaliczone 58 testów zakresowych, w tym zmiana z 20 do 100 przed zebraniem rekordów, pominięcie menu przy 100, odczyt z potwierdzonym rozmiarem po nieudanej zmianie oraz odrzucenie zmienionego zapytania.
  - [x] Potwierdź działanie rzeczywistego menu w ukrytym Chromium.
    - 12 listopada 2026 na pustej liście INC w osobnym profilu. Odczyt przy początkowych 100 wierszach pominął menu. Po ręcznym ustawieniu 20 w sondzie czytnik sam przestawił listę na 100, potwierdził rozmiar i ukończył odczyt w 2,0 s. Użył jednej karty, a Chromium było ukryte we wszystkich 17 próbkach tej próby. Wielostronicowy odczyt 205 rekordów zweryfikowano na danych syntetycznych.
  - [x] Wykonuj ręczne zlecenia w kolejności przyjęcia. Scalaj duplikaty tego samego zakresu i kontekstu. **Sprawdź teraz** zajmuje własne miejsce i przejmuje objęte oczekujące aktualizacje z zachowaniem kolejności pozostałych zleceń. Bieżący odczyt kończy się normalnie. Zalicza się jego poprawny zgodny wynik, a reszta biegnie w kolejności **dashboard → zagrożenia → włączone filtry**.
    - Test kolejki potwierdził scalenie dashboardu i zagrożeń, zachowanie pozycji importu oraz wykorzystanie udanego trwającego odczytu filtra.
  - [x] Zachowaj `Schedule` jako źródło terminów i użyj jednego koordynatora. Sprawdzaj terminy po dashboardzie, imporcie i między filtrami. Zaległe zagrożenia poprzedzają samodzielne zlecenie, chyba że wykona je najbliższa pełna aktualizacja. Ręczne i okresowe zagrożenia ustawiają ten sam termin 60 s od końca próby. Po opóźnieniu wykonaj jeden zaległy odczyt zakresu. Po ręcznym zleceniu dopuść jeden zaległy filtr cykliczny przed następnym samodzielnym zleceniem.
    - Testy z kontrolowanym zegarem potwierdziły pierwszeństwo zagrożeń, dopuszczenie filtra cyklicznego oraz brak natychmiastowej powtórki po pełnej aktualizacji.
  - [x] Rozdziel stany sesji, monitoringu i zleceń. Pokaż oczekiwanie, wykonanie i scalenie. Podczas ponownego logowania pokaż stan sesji obok czasu ostatniego udanego odczytu. Zachowaj ten czas do następnego udanego odczytu.
    - Stan sesji i czas udanego odczytu są niezależne. Regresja stanu dashboardu, historii i aktualizacji przeszła na izolowanych danych.
  - [x] Blokuj przyciski ręcznego odczytu na czas zlecenia odpowiadającego ich zakresowi.
    - Test Tk sprawdził osobne kliknięcia, scalenie przez **Sprawdź teraz**, zmianę wybranego filtra oraz odblokowanie po wyniku poprawnym i błędzie. Zaliczone 72 testy zakresowe.
  - [x] Stop anuluje cykl, a ręczne zlecenia przypisane do przerwanego odczytu cyklicznego pozostają w kolejce. Zamknięcie kończy oba rodzaje pracy.
    - Test przerwał odczyt cykliczny i potwierdził wykonanie identycznego oczekującego odczytu ręcznego. Zamykanie budzi i kończy wątek sesji.
  - [x] Zapisuj przyjęcie, scalenie, start, oczekiwanie na logowanie, wynik i czas przez bezpieczną diagnostykę z identyfikatorami operacji.
    - Test zapisu kolejki potwierdził zachowanie ID przy scaleniu i brak syntetycznego sekretu z adresu filtra. Regresja diagnostyki objęła awarię zapisu.

- [x] **Etap 4. Import Ulubionych w kolejce**
  - [x] Przenieś import na wspólną kartę i kolejkę. Przyjmuj go przy aktywnym i zatrzymanym monitoringu. Dopuść jeden import do zamknięcia podglądu. Pełna aktualizacja pozostawia import w kolejce.
    - Test Tk potwierdził ponowne użycie karty bez osobnego startu Chromium, a test kolejki potwierdził zachowanie importu po scaleniu odczytów.
  - [x] Zachowaj tymczasowy rozmiar tylko podczas czytania menu. Przywróć go przed logowaniem i przed zwolnieniem karty, również po błędzie i anulowaniu. Sprawdź menu w ukryciu na ServiceNow i użyj `HiddenRendering`, jeśli jest potrzebny.
    - W pierwszej próbie rzeczywistej import zakończył się błędem. Zweryfikowano selektory i przywrócono pierwotny stan menu w przeglądarce Codex. Po podłączeniu renderowania wyłącznie dla zalogowanej strony głównej SOW, próba rzeczywista zwróciła 36 pozycji. Diagnostyka potwierdziła rozpoczęcie renderowania, zmianę rozmiaru, odczyt, przywrócenie rozmiaru i zakończenie renderowania.
  - [x] Po odczycie zwolnij kartę i pokaż podgląd w Tk. Przy zapisie ponownie sprawdź konfigurację i duplikaty. Zapisz zatwierdzone filtry jedną operacją jako wyłączone i bez aktywnych powiadomień. Anulowanie kończy tylko import, a zamknięcie podglądu nie zapisuje filtrów.
    - Potwierdzono rzeczywisty podgląd bez zapisu i zaliczono dotychczasowe testy zatwierdzania, odrzucania zmian konfiguracji oraz izolacji importu. Zakres przeglądarki kończy się przed publikacją wyniku.
  - [x] Wyśrodkuj okno importu przed jego pokazaniem.
    - Test Tk na Windows potwierdził pozycję na środku ekranu przy głównym oknie ustawionym w rogu. Zaliczone 39 testów importu i wspólnej sesji.

- [x] **Etap 5. Odbiór i dokumentacja**
  - [x] Sprawdź automatycznie aktywną sesję, autologowanie, ręczne logowanie, anulowanie, awarię i restart Chromium oraz utratę sesji podczas odczytów i importu. Zweryfikuj zachowanie poprawnych danych i czasu ostatniego udanego odczytu, brak podwójnego zapisu i odrzucanie spóźnionych zdarzeń.
    - 12 listopada 2026. Pełna regresja wraz z ponownym uruchomieniem poprawionych modułów objęła 570 testów w 76 modułach. Przeszło 568, pominięto 2 z powodu braku dostępnego fokusu okna testowego i tworzenia dowiązań symbolicznych. Brak niezaliczonych modułów po powtórce. Testy wspólnej sesji objęły też natywne ukrycie Chromium przed udostępnieniem Tk.
  - [x] Sprawdź autostart z opcją włączoną i wyłączoną oraz z wyłączonym automatycznym odświeżaniem dashboardu. Potwierdź, że **Otwórz w SNOW** i otwieranie zgłoszeń korzystają z domyślnej przeglądarki i pozostawiają kartę roboczą do odczytów.
    - Zaliczone próby warunków autostartu, kolejności odczytów i otwierania w domyślnej przeglądarce.
  - [x] Ustaw domyślnie wyłączoną aktualizację dashboardu przy starcie monitoringu.
    - Test startu objął brak zapisanej preferencji i obie jawnie zapisane wartości. Zaliczone 20 testów kolejności odczytów i wspólnej sesji.
  - [x] Sprawdź z kontrolowanym zegarem sekwencję **filtr → dashboard → zagrożenia → Sprawdź teraz**, duplikaty, import między aktualizacjami, zaległe terminy, Stop i odczyty przy zatrzymanym monitoringu. Sprawdź bezpieczne pola logów i odporność na awarię ich zapisu.
    - Testy potwierdziły kolejność i scalenie, anulowanie cyklu bez utraty ręcznego odczytu oraz import przy włączonym i zatrzymanym cyklu.
  - [x] Odbierz na Windows widoczny zimny start z aktywną sesją, autologowaniem i ręcznym logowaniem. Potwierdź ukrycie Chromium przed udostępnieniem głównego okna. Następnie sprawdź jedną kartę, ponowne użycie sesji oraz brak mignięć i nieplanowanego przejęcia fokusu w sekwencji **Start → Stop → ręczny odczyt → import → ponowny Start** oraz podczas automatycznego odzyskiwania sesji. Po awarii sprawdź ukryty restart albo ścieżkę **Połącz ponownie**, zgodnie z wynikiem próby restartu. Osobno sprawdź celowe pokazanie przy MFA, ponowne ukrycie po sukcesie i odpowiadające im wpisy diagnostyczne. Zapisz osobno wyniki rzeczywistego ServiceNow i regresji lokalnej.
    - 14 listopada 2026. Użytkownik potwierdził zaliczenie pozostałych prób odbiorowych.
  - [x] Potwierdź pojawienie się natywnego komunikatu zapisu poświadczeń w Chromium po ręcznym logowaniu ADEO przy włączonym autologowaniu. Użytkownik sam zapisuje poświadczenia w odrębnym profilu.
    - Okno aplikacji i jego wpływ na widoczność Chromium zweryfikowano na syntetycznym logowaniu. Natywną propozycję zapisu w ADEO potwierdził użytkownik w odbiorze 14 listopada 2026.
    - Próba rzeczywista: zaliczone ręczne logowanie, przejście do SOW i ukrycie przed pierwszą pracą. Po przywróceniu istniejącej migracji z JSON do SQLite poprawnie zapisano stan pustej listy w świeżym profilu. Import po włączeniu renderowania SOW zwrócił podgląd 36 pozycji. Obie operacje korzystały z tej samej karty i Chromium było ukryte. Nie zapisywano zaimportowanych filtrów. Warianty autologowania i odzyskania sesji z MFA potwierdził później użytkownik.
  - [x] Zaktualizuj architekturę, instrukcję i decyzje o sesji, kolejce oraz imporcie. Powiąż zastąpione decyzje z nową.
    - Zaktualizowano instrukcję i architekturę. Decyzja 025 dokumentuje wspólną sesję i zastępuje zasady osobnego importu z 022 oraz osobnej karty z 023.
  - [x] Po pełnym odbiorze przenieś plan do zakończonych i popraw indeks. Przebudowa EXE i publikacja wymagają odrębnego zlecenia.
    - Wydanie 1.10.0 zbudowano i opublikowano na odrębne zlecenie. Wyniki buildu i publikacji opisuje [raport wydania](wydanie-1.10.0.md). Po potwierdzeniu pozostałych prób przez użytkownika zamknięto plan i zaktualizowano indeks.

### Regresja odczytu dashboardu zgłoszona podczas odbioru

- [x] Ustal miejsce błędu i odtwórz zachowanie kontrolek ServiceNow.
  - Logi z 12 listopada 2026 wskazały `category_select` dla `assigned` (SLA) i `agent` (Wstrzymane L1 oraz Wnioski L1). W przeglądarce Codex wszystkie trzy kontrolki w stanie `aria-checked="mixed"` po pierwszym kliknięciu przeszły do pustego wyboru, a po drugim do pełnego. Próbę wykonano na osobnej karcie bez zatwierdzania filtrów.
- [x] Sprawdź obsługę częściowego wyboru oraz regresję czytników na izolowanych danych.
  - Czytnik rozpoznaje stan pośredni, czeka na jego opuszczenie i dopiero przy pustym wyborze zaznacza całość. Testy objęły opóźnioną wymianę kontrolki, korelację diagnostyki oraz brak drugiego kliknięcia i zatwierdzenia przy niepotwierdzonej zmianie. Zaliczone 98 testów zakresowych w 10 modułach.
- [x] Potwierdź odczyt wszystkich trzech sekcji w aplikacji z ukrytym Chromium na rzeczywistym ServiceNow.
  - 12 listopada 2026, po ręcznym logowaniu w odrębnym profilu. SLA, Wstrzymane L1 i Wnioski L1 odczytano w pierwszej próbie, a aplikacja przyjęła komplet wyników (`dashboard_complete`). Diagnostyka we wszystkich trzech sekcjach potwierdziła przejście z częściowego do pustego wyboru. Przed odczytem i po nim okno Chromium było ukryte. Aplikacja pracowała na jednej karcie.
