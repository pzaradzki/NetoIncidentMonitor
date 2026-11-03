# Raporty weryfikacji

Raport zachowuje zakres i wersję swojej serii. Wynik testów źródeł, prawdziwej strony, gotowego EXE i publikacji to różne dowody.

| Raport | Zakres |
| --- | --- |
| [Dashboard i zagrożenia](odbior-stabilizacji-dashboardu.md) | Czytniki, kontekst, ponowienia, aktualność i cache |
| [Ukryty dashboard](odbior-ukrytego-dashboardu.md) | Wdrożenie renderowania 007 i rzeczywiste odczyty |
| [Logowanie](odbior-stabilizacji-logowania.md) | Końcowy zestaw 388 testów (1 pominięty), natywny pipeline, autofill, Stop i granice realnego SSO |
| [Syntetyczny projekt zagrożeń](../archiwum/scenariusze-projektowe-zagrozen-sla.md) | 32 scenariusze / 60 kroków izolowanego modelu; bez implementacji i bez odbioru aplikacji |
| [Lokalny build 1.8.1](../wersje/v1.8.1.md) | Test offline, migracja na kopii i cykl pracy potwierdzony przez użytkownika |
| [Audyt PingID](audyt-mfa-2026-11-03.md) | Pomiar bazowy i granice diagnostyki |
| [Lokalny build 1.8.0](../wersje/v1.8.0.md#lokalny-build--2-listopada-2026) | Offline EXE/UI/Chromium i zgodność 53 modułów oraz launchera; bez publikacji |

Wyniki paginacji na stronach 20/100 rekordów zapisano w [zakończonym planie](../plany/zakonczone/stabilizacja-paginacji.md). Surowe logi i lokalne manifesty są w ignorowanym `data/`, nie w dokumentacji lub wydaniu.
