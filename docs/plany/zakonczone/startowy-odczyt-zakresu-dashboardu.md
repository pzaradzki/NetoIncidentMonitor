# Pobranie brakujących list agentów i lokalizacji po logowaniu

**Status.** Wdrożono w źródłach i w lokalnej paczce 1.12.0-experimental.3. Użytkownik potwierdził odbiór uruchomienia na świeżym profilu i restartu na ADEO w wersji [1.12.0-experimental.4](../../wersje/v1.12.0-experimental.4.md).

Po zalogowaniu aplikacja sprawdza lokalnie komplet obu list. Jeśli obie są zapisane i poprawne, korzysta z nich bez weryfikowania aktualności w ServiceNow. Jeśli którejkolwiek brakuje, aplikacja pobiera i zapisuje obie przy użyciu istniejącego mechanizmu ręcznego odświeżania. Użytkownik nadal może sam zlecić aktualizację w ustawieniach.

## 1. Oddzielenie definicji zapytań od lokalnego zakresu

- [x] **Usunąć domyślne listy z paczki i zachować istniejący zakres użytkownika.**
  - [x] Rozdzielono wczytywanie parametrów od sprawdzania kompletu. Błąd formatu pozostawia plik użytkownika do diagnostyki.
  - [x] Zweryfikowano definicje arkusza podczas budowy. Paczka zawiera jedynie dopuszczone parametry, bez `assignees`, `locations`, arkusza i lokalnych danych.
  - [x] Zachowano odczyt wcześniejszych danych profilu. Próby potwierdziły pierwszeństwo zapisu lokalnego i zignorowanie list z dawnych zasobów paczki.
  - [x] Reset źródłowy usuwa obie listy z czytelnej definicji i zachowuje parametry. Próba EXE z pustym profilem potwierdziła gotowość parametrów przed pobraniem zakresu.

## 2. Kolejka po zalogowaniu

- [x] **Ułożyć pobieranie brakującego zakresu w tej samej kolejce co układy kolumn.**
  - [x] Rejestracja następuje po potwierdzeniu sesji, przed `session_ready`.
  - [x] Test kolejki potwierdził **INC → REQ → RITM → SCTASK → zakres dashboardu → dashboard → zagrożenia**, mimo błędu jednego układu. Zapisany zakres pomija automatyczne zlecenie.
  - [x] `dashboard_scope` korzysta z tej samej karty, budżetu i odczytu P1 co przycisk **Aktualizuj**. Test potwierdził scalenie zgłoszenia ręcznego z automatycznym.
  - [x] Początkowy zakres działa w kolejce sesji także bez cyklu monitoringu. Dashboard oczekuje na dostęp do karty, zachowując swój okres.
  - [x] Zlecenie zachowuje ID przy odzyskiwaniu sesji. Istniejący czytnik sprawdza zgodność konta i sygnał zamknięcia przed zapisem. Stop cyklu nie przerywa tego zlecenia.

## 3. Statusy i zachowanie przy błędzie

- [x] **Zachować działanie reszty aplikacji, jeśli pobranie zakresu się nie powiedzie.**
  - [x] Belka pokazuje oczekiwanie na listy. Komunikat o brakującym zakresie kieruje do **Ustawienia → Dane aplikacji → Agenci i lokalizacje Dashboardu SLA → Aktualizuj**.
  - [x] Test potwierdził brak żądań dashboardu przy brakującym zakresie. Błąd kończy żądanie z zachowaniem migawki. Test kolejki potwierdził kontynuację kolejnej pracy.
  - [x] Sprawdzono jednorazową rejestrację i ponowną kontrolę po restarcie na poziomie koordynatora. Zwykłe ręczne ponowienie pozostaje dostępne.
  - [x] Diagnostyka rozróżnia komplet i brak zakresu oraz tryb automatyczny i ręczny. Wyniki stosują istniejącą korelację. Dopuszczone pola zawierają liczby, czasy i przyczyny, bez identyfikatorów i zapytań.

## 4. Testy i odbiór

- [x] **Potwierdzić pobranie zakresu na świeżym profilu i użycie zapisu po restarcie.**
  - Regresja lokalna objęła 166 prób. Zaliczono 165. Jedna próba zabezpieczenia dowiązania została pominięta ze względu na brak możliwości utworzenia dowiązania symbolicznego w tym środowisku.
  - [x] Testy objęły wczytanie i zapis świeżej konfiguracji, starszy plik i błąd formatu lub zapisu. Kolejka używa kompletu bez odświeżenia.
  - [x] Testy lokalne objęły kolejkę z cyklem, brak cyklu, odzyskiwanie logowania, scalenie żądań oraz błąd układu. Istniejące testy okresu i harmonogramu zostały powtórzone.
  - [x] Rozpakowane EXE przeszło próby offline z pustym i zapisanym profilem. Po syntetycznym zapisie drugi start odczytał zakres lokalny. Sprawdzono 1445 plików ZIP-a i potwierdzono brak identyfikatorów ze sprawdzanych list w śledzonych źródłach oraz w konfiguracji paczki.
  - [x] 23 listopada 2026 użytkownik potwierdził, że na ADEO świeży profil pobrał listy agentów i lokalizacji, a ponowne uruchomienie użyło zapisanego zakresu.
  - Potwierdzenie użytkownika obejmuje pobranie i ponowne użycie list. Wyniki poszczególnych odczytów układów, pomiar liczby kart i obserwacja fokusu nie były częścią zgłoszonego wyniku.
