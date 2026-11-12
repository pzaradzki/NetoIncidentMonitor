# 028 — Odsłonięcie głównego okna po logowaniu

**Status.** Przyjęta i odtworzona w źródłach z oryginalnych poprawek. Powtórzono natywną próbę odsłonięcia i przywrócenia. Ręczny odbiór przycisku na pasku zadań pozostaje otwarty w [planie odzyskania](../plany/odzyskanie-zmian-po-v1.10.0.md).

**Decyzja.** Po pokazaniu głównego okna jedna ścieżka przywraca i aktywuje jego ramkę Windows, a osobny pomiar sprawdza odsłonięcie. Ta decyzja uzupełnia [025](025-wspolna-sesja-servicenow.md) bez zmiany cyklu logowania.

**Powód.** Okno może być aktywne i przyjmować fokus klawiatury Tk, a mimo to być całkowicie zasłonięte. Wtedy test samego fokusu daje fałszywe potwierdzenie widoczności, a pasek zadań traktuje monitor jak aktywne okno.

**Realizacja.** Zdarzenia mapowania i fokusu obserwują też aktywację przez Windows. Jeżeli jedno obce okno z flagą „zawsze na wierzchu” zasłania aktywny monitor w próbkowanych punktach, monitor jest podnoszony tylko do utraty aktywności, minimalizacji, ukrycia lub zamknięcia. Nie są zmieniane obce okna. Diagnostyka zapisuje zmianę, ocenę odsłonięcia i potwierdzenie aktywacji bez tytułów okien, ich uchwytów i identyfikatorów procesów.

**Ograniczenia.** Odsłonięcie jest oszacowaniem z punktów wewnątrz ramki. Start zminimalizowany oraz ponowne logowanie w tle nie wymuszają aktywacji. [Pozycja okien Windows](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowpos).
