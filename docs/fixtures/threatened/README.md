# Syntetyczna specyfikacja zagrożeń

To materiał projektowy, **nie czytnik ServiceNow ani wdrożenie aplikacji**. `scenarios.json` opisuje wejścia i niezależnie zapisane oczekiwane wyniki. `reference_model.py` to izolowany model reguł do sprawdzenia spójności projektu; aplikacja go nie importuje.

Uruchomienie z katalogu projektu:

```powershell
.\.venv\Scripts\python.exe docs/fixtures/threatened/reference_model.py
```

Wszystkie identyfikatory, wartości i czasy są syntetyczne. Nie ma HTML, selektorów, adresów zgłoszeń, profilu ani transportu sieciowego. Strona jest tu reprezentowana abstrakcyjnym wynikiem adaptera, którego rzeczywisty kontrakt wymaga dalszej obserwacji.

Model sprawdza obecność/historię, ponowne pojawienia, wybór jednej umowy oraz odrzucanie jawnie niekompletnych stron. Metadane zakresów są **wymaganiem projektowym**, nie potwierdzonym formatem nowoczesnego pagera. Nie testuje parsowania czasu, DOM, działania dysku, logów aplikacji, wysyłek lub ukrytego Chromium. Sukces nie jest odbiorem produktu.

Przy implementacji wykorzystać te same scenariusze przeciw rzeczywistemu modelowi aplikacji przez adapter testowy. Nie przenosić drugiego modelu do kodu produkcyjnego. Nie dodawać fikcyjnych selektorów dla brakujących realnych wierszy.
