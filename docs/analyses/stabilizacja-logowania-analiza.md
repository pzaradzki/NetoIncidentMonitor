# Analiza stabilizacji logowania

> Dokument historyczny analizy/badań. Stan wdrożenia i końcowe dowody z 2 listopada: [raport odbioru](../verification/login-stabilization-verification.md). Poniższe ograniczenia dotyczą opisanej serii, nie zastępują aktualnej architektury.

1 listopada 2026. **Analiza i testy wykonane; aplikacja niezmieniona.** Nowy cel: ukryte logowanie automatyczne przy włączonym ukrywaniu, pokazanie/fokus tylko przy koniecznej ingerencji. [Plan etapów](../plans/completed/stabilizacja-logowania.md).

## Co rzeczywiście sprawdzono

**Kod:** `app.py: open_login_target/wait_for_login`, `AutomaticLogin`, `authentication.py`, `BrowserRuntime`, diagnostyka i testy. Zachowane zabezpieczenia: brak odczytu hasła do Python, ochrona ręcznego wpisywania, kontrola dostarczenia zatwierdzenia, ograniczone próby, identyfikacja popupu przez `opener`, dodatni znacznik sesji i bezpieczna diagnostyka. Nie należy ich usuwać podczas upraszczania.

**Rzeczywista strona w Codex:** ekran jednego zapamiętanego konta to `LI.identifier-first__account-item` z częścią nazwy i osobnym usuwaniem. Formularz hasła: pojedynczy widoczny, edytowalny `INPUT#password`, `autocomplete=current-password`, CSS `:-webkit-autofill=true`. Zatwierdzenie jest `A#signOnButton`, powrót `BUTTON#backButton`; nie znaleziono regionu `role=alert/aria-live`. Odczytano wyłącznie strukturę i booleany, nie wartości pól.

Użytkownik obsługiwał logowanie. Po zatwierdzeniu w tej karcie pojawiła się rzeczywista strona `/external_logout_complete.do`: komunikat „Logout successful”, bez pola hasła i dodatniego znacznika sesji. Automat aplikacji nie pracował w tej karcie — to nie był jego timeout 20/30 s. **Przyczyny zakończenia tego konkretnego SSO nie ustalono**: brak chronologii żądań/przekierowań. Nie wnioskujemy o błędnym haśle, wygaśnięciu challenge ani winie serwera wyłącznie z końcowego widoku. Nie ponawiano automatycznie logowania ani nie wywoływano błędnych prób.

**Natywne Chromium 153.0.8010.12:** osobny pusty profil i rzeczywista strona IdP; nie wpisywano danych ani nie wysyłano formularza. Badano pojedyncze pole identyfikatora typu `text`, nie rzeczywiste hasło. Dwie serie V→H→V→H, z 3 s ustalonego ukrycia:

| Próba gotowości, bez rzeczywistego kliknięcia | Wynik | Czas |
| --- | --- | --- |
| Widoczny, limit 500 ms | 12/12 poprawnych | 31–47 ms |
| Ukryty, limit 500 ms | 0/12 poprawnych | timeout 500–516 ms |
| Ukryty, pojedynczy limit 2500 ms | 2/2 poprawnych | 1047 i 2031 ms |

Pole pozostawało edytowalne. W krótkiej obserwacji klatek widoczny dokument osiągał 4 klatki, ukryty tylko 1 w około 750 ms. Bezpieczne flagi śladu potwierdziły oczekiwanie na gotowość „visible, enabled and stable”; nie wykazały nakładki, wyłączenia ani ukrycia elementu w DOM. To dowód problemu krótkiej kontroli gotowości, nie zgoda na zwiększenie limitów produkcyjnych ani gwarancja działania całego SSO. Brak odczytu obrazów i danych sieciowych. Tymczasowe okno/profil zamknięto.

## Wyniki testów lokalnych

- **77/77 istniejących testów**, 69,870 s: logowanie, ręczne przekazanie, autouzupełnienie, popupy, diagnostyka i widoczność (`data/login-stability-baseline-tests.log`).
- **10/10 reprodukcji aktualnego zachowania**, 10,025 s (`data/login-stability-audit-tests.log`). To potwierdzenie poniższych przypadków, nie dowód ich naprawienia.
- Dwa porównania po 8 scenariuszy na natywnym Chromium z lokalnymi formularzami syntetycznymi: bezpośrednio po ukryciu oraz po 3 s. W obu trybach wybór syntetycznego konta i zatwierdzenie następowały raz; ręczny wpis i syntetyczny MFA blokowały automat. Dla pustego hasła widoczny wariant osiągał limit oczekiwania na autofill, a ukryty nie — krótka próba gotowości nie pozwalała uruchomić zegara. Wynik nie odtwarza prawdziwego magazynu haseł Chromium; syntetyczne wypełnienie nie jest rzeczywistym autofill.

