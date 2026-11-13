# Wydanie 1.11.2

Zakończono 13 listopada 2026. [Opis wersji](../../wersje/v1.11.2.md).

- [x] **Przygotowanie**
  - [x] Ustal zakres i podnieś wersję. Paczka zawiera poprawkę list okresu i zmiany od opublikowanej 1.10.0. Kopia zmienionych źródeł jest w `build/release-1.11.2/source-backup`.
  - [x] Sprawdź składnię, zależności i regresję na izolowanych danych.
    - Składnia 146 plików i `pip check` przeszły. Z 601 testów zaliczono 599, a próby fokusu Windows i dowiązania symbolicznego pominięto z powodu środowiska. Moduł bezpieczeństwa przeszedł po powtórzeniu. Test zapisu adresu filtra przeszedł po poprawieniu inicjalizacji testowej aplikacji. Wyniki w `build/release-1.11.2/tests-final.json`.
- [x] **Paczka Windows**
  - [x] Zbuduj kandydata, porównaj kod i zasoby, przygotuj i rozpakuj ZIP.
    - PyInstaller 6.22.3. Zgodność 60 modułów, launchera i 7 zasobów. ZIP przeszedł kontrolę CRC, a po rozpakowaniu wszystkie 1444 pliki zgadzają się z buildem. Raport w `build/release-1.11.2/package.json`.
  - [x] Uruchom rozpakowaną aplikację offline. Zaktualizuj `dist` z kopią poprzedniej paczki i powtórz próbę.
    - Oba uruchomienia offline potwierdziły 1.11.2, walidację startu i Chromium 153.0.8010.12. Porównanie 1444 plików i sumy ZIP w `dist` przeszło. Poprzednia paczka jest w `build/release-1.11.2/previous/dist-1.11.1`.
    - ZIP ma 269 287 053 bajtów. SHA-256 `cc4307318cb8f75cfe8d046ec5c93268fc439226ed55375af65ab297d2eadabb`.
- [x] **GitHub**
  - [x] Zapisz zmiany w commicie i opublikuj odpowiadający paczce tag `v1.11.2`.
    - Wszystkie 60 modułów EXE porównano z indeksem Git przed commitem. `master` i tag wskazują commit `259e523fadf20d85a97ddf5f802115a9cb9109a0`. Prywatne notatki pozostały poza commitem.
  - [x] Prześlij ZIP do szkicu, potwierdź jego rozmiar i SHA-256, opublikuj jako stabilne wydanie.
    - Wydanie `443928633` opublikowano po potwierdzeniu załącznika `742692558`, rozmiaru 269 287 053 bajtów i zgodnego SHA-256. [Wydanie GitHub](https://github.com/pzaradzki/NetoIncidentMonitor/releases/tag/v1.11.2).
  - [x] Sprawdź najnowsze wydanie, tag i sumę publicznie pobranego ZIP-a. Zamknij plan.
    - Publiczne API potwierdziło `v1.11.2` jako najnowsze stabilne wydanie. Rozmiar i SHA-256 ponownie pobranego publicznie ZIP-a zgadzają się z lokalną paczką. Raport w `build/release-1.11.2/verified.json`. Próby odbioru były lokalne i offline.
