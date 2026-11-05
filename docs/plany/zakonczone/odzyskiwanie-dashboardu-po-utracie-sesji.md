# Odzyskiwanie dashboardu po utracie sesji

Status: zakończone w źródłach i głównej paczce lokalnej, 5 listopada 2026. Odbiór rzeczywistego ServiceNow/SSO pozostaje poza tym etapem.

- [x] Reprodukcja przed zmianą: timeout → AuthenticationRequired kończyło sekcję bez odzyskiwania. Nowa regresja wykazała błąd starego kodu.
- [x] Oddzielne limity: jedno ponowienie odczytu i jedno odzyskanie logowania; do trzech wywołań czytnika, wspólny aktywny budżet 60 s i pierwsza próba 39 s.
- [x] Stop, błąd/odmowa logowania, brak kolejnego odczytu po wyczerpaniu czasu, propagacja zamknięcia przeglądarki i zachowanie tego samego żądania.
- [x] Nowa diagnostyka początku/końca odzyskiwania oraz przyczyny authentication_required. Test rzeczywistego zapisu JSONL potwierdza pola korelacji i brak syntetycznego sekretu.
- [x] Zakresowe testy: 79 zaliczonych w pierwszym pełnym przebiegu zakresowym; po rozszerzeniu nowe odzyskiwanie 9/9 i kolejność workera 8/8. Liczby nakładają się, nie są sumą unikalnych testów.
- [x] Pełna regresja finalnych źródeł: 505 testów, 503 zaliczone, 2 pominięcia środowiskowe (fokus Windows i symlink), bez niezaliczonych modułów i błędów callbacków (`build/section-login-full.json`). Składnia 136 plików Python/PYW, pip check i diff: OK.
- [x] Osobny build istniejącym PyInstallerem 6.22.3; porównano 55 modułów, launcher i 4 zasoby ze źródłami. Offline smoke kandydata: UI/Chromium/walidacja startu OK na tymczasowym LOCALAPPDATA (`build/section-login-candidate-smoke.json`).
- [x] Przed podmianą potwierdzono brak procesu monitora. Główna paczka `dist/Neto Incident Monitor/` zaktualizowana; SHA-256 EXE zgodne z kandydatem. Wcześniejszy pakiet zachowano w `build/section-login-previous/Neto Incident Monitor/`. Ponowny offline smoke głównego EXE 1.9.1: OK (`build/section-login-main-smoke.json`); EXE obecny po próbie.

Bez zmiany numeru 1.9.1 i publikacji GitHub; opublikowany ZIP pozostaje wcześniejszym artefaktem. Nie ingerowano w aktywny monitor ani jego przeglądarkę. Brak nowego odbioru rzeczywistego ServiceNow/SSO. Naprawa dotyczy lokalnego odzyskiwania, nie ustala przyczyny żądania uwierzytelnienia przez ServiceNow. [Decyzja 019](../../decyzje/019-odzyskiwanie-sesji-sekcji.md).

Późniejsze zlecenie publikacji stabilnej poprawki opisuje [wydanie 1.9.2](wydanie-1.9.2.md). Powyższy brak publikacji dotyczy pierwotnego etapu lokalnego.
