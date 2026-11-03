# Raporty weryfikacji

Raport zachowuje zakres i wersję swojej serii. Wynik testów źródeł, prawdziwej strony, gotowego EXE i publikacji to różne dowody.

| Raport | Zakres |
| --- | --- |
| [Dashboard i zagrożenia](dashboard-stabilization-verification.md) | Czytniki, kontekst, ponowienia, aktualność i cache |
| [Ukryty dashboard](hidden-dashboard-verification.md) | Wdrożenie renderowania 007 i rzeczywiste odczyty |
| [Logowanie](login-stabilization-verification.md) | Końcowy zestaw 388 testów (1 pominięty), natywny pipeline, autofill, Stop i granice realnego SSO |
| [Syntetyczny projekt zagrożeń](threatened-design-scenarios.md) | 32 scenariusze / 60 kroków izolowanego modelu; bez implementacji i bez odbioru aplikacji |
| [Lokalny build 1.8.0](../releases/v1.8.0.md#lokalny-build--2-listopada-2026) | Offline EXE/UI/Chromium i zgodność 53 modułów oraz launchera; bez publikacji |

Wyniki paginacji na stronach 20/100 rekordów zapisano w [zakończonym planie](../plans/completed/stabilizacja-paginacji.md). Surowe logi i lokalne manifesty są w ignorowanym `data/`, nie w dokumentacji lub wydaniu.
