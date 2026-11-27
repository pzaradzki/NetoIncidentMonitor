# 051 — Cichy wynik sprawdzenia aktualnej wersji przy starcie

**Status.** Przyjęta i wdrożona w źródłach. Aktualizuje zasady prezentacji z [decyzji 050](050-aktualizacje-przy-starcie.md).

**Decyzja.** Gdy automatyczne sprawdzenie potwierdzi aktualną wersję, kończy się zapisem wyniku w diagnostyce. Ręczne sprawdzenie pokazuje dotychczasowy komunikat również wtedy, gdy używa trwającego odczytu startowego.

**Powód.** Przy starcie użytkownik potrzebuje informacji o dostępnej aktualizacji. Potwierdzenie bieżącej wersji jest przydatne, gdy użytkownik świadomie wybierze **Sprawdź aktualizacje**.

**Realizacja.** `ReleaseCheck` rejestruje wynik wspólnego odczytu, a w trybie automatycznym przekazuje do prezentacji dostępną aktualizację albo błąd. Sprawdzenie nadal używa tego samego porównania wersji, jednego odczytu i wspólnego okna wyniku. [Mechanizm](../../neto_incident_monitor/release_check.py) · [Testy](../../tests/test_release_check.py)
