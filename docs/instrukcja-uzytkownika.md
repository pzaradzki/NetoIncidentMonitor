# Neto Incident Monitor

Instrukcja dla wersji **1.11.2**. [Opis wydania](wersje/v1.11.2.md).

Poprawka przygotowana później w źródłach: miesiąc i rok dashboardu są niedostępne od zlecenia aktualizacji do jej zakończenia, także podczas oczekiwania na logowanie. Po zakończeniu lub Stop można wybrać nowy okres i kliknąć Aktualizuj. Sama zmiana dat w bezczynności nie uruchamia odczytu. Ta poprawka wymaga jeszcze przebudowy EXE.

W źródłach przywrócono również jeden czas „Ostatnio odczytano” pod dashboardem, zamiast listy czasów sekcji. Oznacza ostatni pełny udany odczyt; błąd lub niepełna aktualizacja nie zmienia tego czasu. Jest zapamiętywany między uruchomieniami. Starsze dane bez potwierdzonego czasu całości pokazują „—” do kolejnego pełnego odczytu. Zmiana wymaga przebudowy EXE.

Neto Incident Monitor to aplikacja desktopowa dla systemu Windows, która monitoruje listy incydentów w ServiceNow i powiadamia o nowych zgłoszeniach. Dane są odczytywane z interfejsu internetowego ServiceNow za pomocą Playwright i przeglądarki Chromium. Aplikacja nie korzysta z API ServiceNow.

## Główne funkcje

- Monitorowanie wielu filtrów z możliwością ich włączania i wyłączania podczas pracy.
- Powiadomienia systemowe Windows oraz powiadomienia Microsoft Teams i Google Chat.
- Oddzielna historia każdego filtra.
- Otwieranie incydentów oraz kopiowanie ich numerów i adresów z menu kontekstowego.
- Konfigurowanie widoczności, kolejności i szerokości kolumn.
- Zapamiętywanie układu interfejsu, rozmiaru okna i stanu maksymalizacji.
- Praca w zasobniku systemowym oraz obsługa wybranych scenariuszy automatycznego logowania.

## Wymagania

### Walidacja adresów i treści powiadomień

Ta konfiguracja aplikacji ufa wyłącznie instancji `adeo.service-now.com`. Filtry muszą używać HTTPS, portu 443 (jawnego lub domyślnego) i ścieżek `/incident_list.do`, `/sc_task_list.do`, `/sc_request_list.do` albo `/sc_req_item_list.do`. Obsługiwane są także linki classic normalizowane do tych ścieżek. Dane logowania w adresie, fragmenty oraz znaki sterujące są odrzucane. Walidacja działa przy odczycie konfiguracji i przed nawigacją. Zmiana zaufanej instancji wymaga świadomej zmiany polityki w `service_now_urls.py`.

Obsługiwane są również skróty `/now/nav/ui/classic/__tinyId__/…` tej samej instancji. Aplikacja rozpoznaje ich docelową listę po zalogowaniu, sprawdza adres i odczytuje ją od pierwszej strony. Rozpoznany rodzaj INC/SCTASK/REQ/RITM służy do doboru kolumn i harmonogramu. Historia pozostaje przypisana do oryginalnego adresu filtra. Skrót nie może zawierać parametrów, fragmentu ani wskazywać innego hosta; jego cel musi być obsługiwaną listą.

Linki INC, SCTASK, REQ i RITM są ograniczone do tej samej instancji oraz odpowiednich ścieżek `/incident.do`, `/sc_task.do`, `/sc_request.do` i `/sc_req_item.do`. Nieprawidłowy link pozostawia numer jako zwykły tekst; nie można go otworzyć z menu ani dwukrotnym kliknięciem. Zewnętrzna treść powiadomień nie może wprowadzać własnych hiperłączy lub formatowania Markdown. Jawne adresy w opisach są wyświetlane jako tekst bez automatycznego linkowania.

Pillow jest przypięte do wersji 13.0.0 z poprawkami bezpieczeństwa. Aktualizacja biblioteki i kodu wymaga ponownej budowy dystrybucji; wcześniej przygotowane EXE i ZIP nie zmieniają się automatycznie.

- Windows 10 lub Windows 11 w wersji 64-bitowej.
- Dostęp sieciowy do instancji ServiceNow i uprawnienia do odczytu monitorowanych list.
- Python 3.12 w przypadku uruchamiania aplikacji z kodu źródłowego.

Pakiet aplikacji udostępniany w Releases zawiera wymagane biblioteki i przeglądarkę Chromium. Nie wymaga instalacji Pythona. Instalacja zależności dla kodu źródłowego wymaga dostępu do internetu.

## Instalacja i uruchomienie

### Gotowy pakiet dla Windows

