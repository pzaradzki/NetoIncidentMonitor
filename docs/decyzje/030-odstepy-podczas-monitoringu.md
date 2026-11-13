# 030 — Odstępy odczytów podczas monitoringu

**Status.** Zasady harmonogramu obowiązują w źródłach po wydaniu 1.11.0. Przycisk zapisu zastąpiła [decyzja 031](031-automatyczny-zapis-odstepow.md). Decyzja uzupełnia [decyzję 025](025-wspolna-sesja-servicenow.md).

**Decyzja.** Przycisk **Zapisz odstępy** zapisuje wartości dla INC i zgłoszeń katalogowych razem. Minimum dla obu wynosi 15 sekund. Wątek sesji przyjmuje ostatnią zapisaną zmianę i pozwala rozpoczętej partii dobiec końca.

**Powód.** Interwał ustala termin następnego odczytu, więc jego zmiana może obowiązywać po bieżącej pracy bez zatrzymywania sesji.

**Realizacja.** Tk przekazuje parę wartości po udanym zapisie. `Schedule` budzi wątek sesji, a ten zmienia terminy na granicach odczytów. Dla trwającej partii nowy odstęp liczy się od jej zakończenia. Dla oczekującej partii termin liczy się od zakończenia poprzedniej. Jeśli nowy termin minął, harmonogram wykonuje jeden zaległy odczyt. Diagnostyka odnotowuje wynik zapisu i przyjęcie wartości przez wątek bez wpisywania nieprawidłowego tekstu z pól.

**Ograniczenia.** Dostępność jednej karty i wcześniejsze zlecenia nadal mogą opóźnić odczyt. Ustawienie dotyczy INC i zgłoszeń katalogowych. Zagrożenia SLA mają osobny termin.
