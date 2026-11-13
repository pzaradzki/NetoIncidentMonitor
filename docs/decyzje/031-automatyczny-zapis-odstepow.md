# 031 — Automatyczny zapis interwałów

**Status.** Przyjęta w źródłach po wydaniu 1.11.0. Zastępuje przycisk zapisu z [decyzji 030](030-odstepy-podczas-monitoringu.md).

**Decyzja.** Oba interwały zapisują się po 5 sekundach od ostatniej edycji. Każda kolejna edycja rozpoczyna odliczanie od nowa. Zamknięcie ustawień przyciskiem, krzyżykiem lub Escape zapisuje zmiany od razu.

**Powód.** Odliczanie daje czas na dokończenie wpisywania liczby. Zamknięcie ustawień pozwala zastosować gotowe wartości bez czekania.

**Realizacja.** Tk odlicza na podstawie zegara monotonicznego i odwołuje poprzednie wywołanie po edycji. Zapis korzysta z dotychczasowej walidacji i przekazuje obie wartości wątkowi sesji po udanym zapisie. Uruchomienie monitoringu używa ostatniej zapisanej pary. Rozpoczęty odczyt dobiega końca zgodnie z regułami decyzji 030.

**Ograniczenia.** W razie błędu ustawienia pozostają otwarte przy próbie zamknięcia. Monitor używa poprzednich wartości, a użytkownik może poprawić dane lub ponowić zapis.
