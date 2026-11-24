# 045 — Logi uruchomień ze źródeł

**Status.** Wdrożono w źródłach jako osobną zmianę A10. [Audyt](../archiwum/AUDIT.md#a10--p3-dokumentacja-stanu-wdrożenia-i-ścieżek-diagnostyki-jest-niespójna)

**Decyzja.** Logi uruchomień ze źródeł zapisujemy w `%LOCALAPPDATA%\NetoIncidentMonitor-SourceLogs\<id-kopii>`. Identyfikator wynika ze znormalizowanej ścieżki katalogu źródeł. EXE zapisuje logi w swoim katalogu danych `%LOCALAPPDATA%\NetoIncidentMonitor`.

**Powód.** Logi powinny pozostać poza katalogiem projektu i paczką. Osobny katalog każdej kopii źródeł zapobiega współdzieleniu plików i rotacji między checkoutami. Rozdzielenie katalogów źródeł i EXE chroni logi źródłowe podczas resetu paczki.

**Realizacja.** Launcher i diagnostyka JSONL korzystają z `LOG_DIR`. Nadal dopisują i rotują logi w dotychczasowym formacie. Reset źródeł usuwa własne pliki diagnostyczne i ich archiwa oraz rozpoznane dawne logi z `data/`. Blokada instancji i znacznik wznowienia resetu pozostają przy danych projektu. Jeśli plik logu jest zajęty, reset zachowuje znacznik i ponawia usuwanie po zwolnieniu uchwytu. [Ścieżki](../../neto_incident_monitor/runtime_paths.py) · [Reset](../../neto_incident_monitor/data_reset.py) · [Testy](../../tests/test_data_reset.py)

**Weryfikacja.** Dwa odrębne uruchomienia z syntetycznym katalogiem danych użytkownika dopisały oba logi w tym samym katalogu kopii. Zachowano odrębne i skorelowane identyfikatory uruchomień. Próba resetu z otwartym logiem zachowała znacznik i zakończyła się po zwolnieniu uchwytu. W pełnej regresji Windows zaliczono 563 z 564 testów. Pominięto próbę dowiązania symbolicznego niedostępnego w środowisku. Lokalny raport to `build/e5/a10-full.json`.

**Ograniczenia.** Dawne logi pozostają dostępne w `data/` do resetu lub ręcznego porządkowania. Automatyczny start używa wyłącznie nowej ścieżki. Ustawienia, historia oraz profil Chromium dla źródeł nadal są w `data/`.
