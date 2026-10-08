# Powiadomienia ServiceNow Monitor w Microsoft Teams

Instrukcja dla użytkownika, który chce otrzymywać alerty wyłącznie na swój
prywatny czat z botem „Przepływy pracy”. Każdy użytkownik tworzy własny
przepływ i konfiguruje własny webhook w aplikacji.

Przebieg: ServiceNow Monitor wykrywa nowe incydenty → wywołuje webhook →
przepływ wysyła wiadomość na Teams → Teams może powiadomić na telefonie.

## 1. Przygotowanie

Potrzebujesz firmowego konta Microsoft 365 z dostępem do Teams i możliwości
tworzenia przepływów. Administrator może ograniczyć te funkcje. Jeśli aplikacja
lub wskazane opcje są zablokowane, zgłoś to IT.

Na komputerze uruchom Microsoft Teams i zaloguj się kontem, na które mają
przychodzić alerty. W naszej aplikacji nie podajesz hasła Microsoft 365.

## 2. Otwórz Przepływy pracy

1. W Teams przejdź do **Aplikacje**.
2. Wyszukaj **Przepływy pracy** lub **Workflows**.
3. Wybierz aplikację wydawcy **Microsoft Corporation**.
4. Kliknij **Dodaj** lub **Otwórz**.
5. Przejdź do **Strona główna**.
6. Kliknij **Utwórz od podstaw**.

Nie wybieraj szablonu „Wysyłaj alerty elementu webhook na czat”, jeśli prosi
o istniejący czat grupowy. W tej instrukcji tworzymy prywatną wiadomość od bota.

Jeśli widzisz uproszczony ekran „Rozpoczyna się, gdy”, rozwiń
**Wybierz, co to uruchamia**, a następnie kliknij
**Twórz w usłudze Power Automate, aby zobaczyć więcej wyzwalaczy**.

