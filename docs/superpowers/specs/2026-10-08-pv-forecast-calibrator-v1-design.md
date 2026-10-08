# PV Forecast Calibrator 1.0.0 - specyfikacja

## Cel

PV Forecast Calibrator jest aplikacją Home Assistant OS, która zapisuje przed rozpoczęciem produkcji prognozę dobową z Forecast.Solar i Solcast, uczy się na rzeczywistej produkcji lokalnej oraz publikuje jedną konserwatywnie skorygowaną prognozę produkcji PV.

## Źródła danych

Aplikacja czyta bezpośrednio trzy encje skonfigurowane przez użytkownika:

- prognozę dobową Forecast.Solar;
- prognozę dobową Solcast wraz z atrybutami `estimate`, `estimate10` i `estimate90`;
- dzienną produkcję PV.

Poranna próbka jest zapisywana domyślnie o 04:20 w `Europe/Warsaw`. Dopuszczalne próby ponowienia kończą się o konfigurowanej godzinie granicznej, domyślnie 04:45. Po tej godzinie aplikacja nie traktuje odświeżonej prognozy śróddziennej jako prognozy całego dnia.

## Modele

Z zapisu porannego powstaje siedem modeli:

- FPV - stan encji Forecast.Solar;
- SPV - `estimate` encji Solcast;
- SPV L - `estimate10` encji Solcast;
- SPV H - `estimate90` encji Solcast;
- SPV/L - średnia SPV i SPV L;
- SPV L/H - średnia SPV L i SPV H;
- SPV/H - średnia SPV i SPV H.

Wszystkie siedem modeli jest zapisywanych do lokalnej historii. W wersji 1.0.0 publiczna prognoza korzysta z SPV jako bezpiecznego punktu odniesienia. Pozostałe modele tworzą historię potrzebną do dalszego rozwoju selektora.

## Kalibracja

Reszta historyczna ma postać `produkcja-SPV`. Kandydat korekty jest ważonym czasowo kwantylem reszt:

- przeszacowanie ma koszt 2 razy większy niż takie samo niedoszacowanie;
- odpowiadający kwantyl wynosi `1/(1+2)`;
- nowsze dni mają współczynnik zaniku 0,93;
- korekta może tylko obniżyć SPV;
- korekta nie może być mniejsza niż -1,0 kWh.

Korekta zostaje zastosowana dopiero po testach kroczących. Każda próbka testowa może korzystać wyłącznie z dni wcześniejszych. Korekta musi jednocześnie uzyskać niższy średni koszt asymetryczny i nie wyższy MAE niż surowy SPV. W przeciwnym razie aplikacja publikuje surowy SPV.

Pierwsze 5 kompletnych dni stanowi historię treningową. Do aktywacji korekty potrzeba następnie co najmniej 3 próbek testu kroczącego. Wcześniej stan modelu to `learning`.

## Rozliczenie dnia

Aplikacja śledzi najwyższą liczbową wartość dziennej produkcji. Domyślnie o 23:00 zamyka dzień, zapisuje produkcję, błąd prognozy oraz metryki. Po restarcie może odtworzyć najwyższą wartość produkcji z historii Home Assistant. Stan `unknown` i `unavailable` jest pomijany.

## Encje MQTT

Aplikacja nie duplikuje encji źródłowych. MQTT Discovery tworzy:

- skorygowaną prognozę PV na dzisiaj;
- zastosowaną korektę;
- produkcję PV poprzedniego dnia;
- podpisany błąd poprzedniego dnia, gdzie wartość dodatnia oznacza przeszacowanie;
- MAE z 7 dni;
- MAE z 30 dni;
- liczbę kompletnych dni;
- stan modelu;
- czas ostatniej aktualizacji.

Stany modelu:

- `learning` - za mało danych do bezpiecznej kalibracji;
- `calibrated` - korekta przeszła bramkę testu kroczącego;
- `fallback_spv` - korekta nie poprawia wyniku i publikowany jest SPV;
- `missing_snapshot` - brak pełnej porannej próbki;
- `source_error` - błąd odczytu lub walidacji źródła.

## Trwałość i odporność

- Stan jest zapisywany atomowo w `/data/state.json`.
- Ponowne wykonanie porannego zadania tego samego dnia nie nadpisuje próbki.
- Rekordy są ograniczone do konfigurowanej liczby dni, domyślnie 370.
- Błąd Forecast.Solar nie blokuje SPV, lecz pozostawia FPV jako brakujące.
- Błąd podstawowych wartości Solcast blokuje próbkę, ponieważ SPV jest punktem odniesienia.
- MQTT używa retained discovery, retained stanu oraz availability z Last Will.

## Konfiguracja

Ustawienia aplikacji zawierają encje źródłowe, strefę czasową, godzinę próbki, godzinę graniczną, godzinę zamknięcia dnia, koszt przeszacowania, maksymalną korektę, zanik wag, minimalną historię, minimalną walidację, limit historii, tematy MQTT, nazwę urządzenia i poziom logowania.

## Granice wersji 1.0.0

- Brak Ingressu i własnego panelu.
- Brak sterowania falownikiem lub baterią.
- Brak śróddziennego przeliczania prognozy całodniowej.
- Brak automatycznego wyboru jednego z siedmiu modeli jako prognozy publicznej bez potwierdzonej przewagi w testach kroczących.

