# Wydanie 1.11.2

- [ ] **Przygotowanie**
  - [x] Ustal zakres i podnieś wersję. Paczka zawiera poprawkę list okresu i zmiany od opublikowanej 1.10.0. Kopia zmienionych źródeł jest w `build/release-1.11.2/source-backup`.
  - [ ] Sprawdź składnię, zależności i regresję na izolowanych danych.
- [x] **Paczka Windows**
  - [x] Zbuduj kandydata, porównaj kod i zasoby, przygotuj i rozpakuj ZIP.
    - PyInstaller 6.22.3. Zgodność 60 modułów, launchera i 7 zasobów. ZIP przeszedł kontrolę CRC, a po rozpakowaniu wszystkie 1444 pliki zgadzają się z buildem. Raport w `build/release-1.11.2/package.json`.
  - [x] Uruchom rozpakowaną aplikację offline. Zaktualizuj `dist` z kopią poprzedniej paczki i powtórz próbę.
    - Oba uruchomienia offline potwierdziły 1.11.2, walidację startu i Chromium 153.0.8010.12. Porównanie 1444 plików i sumy ZIP w `dist` przeszło. Poprzednia paczka jest w `build/release-1.11.2/previous/dist-1.11.1`.
    - ZIP ma 269 287 053 bajtów. SHA-256 `cc4307318cb8f75cfe8d046ec5c93268fc439226ed55375af65ab297d2eadabb`.
- [ ] **GitHub**
  - [ ] Zapisz zmiany w commicie i opublikuj odpowiadający paczce tag `v1.11.2`.
  - [ ] Prześlij ZIP do szkicu, potwierdź jego rozmiar i SHA-256, opublikuj jako stabilne wydanie.
  - [ ] Sprawdź najnowsze wydanie, tag i sumę publicznie pobranego ZIP-a. Zamknij plan.
