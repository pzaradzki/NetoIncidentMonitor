# Wydanie 1.9.0

Status: przygotowanie wydania, 4 listopada 2026.

- [x] Sprawdzić poprzednie wydanie i dostępność tagu: najnowsze 1.8.1, v1.9.0 wolny.
- [x] Ustawić numer 1.9.0 i opisać zmiany oraz ograniczenia.
- [x] Uruchomić pełną regresję Windows w osobnych procesach: 65 modułów, 465 testów, 463 zaliczone i 2 pominięte.
- [ ] Zapisać kontrolowane zmiany w Git, bez lokalnych notatek, logów i danych użytkownika.
- [ ] Zbudować pakiet i potwierdzić zgodność modułów, launchera i zasobów z commitem.
- [ ] Utworzyć nowy ZIP, sprawdzić integralność i rozpakowany EXE na osobnych danych.
- [ ] Opublikować tag i wydanie z nowym ZIP-em.
- [ ] Pobrać opublikowaną paczkę i potwierdzić SHA-256 oraz najnowsze wydanie.

Wyniki będą uzupełniane po wykonaniu kontroli. Opis zmian: [1.9.0](../wersje/v1.9.0.md).

Pierwszy przebieg wykrył różnicę kodowania `!` w długim adresie. Przywrócono jego dotychczasowy zapis, zachowując dekodowane wartości i zgodność opakowanego adresu z bezpośrednim. Ponowiono pełną regresję finalnego kodu. Błąd końcowego sprzątania testu ukrytego Chromium poprawiono przez tolerowanie już zamkniętego kontekstu w teardown; asercje zachowania pozostały bez zmian, a moduł przeszedł osobno po zakończeniu pozostałych procesów. Pierwsze wyniki i logi ponowień zachowano lokalnie.

Pominięcia dotyczą braku uprawnienia do tworzenia dowiązania symbolicznego w teście resetu oraz nieudzielenia fokusu przez Windows w teście okna. Pozostałe próby resetu i okna wykonano. Logi i raporty testów nie są częścią wydania.
