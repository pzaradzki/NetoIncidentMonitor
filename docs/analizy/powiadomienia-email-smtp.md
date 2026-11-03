# Powiadomienia e-mail przez SMTP — rozpoznanie

2 listopada 2026. **Rozpoznanie zakończone; potencjalna funkcjonalność, niewdrożona.** Notatka nie jest zatwierdzonym planem implementacji. Aplikacji, EXE i ZIP nie zmieniano.

## Wynik jednorazowego testu

Na polecenie użytkownika osobny skrypt wysłał jedną wiadomość testową z jego adresu na ten sam adres. Nie używano danych zgłoszeń ani poświadczeń.

| Parametr | Potwierdzone w tej próbie |
| --- | --- |
| Serwer | `IISRelay.pl.corp.leroymerlin.com` |
| Port | TCP 25 |
| Szyfrowanie | STARTTLS; standardowa weryfikacja certyfikatu i nazwy hosta zakończona powodzeniem, bez wyłączania zabezpieczeń |
| Uwierzytelnianie SMTP | Nie używano loginu ani hasła; serwer nie reklamował AUTH w początkowym EHLO |
| Przyjęcie wiadomości | MAIL FROM, RCPT TO oraz zakończenie DATA: kod 250; cała udana próba około 0,8 s |
| Dostarczenie | Użytkownik pokazał otrzymaną wiadomość z tematem testu `[992d2b39]`; potwierdzenie skrzynki jest osobnym dowodem od odpowiedzi SMTP |

Pierwsze połączenie zakończyło się przed MAIL/RCPT/DATA z powodu błędnego przekazania nazwy hosta w skrypcie testowym. Po poprawce wykonano udaną próbę; wysłano jedną wiadomość. Nie był to błąd serwera ani odrzucenie certyfikatu.

Lokalny skrypt: `data/smtp_relay_test.py`; raport udanej próby: `data/smtp-test-result-992d2b39bd234b96af502bfb0618c30d.json`. Katalog `data/` jest ignorowany i nie stanowi części wydania. Pole `delivery_confirmed: false` w raporcie oznacza, że sam skrypt nie sprawdza skrzynki; późniejsze potwierdzenie użytkownika zapisano tutaj, bez zmiany surowego wyniku testu.

## Granice ustaleń

- Sprawdzono jeden komputer i jedną konfigurację sieci, jeden adres nadawcy oraz jednego odbiorcę. Nie dowodzi to dostępu z innych komputerów, spoza sieci firmowej lub przez VPN ani zgody na dowolnego nadawcę/odbiorcę.
- Brak AUTH w udanej próbie nie oznacza otwartego relay dla wszystkich. Reguły dopuszczania klientów (np. adresy IP), domen, limity i dozwolony nadawca wymagają ustalenia z administratorem.
- Nie testowano masowej wysyłki, załączników, HTML, wielu odbiorców, błędów i ponowień. Czas jednej wiadomości nie jest gwarancją wydajności.
- STARTTLS potwierdzono z obecnym systemowym zaufaniem certyfikatów. Inne komputery mogą wymagać odpowiedniego firmowego łańcucha zaufania; nie omijać weryfikacji.

## Możliwy przyszły zakres

Kanał „Powiadomienia e-mail”: globalny przełącznik, konfiguracja nadawcy i odbiorców, SMTP/port/TLS oraz świadomie uruchamiany test wysyłki. Rozważyć wybór kanału per filtr oraz wykorzystanie go dla zagrożeń SLA zgodnie z osobnym planem. Wysyłka w tle, ograniczona kolejka i timeouty, korelacja zadania z wynikiem oraz diagnostyka bez treści wiadomości i danych odbiorców w logach. Nie powtarzać automatycznie niepewnego wysłania po DATA.

Przed implementacją: potwierdzić zasady relay i dostęp z docelowych komputerów, uzgodnić nadawcę/odbiorców i treść, zaprojektować integrację ze wspólnymi mechanizmami powiadomień oraz testy awarii. Osobno zlecić wdrożenie; nie włączać wysyłania domyślnie na podstawie tej próby.
