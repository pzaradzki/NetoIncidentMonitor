# Sprawdzanie aktualizacji przy starcie aplikacji

**Status.** Zakończono. Wdrożono w źródłach i zweryfikowano na Windows.

Po zakończeniu planu automatyczne potwierdzenie aktualnej wersji przestało otwierać okno. Ręczne sprawdzenie nadal pokazuje komunikat. [Decyzja 051](../../decyzje/051-cichy-wynik-sprawdzenia-przy-starcie.md)

## Oczekiwane zachowanie

W sekcji **Ustawienia → Uruchamianie i okno aplikacji** pojawi się przełącznik **„Sprawdzaj dostępność aktualizacji przy starcie aplikacji”**. Domyślnie będzie włączony również dla istniejącej konfiguracji bez tego ustawienia. Zmiana wyboru zapisze się od razu i wpłynie na następne uruchomienie. Główna instancja wykona jedno sprawdzenie podczas zwykłego startu, niezależnie od logowania i monitoringu ServiceNow.

Automatyczne i ręczne sprawdzenie użyją tego samego odczytu najnowszego stabilnego wydania oraz tych samych komunikatów. Monit o nowej wersji ma być widoczny po otrzymaniu wyniku, również przy starcie zminimalizowanym albo w zasobniku. Zawiera dotychczasowe akcje otwarcia strony wydania i anulowania. Pobranie aktualizacji pozostaje czynnością użytkownika. Przy ukrytym oknie komunikat o aktualnej wersji lub błędzie można pokazać po przywróceniu głównego widoku, bez odsłaniania go wyłącznie w celu prezentacji tego komunikatu. Ręczny przycisk pozostaje dostępny również przy wyłączonym przełączniku. [Obecne sprawdzanie](../../../neto_incident_monitor/release_check.py) · [Zasady odsłaniania okna](../../decyzje/028-odsloniecie-glownego-okna.md)

## 1. Przełącznik i zapis preferencji

- [x] Dodać w istniejącej pętli sekcji uruchamiania jeden wiersz z `Toggle` i `BooleanVar`. Ustawić wartość domyślną na `True` dla nowej preferencji `check_updates_on_startup`, uwzględniając wartość zapisaną przez użytkownika. [Budowa ustawień](../../../neto_incident_monitor/settings_ui.py)
- [x] Dołączyć preferencję do istniejącego `App.save_startup_preference()` i schematu `validate_config()`. Przyjąć ten sam format wartości logicznej co pozostałe przełączniki, z dotychczasową obsługą `0` i `1`. [Zapis preferencji](../../../neto_incident_monitor/app.py) · [Walidacja](../../../neto_incident_monitor/data_validation.py)
- [x] Zweryfikować zapis zmiany w obie strony, zachowanie poprzedniej wartości po odmowie zapisu i odczyt przy ponownym uruchomieniu. Sprawdzić, że samo przełączenie podczas sesji zapisuje wybór na następny start.

## 2. Jeden mechanizm dla startu i przycisku

- [x] Rozszerzyć istniejące `check_updates()`, w którym dziś przycisk **Sprawdź aktualizacje** jest wymaganym argumentem. Umożliwić uruchomienie z głównego okna bez przycisku i zachować jego dotychczasową blokadę podczas pracy. [Ręczne wywołanie](../../../neto_incident_monitor/settings_ui.py) · [Mechanizm](../../../neto_incident_monitor/release_check.py)
- [x] Użyć jednej ścieżki `latest_release()` i jednego `show_result()`. Zachować porównanie wersji stabilnych, limit czasu, odczyt strony wydania przy limicie GitHuba, klasyfikację błędów oraz potwierdzenie użytkownika przed otwarciem GitHuba.
- [x] Zaplanować wywołanie z normalnej ścieżki `app.main()` po walidacji konfiguracji i inicjalizacji Tk. Użyć istniejącego `after_idle` do uruchomienia wspólnej operacji w tle. Uniezależnić je od zdarzenia `session_ready`, ponownego logowania i harmonogramu odczytów ServiceNow. [Start aplikacji](../../../neto_incident_monitor/app.py) · [Wspólna sesja ServiceNow](../../decyzje/025-wspolna-sesja-servicenow.md)
- [x] Sprawdzić granice działania. Wyłączone ustawienie, druga instancja, podgląd UI i próba offline z `apply_startup=False` pomijają sprawdzenie startowe. [Blokada instancji](../../../neto_incident_monitor/single_instance.py) · [Podgląd UI](../../../tools/preview_ui.py) · [Próba offline](../../../tools/package_smoke.py)
- [x] Przy kliknięciu ręcznym w trakcie sprawdzenia startowego wykorzystać rozpoczęty odczyt. Ustalić właściciela jednego okna wyniku i zwolnić blokadę przycisku także po błędzie. Po zakończeniu kolejne ręczne kliknięcie uruchamia świeże sprawdzenie.

## 3. Widoczność monitu i cykl życia okien

