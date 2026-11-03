# Analizy i eksperymenty

Dokumenty historyczne: opisują obserwacje i hipotezy z danego etapu. Nie są bieżącą listą braków ani zgodą na ponowne wdrożenie. Obecny stan: [architektura](../../architektura.md); wyniki wdrożenia: [weryfikacja](../../weryfikacja/README.md).

| Analiza | Rola |
| --- | --- |
| [Ukryte Chromium — pierwsza seria](ukryte-chromium-dashboard.md) | 32 odczyty i początkowe ograniczenia widoczności |
| [Rozwiązanie ukrytego Chromium](ukryte-chromium-rozwiazanie.md) | Warianty, prototyp i uzasadnienie 007 |
| [Audyt logowania](stabilizacja-logowania-analiza.md) | Problemy L1–L10 przed stabilizacją |
| [Badania ukrytego logowania](logowanie-ukryte-chromium-badania.md) | Porównanie metod i dowody prowadzące do 009 |
| [Audyt odczytu filtrów INC/REQ/RITM/SCTASK](filtry-odczyt-audyt.md) | 20 rzeczywistych prób, 86 testów zakresowych oraz kontrprzykłady walidacji i zapisu; priorytety aktualizacji, bez wdrożenia |
| [Audyt stanu i ustawień podczas monitoringu](stan-i-ustawienia-audyt.md) | Kolejki, Stop, zmiany filtrów i kanałów oraz zamykanie aplikacji |

Nie usuwaj nieudanych prób lub ograniczeń tylko dlatego, że późniejszy wariant zadziałał. Nowy stan dopisuj z datą albo opisz w nowym raporcie.

## Obserwacje listy zagrożeń SLA

[Lista zagrożonych incydentów i powiadomienia](zagrozone-lista-powiadomienia-analiza.md) — wznowiono 2 listopada: potwierdzono nowoczesną listę i 3+3 próby pustego wyniku widoczne/ukryte. Opracowano [plan](../../plany/zakonczone/lista-zagrozonych-i-powiadomienia.md); późniejszy odbiór jednej strony zapisano w tym planie. Paginacja ma osobny plan.
