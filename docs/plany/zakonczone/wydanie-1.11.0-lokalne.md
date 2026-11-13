# Lokalne wydanie 1.11.0

Zakończono 12 listopada 2026. Zakres obejmuje lokalny EXE i ZIP dla Windows. Wydanie 1.10.0 pozostaje opublikowaną paczką. [Opis zmian](../../wersje/v1.11.0.md), [odbiór odtworzonych źródeł](odzyskanie-zmian-po-v1.10.0.md).

- [x] **Etap 1. Przygotowanie**
  - [x] Ustal numer i zakres. Podniesiono wersję do 1.11.0 w źródłach i zapisano zmiany użytkowe w notatkach.
  - [x] Sprawdź składnię, zależności i testy zakresowe na izolowanych danych.
    - Składnia 145 plików poprawna. `pip check` przeszedł. PyInstaller 6.22.3 oraz Chromium i FFmpeg wymagane przez Playwright są dostępne lokalnie.
    - Przeszło 19/19 testów wersji, startu Windows i diagnostyki (`build/release-1.11.0/tests.json`).
- [x] **Etap 2. Budowanie i odbiór**
  - [x] Zbuduj paczkę istniejącą specyfikacją w osobnym katalogu.
    - PyInstaller 6.22.3 zbudował `build/release-1.11.0/candidate/Neto Incident Monitor/` z bieżącej specyfikacji i lokalnie dostępnych binariów. Log zapisano w `build/release-1.11.0/build.log`.
  - [x] Porównaj kod i zasoby w paczce ze źródłami. Sprawdź ZIP i rozpakuj go do próby.
    - Porównano 60 modułów i launcher oraz SHA-256 7 zasobów. ZIP przeszedł kontrolę CRC, a wszystkie 1444 pliki po rozpakowaniu mają sumy zgodne z buildem (`build/release-1.11.0/package.json`).
  - [x] Uruchom offline rozpakowany EXE na osobnym katalogu danych. Sprawdź numer, interfejs i dołączone Chromium.
    - `smoke-unpacked/result.json` potwierdza tytuł 1.11.0, interfejs, walidację startu i Chromium 153.0.8010.12 z paczki. Próba użyła oddzielnego katalogu danych.
- [x] **Etap 3. Lokalna podmiana**
  - [x] Zachowaj poprzedni katalog i ZIP w `build` przed podmianą w `dist`.
    - Zachowano pierwotny `dist` w `build/release-1.11.0/previous/dist-1.10.0`. W pierwotnym rozpakowanym katalogu brakowało EXE. Pełna kopia ZIP 1.10.0 w `previous/` zawiera EXE i ma SHA-256 zgodną z raportem wydania.
  - [x] Podmień lokalną paczkę i potwierdź, że EXE oraz ZIP odpowiadają zweryfikowanemu buildowi. Zapisz SHA-256.
    - Podmieniono `dist`. Sumy SHA-256 wszystkich 1444 plików oraz ZIP-a zgadzają się ze zweryfikowanym buildem. Próba offline z `dist` potwierdziła numer, interfejs, walidację startu i Chromium (`smoke-dist/result.json`).
    - `dist/Neto Incident Monitor.zip` ma 269 281 737 bajtów i SHA-256 `cd40050727ed15eabb81c96a862cca768c7b1caad3d2f7c37a0766b50d5f3827`. SHA-256 EXE to `2b17051c00e8521a22e94bed57161d8e5217625fe4fb923a3426897a883851d6`.