Alternatywnie otwórz [Power Automate](https://make.powerautomate.com/) w przeglądarce
i zaloguj się firmowym kontem. Utwórz nowy automatyczny przepływ w chmurze;
jeśli początkowe okno nie znajduje wyzwalacza, użyj **Pomiń**, aby dodać go
w edytorze. Nazwy i rozmieszczenie opcji mogą różnić się między wersjami edytora.

## 3. Dodaj wyzwalacz webhook

1. Nazwij przepływ **Alerty ServiceNow**.
2. W edytorze wybierz zakładkę **Wyzwalacze**, jeśli zaznaczone są **Akcje**.
3. W wyszukiwarce wpisz **webhook**.
4. Wybierz **Po odebraniu żądania skierowanego do elementu webhook aplikacji Teams**.
   Angielska nazwa to **When a Teams webhook request is received**.
5. Jeśli nie widzisz tej pozycji, wyszukaj łącznik webhook aplikacji Microsoft
   Teams i rozwiń jego wyzwalacze. Nie zastępuj go ogólnym wyzwalaczem HTTP.
6. W polu **Who can trigger the flow?** wybierz **Anyone**.

Ta aplikacja wysyła żądania przy użyciu sekretu w adresie webhooka. Nie obsługuje
logowania OAuth do Microsoft 365, którego wymagają opcje
„Any user in my tenant” i „Specific users in my tenant”. Jeśli firma nie pozwala
na „Anyone”, obecna integracja wymaga uzgodnienia innego sposobu uwierzytelnienia z IT.

**Anyone nie zmienia odbiorcy wiadomości.** Odbiorcę ustawisz w następnym kroku.
Osoba posiadająca pełny adres będzie jednak mogła uruchomić ten przepływ.
Traktuj adres jak hasło i nie publikuj go w instrukcjach ani na zrzutach.

Pole **Adres URL żądania HTTP POST** na razie informuje, że adres zostanie
wygenerowany po zapisaniu. To prawidłowe.

## 4. Dodaj wysyłanie wiadomości do siebie

1. Kliknij **+ Nowy krok** lub znak **+** pod wyzwalaczem.
2. Wyszukaj **Microsoft Teams**.
3. Wybierz akcję **Opublikuj wiadomość na czacie lub w kanale**
   (*Post message in a chat or channel*).
4. Jeśli edytor prosi o połączenie z Teams, zaloguj się własnym kontem firmowym.
5. Ustaw pola zgodnie z tabelą:

| Pole | Wartość |
| --- | --- |
| Opublikuj jako / Post as | Bot przepływu / Flow bot |
| Opublikuj w / Post in | Czatuj z botem przepływu / Chat with Flow bot |
| Recipient / Odbiorca | Twój firmowy adres e-mail; wybierz swoje konto z podpowiedzi |
| Komunikat / Message | Wyrażenie opisane w punkcie 5 |
| IsAlert | Pozostaw bez zmian |
| FeedbackLoopEnabled | Pozostaw bez zmian |

Nie wybieraj kanału ani czatu grupowego. Sprawdź, że w polu odbiorcy znajduje
się wyłącznie Twoje konto.

Microsoft opisuje prywatne wiadomości od bota w
[dokumentacji wysyłania wiadomości Teams](https://learn.microsoft.com/en-us/power-automate/teams/send-a-message-in-teams#post-a-message-as-the-flow-bot-directly-to-a-user).

## 5. Ustaw dynamiczną treść wiadomości — ważny krok

1. Kliknij pole **Komunikat**.
2. Usuń wpisany wcześniej tekst, np. „Test powiadomień ServiceNow”.
3. Otwórz **Zawartość dynamiczna**. W zależności od edytora służy do tego
   link pod polem, panel z boku lub ikona przy polu.
4. Wybierz zakładkę **Wyrażenie** (*Expression*) lub ikonę **fx**.
5. Wpisz dokładnie:

```text
triggerBody()?['text']
```

6. Zatwierdź przez **OK**, **Dodaj** lub **Wstaw**.
7. Sprawdź, że w polu pojawił się element wyrażenia oznaczony **fx**.

**Nie wpisuj tego bezpośrednio jako zwykłego tekstu w polu Komunikat.**
W przeciwnym razie Teams wyświetli dosłownie `triggerBody()?['text']`.
Wyrażenie musi być obliczane przez przepływ, aby pobrać treść wysłaną przez aplikację.
Nie dodawaj cudzysłowów wokół całego wyrażenia.

## 6. Zapisz i skopiuj adres

1. Kliknij **Zapisz** i zaczekaj na zakończenie zapisywania.
2. Rozwiń pierwszy blok **When a Teams webhook request is received**.
3. W polu **Adres URL żądania HTTP POST** pojawi się pełny adres.
4. Skopiuj go ikoną kopiowania obok pola.

Kopiuj cały adres razem z parametrami po `?`, w tym `sig=`. Nie usuwaj fragmentów,
nie dopisuj znaków i nie używaj adresu strony edycji przepływu.

Nasza aplikacja przyjmuje adresy Power Automate z hostami kończącymi się
na `.api.powerplatform.com` lub `.logic.azure.com`, zakończone ścieżką `/invoke`
i zawierające podpis `sig` w parametrach.

Samo zapisanie przepływu nie wysyła wiadomości. Przepływ zadziała dopiero po
żądaniu z naszej aplikacji.

## 7. Połącz z ServiceNow Monitor

1. Uruchom aktualną wersję aplikacji.
2. W lewym panelu włącz **Powiadomienia Teams**.
3. Przy pierwszym włączeniu otworzy się okno konfiguracji.
   Później możesz otworzyć je przyciskiem **Konfiguruj**.
4. Wklej pełny adres do pola **Adres webhooka Power Automate**.
5. Kliknij **Zapisz**.
6. Ponownie otwórz **Konfiguruj** i kliknij **Wyślij test**.
7. Zaczekaj na wynik i sprawdź czat **Przepływy pracy** w Teams.

Oczekiwana wiadomość:

> Test powiadomień ServiceNow  
> Połączenie z aplikacją działa.

Komunikat aplikacji o przyjęciu żądania oznacza, że webhook odpowiedział.
Ostatecznym potwierdzeniem dostarczenia jest wiadomość na czacie. W razie
problemu sprawdź historię uruchomień przepływu w Power Automate.

Adres jest zapamiętywany na tym komputerze. Wersja EXE zapisuje go w lokalnym
`config.json` w `%LOCALAPPDATA%\ServiceNow Monitor`. Wersja uruchamiana z kodu
zapisuje dane w folderze `data` aplikacji. Pole ukrywa adres, ale plik konfiguracji
nie jest szyfrowany. Nie przekazuj folderu danych innym użytkownikom.
W udostępnianym EXE nie ma webhooka autora.

## 8. Sprawdź rzeczywiste alerty

1. Pozostaw włączone **Powiadomienia Teams**.
2. Rozpocznij monitoring i zaloguj się do ServiceNow w przeglądarce bota.
3. Pierwszy odczyt danego filtra tworzy punkt odniesienia. Nie zgłasza wszystkich
   istniejących incydentów jako nowych.
4. Gdy pojawią się nowe incydenty, aplikacja wyśle alert zbiorczy po cyklu odczytu.

Przykładowa treść:

```text
Nowe incydenty: 2
INC1234567 - STORE 003 GDAŃSK - Problem z kasą
INC1234568 - STORE 073 GDYNIA - Problem z drukarką
```

Każdy incydent ma numer, lokalizację i opis. Długi tekst Teams może zawinąć.
Kolumny „Numer”, „Krótki opis” i „Lokalizacja” powinny być widoczne w ServiceNow.
Brak danych daje „Brak lokalizacji” lub „Brak opisu”.

Powiadomienia Windows i Teams można włączać niezależnie. Nadawca w Teams
pozostaje „Przepływy pracy”. Nazwa samego przepływu nie zmienia nadawcy.

## 9. Powiadomienia na telefonie

Zaloguj się w mobilnym Teams na to samo konto. W ustawieniach telefonu pozwól
Teams wyświetlać powiadomienia; sprawdź też ustawienia czatu i powiadomień w Teams.
Jeżeli wiadomość pojawia się w czacie, ale telefon nie powiadamia, sprawdź
wyciszenie, godziny ciszy oraz blokowanie powiadomień przy aktywności na komputerze.

Komputer z ServiceNow Monitor nadal musi pracować i mieć dostęp do ServiceNow
oraz Internetu. Zamknięcie aplikacji lub uśpienie komputera zatrzymuje wykrywanie.

## 10. Rozwiązywanie problemów

| Objaw | Co sprawdzić |
| --- | --- |
| Teams pokazuje `triggerBody()?['text']` | Usuń zwykły tekst i dodaj wyrażenie przez zakładkę Wyrażenie / fx — punkt 5. |
| Zawsze przychodzi stały tekst testowy | Zastąp go wyrażeniem i zapisz przepływ. |
| Aplikacja odrzuca adres | Skopiuj pełny URL HTTP POST z pierwszego bloku, razem z podpisem; nie link do edytora. |
| HTTP 401 lub 403 | Sprawdź „Anyone”, pełny adres i aktywność przepływu; ograniczenia firmowe wymagają kontaktu z IT. |
| Żądanie przyjęte, ale wiadomości brak | Sprawdź historię uruchomień, wynik akcji Teams, połączenie z kontem i odbiorcę. |
| Przepływ zgłasza brak treści | Sprawdź zapisane wyrażenie oraz to, czy test pochodzi z aktualnej wersji aplikacji. |
| Test działa, ale nowych incydentów nie zgłasza | Sprawdź włączenie Teams, odczyt filtra i to, czy incydent jest rzeczywiście nowo wykryty. Pierwszy odczyt jest punktem odniesienia. |
| Wiadomość jest na komputerze, lecz bez alertu na telefonie | Sprawdź mobilne ustawienia powiadomień — punkt 9. |
| Brak lokalizacji lub opisu | Włącz odpowiednie kolumny w widoku listy ServiceNow. |

## 11. Udostępnianie i zmiana webhooka

Testerowi przekaż EXE i tę instrukcję, bez własnego `config.json`, historii
i profilu przeglądarki. Tester tworzy własny przepływ i podaje własny adres.

Jeśli adres ujawniono osobom nieuprawnionym, unieważnij stary webhook.
Możesz utworzyć nowy przepływ według instrukcji, podmienić adres w aplikacji,
sprawdzić test i następnie wyłączyć lub usunąć stary przepływ. Samo zastąpienie
adresu w aplikacji nie unieważnia starego URL.

Źródła Microsoft:

- [Łącznik Teams i wyzwalacz webhook](https://learn.microsoft.com/en-us/connectors/teams/).
- [Wysyłanie wiadomości przez Power Automate](https://learn.microsoft.com/en-us/power-automate/teams/send-a-message-in-teams).

Instrukcja odpowiada konfiguracji sprawdzonej z ServiceNow Monitor. Microsoft
może zmienić etykiety lub układ edytora; podano polskie i angielskie nazwy
najważniejszych opcji.
