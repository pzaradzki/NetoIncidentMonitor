# Wydanie 1.9.0

Status: publikacja zakończona, 4 listopada 2026.

- [x] Sprawdzić poprzednie wydanie i dostępność tagu: najnowsze 1.8.1, v1.9.0 wolny.
- [x] Ustawić numer 1.9.0 i opisać zmiany oraz ograniczenia.
- [x] Uruchomić pełną regresję Windows w osobnych procesach: 65 modułów, 465 testów, 463 zaliczone i 2 pominięte.
- [x] Zapisać kontrolowane zmiany w Git, bez lokalnych notatek, logów i danych użytkownika.
- [x] Zbudować pakiet i potwierdzić zgodność modułów, launchera i zasobów z commitem.
- [x] Utworzyć nowy ZIP, sprawdzić integralność i rozpakowany EXE na osobnych danych.
- [x] Opublikować tag i wydanie z nowym ZIP-em.
- [x] Pobrać opublikowaną paczkę i potwierdzić SHA-256 oraz najnowsze wydanie.

Opis zmian: [1.9.0](../../wersje/v1.9.0.md).

Pierwszy przebieg wykrył różnicę kodowania `!` w długim adresie. Przywrócono jego dotychczasowy zapis, zachowując dekodowane wartości i zgodność opakowanego adresu z bezpośrednim. Ponowiono pełną regresję finalnego kodu. Błąd końcowego sprzątania testu ukrytego Chromium poprawiono przez tolerowanie już zamkniętego kontekstu w teardown; asercje zachowania pozostały bez zmian, a moduł przeszedł osobno po zakończeniu pozostałych procesów. Pierwsze wyniki i logi ponowień zachowano lokalnie.

Pominięcia dotyczą braku uprawnienia do tworzenia dowiązania symbolicznego w teście resetu oraz nieudzielenia fokusu przez Windows w teście okna. Pozostałe próby resetu i okna wykonano. Logi i raporty testów nie są częścią wydania.

## Wynik publikacji

- Commit i tag: `8b4b73aa57698a594a92a1a2a8f6929b312ee5f0`, `v1.9.0`.
- Zweryfikowano 54 moduły, launcher, 4 zasoby oraz wszystkie 1441 plików paczki. W ZIP brak konfiguracji użytkownika, logów i profilu przeglądarki.
- Rozpakowany EXE przeszedł test offline UI, początkowych teł kafelków i Chromium 153.0.8010.12 na osobnych danych. Wersja pakietu: 1.9.0.
- [Wydanie v1.9.0](https://github.com/pzaradzki/NetoIncidentMonitor/releases/tag/v1.9.0) jest najnowszym stabilnym wydaniem. Załącznik `Neto.Incident.Monitor.zip`, 269194772 bajty.
- SHA-256 lokalnego i ponownie pobranego ZIP-a: `e41729a514f4f115fdc7465c657bfda63fd31b7bdec9c8b3898710f39a8d7fce`.
- Lokalny folder `dist/Neto Incident Monitor` również zaktualizowano do sprawdzonego pakietu. Prywatne lokalne notatki pozostały poza commitem i wydaniem.
