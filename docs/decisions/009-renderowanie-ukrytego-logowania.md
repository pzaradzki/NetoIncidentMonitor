# 009 — Renderowanie ukrytego logowania

2 listopada 2026. **Status: przyjęta; wdrożona w źródłach.** Użytkownik najpierw dopuścił test rzeczywistego SSO z klatkami 1×1, następnie zlecił całe wdrożenie A–F.

## Decyzja

Rozszerzamy historyczne wyłączenie uwierzytelniania z [007](007-ukryty-dashboard.md) wyłącznie na rozpoznany własny formularz HTTPS `idpb2e.adeo.com:443`, bez userinfo. `HiddenRendering(scope='login')` współdzieli lifecycle/ACK/sprzątanie z analityką, ma osobną instancję i warunki startu. Parametry są stałe: JPEG quality=0, maxWidth/maxHeight=1, everyNthFrame=60.

To lokalne przechwytywanie klatek, nie „brak przechwytywania”. Payload auth jest natychmiast odrzucany w pamięci bez dekodowania, mierzenia, zapisu, wyświetlenia lub wysyłki do zewnętrznych usług. Diagnostyka zawiera wyłącznie liczbę klatek/ACK, czas, etap i bezpieczny kod błędu.

## Powód

Zwykłe ukrycie dławi gotowość fizycznej akcji. Emulacja fokusu i zmiana silnika nie spełniły kryteriów; alpha=0 miała wyścig widoczności popupów. Na rzeczywistym formularzu z prawdziwym autofill dwie serie po trzy pary dały: widoczne **24/24**, ukryte ze wsparciem **24/24**, ukryte zwykłe **0/24**. Mediana obu sprawnych wariantów: **31 ms**. [Badania i ograniczenia](../analyses/logowanie-ukryte-chromium-badania.md).

## Realizacja i ograniczenia

Start wymaga rozpoznanego uwierzytelniania, ukrycia i braku ingerencji. Każda główna nawigacja kończy poprzedni zakres; nowy dokument jest oceniany ponownie. Ręczna obsługa/auto off/jawne pokazanie, Stop, close, opuszczenie originu i awaria ACK kończą wsparcie. Przy awarii startu/ACK logowanie przechodzi do obsługi widocznej, bez osobnego retry i bez ponowienia dostarczonej/niepewnej akcji. Renderer jest wyłączany przed pokazaniem formularza.

Klatka ani autofill nie potwierdzają sesji lub dostarczenia. Zachowane są zwykłe akcje Playwright, kontrola formularza, jedno zatwierdzenie i dodatni dowód sesji. Bez `force`, syntetycznego submit w produkcji, obchodzenia MFA/TLS, nowych workerów i chowania poza ekran.

API pozostaje eksperymentalne; przyszła zmiana Chromium lub SSO wymaga regresji. Natywny PID/widoczność są uzgadniane po utworzeniu okna; nie gwarantujemy braku pojedynczego mignięcia ikony Windows przed pierwszym dostępnym uchwytem. [Raport odbioru i granice prób](../verification/login-stabilization-verification.md). Nie przebudowano EXE.
