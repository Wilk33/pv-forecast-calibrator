# PV Forecast Calibrator

## Działanie

Aplikacja zapisuje prognozę dobową przed rozpoczęciem produkcji, a po zakończeniu dnia porównuje ją z rzeczywistą produkcją. Uczy się wyłącznie na dniach wcześniejszych. Nie używa odświeżonej prognozy śróddziennej jako prognozy całego dnia.

Prognozą bazową jest `estimate` z encji Solcast. Aplikacja zapisuje również Forecast.Solar, `estimate10`, `estimate90` i trzy średnie modeli. Aplikacja publikuje SPV z lokalną korektą w dół albo w górę tylko wtedy, gdy test kroczący potwierdza poprawę zarówno kosztu asymetrycznego, jak i MAE.

## Konfiguracja encji

- `forecast_solar_entity` - encja dziennej prognozy Forecast.Solar, zwykle `sensor.energy_production_today`.
- `solcast_entity` - encja dziennej prognozy Solcast posiadająca atrybuty `estimate`, `estimate10` i `estimate90`.
- `production_entity` - encja dziennej produkcji PV, która w ciągu dnia rośnie i po północy się zeruje.

Aplikacja nie wymaga encji pośrednich SPV L, SPV H ani ich średnich.

## Czas

- `snapshot_time` - początek pobierania pełnej prognozy dobowej, domyślnie 04:20.
- `snapshot_deadline` - ostatnia dopuszczalna chwila pobrania, domyślnie 04:45.
- `settlement_time` - chwila zamknięcia dnia, domyślnie 23:00.
- `timezone` - strefa wszystkich harmonogramów, domyślnie `Europe/Warsaw`.

Jeżeli aplikacja zostanie uruchomiona po godzinie granicznej i nie ma zapisanej porannej próbki, ustawi stan `missing_snapshot`. Nie zapisze bieżącej prognozy jako prognozy całego dnia.

## Kalibracja

Domyślne parametry zostały ustalone na podstawie dostarczonej lokalnej historii:

- przeszacowanie jest karane 2 razy mocniej od niedoszacowania;
- korekta może obniżyć albo podwyższyć SPV;
- maksymalne obniżenie i podwyższenie mają osobne limity, domyślnie po 1 kWh;
- nowsze błędy otrzymują większą wagę przez współczynnik zaniku 0,93;
- pierwsze 5 dni tworzy historię treningową;
- wymagane są co najmniej 3 późniejsze próbki testu kroczącego.

Zmiana parametrów w ustawieniach nie usuwa historii. Jeśli nowa korekta nie przejdzie bramki jakości, wynik wraca do surowego SPV i stan zmienia się na `fallback_spv`.

Wynik dzienny jest liczony jako poranna prognoza Solcast SPV plus korekta wyznaczona z wcześniejszych błędów. Ujemna korekta obniża prognozę, a dodatnia ją podwyższa. Parametr `max_downward_correction_kwh` ogranicza obniżenie, a `max_upward_correction_kwh` ogranicza podwyższenie.

## Encje

Aplikacja publikuje przez MQTT Discovery:

- skorygowaną prognozę PV na dzisiaj;
- zastosowaną korektę;
- produkcję poprzedniego dnia;
- podpisany błąd poprzedniego dnia;
- MAE z 7 i 30 dni;
- liczbę kompletnych dni;
- stan modelu;
- czas ostatniej aktualizacji.

Dodatni błąd oznacza przeszacowanie, a ujemny niedoszacowanie.

## Stan modelu

- `learning` - historia jest jeszcze za krótka.
- `calibrated` - korekta przeszła test kroczący.
- `fallback_spv` - bezpieczniejszy jest surowy SPV.
- `missing_snapshot` - brak porannej próbki.
- `source_error` - źródło zwróciło niepełne lub błędne dane.

## Trwałość

Historia znajduje się w `/data/state.json` i jest objęta kopiami zapasowymi aplikacji Home Assistant. Zapis jest atomowy. Wartości `unknown`, `unavailable`, ujemne i niefinitywne są pomijane.

Opcja `reset_history_on_start` jest jednorazowym resetem algorytmu. Po ustawieniu jej na `on` i ponownym uruchomieniu aplikacja usuwa cały plik stanu, w tym historię dni, bieżące maksimum produkcji i stan uczenia. Następnie przez API Supervisora zapisuje tę opcję z powrotem jako `off`. Po resecie model zaczyna od stanu `learning`.

Po aktualizacji z wersji 1.0.0 aplikacja ponownie odczytuje historyczną produkcję od godziny porannej próbki do północy. Rekord jest używany do uczenia dopiero po takim potwierdzeniu. Zapobiega to przejęciu końcowej wartości poprzedniego dnia, gdy dzienny licznik produkcji zeruje się kilka minut po północy.

## Logi

Poziom `INFO` zapisuje uruchomienie, konfigurację, uzgodnienie historii, poranną próbkę, postęp treningu i walidacji, metryki bramki jakości oraz zamknięcie dnia. Poziom `DEBUG` dodatkowo zapisuje każdy cykl, surowy odczyt produkcji, maksimum dzienne i pakiet publikowany przez MQTT.
