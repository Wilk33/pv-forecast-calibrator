# PV Forecast Calibrator

**Status: wersja 1.2.0 jest gotowa do testów w Home Assistant OS. Aplikacja nie steruje falownikiem ani baterią.**

PV Forecast Calibrator zapisuje przed rozpoczęciem produkcji pełną prognozę dobową Forecast.Solar i Solcast, porównuje siedem modeli z lokalną produkcją PV, wylicza ich dynamiczne wagi i publikuje jedną konserwatywną prognozę przez MQTT Discovery.

## Najważniejsze zachowanie

- czyta bezpośrednio Forecast.Solar, Solcast i dzienną produkcję PV;
- pobiera z Solcast `estimate`, `estimate10` i `estimate90` bez encji pośrednich;
- liczy lokalnie SPV/L, SPV L/H i SPV/H;
- wyznacza osobną wagę każdego z siedmiu modeli na podstawie błędu w kWh;
- zmniejsza wpływ modeli, które często przeszacowują produkcję;
- zapisuje niezmienną próbkę domyślnie o 04:20;
- nie używa prognozy śróddziennej jako prognozy całego dnia;
- premiuje niedoszacowanie przez karę 2:1 za przeszacowanie;
- ogranicza korektę wyniku osobnymi limitami w dół i w górę;
- uruchamia korektę tylko po wygranym teście kroczącym;
- wybiera model ważony tylko wtedy, gdy pokonuje najlepszy dopuszczony wariant SPV według MAE i kosztu asymetrycznego;
- wraca do sprawdzonego wariantu SPV, jeśli model ważony nie przechodzi bramki jakości;
- udostępnia jednorazowy przełącznik wyczyszczenia historii przy uruchomieniu;
- publikuje wynik ważony, wynik końcowy, korektę, siedem wag i metryki, bez powielania encji źródłowych.

## Instalacja

1. W Home Assistant przejdź do Ustawienia - Aplikacje - Sklep z aplikacjami.
2. Dodaj repozytorium `https://github.com/Wilk33/pv-forecast-calibrator`.
3. Zainstaluj PV Forecast Calibrator.
4. W ustawieniach wybierz encję Forecast.Solar, encję Solcast oraz dzienną produkcję PV.
5. Uruchom aplikację i sprawdź dziennik.

Wymagana jest działająca integracja MQTT. Szczegóły ustawień i stanów modelu znajdują się w [dokumentacji aplikacji](pv-forecast-calibrator/DOCS.md).

## Walidacja modelu

Regresja na dostarczonych 20 dniach danych wykorzystuje pierwsze 5 dni jako historię, a kolejne 15 dni jako test bez dostępu do przyszłości. Dla tego zakresu:

- surowy SPV osiągnął MAE 2,228 kWh;
- obecna zewnętrzna prognoza ważona osiągnęła MAE 6,703 kWh;
- konserwatywny SPV z ograniczeniem korekty do 1 kWh w obu kierunkach osiągnął MAE 2,153 kWh i niższy koszt asymetryczny;
- kandydat ważony z wersji 1.2.0 został na tym krótkim zakresie odrzucony przez bramkę jakości, więc aplikacja zachowała lepszy wynik skorygowanego SPV zamiast wymuszać gorszą średnią.

Ten krótki zakres nie jest dowodem skuteczności w całym roku. Dlatego aplikacja utrzymuje SPV jako obowiązkowy punkt odniesienia i automatycznie wyłącza lokalną korektę, gdy test kroczący nie potwierdza poprawy.

## Rozwój

```text
python -m unittest discover -s tests -v
python tools/sync_runtime.py
python -m compileall -q pv_forecast_calibrator pv-forecast-calibrator/rootfs/usr/src/app/pv_forecast_calibrator
```

## Źródła

- [Home Assistant - konfiguracja aplikacji](https://developers.home-assistant.io/docs/apps/configuration/)
- [Home Assistant - komunikacja aplikacji z Core, Supervisorem i usługami](https://developers.home-assistant.io/docs/apps/communication/)
- [Home Assistant Supervisor API - endpointy aplikacji](https://developers.home-assistant.io/docs/api/supervisor/endpoints/)
- [Home Assistant REST API](https://developers.home-assistant.io/docs/api/rest/)
- [Home Assistant MQTT Discovery](https://www.home-assistant.io/integrations/mqtt/)
