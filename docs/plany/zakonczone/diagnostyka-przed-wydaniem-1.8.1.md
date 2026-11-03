# Diagnostyka błędów przed publikacją 1.8.1

**Status** — publikacja zakończona. Poniższa checklista zachowuje pierwotny plan, a wyniki i odstępstwa zapisano na końcu. Punktem odniesienia jest commit `4ff5c9f`. ZIP przeszedł kontrolę integralności, porównanie 53 modułów i launchera z commitem oraz test offline rozpakowanego EXE. Publikację zatrzymano po błędach testów. Przed rozpoczęciem publikacji najnowszym wydaniem było 1.7.17.

## A. Odtworzenie warunków

- [ ] Zapisać commit, stan śledzonych plików, wersje Python, Playwright i Chromium, tryb wykonania oraz katalog artefaktów. Zachować raporty z pierwszego uruchomienia i manifest ZIP w lokalnym `data/`.
- [ ] Uruchamiać testy na oddzielnych katalogach danych i plików tymczasowych. Użyć standardowego cache Playwright z Chromium i Chromium Headless Shell. Wcześniejsza próba wskazująca przeglądarkę z paczki nie miała Headless Shell, którego potrzebuje część testów. Odróżnić błędy dostępu sandboxa oraz braki zależności od błędów produktu.
- [ ] Zebrać wynik każdego modułu, liczbę zaliczonych i pominiętych testów, czas oraz kod zakończenia. Sprawdzić, czy wszystkie moduły wystartowały i zakończyły się. Timeout, pusty log lub brak podsumowania traktować jako niepełny wynik.
- [ ] Odtworzyć cztery poniższe przypadki pojedynczo, a potem w całych modułach. Dla każdego zapisać pierwsze miejsce rozbieżności, oczekiwane zachowanie i obserwowany wynik. Klasyfikować dopiero po potwierdzeniu przyczyny.

## B. Krótki link do listy ServiceNow — priorytet

**Objaw** — test `test_browser_short_link_to_task_list_and_empty_list` kończy się `query_mismatch` podczas potwierdzania pierwszej strony.

- [ ] Rozdzielić przypadek z rekordem od pustego wyniku. Prześledzić przejście od krótkiego linku przez rozpoznanie zaufanej ramki i docelowej listy do sprawdzenia zapytania, typu, tabeli, pagera i zakresu. Ustalić dokładnie, który dowód odrzuca pierwszy odczyt.
- [ ] Porównać fixture z aktualnym kontraktem czytnika. Przykład ma adres ramki z filtrem, ale uproszczoną tabelę bez potwierdzenia jej zapytania, krótki syntetyczny `sys_id` oraz samotny komunikat pustki. Sprawdzić każdy z tych elementów osobno. [Test](../../../tests/test_short_links.py) · [Walidacja kontekstu](../../../neto_incident_monitor/list_context.py) · [Paginacja](../../../neto_incident_monitor/pagination.py)
- [ ] Przed zmianą integracji sprawdzić w przeglądarce Codex rzeczywisty krótki link na osobnym profilu. Ustalić, jaki kontekst ServiceNow zachowuje po przekierowaniu i jak wygląda potwierdzona pusta lista. Użytkownik obsługuje logowanie. Zapisać jedynie bezpieczne cechy struktury. Brak dostępu odnotować jako otwartą weryfikację.
- [ ] Jeśli kontrakt jest prawidłowy, zaktualizować dodatnią i pustą fixture, a brak tabeli, błędne zapytanie, obcy typ i niepoprawny identyfikator zachować jako przypadki odrzucenia. Jeśli prawidłowa rzeczywista lista jest odrzucana, poprawić wspólną walidację w potwierdzonym zakresie. Sprawdzić brak częściowego zapisu oraz odczyt po przekierowaniu na pierwszą stronę.

## C. Menu kontekstowe rekordu

**Objaw** — `KeyError: 'Kopiuj link'` w teście klikniętego incydentu.

- [ ] Sprawdzić wywołanie `safe_record_url` dla linku z testu. Fixture wskazuje samo `incident.do` bez `sys_id`. Porównać rezultat z prawidłowym linkiem zawierającym syntetyczny identyfikator 32-znakowy i z linkami rzeczywiście zwracanymi przez czytnik.
- [ ] Potwierdzić osobno menu poprawnego rekordu i menu bez poprawnego adresu. Sprawdzić wybór klikniętego wiersza, kopiowanie numeru i linku, otwieranie rekordu oraz oznaczanie jako przeczytany wyłącznie po udanym otwarciu. Przy niepoprawnym linku oczekiwać braku akcji otwarcia i kopiowania URL. Nie osłabiać walidacji dla uproszczonej fixture. [Test](../../../tests/test_context_menu.py) · [Walidacja adresów](../../../neto_incident_monitor/service_now_urls.py)

## D. Blokada okresu dashboardu przy starcie

**Objaw** — `active_request` ma wartość `None` w atrapie startu wątku. Traceback przechodzi przez wcześniejsze `alert_writer.submit`.