- [x] Pokazać monit o nowej wersji z istniejącego `show_result()` w wątku Tk. Przy widocznym głównym oknie wykorzystać je jako właściciela. Dla okna schowanego przy starcie, zminimalizowanego lub w zasobniku umożliwić pokazanie tego samego monitu samodzielnie. Własność `transient` nie może uzależniać widoczności monitu od widoczności rodzica.
- [x] Sprawdzić start z trwającym logowaniem, gotową sesją i niedostępnym ServiceNow. Sprawdzić też jednoczesny dialog logowania lub zapisu hasła. Monit o nowej wersji ma być dostępny od razu po wykryciu i nie może przejąć istniejącej blokady modalnej innego dialogu. [Zasady fokusu](../../decyzje/028-odsloniecie-glownego-okna.md) · [Dialog poświadczeń](../../decyzje/026-potwierdzenie-zapisu-poswiadczen.md)
- [x] Zachować dotychczasowe komunikaty o aktualnej wersji oraz o błędzie. Dla wyniku startowego przy ukrytym oknie powiązać ich pokazanie z przywróceniem widoku. Gdy użytkownik uruchomi sprawdzenie ręcznie, pokazać wynik w ustawieniach.
- [x] Sprawdzić zamknięcie ustawień oraz wyjście z aplikacji podczas sprawdzania. Zamknięcie ustawień odłącza ich przycisk, a wyjście unieważnia oczekujący wynik i usuwa zaplanowane wywołania Tk. Spóźniony wynik kończy się bez nowego okna i bez błędu Tcl. [Zamykanie i widoczność](../../../neto_incident_monitor/app.py)

## 4. Diagnostyka i testy

- [x] Korzystać ze wspólnej diagnostyki. Powiązać początek i koniec próby z uruchomieniem i identyfikatorem sprawdzenia. Zapisać źródło `startup` lub `manual`, czas, wynik, dozwoloną kategorię błędu i zastosowanie istniejącego odczytu zastępczego przy limicie GitHuba. Pomijać treści odpowiedzi, nagłówki uwierzytelniania i dane użytkownika. [Decyzja 004](../../decyzje/004-bezpieczna-diagnostyka.md)
- [x] Rozszerzyć istniejące testy sprawdzania wydań o nową i aktualną wersję, niedostępną sieć, limit GitHuba, wspólne sprawdzenie przy zbieżności z ręcznym kliknięciem oraz zamykanie okien w trakcie pracy. Użyć odpowiedzi syntetycznych i sprawdzić, że przeglądarka otwiera się po kliknięciu **Otwórz Github**. [Testy sprawdzania](../../../tests/test_release_check.py)
- [x] Rozszerzyć testy startu o starszą konfigurację, włączony i wyłączony przełącznik, dokładnie jedną próbę na start oraz o brak sprawdzenia w trybach testowych i podczas odzyskiwania sesji. Potwierdzić zachowanie istniejących opcji startu, minimalizacji do paska i zasobnika. [Testy startu](../../../tests/test_startup.py) · [Testy sesji](../../../tests/test_shared_session.py)
- [x] Sprawdzić na Windows rzeczywistą widoczność monitu z syntetyczną odpowiedzią o nowszej wersji podczas zwykłego i zminimalizowanego startu oraz startu w zasobniku. Zweryfikować widoczność i działanie przycisków, zamknięcie monitu i zachowanie głównego okna. Sprawdzić jedno ręczne uruchomienie z wyłączoną opcją startową.
- [x] Uruchomić testy zakresowe i pełną regresję Windows. Zanotować wynik, pominięcia oraz zakres rzeczywistej próby. [Runner regresji](../../../tools/run_regression.py)

**Wynik prób zakresowych.** Zaliczone 35 testów. Na pulpicie Windows, z syntetyczną odpowiedzią GitHub, potwierdzono widoczność monitu przed gotowością sesji ServiceNow i po przejściu do głównego okna, paska zadań i zasobnika. Sprawdzono zachowanie istniejącej blokady modalnej, zapis po zmianie ustawienia, odmowę zapisu, współdzielenie odczytu i odrzucenie wyniku po zamknięciu. Raport w `build/startup-release-check/focused-final.json`.

**Regresja Windows.** Zaliczone 604 z 606 testów. Pominięto pomiar pasywnego fokusu okna i próbę tworzenia dowiązania symbolicznego z powodu ograniczeń środowiska. Raport w `build/startup-release-check/regression.json`.

## 5. Domknięcie planu

- [x] Po odbiorze uzupełnić architekturę o punkt uruchomienia sprawdzenia, wspólny mechanizm z przyciskiem i zasady widoczności monitu. [Architektura](../../architektura.md) · [Decyzja 050](../../decyzje/050-aktualizacje-przy-starcie.md)
- [x] Zaznaczać checkboxy po weryfikacji. Dopisać wynik lub odnośnik do raportu, a po ukończeniu przenieść plan do `zakonczone/` i zaktualizować indeks. [Indeks planów](../README.md)
