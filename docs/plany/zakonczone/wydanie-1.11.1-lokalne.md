# Lokalne wydanie 1.11.1

Zakończono 12 listopada 2026. Paczka Windows z bieżących źródeł. [Opis wydania](../../wersje/v1.11.1.md) i [poprzednie wydanie lokalne](wydanie-1.11.0-lokalne.md).

- [x] **Przygotowanie**
  - [x] Potwierdź poprzednią paczkę i wybierz numer.
    - EXE i ZIP w `dist` odpowiadają zapisanym sumom 1.11.0. Dla kolejnej paczki przyjęto 1.11.1. Kopie edytowanych źródeł zapisano w `build/release-1.11.1/source-backup`.
  - [x] Podnieś wersję w źródłach i wykonaj testy zakresowe.
    - Podniesiono wersję, `pip check` przeszedł i sprawdzono składnię 146 plików. Przeszło 81/81 testów zakresowych na izolowanych danych (`build/release-1.11.1/tests.json`). Przebieg w piaskownicy nie ukończył prób rejestru i diagnostyki, więc zweryfikowano je w pełnym przebiegu zakresowym Windows.
- [x] **Budowanie i sprawdzenie**
  - [x] Zbuduj EXE istniejącą specyfikacją PyInstaller w katalogu kandydata.
    - PyInstaller 6.22.3 zakończył budowanie. Sumy 310 plików Chromium i 4 plików FFmpeg użytych do budowy zgadzają się z manifestem 1.11.0. Log w `build/release-1.11.1/build.log`.
  - [x] Sprawdź kod i zasoby w EXE, przygotuj ZIP oraz porównaj pliki po rozpakowaniu.
    - Potwierdzono 60 modułów, launcher i 7 zasobów. ZIP przeszedł sprawdzenie CRC, a po rozpakowaniu sumy 1444 plików zgadzają się z kandydatem. Raport `build/release-1.11.1/package.json`.
  - [x] Uruchom rozpakowane EXE offline z izolowanymi danymi i sprawdź Chromium z paczki.
    - `smoke-unpacked/result.json` potwierdza wersję 1.11.1, interfejs, walidację danych startowych i Chromium 153.0.8010.12 z pakietu.
- [x] **Lokalna podmiana**
  - [x] Zachowaj poprzednią paczkę i podmień `dist` po sprawdzeniu, że monitor z tego katalogu jest zamknięty.
    - Zachowano cały poprzedni `dist` w `build/release-1.11.1/previous/dist-1.11.0`. Zweryfikowany EXE i ZIP 1.11.1 trafiły do `dist`.
  - [x] Zweryfikuj pliki i próbę offline w `dist`. Zapisz wyniki oraz zaktualizuj indeksy i instrukcję.
    - Wszystkie 1444 pliki i ZIP zgadzają się ze zweryfikowanym buildem. `smoke-dist/result.json` potwierdza uruchomienie offline z izolowanymi danymi. Zachowana kopia 1.11.0 ma oryginalne sumy EXE i ZIP-a.
    - SHA-256 ZIP-a `7b46d2200598c3398bb353e8793fed287fc9cfb5625954d3345171e87aef33d1`. SHA-256 EXE `33c3dd460b3115cd7b1d54c2797058970e86ae138859f038a691f218c530ddf2`.
    - Zakres odbioru obejmuje próby lokalne. Nie wykonywano próby logowania na rzeczywistym ServiceNow. Wydanie pozostaje lokalne.