1. Pobierz plik `Neto.Incident.Monitor.zip` z [najnowszego wydania](https://github.com/pzaradzki/NetoIncidentMonitor/releases/latest).
2. Rozpakuj całe archiwum do wybranego katalogu.
3. Uruchom `Neto Incident Monitor.exe`.

Katalog `_internal` musi znajdować się obok pliku wykonywalnego. Zawiera biblioteki, zasoby graficzne i przeglądarkę niezbędne do działania aplikacji.

Aby zainstalować aktualizację, zamknij aplikację i zastąp jej katalog zawartością nowego pakietu. Ustawienia i historia pozostaną zachowane, ponieważ są przechowywane poza katalogiem instalacji.

### Uruchomienie z kodu źródłowego

W katalogu projektu uruchom `start.bat`. Skrypt tworzy środowisko wirtualne `.venv`, instaluje zależności i Chromium, a następnie uruchamia aplikację.

Środowisko można również przygotować ręcznie w PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe launcher.pyw
```

Po przygotowaniu środowiska plik `Neto Incident Monitor.vbs` umożliwia uruchamianie aplikacji bez okna konsoli.

## Obsługa aplikacji

Obsługiwane listy to INC (`incident_list.do`), SCTASK (`sc_task_list.do`), REQ (`sc_request_list.do`) i RITM (`sc_req_item_list.do`) w instancji `adeo.service-now.com`. REQ i RITM dodaje się tak samo jak inne filtry; działają dynamiczne kolumny, historia oraz powiadomienia z linkami do rekordów. SCTASK, REQ i RITM korzystają ze wspólnego interwału „Zgłoszenia katalogowe”. Licznik czasu od utworzenia INC pozostaje dostępny tylko dla incydentów.

### Konfiguracja monitorowania

1. Wybierz **Dodaj filtr** i wprowadź nazwę oraz pełny adres listy ServiceNow z zastosowanym filtrem.
2. Chromium otwiera się przy starcie. Dokończ logowanie, jeśli jest potrzebne. Aplikacja ukryje Chromium i udostępni główne okno po potwierdzeniu sesji oraz ewentualnej decyzji w sprawie zapisu poświadczeń. Wybierz **Uruchom monitoring**, jeśli automatyczny start jest wyłączony.
3. Korzystaj z przełączników przy filtrach, aby włączać lub wyłączać poszczególne listy, również podczas monitorowania.

**Zmiana źródeł z 4 listopada 2026 i głównej paczki lokalnej `dist/Neto Incident Monitor`:** po zalogowaniu aktualizacja przebiega w kolejności **dashboard → incydenty zagrożone → filtry**. Przy wyłączonej automatycznej aktualizacji dashboardu start pomija dashboard. **Sprawdź teraz** dla całości używa nowej kolejności; przyciski poszczególnych sekcji nadal aktualizują wybrany zakres. Zagrożenia zachowują niezależny termin 60 s od końca poprzedniej próby, ale dashboard lub długi filtr mogą go opóźnić. Nie oznacza to zmiany już opublikowanego wydania.

Każdy filtr ma własną listę bieżących incydentów i własną historię. Czerwone zaznaczenie w panelu filtrów określa zawartość obu zakładek. Ten sam numer incydentu może być niezależnie wykryty w kilku filtrach.

Kolejność filtrów można zmieniać, przeciągając je myszą. Czerwona linia wskazuje miejsce upuszczenia. Zmiany są zapamiętywane między uruchomieniami i można je wprowadzać również podczas monitorowania.

W wersji 1.11.0 przyciski **Dodaj filtr**, **Edytuj** i **Usuń** działają także podczas monitorowania. Filtr dodany podczas rozpoczętej partii trafi do następnej partii swojego typu. Możesz odczytać go wcześniej przyciskiem **Aktualizuj**. Zmiana nazwy pozwala dokończyć odczyt. Zmiana adresu lub usunięcie pomija odczyty starego filtra, zachowując zatwierdzoną historię. **Sprawdź teraz** obejmuje zestaw filtrów z chwili zlecenia.

Lewy panel filtrów ma domyślnie 329 px szerokości. Aby zmienić szerokość, przeciągnij separator przy prawej krawędzi panelu. Aplikacja zapamięta wybraną szerokość.

W wersji 1.11.0 ikony Windows, Google Chat i Teams obok przełącznika filtra pokazują jego ustawienia powiadomień. Kolor oznacza kanał włączony dla filtra, a szarość kanał wyłączony. Kanał wyłączony globalnie jest ukryty.

Przycisk **Konfiguruj** obok przycisku **Kolumny** otwiera **Ustawienia filtra** zaznaczonego na liście, obejmujące powiadomienia i zgodę na duże odczyty.

Zębatka po lewej stronie przełącznika Microsoft Teams lub Google Chat otwiera konfigurację powiadomienia danego kanału. Można w niej podać osobny webhook filtra. Przycisk **Zastosuj** od razu zapisuje webhook i wybór szablonu tego kanału. Późniejsze **Anuluj** w oknie filtra nie cofa tych zmian; pozostałe przełączniki filtra zatwierdza **Zapisz**. Puste pole korzysta z adresu globalnego. Webhook filtra ma pierwszeństwo także dla opcji **Test powiadomienia**. Adresy są maskowane w oknie i szyfrowane dla bieżącego konta Windows przez DPAPI. Globalne wyłączenie kanału nadal blokuje wysyłanie i ukrywa jego ustawienia w filtrze, zachowując zapisany adres.

- **Powiadomienia Windows**, **Powiadomienia Microsoft Teams** i **Powiadomienia Google Chat** są włączane osobno. Odpowiedni kanał musi być również włączony globalnie; w przeciwnym razie jego ustawienia w filtrze są ukryte.
- **Tylko pierwsze wystąpienie** ogranicza powiadomienia do pierwszego wykrycia numeru w danym filtrze. Domyślnie opcja jest wyłączona, więc powiadomienie jest wysyłane także po potwierdzonym powrocie incydentu.

Powrót oznacza ponowne pojawienie się incydentu po poprawnym odczycie, który potwierdził jego nieobecność. Błąd odczytu, wyłączenie filtra i ponowne uruchomienie aplikacji nie stanowią potwierdzenia zniknięcia. Ostatnia potwierdzona obecność i wcześniejsze wystąpienia są zachowywane między uruchomieniami.

Pierwszy odczyt nowego filtra wykrywa znajdujące się w nim incydenty i może wysłać powiadomienia zgodnie z ustawieniami kanałów. Przy aktualizacji istniejące dane wykrywania są zachowywane, aby uniknąć ponownych alertów tylko z powodu aktualizacji.

Powiadomienie zawiera nazwę filtra, liczbę wykrytych incydentów oraz ich numery, lokalizacje i krótkie opisy. Zmiana danych incydentu pozostającego na liście nie powoduje nowego powiadomienia o pojawieniu się.

### Własny format powiadomień filtra

W zębatce przy Teams lub Google Chat wybierz **Szablon powiadomienia**. Biblioteka nazwanych szablonów jest wspólna dla filtrów i obu kanałów, natomiast wybór jest niezależny dla każdego filtra i kanału. Windows zachowuje standardowy format.

**Dodaj** otwiera edytor z polem nazwy. **Edytuj** zmienia wybrany szablon we wszystkich miejscach użycia. Nazwy muszą być unikalne. **Usuń** wymaga potwierdzenia i przełącza używające go filtry na **Standardowy**. Dla pozycji **Standardowy** przyciski **Edytuj** i **Usuń** są nieaktywne. Standardowy format to `Nazwa filtra · liczba`, a poniżej lista `Numer - Krótki opis`, jednakowo dla obsługiwanych rodzajów zgłoszeń.

- **Szablon wiadomości** opisuje całą wiadomość i obsługuje `{nazwa filtra}`, `{liczba elementów}` oraz `{lista elementów}`. Starsze nazwy zmiennych nadal są obsługiwane. Lista jest wymagana i może znaleźć się w dowolnym miejscu wiadomości.
- **Szablon elementu listy** jest powtarzany dla każdego elementu. Wybierz kolumnę filtra i kliknij **Wstaw**. Dostępne są wszystkie kolumny odczytane z tej listy ServiceNow, także niestandardowe i ukryte w tabeli aplikacji. Przed pierwszym odczytem uruchom monitoring filtra.

Przykład elementu: `{Numer} - {Krótki opis}`. Selektor pokazuje nagłówki kolumn, a przycisk **Wstaw** umieszcza wybrany nagłówek w nawiasach klamrowych. Powiązania z identyfikatorami kolumn są zachowane wewnętrznie: zmiana nagłówka nie psuje zapisanego szablonu. Powtarzające się nazwy dostają przyrostek `(2)`, `(3)` itd. Starsze zmienne techniczne nadal działają i są przedstawiane czytelnie po otwarciu edytora. Brakująca wartość jest pusta, a wpisane separatory pozostają. Edytor wskazuje niedostępne kolumny. Numery pozostają klikalne w obu kanałach.

Podgląd aktualizuje się podczas edycji. **Wyślij test** wysyła dane przykładowe na webhook filtra lub adres globalny, bez zapisywania zmian. **Zapisz szablon** od razu zapisuje szablon w bibliotece na dysku. Potwierdzone usunięcie również zapisuje bibliotekę od razu. **Zastosuj** od razu zapisuje wybór szablonu i webhook kanału. **Zapisz** w oknie filtra zatwierdza pozostałe przełączniki. Anulowanie nadrzędnego okna nie cofa zapisanych zmian kanału ani zapisania lub potwierdzonego usunięcia szablonu. Dotychczasowe własne formaty są automatycznie przenoszone do biblioteki; wybór **Standardowy** nie usuwa własnych szablonów.

### Bieżące incydenty i historia

Dwukrotne kliknięcie wpisu na liście filtrów otwiera jego adres w domyślnej przeglądarce. Kliknięcie przełącznika aktywności nie otwiera przeglądarki.

Przy dodawaniu filtra można wkleić bezpośredni adres listy, długi adres ServiceNow `/now/nav/ui/classic/params/target/…` albo skrót `__tinyId__`. Długi adres jest zapisywany jako bezpośredni, z zachowaniem warunków i widoku. Jeśli adres zawiera sprzeczne wartości tego samego parametru listy, zostanie odrzucony bez zapisu. Skrócenie długiego adresu do `__tinyId__` przez sam ServiceNow jest normalnym zachowaniem.

Duże tabele (ponad 150 rekordów historii lub bieżącej listy) są przygotowywane poza wątkiem interfejsu i wczytywane krótkimi partiami. Ukryta duża tabela czeka na otwarcie swojej zakładki. Zmiana filtra lub zakładki przerywa poprzednie ładowanie; postęp jest widoczny nad tabelą. Małe zestawy pozostają wczytywane bezpośrednio. Nie ma limitu liczby zachowanych wpisów historii.

Zakładka **Bieżące zgłoszenia** przedstawia wyniki ostatniego odczytu zaznaczonego filtra. Zakładka **Historia zgłoszeń** zawiera zapisane incydenty wykryte podczas monitorowania. Dane historyczne nie są na bieżąco aktualizowane i mogą różnić się od aktualnych danych w ServiceNow.

Dwukrotne kliknięcie wiersza otwiera zgłoszenie w domyślnej przeglądarce. Menu kontekstowe umożliwia otwarcie zgłoszenia i skopiowanie jego numeru lub adresu.

**Wyczyść historię** usuwa wpisy tego filtra po potwierdzeniu operacji. Aplikacja zachowuje informacje o wcześniej rozpoznanych numerach, aby nie traktować ich ponownie jako nowych incydentów.

### Kolumny i układ interfejsu

Przycisk **Kolumny** jest dostępny po pierwszym pełnym odczycie filtra. Aplikacja pobiera wszystkie widoczne kolumny z listy ServiceNow, także pola niestandardowe, i początkowo wyświetla je w tej samej kolejności. Odczyt pustej listy z rozpoznanymi nagłówkami również udostępnia konfigurację.

- Przeciągnięcie nagłówka zmienia kolejność kolumn.
- Przeciągnięcie krawędzi nagłówka zmienia szerokość kolumny.
- Dwukrotne kliknięcie separatora dopasowuje kolumnę po jego lewej stronie do nagłówka i zawartości wszystkich wczytanych wierszy. Dopasowana szerokość jest zapamiętywana dla filtra.
- Kliknięcie nagłówka przełącza sortowanie pomiędzy kolejnością rosnącą, malejącą i domyślną.

Widoczność, kolejność i szerokości kolumn są zapisywane osobno dla każdego filtra, wspólnie dla jego bieżącej listy i historii. Dodanie lub usunięcie kolumny w ServiceNow przywraca pełny zestaw i kolejność ze strony. Sama zmiana kolejności na stronie zachowuje własny układ użytkownika. Niepełny lub nieudany odczyt nie zmienia zapisanej konfiguracji.

Po pierwszym udanym odczycie listy INC bez zapisanego układu **Wiek (min)** pojawia się jako pierwsza kolumna. **Przywróć domyślne** ustawia ją na początku listy INC i wybiera wszystkie kolumny ServiceNow w ostatnio odczytanej kolejności. Kolumny lokalne znajdziesz w sekcji **Kolumny dodatkowe**. Datę wykrycia w historii można włączyć osobno. Zmiany w konfiguratorze zatwierdza przycisk **Zapisz**.

Separator pomiędzy panelem filtrów a tabelą umożliwia zmianę szerokości panelu. Układ kolumn, szerokość panelu oraz rozmiar i stan maksymalizacji okna są zapamiętywane między uruchomieniami.

### Ustawienia i praca w tle

Przycisk **Ustawienia**, oznaczony ikoną koła zębatego, otwiera konfigurację częstotliwości odczytu, powiadomień, logowania i minimalizacji. Podczas monitoringu można zmieniać interwały odczytu i globalne powiadomienia Windows.

Przycisk **Zatrzymaj** kończy monitorowanie. Zamknięcie głównego okna kończy działanie aplikacji. Przy włączonej minimalizacji do zasobnika systemowego monitoring pozostaje aktywny po zminimalizowaniu okna.

## Logowanie i powiadomienia

Automatyczne logowanie może wybrać pojedyncze zapamiętane konto i zatwierdzić gotowy formularz z potwierdzonym autouzupełnieniem. Przy wielu kontach wybiera użytkownik; późniejsze autofill pozwala kontynuować automatycznie. Wpisywanie, wklejanie, ręczne wysłanie lub MFA oddają kontrolę użytkownikowi. Aplikacja nie wpisuje ani nie zapisuje samodzielnie hasła; korzysta z własnego profilu Chromium, niezależnego od zwykłego Chrome.

Pierwsze logowanie odbywa się w widocznym Chromium. Po udanym logowaniu aplikacja ukrywa Chromium. Jeśli sesja wygaśnie, próbuje ją odzyskać w tle i pokazuje okno, gdy potrzebna jest Twoja interwencja. Podczas takiego oczekiwania możesz użyć **Pokaż okno logowania**. Po zamknięciu lub awarii Chromium użyj **Połącz ponownie**, aby rozpocząć widoczne połączenie.

Jeśli przy włączonym autologowaniu wpiszesz hasło samodzielnie, po udanym logowaniu aplikacja pokaże aktywny komunikat o zapisie poświadczeń na środku ekranu. Kliknij **Zapisz** w Chromium, a następnie **Zapisano** w oknie aplikacji. Możesz też wybrać **Wyłącz autologowanie**, aby zapisać zmianę ustawienia. Chromium pozostanie widoczne do wyboru. Dotyczy to pierwszego logowania i odzyskiwania sesji.

Po zalogowaniu odczyty ręczne i import Ulubionych są dostępne także przy zatrzymanym monitoringu. Zlecenia korzystają z jednej karty i wykonują się kolejno. **Sprawdź teraz** może scalić oczekujące odczyty. Po zakończeniu odczytu Ulubionych możesz obejrzeć podgląd, podczas gdy karta obsługuje kolejne zlecenie.

Opcja **Automatycznie zaktualizuj dashboard przy starcie monitoringu** jest domyślnie wyłączona. Jeśli chcesz pobierać dashboard przy każdym uruchomieniu monitoringu, włącz ją w sekcji **Monitorowanie**.

Przycisk **Aktualizuj** jest nieaktywny, gdy jego odczyt czeka w kolejce lub trwa. W tym czasie możesz zlecić inny zakres albo wybrać **Sprawdź teraz**. Pełna aktualizacja blokuje objęte nią przyciski do zakończenia ich odczytów. Przycisk **Sprawdź teraz** odblokowuje się po zakończeniu całego zlecenia.

Przycisk **Aktualizuj** odczytuje wybrany filtr także wtedy, gdy jego przełącznik jest wyłączony. To jednorazowy odczyt z wynikiem w tabeli i zapisem do historii, bez powiadomień dla wyłączonego filtra. Harmonogram i **Sprawdź teraz** obejmują filtry z włączonym przełącznikiem.

Gotowe puste pole otrzymuje 5 sekund na autofill; później udostępniane jest okno, bez założenia, że hasła nie ma w magazynie. Dostarczone lub niepewne zatwierdzenie nie jest powtarzane. Przy wylogowaniu lub problemie sieciowym monitoring kontrolowanie oczekuje/odzyskuje sesję; **Zatrzymaj** kończy oczekiwanie. Szczegóły limitów, diagnostyki i ograniczeń opisuje [kontrakt logowania](kontrakty/diagnostyka-logowania.md).

Powiadomienia Microsoft Teams wymagają skonfigurowania adresu webhook w Power Automate. Procedurę opisuje [film instruktażowy konfiguracji powiadomień Teams](https://netology-my.sharepoint.com/:v:/g/personal/piotr_zaradzki_netology_com_pl/IQCv86cQd-JrTLpRyIrcA8ZPAVtyK6Ya9HGxTT4NMxRQ8S0?nav=eyJyZWZlcnJhbEluZm8iOnsicmVmZXJyYWxBcHAiOiJPbmVEcml2ZUZvckJ1c2luZXNzIiwicmVmZXJyYWxBcHBQbGF0Zm9ybSI6IldlYiIsInJlZmVycmFsTW9kZSI6InZpZXciLCJyZWZlcnJhbFZpZXciOiJNeUZpbGVzTGlua0NvcHkifX0&e=wLs9Sr), dostępna także przez przycisk **Instrukcja** w oknie konfiguracji. Przy włączonych i skonfigurowanych powiadomieniach aplikacja może również wysłać alert o wygaśnięciu sesji.

Google Chat jest trzecim, niezależnym kanałem. W ustawieniach globalnych wybierz **Google Chat → Konfiguruj**, wklej adres webhooka, użyj **Wyślij test**, zapisz konfigurację i włącz kanał. Przycisk **Instrukcja** prowadzi do [instrukcji Google](https://developers.google.com/workspace/chat/quickstart/webhooks). Webhook tworzysz w przeglądarkowej wersji Google Chat: wybrana przestrzeń → **Aplikacje i integracje → Dodaj webhooki**. Organizacja Google Workspace musi zezwalać na używanie webhooków. Power Automate i logowanie do Google w naszej aplikacji nie są potrzebne.

Google Chat jest domyślnie wyłączony globalnie. Po skonfigurowaniu można wybierać powiadomienia osobno dla każdego filtra, tak samo jak Windows i Teams. Kanały mogą działać jednocześnie. Obsługiwane są INC i SCTASK, hiperłącza pod numerami oraz **Test powiadomienia** z menu kontekstowego. Ustawienia i webhook są zapamiętywane między sesjami. Wysyłanie działa w tle z ograniczoną kolejką i odstępem między wiadomościami; większe zestawy zgłoszeń są dzielone na części. Adres jest maskowany w oknie konfiguracji, a komunikaty błędów nie zawierają parametrów `key` ani `token`. Webhooki Google Chat i Teams są zapisywane lokalnie w postaci zaszyfrowanej przez Windows DPAPI. Nadal nie należy udostępniać katalogu danych ani profilu przeglądarki.

## Przechowywanie danych

### Ochrona webhooków

Adresy webhooków Teams i Google Chat są przechowywane jako zaszyfrowane wartości w `config.json`, chronione przez Windows DPAPI w zakresie bieżącego użytkownika. Aplikacja odszyfrowuje je wyłącznie do użycia w pamięci. Nie wymaga to dodatkowego hasła, logowania ani uprawnień administratora.

Przy pierwszym odczycie konfiguracji z wcześniejszej wersji jawne webhooki są automatycznie szyfrowane, a plik atomowo zastępowany bez tworzenia jawnej kopii zapasowej. Jeśli migracja się nie powiedzie, dotychczasowy plik pozostaje bez zmian, a aplikacja informuje o problemie. Nie jest stosowany zapis nowych sekretów jawnym tekstem jako mechanizm zastępczy.

Po skopiowaniu danych na inne konto lub komputer odszyfrowanie może nie być możliwe. Aplikacja wyłącza wtedy odpowiedni kanał i wyświetla informację o konieczności ponownego wpisania webhooka. Nieczytelna zaszyfrowana wartość pozostaje zachowana przy zapisie pozostałych ustawień. Przeniesienie samego katalogu aplikacji na tym samym komputerze i koncie nie wymaga ponownej konfiguracji.

Starsze wersje aplikacji nie obsługują nowego formatu sekretów. Po migracji należy korzystać z wersji obsługującej DPAPI. Ochrona nie zastępuje uprawnień dostępu do katalogu danych i nie chroni przed procesem działającym już jako ten sam użytkownik. Wcześniej utworzone kopie jawnej konfiguracji nie są automatycznie usuwane.

| Sposób uruchomienia | Katalog danych |
| --- | --- |
| Pakiet z plikiem EXE | `%LOCALAPPDATA%\NetoIncidentMonitor` |
| Kod źródłowy | `data` w katalogu projektu |

Katalog danych zawiera ustawienia, historię, logi i profil przeglądarki. Wersja wykonywalna i wersja uruchamiana z kodu źródłowego korzystają z oddzielnych katalogów danych.

W ustawieniach, w sekcji **Uruchamianie i okno aplikacji**, można włączyć automatyczny monitoring po uruchomieniu aplikacji oraz uruchamianie ze zminimalizowanym oknem. Opcje są domyślnie wyłączone. Po jednoczesnym włączeniu **Uruchom aplikację zminimalizowaną** oraz **Minimalizacja do zasobnika** okno przy starcie trafia do zasobnika, również gdy ikona pojawi się z opóźnieniem. Przy błędzie zasobnika okno zostaje przywrócone. Automatyczny monitoring wymaga przynajmniej jednego włączonego filtra; logowanie do ServiceNow działa zgodnie z ustawieniami logowania. Autostart Windows jest domyślnie wyłączony, a jego przełącznik jest ukryty w UI źródeł i głównej paczki lokalnej po zmianie z 4 listopada 2026. Mechanizm pozostaje zachowany; wcześniej istniejące wpisy nie są automatycznie usuwane.

Dane użytkownika, w tym adres webhook i dane sesji przeglądarki, nie powinny być dodawane do repozytorium ani do pakietów dystrybucyjnych. Repozytorium zawiera kod źródłowy; pliki wykonywalne, Chromium i katalog `dist` są udostępniane jako pakiety wydań.

## Przygotowanie pakietu dystrybucyjnego

Po utworzeniu środowiska `.venv` uruchom w PowerShell:

```powershell
.\scripts\build_exe.ps1
```

Skrypt instaluje narzędzia do budowania oraz Chromium, a następnie przygotowuje pakiet za pomocą PyInstaller:

```text
dist/
  Neto Incident Monitor/
    Neto Incident Monitor.exe
    _internal/
```

Do dystrybucji wymagany jest cały katalog `Neto Incident Monitor`. Dane i konfiguracja użytkownika nie są częścią pakietu.

## Testy i diagnostyka

Uruchomienie testów automatycznych:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Testy interfejsu wymagają aktywnej sesji pulpitu Windows. Testy odczytu danych korzystają z lokalnych stron testowych i Chromium; nie wymagają konta ServiceNow. Integrację z docelową instancją, filtrami i procesem logowania należy zweryfikować oddzielnie.

Podstawowy test uruchomienia pakietu, bez połączenia z ServiceNow:

```powershell
& '.\dist\Neto Incident Monitor\Neto Incident Monitor.exe' --smoke-test "$PWD\smoke-result.json"
```

Raport potwierdza uruchomienie interfejsu i dołączonej przeglądarki Chromium. Log błędów `monitor.log` znajduje się w katalogu danych aplikacji. Rotacja logów zachowuje do trzech plików archiwalnych.

Szczegółowy przebieg logowania jest automatycznie zapisywany w `login-diagnostics.jsonl` w tym samym katalogu. Dla wersji EXE jest to `%LOCALAPPDATA%\NetoIncidentMonitor`, a dla kodu źródłowego katalog `data`. Każda próba ma własny identyfikator i czas zdarzeń. Log zawiera stan formularza (obecność i autouzupełnienie hasła, dostępność przycisku, liczba kont), próby kliknięć, przyczyny oczekiwania i przejścia do ręcznego logowania oraz typy błędów. Nie zapisuje wartości pól, loginów, haseł, treści strony, ciasteczek, ścieżek ani parametrów adresów SSO. Niezmieniony stan jest odnotowywany co 10 sekund. Plik ma limit 2 MB i trzy archiwalne kopie. Przy problemie z logowaniem zachowaj `login-diagnostics.jsonl` wraz z jego plikami `.1`, `.2`, `.3` oraz `monitor.log`.

## Struktura projektu

```text
NetoIncidentMonitor/
├── neto_incident_monitor/   # kod aplikacji
├── tests/                  # testy automatyczne
├── tools/                  # narzędzia diagnostyczne i podgląd interfejsu
├── scripts/                # skrypt budowania i konfiguracja PyInstaller
├── docs/                   # dokumentacja konfiguracji
├── assets/                 # zasoby graficzne i ikony
├── launcher.pyw            # punkt wejścia aplikacji
├── start.bat               # przygotowanie środowiska i uruchomienie
├── Neto Incident Monitor.vbs
├── requirements.txt
└── requirements-build.txt
```

Kod aplikacji jest zorganizowany jako pakiet `neto_incident_monitor`. Narzędzia pomocnicze należy uruchamiać z katalogu głównego projektu, np. `python -m tools.preview_ui`.

Katalogi `data`, `build` i `dist` oraz środowisko `.venv` są tworzone lokalnie i nie są częścią repozytorium.

### Zadania katalogowe (SCTASK)

Filtry mogą monitorować również listy zadań katalogowych ServiceNow (`sc_task_list.do`). Obsługiwane są zarówno adresy bezpośrednie, jak i linki nawigacyjne `/now/nav/ui/classic/params/target/`. Po dodaniu filtra zadania SCTASK są odczytywane ze wszystkich stron listy i korzystają z osobnej historii oraz ustawień powiadomień tego filtra.

W wyborze kolumn dostępne są także **Wnioskowane dla** i **Otwarte przez**. Pola są odczytywane tylko wtedy, gdy są widoczne na liście ServiceNow. Przy kilku kolumnach o nazwie Stan aplikacja preferuje identyfikator pola stanu zadania. Powiadomienia o SCTASK używają określenia zadanie katalogowe. Aplikacja nie rozwija automatycznie powiązanych REQ ani RITM; monitoruje zadania widoczne na wskazanej liście.

W sekcji **Monitorowanie** można ustawić osobne interwały odczytu dla **INC** i **zgłoszeń katalogowych (SCTASK, REQ, RITM)**. Minimum to 15 sekund. Domyślny interwał zgłoszeń katalogowych wynosi 60 sekund.

Edycja pola interwału uruchamia licznik widoczny na dole ustawień. Aplikacja zapisuje interwały po 5 sekundach od ostatniej edycji. Zamknięcie ustawień zapisuje je od razu. Jeśli wartość jest błędna lub zapis się nie powiedzie, ustawienia pozostają otwarte z komunikatem, a harmonogram korzysta z poprzednich wartości.

Rozpoczęta partia kończy się normalnie. Nowy interwał liczy się od jej zakończenia. Jeśli monitor już czeka, termin przelicza się od końca ostatniej partii danego rodzaju. Gdy nowy termin już minął, odczyt czeka na zwolnienie karty.

Licznik wskazuje najbliższy zaplanowany odczyt, a **Sprawdź teraz** sprawdza wszystkie włączone filtry niezależnie od ich rodzaju. Odczyty odbywają się kolejno w jednej przeglądarce, więc długi odczyt może opóźnić następny.

### Ochrona przed dużymi listami

Przy listach zawierających ponad 1000 wpisów aplikacja pyta o zgodę na pełny odczyt. Pytanie dotyczy zarówno INC, jak i SCTASK. Masz 15 sekund na odpowiedź: **Kontynuuj odczyt** pozwala na bieżący odczyt, **Wyłącz filtr** wyłącza filtr, a brak odpowiedzi pomija bieżący odczyt bez wyłączania filtra. Zaznaczenie **Zapamiętaj zgodę dla tego filtra** przy potwierdzeniu zapisuje zgodę między sesjami. Bez zaznaczenia pytanie wróci przy każdym odczycie dużej listy. Gdy licznik wszystkich wpisów w SNOW jest niedostępny, pytanie pojawia się po przekroczeniu 1000 odczytanych rekordów. Pominięcie nie zapisuje częściowego wyniku, nie zmienia historii ani potwierdzonej obecności zgłoszeń.

Zapamiętaną zgodę na duże odczyty można cofnąć w **Ustawieniach filtra**: wyłącz **Pobieraj duże listy bez pytania** i wybierz **Zapisz**. Pytanie wróci przy następnym odczycie listy ponad 1000 wpisów; bieżący odczyt nie jest przerywany.

W powiadomieniach Teams numery INC i SCTASK są hiperłączami do rekordów ServiceNow. Format INC: numer, lokalizacja, krótki opis. Format SCTASK: numer, krótki opis, wnioskowane dla. W powiadomieniach Windows numery pozostają zwykłym tekstem. Przepływ korzystający z `triggerBody()?['text']` otrzymuje gotową treść HTML z hiperłączami.

Opcja **Test powiadomienia** na dole menu kontekstowego wysyła powiadomienie z klikniętym INC lub SCTASK, korzystając z danych bieżącej listy albo historii. Obowiązują globalne i indywidualne ustawienia kanałów powiadomień. Test nie zmienia pamięci wykrytych zgłoszeń i działa także dla wyłączonego filtra.

### Przywrócenie stanu pierwszego uruchomienia

W **Ustawienia → Dane aplikacji** wybierz **Usuń wszystkie dane aplikacji…**, a następnie **Usuń dane i zamknij**. Reset usuwa ustawienia, filtry, szablony, historię, oczekujące alerty, pamięć dashboardu, logi i profil Chromium monitora. Aplikacja się zamknie. Przy kolejnym uruchomieniu może być potrzebne ponowne logowanie. Jeśli plik jest zablokowany, można ponowić reset albo zamknąć aplikację. Kolejny start dokończy zapisane żądanie przed wczytaniem danych.

Po przeniesieniu folderu aplikacji uruchom monitor ręcznie z nowej lokalizacji. Jeśli wpis autostartu istnieje, monitor zaktualizuje jego ścieżkę. Przełącznik autostartu Windows jest ukryty w UI; Windows może dodatkowo wyłączyć istniejący wpis w swoich ustawieniach. Reset danych usuwa wpis bieżącego wariantu aplikacji.

W bieżących źródłach kafelki dashboardu i zagrożeń SLA wyświetlają wyniki i podświetlają się po najechaniu. Aby przejść do ServiceNow, użyj przycisku **Otwórz w SNOW** w nagłówku panelu. WJRUW jest wskaźnikiem obliczanym lokalnie.

Pigułka **Aktualizuje** na bocznym przycisku pokazuje trwający odczyt dashboardu lub zagrożeń SLA. Stopka dashboardu pokazuje okres SLA, czas ostatniej pełnej aktualizacji i bieżący status.