## Słabe punkty i priorytety

| ID | Ustalenie | Dowód i znaczenie |
| --- | --- | --- |
| L1 | Faza `login` zawsze pokazuje okno. | Kod i reprodukcja polityki; nowy cel wymaga zmiany `BrowserRuntime`, a nie samej opcji ukrywania. |
| L2 | `external_logout_complete.do` nie jest rozpoznanym stanem. | Rzeczywisty widok + reprodukcja: `authentication_required=False`, `authenticated_session=False`. Pętla może próbować ponownie otwierać cel co 5 s zamiast wyjaśnić wylogowanie. |
| L3 | Krótki `trial=True` może zatrzymywać postęp ukrytego logowania. | Rzeczywiste próby powyżej; syntetyczna reprodukcja zerowania `prefill_since`. Timer autofill nie powinien wymagać udanego fizycznego testu kliknięcia. |
| L4 | Stan procesu jest rozdzielony między kilka flag i warstw. | `manual_required`, `manual_shown`, `blocked`, `submitted`, `prefill_since` i guard interakcji mają różne znaczenia. Brak jednego kontraktu „proszę użytkownika” kontra „użytkownik przejął formularz”. |
| L5 | Globalne wyszukiwanie tekstu może błędnie wykrywać interwencję. | Syntetyczny zwykły tekst „invalid ticket number” poza formularzem blokuje automat. `body.inner_text` przenosi też zbędną treść do Python, mimo że nie trafia ona do logu. |
| L6 | Część przejść nadal jest sterowana zegarem. | Wybór konta: odstęp 5 s i do 3 kliknięć; pokazanie po 20 s; blokada 30 s po wysłaniu; ponowne otwieranie celu co 5 s; granica celu 180 s. Nie rozróżniają same w sobie postępu, bezczynności i potrzeby użytkownika. |
| L7 | Wybranie konta pełni też rolę potwierdzenia pochodzenia wypełnienia. | Przy `account_clicked=True` nie jest wymagany CSS autofill. Reprodukcja wysłała syntetycznie wypełniony formularz; ręczny wpis nadal chroni guard. To słabszy warunek, nie stwierdzony wyciek hasła. |
| L8 | Zakres zaufania i rozpoznawanie formularzy wymagają kontraktu. | Regex hosta IdP dopuszcza niestandardowy port; reprodukcja :444 została automatycznie zatwierdzona. Zwykły angielski przycisk bez znanego ID nie jest obsługiwany — aktualny rzeczywisty `A#signOnButton` jest. Nie rozszerzać selektorów przez zgadywanie. |
| L9 | Przebudowa formularza jest traktowana zachowawczo, bez rozróżnienia przyczyny. | Wymiana pustego pola w tym samym dokumencie powoduje przekazanie do użytkownika. To obecnie bezpieczne, lecz wymaga oddzielenia renderowania od nowej transakcji SSO; nie wolno bez dowodu resetować ochrony wysłania. |
| L10 | Dwa sygnały sesji mogą być sprzeczne. | Syntetyczne `g_user` w głównym dokumencie i hasło w ramce dają równocześnie `session_ready=True` i `authentication_required=True`. Pętla często wybiera bezpieczną gałąź, ale helpery nie mają jednoznacznego kontraktu. Sam `g_user` nie wystarcza do wszystkich decyzji. |

**Najpierw:** L2/L4 i spójny kontrakt obserwacji; następnie L3 oraz prywatność i wykonalność ukrycia; dopiero później zmiana polityki widoczności. Nie wystarczy usunąć `show_window` ani zamienić wszystkich timeoutów na większe.

## Granice wniosków

Nie wykonano prawdziwego automatycznego wysłania hasła w ukrytym natywnym Chromium, pomiaru MFA, błędnego hasła, wygasłego SAML ani długiej aktywnej sesji. Nie kopiowano profilu monitora, nie czytano magazynu haseł i nie wymuszano wylogowania. Nie badano jeszcze braku pojedynczego błysku okna podczas startu; `--start-minimized` i brak aktywnego okna nie są dowodem pełnego ukrycia. Nowy plan musi zamknąć te braki przed odbiorem.

Skrypty i wyniki techniczne są lokalnie w `data/`; nie dołączać ich, profilu ani logów do wydania. Odcisk źródeł przed/po pomiarach jest zgodny. Kod aplikacji, wersja, EXE i ustawienia nie były zmieniane.
