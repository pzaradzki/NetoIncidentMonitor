# Wydanie 1.10.0

Publikacja zakończona 12 listopada 2026. Zakres obejmuje wspólną sesję ServiceNow, kolejkę odczytów i import Ulubionych oraz poprawki interfejsu i odczytów opisane w notatkach wydania. [Opis wersji](../../wersje/v1.10.0.md).

- Z 585 testów zaliczono 583. Trzy moduły, które zgłosiły błędy Tk podczas równoległej regresji, przeszły po osobnym uruchomieniu. Dwie próby pominięto ze względu na ograniczenia fokusu Windows i tworzenia dowiązań symbolicznych. Wyniki zapisano w `build/release-1.10.0-tests-final.json`.
- Sprawdzono składnię 145 plików i zależności. Kod 60 modułów oraz launchera w EXE odpowiada źródłom, a 4 zasoby zgadzają się z repozytorium. Kontrola ZIP-a i porównanie 1441 rozpakowanych plików z buildem przeszły. Rozpakowany EXE 1.10.0 i dołączone Chromium uruchomiono offline na izolowanych danych. [Zakres odbioru na ServiceNow](../wspolna-sesja-servicenow.md).
- Tag `v1.10.0` wskazuje commit `750707260f296b74c6896816b6f901454bfb2598`. GitHub zwrócił zgodny SHA-256 załącznika w szkicu. Po publikacji API potwierdziło status najnowszego stabilnego wydania, a SHA-256 ponownie pobranego ZIP-a zgadza się z lokalnym plikiem. Wyniki zapisano w `build/release-1.10.0-verified.json`. [Wydanie na GitHubie](https://github.com/pzaradzki/NetoIncidentMonitor/releases/tag/v1.10.0).
- Główne lokalne EXE i ZIP zaktualizowano w `dist`. Poprzednie pliki zachowano w `build/release-1.10.0-previous`. Próba offline głównej paczki na izolowanych danych potwierdziła wersję 1.10.0.

Załącznik `Neto.Incident.Monitor.zip` ma 269 262 355 bajtów. SHA-256 `a51dda1dae8d159b6e84952bb16de84044378a1717fa201ad3d453a49c520d47`.