- [ ] Prześledzić kolejność inicjalizacji nadawcy, utworzenia żądania dashboardu, blokady kontrolek i startu workera monitoringu. Sprawdzić, czy podmiana `threading.Thread` obejmuje także wątek executora alertów. Oddzielić oba wywołania w teście.
- [ ] Odtworzyć udany start i wymusić awarię startu właściwego workera. Sprawdzić istnienie żądania i blokadę obu kontrolek przed startem oraz zwolnienie blokady, koordynatora i stanu po awarii. Osobno sprawdzić zachowanie, gdy nie można uruchomić nadawcy alertów, z izolowaną kolejką i atrapą transportu. [Test](../../../tests/test_dashboard_period.py) · [Koordynacja aplikacji](../../../neto_incident_monitor/app.py)

## E. Zmiana kolejności filtrów i zamykanie Tk

**Objaw** — `TclError: can't delete Tcl command` podczas niszczenia widżetów.

- [ ] Ustalić, czy asercje kolejności, zapisu i oczekujących odczytów przechodzą przed sprzątaniem. Zanotować pierwszą awarię, liczbę wywołań zamknięcia, oczekujące callbacki Tk i to, kto niszczy okno.
- [ ] Porównać izolowany test z całym modułem i powtórzeniami na natywnym Windows. Sprawdzić `after`, anulowanie callbacków i procedurę zamykania. Oddzielić podwójne sprzątanie fixture od błędu normalnego zamknięcia aplikacji. Zweryfikować, że przestawienie filtrów nadal zachowuje tożsamość filtra oraz kieruje kolejkę do właściwego celu. [Test](../../../tests/test_filter_reorder.py)

## F. Dowody i wznowienie wydania

- [ ] Dla każdej przyczyny zapisać dowód, klasyfikację, minimalną poprawkę i wynik powtórki. Dla zmiany funkcjonalnej sprawdzić wspólną diagnostykę, korelację oraz brak syntetycznych sekretów w logach. Nie zapisywać HTML, wartości formularzy, pełnych adresów SSO ani danych zgłoszeń.
- [ ] Uruchomić pełną regresję. Jeśli wspólny proces nadal powoduje udokumentowane konflikty między testami, wykonać pełny zestaw modułami w osobnych procesach i podać oba wyniki. Każdy błąd, timeout i pominięcie musi mieć wyjaśnienie. Błędy zachowania aplikacji muszą być naprawione przed wydaniem.
- [ ] Ustalić finalny commit i porównać z nim kod i zasoby w paczce. Jeśli kod lub zasoby się zmieniły, przebudować EXE. Sprawdzić zawartość i integralność ZIP, uruchomić test offline po rozpakowaniu i zapisać SHA-256. Próby rzeczywiste opisać osobno.
- [ ] Po zaliczeniu kontroli wrócić do procedury wydania. Sprawdzić tag i docelowy commit, zweryfikować załącznik szkicu oraz po publikacji porównać SHA-256 pobranego ZIP-a. [Stan wersji lokalnej](../../wersje/v1.8.1.md)

## Wynik diagnostyki czterech błędów

- [x] Krótki link. Uproszczona fixture nie potwierdzała kontekstu tabeli ani pustego wyniku. Test korzysta teraz ze wspólnej syntetycznej listy klasycznej z metadanymi dla SCTASK i poprawnym syntetycznym identyfikatorem rekordu. Oba warianty przeszły w Chromium. Kod integracji pozostał bez zmian. W tej serii nie wykonano nowej obserwacji rzeczywistego krótkiego linku.
- [x] Menu kontekstowe. Adres bez identyfikatora rekordu został odrzucony zgodnie z kontraktem. Test akcji poprawnego rekordu używa syntetycznego identyfikatora. Moduł przeszedł 3 testy.
- [x] Okres dashboardu. Globalna podmiana wątku przechwytywała start executora alertów przed utworzeniem żądania. Test izoluje zlecenie do executora i wymusza awarię startu workera monitoringu. Moduł przeszedł 16 testów.
- [x] Kolejność filtrów. Sprzątanie używało metody głównego okna do anulowania timerów należących do widżetów. Anulowanie timerów na poziomie Tcl pozostawia usuwanie poleceń ich właścicielom podczas niszczenia okna. Moduł przeszedł 4 testy.

Zmiany objęły wyłącznie testy i dokumentację. Potwierdzono zgodność istniejącego EXE z finalnym commitem.

## Wynik publikacji

- [x] Pełna regresja w 61 osobnych procesach. 427 testów zaliczonych, 1 pominięty w module okna przeglądarki. Wspólny przebieg nie stanowi podstawy odbioru.
- [x] Kod 53 modułów, launcher i cztery zasoby zgodne z commitem `e4ead42`. Test offline rozpakowanego ZIP-a zaliczony.
- [x] [Wydanie v1.8.1](https://github.com/pzaradzki/NetoIncidentMonitor/releases/tag/v1.8.1) opublikowano jako najnowsze stabilne wydanie. SHA-256 pobranego ZIP-a jest identyczne z lokalnym: `cdfe6e1eae05d4f22af84ea1c281df306dacfa9134edbecc2e2be7b6d35028fc`.

Nowa próba krótkiego linku na rzeczywistym ServiceNow oraz osobna próba awarii startu nadawcy nie zostały wykonane. Zmiany dotyczyły testów, więc opublikowano wcześniej zweryfikowany kod aplikacji.
