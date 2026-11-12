# 026 — Potwierdzenie zapisu poświadczeń w Chromium

12 listopada 2026. **Status.** Przyjęta, wdrożona w źródłach.

**Decyzja.** Gdy użytkownik ręcznie wpisze hasło podczas włączonego autologowania, po potwierdzeniu sesji Chromium pozostaje widoczne do wyboru **Zapisano** lub **Wyłącz autologowanie**. Obowiązuje przy pierwszym logowaniu i odzyskiwaniu sesji. To uzupełnia regułę ukrycia okna z [decyzji 025](025-wspolna-sesja-servicenow.md).

**Powód.** Użytkownik potrzebuje dostępu do komunikatu Chromium o zapisie hasła, który może pojawić się po przekierowaniu.

**Realizacja.** Strażnik logowania przekazuje wyłącznie sygnał zaufanego zdarzenia wpisywania w polu hasła. Sygnał obowiązuje w ramach bieżącego logowania. `SharedSession` czeka na decyzję Tk przed ukryciem Chromium i udostępnieniem karty. **Wyłącz autologowanie** zapisuje preferencję przed zakończeniem oczekiwania. Wspólna sesja pomija flagę wyłączającą natywną propozycję zapisu Chromium. [Kod Chromium](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/chrome/browser/password_manager/chrome_password_manager_client.cc).

**Ograniczenia.** Przechowywaniem poświadczeń zarządza Chromium zgodnie z ustawieniami profilu i zasadami organizacji. **Zapisano** przyjmuje decyzję użytkownika.
