# Historia zmian

## 1.0.1

- Naprawiono przejmowanie końcowej produkcji poprzedniego dnia przed opóźnionym resetem licznika dziennego.
- Odzyskiwanie produkcji z historii zaczyna się od godziny porannej próbki zamiast od północy.
- Istniejące rekordy z wersji 1.0.0 są uzgadniane z historią Home Assistant i dopiero po potwierdzeniu trafiają do uczenia.
- Rozbudowano logi INFO o konfigurację, poranną próbkę, postęp uczenia, bramkę jakości, uzgodnienie historii i zamknięcie dnia.
- Rozbudowano logi DEBUG o każdy cykl, odczyty produkcji i publikowany pakiet MQTT.

## 1.0.0

- Bezpośredni odczyt Forecast.Solar, Solcast i dziennej produkcji PV.
- Zapis niezmiennej próbki prognozy przed rozpoczęciem produkcji.
- Siedem lokalnie porównywanych modeli prognozy.
- Konserwatywna korekta SPV z karą 2:1 za przeszacowanie.
- Ograniczenie korekty do maksymalnie 1 kWh w dół.
- Test kroczący i automatyczny powrót do surowego SPV.
- Trwała historia oraz odzyskiwanie produkcji po restarcie.
- Dziewięć encji MQTT Discovery bez duplikowania źródeł.
