# Wydanie 1.13.4

Zakończono 27 listopada 2026. [Opis wersji](../../wersje/v1.13.4.md)

- [x] **Źródła i regresja**
  - [x] Potwierdzić zakres zmian od 1.13.1, w tym obsługę pustego przypisania INC i odbiór na ADEO. [Odbiór poprawki](puste-przypisanie-w-filtrach-inc.md)
  - [x] Wskazać commit źródeł użyty do budowy `588f0726a45b1460d8df876e6c1f4d7489293370`.
  - [x] Uruchomić pełną regresję na czystym checkoutcie. Zaliczone 596 z 598 testów. Dwie próby pominięto z powodu ograniczeń Windows dotyczących fokusu i dowiązań symbolicznych. Raport w `build/r134/tests-publication.json`.
- [x] **Paczka Windows**
  - [x] Porównać obie budowy z przypiętymi wejściami. ZIP-y były bitowo identyczne. Sprawdzono CRC i SHA-256 wszystkich 1441 plików oraz zgodność kodu EXE ze źródłami.
  - [x] Uruchomić rozpakowane EXE offline z dołączonym Chromium 153.0.8010.12 na pustym i zapisanym profilu. Wszystkie cztery próby przeszły. Raport w `build/r134/acceptance.json`.
- [x] **GitHub**
  - [x] Wypchnąć commit i adnotowany tag `v1.13.4`. Potwierdzono zgodność z commitem paczki.
  - [x] Przesłać `Neto.Incident.Monitor.zip` do szkicu i potwierdzić rozmiar oraz SHA-256 przed publikacją. Raport w `build/r134/asset.json`.
  - [x] Opublikować jako najnowsze stabilne wydanie i sprawdzić publiczny status oraz SHA-256 ponownie pobranego ZIP-a. Raport w `build/r134/verified.json`. [Wydanie GitHub](https://github.com/pzaradzki/NetoIncidentMonitor/releases/tag/v1.13.4)
