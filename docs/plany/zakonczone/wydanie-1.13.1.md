# Wydanie 1.13.1

Zakończono 25 listopada 2026. [Opis wersji](../../wersje/v1.13.1.md).

- [x] **Przygotowanie**
  - [x] Zapisz korektę pionowego wyrównania ikon i ustaw wersję 1.13.1. Commit źródeł wydania to `95c66b56931df5be45ef3bbf2b6e074c38d08d8d`.
  - [x] Sprawdź położenie ikon przy skalach 100% i 125%, w tym brak kolizji z pigułką statusu. [Test układu](../../../tests/test_filter_card_counts.py).
  - [x] Uruchom regresję Windows z czystego checkoutu. Z 586 testów zaliczono 584. Ograniczenia środowiska uniemożliwiły pomiar pierwszego planu okna, także w pojedynczym ponowieniu, oraz utworzenie dowiązania symbolicznego. Raporty w `build/r131/tests-final.json` i `build/r131/focus-retry.json`.
- [x] **Paczka Windows**
  - [x] Zbuduj dwie paczki z czystych checkoutów tego samego commita przy użyciu przypiętych wejść.
  - [x] Porównaj sumy obu ZIP-ów. Sprawdź CRC i sumy 1441 plików po rozpakowaniu.
  - [x] Uruchom oba EXE offline z dołączonym Chromium 153.0.8010.12. Cztery próby potwierdziły wersję 1.13.1 oraz uruchomienie z pustym i zapisanym profilem testowym. Raport w `build/r131/acceptance.json`. Paczka lokalna jest w `dist/1.13.1`.
- [x] **GitHub**
  - [x] Wypchnij commit wydania i tag `v1.13.1`. Sprawdź zgodność tagu ze źródłami paczki.
  - [x] Prześlij `Neto.Incident.Monitor.zip` do szkicu i zweryfikuj rozmiar oraz SHA-256 przed publikacją. [Wydanie GitHub](https://github.com/pzaradzki/NetoIncidentMonitor/releases/tag/v1.13.1).
  - [x] Potwierdź status najnowszego stabilnego wydania w publicznym API. Pobierz załącznik i porównaj jego SHA-256 z lokalnym ZIP-em. Raport w `build/r131/verified.json`.

Odbiór paczki obejmował regresję na danych testowych i uruchomienia offline.
