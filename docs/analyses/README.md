# Analizy i eksperymenty

Dokumenty historyczne: opisują obserwacje i hipotezy z danego etapu. Nie są bieżącą listą braków ani zgodą na ponowne wdrożenie. Obecny stan: [architektura](../architecture.md); wyniki wdrożenia: [weryfikacja](../verification/README.md).

| Analiza | Rola |
| --- | --- |
| [Ukryte Chromium — pierwsza seria](ukryte-chromium-dashboard.md) | 32 odczyty i początkowe ograniczenia widoczności |
| [Rozwiązanie ukrytego Chromium](ukryte-chromium-rozwiazanie.md) | Warianty, prototyp i uzasadnienie 007 |
| [Audyt logowania](stabilizacja-logowania-analiza.md) | Problemy L1–L10 przed stabilizacją |
| [Badania ukrytego logowania](logowanie-ukryte-chromium-badania.md) | Porównanie metod i dowody prowadzące do 009 |
| [Powiadomienia e-mail przez SMTP](powiadomienia-email-smtp.md) | Udany test relay na porcie 25 z STARTTLS bez AUTH i potwierdzone dostarczenie; ograniczenia i potencjalna funkcja, bez wdrożenia |
| [Audyt odczytu filtrów INC/REQ/RITM/SCTASK](filtry-odczyt-audyt.md) | 20 rzeczywistych prób, 86 testów zakresowych oraz kontrprzykłady walidacji i zapisu; priorytety aktualizacji, bez wdrożenia |

| [Audyt stanu i ustawień podczas monitoringu](stan-i-ustawienia-audyt.md) | Kolejki, Stop, zmiany filtrów i kanałów oraz zamykanie aplikacji |

Nie usuwaj nieudanych prób lub ograniczeń tylko dlatego, że późniejszy wariant zadziałał. Nowy stan dopisuj z datą albo opisz w nowym raporcie.

## Analiza bieżąca

[Lista zagrożonych incydentów i powiadomienia](zagrozone-lista-powiadomienia-analiza.md) — wznowiono 2 listopada: potwierdzono nowoczesną listę i 3+3 próby pustego wyniku widoczne/ukryte. Opracowano [plan](../plans/lista-zagrozonych-i-powiadomienia.md); niepuste rekordy, zakres źródła i paginacja wymagają dalszego potwierdzenia przed wdrożeniem.
