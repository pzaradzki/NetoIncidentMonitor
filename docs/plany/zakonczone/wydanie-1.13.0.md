# Wydanie 1.13.0

Zakończono 25 listopada 2026. [Opis wersji](../../wersje/v1.13.0.md).

- [x] **Przygotowanie**
  - [x] Podnieś wersję programu do 1.13.0 i zapisz źródła wydania w commicie `c9e0bfc8ff17f17e00fc56d7bdbc100efbfa093d`.
  - [x] Uruchom pełną regresję Windows. Z 586 testów zaliczono 584, w tym test startu i ponownego logowania po powtórzeniu w izolacji. Dwa pominięcia wynikały z ograniczeń pierwszego planu okien i tworzenia dowiązań symbolicznych. Raporty w `build/r13/tests-final.json` oraz `build/r13/tests-native-retry.json`.
- [x] **Paczka Windows**
  - [x] Zbuduj ZIP dwukrotnie z czystych checkoutów tego samego commitu, używając tych samych przypiętych zależności, Chromium i zatwierdzonych definicji dashboardu.
  - [x] Sprawdź CRC, porównaj sumy 1441 plików i potwierdź identyczną sumę SHA-256 obu ZIP-ów.
  - [x] Uruchom oba rozpakowane EXE offline z dołączonym Chromium 153.0.8010.12. Cztery próby potwierdziły start z pustym i zapisanym profilem testowym oraz wersję 1.13.0. Raport w `build/r13/acceptance.json`. Gotowa paczka jest w `dist/1.13.0`.
- [x] **GitHub**
  - [x] Wypchnij commit i tag `v1.13.0`. Zweryfikuj, że tag wskazuje commit użyty w obu budowach.
  - [x] Prześlij `Neto.Incident.Monitor.zip` do szkicu i sprawdź rozmiar oraz SHA-256 załącznika przed publikacją. [Wydanie GitHub](https://github.com/pzaradzki/NetoIncidentMonitor/releases/tag/v1.13.0).
  - [x] Potwierdź w publicznym API, że 1.13.0 jest najnowszym stabilnym wydaniem, pobierz publiczny ZIP i porównaj sumę z lokalną. Raport w `build/r13/verified.json`.

Odbiór paczki obejmował regresję na danych testowych i uruchomienia offline.
