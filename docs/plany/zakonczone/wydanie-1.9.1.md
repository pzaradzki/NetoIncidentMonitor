# Wydanie 1.9.1

Status: przygotowanie, 4 listopada 2026. Publikacja zatwierdzona przez użytkownika.

- [x] Potwierdzić najnowsze wydanie 1.9.0 i brak tagu v1.9.1.
- [x] Ustawić numer 1.9.1 i opisać zatwierdzone zmiany po 1.9.0 oraz ograniczenia.
- [x] Pełna regresja finalnej wersji: 495 testów, 493 zaliczone, 2 pominięcia środowiskowe (fokus Windows i symlink), bez niezaliczonych modułów i błędów callbacków Tk (`build/release-1.9.1-tests.json`).
- [x] Kontrola składni, pip check i diff: OK. Commit obejmuje kontrolowane pliki bez prywatnych notatek i danych.
- [x] Build głównej paczki istniejącym PyInstallerem 6.22.3; zgodność 55 modułów, launchera i 4 zasobów ze źródłami przygotowanymi do commita.
- [x] Nowy ZIP: 1441 plików, kontrola CRC i porównanie wszystkich plików po rozpakowaniu. Brak konfiguracji, historii, logów i profilu użytkownika. Offline smoke UI/Chromium i walidacji startu na osobnych danych: OK, wersja 1.9.1 (`build/release-1.9.1-smoke.json`).
- [ ] Publikacja commita, tagu i wydania z ZIP-em na wzór 1.9.0.
- [ ] Ponowne pobranie załącznika, zgodność SHA-256 i potwierdzenie latest.

Opis zmian: [1.9.1](../../wersje/v1.9.1.md). Bez zmian schematów i zależności. Bez nowego odbioru rzeczywistego ServiceNow/SSO. Retencja outbox i lokalizacja logów źródłowych wymagają osobnej decyzji; optymalizacje wydajności odłożono do pomiarów.

Paczka `Neto.Incident.Monitor.zip`: 269206217 bajtów. SHA-256: `130602fd0aaf288e6b2bd8c60f4e6bfec2213f68bb851d53f2b7f6a553fa9e20`. Lokalnie: `dist/Neto Incident Monitor.zip` i główna paczka `dist/Neto Incident Monitor/`.
