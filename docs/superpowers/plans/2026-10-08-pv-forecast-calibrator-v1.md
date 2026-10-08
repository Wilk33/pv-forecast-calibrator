# PV Forecast Calibrator 1.0.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Zbudować i opublikować instalowalną aplikację Home Assistant OS, która bezpośrednio odczytuje Forecast.Solar, Solcast i produkcję PV, prowadzi historię lokalnych błędów i bezpiecznie publikuje skorygowaną prognozę.

**Architecture:** Moduły Pythona rozdzielają konfigurację, model siedmiu prognoz, kalibrację kroczącą, trwały stan, klienta Home Assistant, MQTT Discovery oraz pętlę czasu. Kod źródłowy jest synchronizowany do rootfs dodatku, a zachowanie algorytmu jest sprawdzane na zanonimizowanej próbce danych użytkownika.

**Tech Stack:** Python 3.12, aiohttp, paho-mqtt, unittest, Home Assistant OS app packaging.

**Spec:** `docs/superpowers/specs/2026-10-08-pv-forecast-calibrator-v1-design.md`

## Global Constraints

- Wersja aplikacji i pakietu: 1.0.0.
- Strefa domyślna: Europe/Warsaw.
- Próbka domyślna: 04:20, granica: 04:45, zamknięcie dnia: 23:00.
- Kara za przeszacowanie: 2,0.
- Maksymalna korekta w dół: 1,0 kWh.
- Git i GitHub są uruchamiane poza sandboxem Windows.
- Przed każdym Git sprawdzić, że `.git` należy do `PC1-MATEUSZ\mskip`.

## Review Focus

- Solcast bez `estimate10` lub `estimate90` - próbka ma zostać odrzucona jako niepełna.
- Restart po 04:45 bez próbki - nie wolno zapisać prognozy śróddziennej jako całodniowej.
- `unknown`, `unavailable`, NaN i liczby ujemne - nie mogą wejść do historii ani metryk.
- Korekta lepsza asymetrycznie, lecz gorsza według MAE - musi pozostać fallback SPV.
- Ponowienie zapisu lub zamknięcia dnia - musi być idempotentne.

---

### Task 1: Model prognoz, kalibracja i trwała historia

**Files:**
- Create: `pv_forecast_calibrator/models.py`
- Create: `pv_forecast_calibrator/calibration.py`
- Create: `pv_forecast_calibrator/storage.py`
- Create: `tests/test_models.py`
- Create: `tests/test_calibration.py`
- Create: `tests/test_storage.py`
- Create: `tests/fixtures/local_history.json`

**Interfaces:**
- Produces: `ForecastSet.from_states()`, `DailyRecord`, `CalibrationDecision`, `decide_forecast()`, `JsonStateStore`.

- [ ] Write failing tests for direct Solcast attributes, three derived averages, numeric validation and optional FPV.
- [ ] Run model tests and confirm failures caused by missing implementation.
- [ ] Implement the immutable forecast and daily-record types.
- [ ] Run model tests and confirm success.
- [ ] Write failing calibration tests for the 2:1 loss, -1,0 kWh clamp, walk-forward isolation, activation gate and SPV fallback.
- [ ] Run calibration tests and confirm failures caused by missing implementation.
- [ ] Implement weighted quantile correction and walk-forward gate.
- [ ] Run calibration tests and confirm success.
- [ ] Write failing storage tests for atomic round-trip, corrupt files, idempotent records and history trimming.
- [ ] Implement state storage and run the whole task suite.
- [ ] Commit Task 1.

### Task 2: Konfiguracja, Home Assistant i logika czasu

**Files:**
- Create: `pv_forecast_calibrator/config.py`
- Create: `pv_forecast_calibrator/ha.py`
- Create: `pv_forecast_calibrator/runtime.py`
- Create: `tests/test_config.py`
- Create: `tests/test_ha.py`
- Create: `tests/test_runtime.py`

**Interfaces:**
- Consumes: typy Task 1.
- Produces: `AppConfig.from_options()`, `HomeAssistantClient`, `ForecastRuntime.tick()` i `ForecastRuntime.state_payload()`.

- [ ] Write failing configuration tests for entity IDs, time ordering and numeric ranges.
- [ ] Implement configuration and make tests green.
- [ ] Write failing parser/client tests for state attributes and maximum daily production from history.
- [ ] Implement Home Assistant REST operations and make tests green.
- [ ] Write failing runtime tests for the 04:20-04:45 window, late-start rejection, idempotent snapshot, tracking production and 23:00 settlement.
- [ ] Implement the runtime and make the whole task suite green.
- [ ] Commit Task 2.

### Task 3: MQTT Discovery i proces aplikacji

**Files:**
- Create: `pv_forecast_calibrator/mqtt.py`
- Create: `pv_forecast_calibrator/supervisor.py`
- Create: `pv_forecast_calibrator/__init__.py`
- Create: `pv_forecast_calibrator/__main__.py`
- Create: `tests/test_mqtt.py`
- Create: `tests/test_supervisor.py`

**Interfaces:**
- Consumes: stan publikowany przez Task 2.
- Produces: retained discovery dla dziewięciu encji, publikację stanu i uruchamialny proces dodatku.

- [ ] Write failing tests for exact MQTT entity set, availability, units, enum options and absence of duplicated source forecasts.
- [ ] Implement MQTT messages and publisher, then make tests green.
- [ ] Write failing tests for normalization odpowiedzi usługi MQTT Supervisora.
- [ ] Implement Supervisor client and application entry point.
- [ ] Run the whole task suite and commit Task 3.

### Task 4: Pakowanie Home Assistant OS i dokumentacja

**Files:**
- Create: `repository.yaml`
- Create: `pv-forecast-calibrator/config.yaml`
- Create: `pv-forecast-calibrator/build.yaml`
- Create: `pv-forecast-calibrator/Dockerfile`
- Create: `pv-forecast-calibrator/run.sh`
- Create: `pv-forecast-calibrator/DOCS.md`
- Create: `pv-forecast-calibrator/CHANGELOG.md`
- Create: `pv-forecast-calibrator/translations/pl.yaml`
- Create: `pv-forecast-calibrator/translations/en.yaml`
- Create: `pv-forecast-calibrator/rootfs/requirements.txt`
- Create: `tools/sync_runtime.py`
- Create: `tests/test_packaging.py`
- Create: `README.md`
- Create: `LICENSE`
- Create: `.github/workflows/test.yml`

**Interfaces:**
- Consumes: cały pakiet aplikacji.
- Produces: instalowalne repozytorium aplikacji Home Assistant OS w wersji 1.0.0.

- [ ] Write failing packaging tests for required files, option schema, version agreement and runtime synchronization.
- [ ] Add packaging, Polish and English settings, documentation and CI.
- [ ] Synchronize source into rootfs and make packaging tests green.
- [ ] Run unittest discovery, compileall, YAML parsing and `git diff --check`.
- [ ] Commit Task 4.

### Task 5: Weryfikacja, publikacja i instalowalność

**Files:**
- Modify only files required by findings.

**Interfaces:**
- Consumes: complete Task 1-4 repository.
- Produces: commit and tag `v1.0.0` on GitHub.

- [ ] Review the entire diff against the spec and Review Focus.
- [ ] Run a clean full test suite and compileall.
- [ ] Verify Git ownership and status outside the sandbox.
- [ ] Push the default branch and tag `v1.0.0` outside the sandbox.
- [ ] Verify remote branch, tag and GitHub Actions state.

