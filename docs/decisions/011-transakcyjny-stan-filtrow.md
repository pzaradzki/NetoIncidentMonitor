# 011 — Wspólny magazyn historii i obecności filtrów

3 listopada 2026. **Status: przyjęta, wdrożona w źródłach dla historii, obecności i automatycznych alertów filtrów.**

**Decyzja.** Używamy lokalnej bazy SQLite z osobnymi tabelami historii i obecności w jednej transakcji. Zachowujemy fasadę History i nie zapisujemy po przełączeniu równoległych kopii JSON.

**Powód.** Na 20 000 syntetycznych wpisów zapis po oznaczeniu jednego wpisu jako przeczytanego trwał 311 ms w prototypie JSON i 12 ms w SQLite. Pierwszy zapis w SQLite trwał 211 ms, niezmieniony odczyt 18 ms. Są to pojedyncze pomiary lokalne.

**Realizacja.** Pierwszy udany zapis odczytu tworzy schemat, znacznik wersji i dane w jednej transakcji. Stare pliki zostają na dysku. Po uaktywnieniu bazy odczyt korzysta tylko z niej. Próba wymuszonej awarii po zapisie historii i przed zapisem obecności potwierdziła rollback po ponownym otwarciu.

**Ograniczenia.** Cofnięcie wersji do dawnych plików nie odtworzy nowszych zmian z bazy. Migracja kopii danych projektu zachowała 933 wpisy historii i stan 9 filtrów. Trwała kolejka wznawia po restarcie oczekujące zadania. Rozpoczętą wysyłkę bez wyniku oznacza jako niepewną i pomija automatyczne ponowienie. Wspólna rewizja ustawień powiadomień chroni przed wysłaniem oczekującego zadania pod zmieniony adres, również po przywróceniu poprzedniej konfiguracji. Stan odbioru opisuje [plan](../plans/stabilizacja-odczytu-filtrow.md).
