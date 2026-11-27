# Wydanie 1.13.5

Zakończono 27 listopada 2026. [Opis wersji](../../wersje/v1.13.5.md)

- [x] **Źródła i regresja**
  - [x] Zamknąć zmiany automatycznego sprawdzania aktualizacji oraz ustawić numer 1.13.5. Commit źródeł to `8c46f1b566a3e1f112ab7e7e0d3776b8f4f0a6ad`. [Odbiór wdrożenia](sprawdzanie-aktualizacji-przy-starcie.md)
  - [x] Uruchomić pełną regresję na czystym checkoutcie. Zaliczone 605 z 607 testów. Dwie próby pominięto z powodu ograniczeń Windows dotyczących fokusu okna i dowiązań symbolicznych. Raport w `build/r135/tests-publication.json`.
- [x] **Paczka Windows**
  - [x] Porównać dwie niezależne budowy z przypiętymi wejściami. Potwierdzono identyczne ZIP-y, CRC, sumy 1441 plików i zgodność modułów EXE ze źródłami.
  - [x] Uruchomić oba rozpakowane EXE offline z dołączonym Chromium 153.0.8010.12. Cztery próby na pustych i zapisanych profilach przeszły. Raport w `build/r135/acceptance.json`.
- [x] **GitHub**
  - [x] Wypchnąć commit i adnotowany tag `v1.13.5`. Potwierdzono zgodność z commitem paczki.
  - [x] Przesłać `Neto.Incident.Monitor.zip` do szkicu i potwierdzić rozmiar oraz SHA-256 przed publikacją. Raport w `build/r135/asset.json`.
  - [x] Opublikować jako najnowsze stabilne wydanie i zweryfikować SHA-256 publicznie pobranego załącznika. Raport w `build/r135/verified.json`. [Wydanie GitHub](https://github.com/pzaradzki/NetoIncidentMonitor/releases/tag/v1.13.5)
