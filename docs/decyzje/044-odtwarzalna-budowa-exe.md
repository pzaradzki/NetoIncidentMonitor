# 044 — Odtwarzalna budowa EXE

**Status.** Wdrożono w źródłach i odebrano na dwóch zgodnych paczkach Windows. [Instrukcja budowy](../budowa-exe.md) · [Raport odbioru](../weryfikacja/odtwarzalna-budowa-exe.md)

**Decyzja.** Budowa Windows x64 pobiera jawnie wskazany plik parametrów analityki. Repozytorium wersjonuje jego rewizję i SHA-256, a uprawnieni uzyskują parametry z zatwierdzonych definicji instancji. Osobny zestaw wymagań budowy przypina koła, a manifest wiąże binaria Chromium i FFmpeg z rewizjami Playwright.

**Powód.** Zatwierdzony arkusz lokalny zawiera dane wykraczające poza zakres paczki. Dotychczasowa budowa używała tego arkusza i istniejącego środowiska. Jawne wejścia pozwalają odtworzyć paczkę i potwierdzić jej zawartość bez osobistej konfiguracji monitora.

**Realizacja.** Importer eksportuje wyłącznie osiem wymaganych pól w stałym formacie. PyInstaller i skrypt budowy weryfikują sumę oraz osadzają plik jako `defaults/dashboard-api.json`. Budowa używa własnych katalogów i sporządza raport oraz wykaz plików ZIP. Dane zakresu pozostają w profilu użytkownika zgodnie z decyzją 040. [Decyzja 040](040-startowy-zakres-dashboardu.md)

**Ograniczenia.** Odtworzenie wymaga dostępu do zatwierdzonego pliku parametrów oraz do źródła lub sprawdzonej kopii kół i binariów. Manifest dokumentuje zestaw dla CPythona 3.12.6 na Windows x64. Zmiana platformy lub wersji narzędzi wymaga osobnego odbioru.
