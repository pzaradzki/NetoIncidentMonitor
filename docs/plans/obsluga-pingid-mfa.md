# Obsługa kodu PingID w logowaniu ServiceNow

**Status planu** — do realizacji. Celem jest szybkie przekazanie formularza kodu użytkownikowi, również gdy Chromium było ukryte po automatycznym zatwierdzeniu hasła. Po ręcznym ukończeniu weryfikacji monitoring wraca do pracy po potwierdzeniu sesji ServiceNow.

Dotychczasowe 125 ms dotyczy ogólnej klasyfikacji strony zewnętrznego dostawcy. Pomiar 109 ms dotyczy pokazania pierwszego ekranu logowania. Zrzut dokumentuje wariant kodu e-mail, a test syntetyczny potwierdza pokazanie i fokus okna dla standardowego pola `one-time-code`. Bazowe czasy rzeczywistego formularza i jego struktura pozostają do ustalenia. [Audyt MFA](../verification/audyt-mfa-2026-11-03.md)

## Kolejność prac

1. **Zweryfikować formularz i zmierzyć stan bazowy.** W izolowanym Chromium poza siecią firmową użytkownik przechodzi firmowe logowanie i zatrzymuje się na formularzu kodu. Sprawdzić rzeczywiste pochodzenie, kartę lub ramkę, role i atrybuty kontrolki oraz różnicę między przekierowaniem, oczekiwaniem i gotowym formularzem. Zacząć od wariantu e-mailowego. Jeśli dostępny jest wariant kodu z aplikacji, udokumentować go osobno. Przed próbą sprawdzić na syntetycznym przejściu, że sonda działa w aktywnej pętli logowania i zapisuje zdarzenia do pliku.
2. **Włączyć potwierdzony sygnał do istniejącego obserwatora.** W `login_observation.py` rozpoznawać widoczną kontrolkę kodu w potwierdzonym kontekście PingID. Ustalić selektory na podstawie pomiaru. Sygnał ma oznaczać ręczną obsługę i przetrwać przejściowe przekierowania tej próby. Zachować istniejącą granicę automatycznych akcji. Kod i jego zatwierdzenie pozostają po stronie użytkownika. [Decyzja 008](../decisions/008-obserwacja-logowania.md)
3. **Przekazać okno przez istniejący koordynator i BrowserRuntime.** Po wykryciu zatrzymać automatyczne akcje i pomocnicze renderowanie logowania, pokazać właściwe okno oraz poprosić Windows o fokus. Status ma wskazywać konieczność wpisania kodu PingID. Widoczność i fokus potwierdzać osobno. Jeśli system odmówi fokusu, zachować widoczne okno i sprawdzić działanie istniejącej opcji „Pokaż przeglądarkę”. Po pozytywnym potwierdzeniu sesji przywrócić ustawienia widoczności monitoringu. [Decyzja 009](../decisions/009-renderowanie-ukrytego-logowania.md)
4. **Odebrać zmianę na rzeczywistym ServiceNow.** Powtórzyć porównywalne próby przed zmianą i po niej. Kluczowy przebieg zaczyna się z ukrytym oknem i automatycznie przechodzi etap hasła, a PingID żąda kodu. Sprawdzić też już widoczne okno, ręczne logowanie, działającą sesję bez MFA oraz powrót monitoringu po ręcznym zatwierdzeniu kodu. Gdy warunki pozwolą, zebrać trzy porównywalne przebiegi dla kluczowej ścieżki. Raportować liczebność, medianę i najdłuższy czas. Brak próby z realnym PingID w ukrytym oknie pozostawia odbiór tej ścieżki otwarty.

## Pomiar i kryteria odbioru

- Użyć zegara monotonicznego i odnotować osobno nawigację, pierwszą potwierdzoną gotowość formularza, rozpoznanie MFA, pierwszą widoczność, fokus i potwierdzenie sesji. W widocznym oknie mierzyć rozpoznanie bez przypisywania mu odsłonięcia. Czas wpisywania kodu podawać oddzielnie.
- Oczekiwane zachowanie to reakcja w pierwszym cyklu, w którym formularz spełnia potwierdzone kryteria. Docelowy próg czasu ustalić po pomiarze bazowym. Porównać opóźnienie rozpoznania z czasem pokazywania okna. Interwał odpytywania zmieniać tylko wtedy, gdy pomiary wykażą jego istotny udział.
- Testy lokalne pokrywają opóźnione pojawienie się formularza, przekierowanie bez MFA, pole kodu poza właściwym kontekstem, odmowę fokusu, anulowanie i potwierdzoną sesję. Wyniki syntetyczne i rzeczywiste zapisać oddzielnie.
- Wspólna diagnostyka zapisuje identyfikator próby, etap, czasy, wynik widoczności i fokusu. Zweryfikować zapis do pliku oraz brak syntetycznych sekretów. W pomiarze rzeczywistym zbierać wyłącznie potrzebne metadane, bez wartości formularzy, danych konta i pełnych adresów przekierowań. [Zasady diagnostyki](../decisions/004-bezpieczna-diagnostyka.md)

## Checklista postępu

- [x] Zebrano wyniki wcześniejszego audytu i rozdzielono pomiar ogólnego logowania od pomiaru MFA.
- [x] Zweryfikować sondę w aktywnej pętli logowania i zapis metadanych do pliku.
- [x] Zaobserwowano rzeczywisty formularz e-mail. Sonda wykryła pole o limicie sześciu znaków, instrukcję i opcję ponownej wysyłki. Pole nie używało autocomplete one-time-code. Okno było już widoczne podczas pomiaru.
- [x] Dodano rozpoznawanie zaobserwowanej kombinacji sygnałów i podłączono ją do istniejącej ścieżki ręcznej obsługi.
- [ ] Przejść testy regresji i odebrać poprawkę na rzeczywistym ServiceNow.

### Próby po poprawce

- [x] Regresja obserwatora i natywnego okna Chromium na Windows. Przeszło 16 testów.
- [x] Rzeczywista sesja bez żądania kodu. Zapisany profil potwierdził sesję po 2,6 s. Okno pozostało ukryte w zarejestrowanych obserwacjach.
- [ ] Rzeczywiste żądanie kodu po automatycznym przejściu hasła w ukrytym oknie. W powyższej próbie dostawca nie wyświetlił PingID.

- [x] Rzeczywisty PingID po resecie cookies. Pierwszy sygnał interwencji w 26,484 s od startu, potwierdzenie widoczności i fokusu w 26,500 s. Użytkownik wpisał kod. Sesja gotowa i okno ponownie ukryte po zakończeniu próby w 48,3 s.
- [ ] Pomiar odsłonięcia okna wyłącznie przez PingID. W tej próbie okno pokazano wcześniej do ręcznego logowania.

- [x] Po przygotowaniu profilu i ręcznym podaniu identyfikatora aplikacja automatycznie zatwierdziła hasło w 18,235 s. PingID wykryto w 19,828 s, a widoczność i fokus potwierdzono 32 ms później. Sesję potwierdzono w 41,594 s po ręcznym wpisaniu kodu. Okno pokazano już wcześniej przy identyfikacji konta.
