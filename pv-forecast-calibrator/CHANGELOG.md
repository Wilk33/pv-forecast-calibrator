# Historia zmian

## 1.0.0

- Bezpośredni odczyt Forecast.Solar, Solcast i dziennej produkcji PV.
- Zapis niezmiennej próbki prognozy przed rozpoczęciem produkcji.
- Siedem lokalnie porównywanych modeli prognozy.
- Konserwatywna korekta SPV z karą 2:1 za przeszacowanie.
- Ograniczenie korekty do maksymalnie 1 kWh w dół.
- Test kroczący i automatyczny powrót do surowego SPV.
- Trwała historia oraz odzyskiwanie produkcji po restarcie.
- Dziewięć encji MQTT Discovery bez duplikowania źródeł.
