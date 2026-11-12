# 023 — Naturalny rozmiar logowania, ograniczony viewport odczytu

6 listopada 2026. **Status: zasady wyboru osobnej karty zastąpiła [025](025-wspolna-sesja-servicenow.md).** Tymczasowy viewport odczytu i jego przywracanie pozostają w mocy.

**Decyzja:** import nie ustawia stałego viewportu przy uruchomieniu sesji. Po nawigacji najpierw sprawdza uwierzytelnienie, a dopiero przy wejściu w czytnik menu tymczasowo wymusza 751×884 przez CDP Emulation. W finally usuwa override i odłącza sesję CDP. Sukces, błąd, Stop i AuthenticationRequired opuszczają ten sam zakres; odzyskiwanie logowania korzysta z naturalnego rozmiaru. Jeśli wywołujący miał jawny viewport, przywraca się jego ustawienie zamiast naturalnego trybu.

**Powód:** stały rozmiar ustawiony przed pierwszą nawigacją ograniczał również stronę SSO i pozostawiał niewykorzystany obszar okna. Samo ponowne ustawienie rozmiaru pikselowego nie przywraca adaptacyjnego zachowania strony. Naturalny viewport musi nadal reagować na wielkość okna użytkownika.

**Karty:** jedyna startowa karta about:blank jest wykorzystywana jako karta importu. Jeśli kontekst ma inne karty lub więcej niż jedną kartę, tworzy się własną kartę bez zamykania i nawigowania po zastanych. Import nadal jawnie zamyka tylko używaną przez siebie kartę, a następnie własną sesję.

Zastępuje wyłącznie stałe wymuszenie rozmiaru przez całą sesję i bezwarunkowe tworzenie nowej karty z [022](022-import-ulubionych-na-zadanie.md). Pozostałe zasady wyłączności, logowania, budżetu, podglądu i zapisu pozostają w mocy. Monitoring nie otrzymuje nowego mechanizmu rozmiaru ani kart.

**Ograniczenia:** wykrywanie propozycji zapisu hasła i oczekiwanie na użytkownika zostały wyłączone z zakresu na jego polecenie po niepotwierdzonej próbie wykrywania natywnego monitu. Nie dodano odczytu ani zapisu poświadczeń, pauzy lub nowej opcji autologowania. Odczyt menu nadal wymaga znanego wąskiego wariantu UI. [Wyniki i granice weryfikacji](../plany/zakonczone/import-ulubionych-servicenow.md).
