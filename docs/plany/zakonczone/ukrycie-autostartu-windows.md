# Ukrycie autostartu Windows

Status: zakończone w źródłach i głównej paczce lokalnej, 4 listopada 2026. Bez publikacji.

Zakres: usunięto z ustawień wiersz i przełącznik uruchamiania aplikacji przy starcie Windows. Automatyczny start monitoringu, start ze zminimalizowanym oknem i zasobnik pozostają dostępne. Zachowano wewnętrzne zmienne, zapis/odczyt rejestru, naprawę istniejącego wpisu po przeniesieniu oraz usuwanie przy resecie. Nie zmieniano schematów, zależności ani wersji.

Domyślny stan był i pozostaje wyłączony: brak wpisu Run zwraca disabled i nie uruchamia rejestracji. Test obejmuje wariant źródłowy oraz EXE. Ukrycie opcji nie usuwa istniejących wpisów; ich dotychczasowa obsługa pozostaje zgodna z żądaniem zachowania funkcjonalności. Lokalna kontrola tylko obecności wpisów potwierdziła brak obu wpisów Neto; rejestru nie zmieniano.

Weryfikacja:
- Nowy test UI przed zmianą wykazał obecność przełącznika. Po zmianie sprawdza jego brak dla stanów disabled/current/repaired/unknown oraz obecność pozostałych opcji startowych i brak zapisu rejestru przy budowie UI.
- Testy zakresowe: 20 testów, 1 pominięcie środowiskowe; bez błędów (`build/autostart-focused.json`).
- Pełna regresja: 495 testów, 493 zaliczone, 2 pominięcia środowiskowe (fokus okna i symlink), bez niezaliczonych modułów ani błędów callbacków (`build/autostart-full.json`).
- Składnia zmienionych modułów, pip check i git diff --check: OK.
- Główna paczka `dist/Neto Incident Monitor/` przebudowana istniejącym PyInstallerem i specyfikacją. Offline smoke na izolowanym LOCALAPPDATA: UI, Chromium i walidacja startu OK; EXE obecny po próbie (`build/autostart-smoke.json`). Bez publikacji.

Diagnostyka: zachowano istniejące komunikaty odczytu/naprawy autostartu; ukrycie kontrolki nie dodaje nowej operacji ani nowych pól logowania. Testy rejestracji nadal używają mocków i osobnego klucza testowego, bez zapisów rzeczywistego autostartu.
