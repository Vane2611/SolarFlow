# SolarFlow — AI-Powered Predictive Greenhouse Management System

SolarFlow monitors greenhouse temperature and humidity, forecasts
conditions up to 30 minutes ahead using a Random Forest model, identifies
crop-specific risks before they occur, and recommends or automatically
triggers ventilation.

The system works out of the box with simulated sensor data.  A hardware
integration layer lets you connect a real Arduino + DHT22 + relay once the
software is validated.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  Browser                                                            │
│  React / Vite / TypeScript SPA                                      │
│  Recharts dashboards  ←→  REST API                                  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ HTTP / JSON
┌──────────────────────────────▼──────────────────────────────────────┐
│  FastAPI backend  (Python 3.11)                                     │
│                                                                     │
│  APScheduler tick (every 5 s)                                       │
│    ├─ GreenhouseSimulator  →  SensorReading                         │
│    ├─ AlertEngine          →  Alert rows                            │
│    ├─ ControlEngine        →  ControlState + hardware command       │
│    └─ ForecastingService   →  ForecastRecord rows                   │
│                                                                     │
│  SQLite (solarflow.db)                                              │
│                                                                     │
│  HardwareInterface  ←→  Serial (9 600 baud JSON)                    │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ USB serial  (optional)
┌──────────────────────────────▼──────────────────────────────────────┐
│  Arduino Uno                                                        │
│  DHT22 (pin 2)  +  16x2 LCD (4-bit, pins 3/4/5/6/11/12)            │
│  5 V relay module (pin 7)  →  DC fan                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python      | 3.11+   | Tested on 3.11.9 |
| Node.js     | 18+     | npm 9+ |
| Arduino IDE | 2.x     | Only needed for hardware integration |
| Git         | any     | |

Python packages (installed automatically): FastAPI, SQLAlchemy, pandas,
scikit-learn, APScheduler, pyserial, and others listed in
`backend/requirements.txt`.

---

## Setup

### 1. Clone the repository

```bash
git clone <repo-url>
cd SolarFlow
```

### 2. Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # edit as needed
```

Key environment variables (all have defaults; only SERIAL_PORT needs
editing for hardware mode):

| Variable                     | Default                      | Description |
|------------------------------|------------------------------|-------------|
| `DATABASE_URL`               | `sqlite:///./solarflow.db`   | SQLite path |
| `SIMULATION_MODE`            | `true`                       | Generate simulated readings when `true` |
| `SIMULATION_INTERVAL_SECONDS`| `5`                          | Seconds between simulated readings |
| `GREENHOUSE_ID`              | `greenhouse-01`              | Identifier stored in DB |
| `LOG_LEVEL`                  | `info`                       | Python logging level |
| `TEMP_MAX_C`                 | `32.0`                       | Reactive fan-on temperature threshold |
| `TEMP_WARN_C`                | `30.0`                       | Predictive warning level |
| `HUMIDITY_MAX_PCT`           | `85.0`                       | Upper humidity limit |
| `HUMIDITY_MIN_PCT`           | `50.0`                       | Lower humidity limit |
| `HYSTERESIS_C`               | `2.0`                        | Hysteresis band below TEMP_MAX_C |
| `MIN_FAN_RUN_SECONDS`        | `120`                        | Minimum fan run time |
| `MIN_FAN_OFF_SECONDS`        | `60`                         | Minimum fan off time |
| `SERIAL_PORT`                | *(unset)*                    | e.g. `COM3` or `/dev/ttyUSB0` |
| `SERIAL_BAUD`                | `9600`                       | Serial baud rate |

### 3. Frontend

```bash
cd frontend
npm install
```

---

## Running the system

### Backend (API server)

```bash
cd backend
uvicorn main:app --reload --port 8000
```

The API is available at `http://localhost:8000`.
Interactive docs: `http://localhost:8000/docs`

### Frontend (development)

```bash
cd frontend
npm run dev
```

The dashboard opens at `http://localhost:5173`.

### Frontend (production build)

```bash
cd frontend
npm run build
```

Output goes to `frontend/dist/`.

---

## API endpoint reference

| Method | Path | Description | Example response shape |
|--------|------|-------------|------------------------|
| GET | `/api/health` | Liveness check | `{"status":"ok","version":"1.0.0","simulation_mode":true}` |
| GET | `/api/readings/latest` | Most recent sensor reading | `SensorReadingOut` or `null` |
| GET | `/api/readings/history` | Historical readings (newest first) | `[SensorReadingOut, ...]` |
| GET | `/api/predictions` | Forecasts + model metrics | `PredictionsResponse` |
| GET | `/api/alerts` | Active and historical alerts | `[AlertOut, ...]` |
| GET | `/api/devices/status` | Hardware connection status | `DeviceStatusResponse` |
| GET | `/api/control/mode` | Current control state | `ControlStateOut` |
| POST | `/api/control/mode` | Set control mode | `ControlStateOut` |
| POST | `/api/control/manual-override` | Issue a manual fan command | `ControlStateOut` |
| GET | `/api/analytics/comparison` | Reactive vs predictive stats | `[AnalyticsSnapshotOut, ...]` |

### POST /api/control/mode — request body

```json
{"mode": "reactive"}
```

Allowed values: `"reactive"`, `"predictive"`, `"manual"`.

### POST /api/control/manual-override — request body

```json
{"action": "fan_on", "duration_seconds": 300}
```

Allowed actions: `"fan_on"`, `"fan_off"`, `"noop"`.  Any other string
returns HTTP 422.  `duration_seconds` defaults to 300.

### PredictionsResponse shape

```json
{
  "greenhouse_id": "greenhouse-01",
  "generated_at": "2024-01-01T12:00:00Z",
  "data_is_synthetic": true,
  "note": "UNVALIDATED — model trained on synthetic data.",
  "forecasts": [
    {
      "horizon_minutes": 10,
      "predicted_temperature_c": 27.3,
      "predicted_humidity_pct": 64.1,
      "model_version": "rf-v1",
      "is_validated": false
    }
  ],
  "model_metrics": [
    {
      "horizon_minutes": 10,
      "baseline": {"mae_temperature": 0.51, "rmse_temperature": 0.67, ...},
      "random_forest": {"mae_temperature": 0.48, "rmse_temperature": 0.63, ...}
    }
  ]
}
```

---

## Machine learning

### Models

Two models are trained for each forecast horizon (10, 15, 30 minutes):

**Persistence baseline** — predicts the last observed value.  Serves as a
naive lower bound for comparison.

**Random Forest regressor** — `sklearn.ensemble.RandomForestRegressor` with
100 estimators and `random_state=42`.  Separate models are fitted for
temperature and humidity at each horizon.

### Features

| Feature | Description |
|---------|-------------|
| `hour_of_day` | Fractional hour (0–24), captures diurnal patterns |
| `temp_lag_1` … `temp_lag_12` | Temperature 1, 2, 3, 6, 12 readings back |
| `humid_lag_1` … `humid_lag_12` | Humidity lags |
| `temp_roll_mean_6/12` | Rolling mean over 6 and 12 reading windows |
| `temp_roll_std_6/12` | Rolling standard deviation |
| `humid_roll_mean_6/12` | Rolling humidity mean |
| `humid_roll_std_6/12` | Rolling humidity std |
| `temperature_c`, `humidity_pct` | Current reading |

### Metrics

MAE (Mean Absolute Error) and RMSE (Root Mean Square Error) are computed on
a chronologically held-out test split (the last 20 % of the training
dataset by time order).  Time-series records are never shuffled.

### Synthetic data and unvalidated status

When fewer than 50 real readings exist in the database (true at startup),
the service trains on 24 hours of synthetic data generated by
`generate_synthetic_training_data()`.

**All predictions produced from synthetic-trained models are labelled
`is_validated: false` and the API response includes an explicit
`data_is_synthetic: true` flag.**  Metrics reflect the synthetic data
distribution only and should not be interpreted as real greenhouse accuracy.

Once sufficient real readings accumulate, re-trigger training by restarting
the backend or calling `forecasting_service.train(db=db)` programmatically.

---

## Control logic

### Reactive mode

The fan turns ON when the measured temperature reaches `TEMP_MAX_C`
(default 32 °C).  It turns OFF when the temperature falls below
`TEMP_MAX_C - HYSTERESIS_C` (default 30 °C).  This mirrors conventional
threshold-based automation.

### Predictive mode

The engine inspects the 10- and 15-minute forecasts.  If any forecast
predicts temperature above `TEMP_WARN_C - 1` (default 29 °C) **and** the
current temperature is already above `TEMP_WARN_C - 3` (default 27 °C),
the fan is activated early.  If a forecast exceeds `TEMP_MAX_C`, the fan
is activated proactively.

The action reason text always explains which forecast triggered the
decision and notes that outdoor conditions are unknown (fan effect on
humidity is not guaranteed).

### Fallback behaviour

If predictive mode is selected but no forecasts are available (service not
yet trained, or DB query returns nothing), the engine falls back to
reactive logic automatically and notes this in the action reason.

### Minimum timing

A minimum fan run time (120 s) and a minimum fan off time (60 s) prevent
rapid cycling that would stress the relay contacts and motor.

### Manual override

The operator can issue `fan_on`, `fan_off`, or `noop` via the API with a
configurable duration.  The override is honoured until it expires;
automatic control resumes afterwards.

### Hardware command allowlist

Only three strings may ever reach the serial port: `"fan_on"`, `"fan_off"`,
`"noop"`.  Any other string raises `ValueError` before any I/O occurs.
Raw user input is never forwarded to hardware.

---

## Hardware wiring

See `firmware/PROTOCOL.md` for the complete wiring diagram (ASCII art),
component values, relay compatibility notes, flyback diode requirements,
and safety notes.

### Quick reference

```
Arduino pin 2  →  DHT22 DATA  (with 10 kΩ pull-up to VCC)
Arduino pin 7  →  Relay IN
Relay COM      →  Fan +
Relay NO       →  Fan − (through external PSU)
External PSU − →  Arduino GND (common ground)

Arduino pin 12 →  LCD RS
Arduino pin 11 →  LCD EN
Arduino pin 5  →  LCD D4
Arduino pin 4  →  LCD D5
Arduino pin 3  →  LCD D6
Arduino pin 6  →  LCD D7
Arduino 5 V    →  LCD VCC
Arduino GND    →  LCD GND
```

The LCD is a 16x2 character module in 4-bit parallel mode.  It shows the
live readings and the fan state:

```
┌────────────────┐
│T:25.4°C H:68.2%│   ← temperature and humidity
│FAN:ON  OK      │   ← fan state and status token
└────────────────┘
```

Status tokens: `OK` (healthy), `WARN` (temperature ≥ 30 °C or humidity
≥ 85 %), `ERR` (the last sensor read failed).

### Uploading firmware

1. Install the **DHT sensor library** by Adafruit and **ArduinoJson** (v6
   or v7) via the Arduino Library Manager.
2. Open `firmware/solarflow_sensor/solarflow_sensor.ino` in Arduino IDE.
   The sketch folder also contains `lcd_display.h` / `lcd_display.cpp`,
   which Arduino IDE compiles automatically.  The `LiquidCrystal` library
   ships with the IDE — no installation needed.
3. Select your board (Arduino Uno) and port.
4. Click Upload.

### Running against real hardware

1. Wire the DHT22, the LCD and the relay as shown above.
2. Upload the firmware and open the Arduino Serial Monitor at **9600
   baud** to confirm the readings arrive.
3. Configure the backend in `backend/.env`:

   ```
   SIMULATION_MODE=false
   SERIAL_PORT=COM3          # Windows — adjust to your port
   SERIAL_BAUD=9600
   ```

4. Start the backend.  It opens the serial port, logs
   `Hardware link active on COM3 at 9600 baud`, and stores every DHT22
   sample as a `SensorReading` row with `data_source = "real"`.

If the port cannot be opened the backend logs a warning and keeps running
on simulated readings, so the dashboard stays available.  The **Device
Health** card shows the live connection state, the firmware version and
the last command sent to the relay.

---

## Testing

```bash
cd backend
pytest app/tests/ -v
```

All tests use an in-memory SQLite database; no external services are
required.

Test files:

| File | What it covers |
|------|----------------|
| `app/tests/test_forecasting.py` | Synthetic data generator, feature matrix builder, `train_models`, `ForecastingService` |
| `app/tests/test_control.py` | `ControlEngine` reactive/predictive/override/timing, `AlertEngine`, `HardwareInterface` allowlist |
| `app/tests/test_api.py` | All major API endpoints via `TestClient` |
| `app/tests/test_hardware.py` | Serial reader thread, DHT22 reading ingestion, command acknowledgement, hardware-mode reading conversion |

---

## Known limitations

- **Forecasts are unvalidated on synthetic data.** The Random Forest model
  was not tested on real greenhouse measurements.  Treat predictions as
  indicative until the system has accumulated real data and been re-trained.

- **30-minute horizon accuracy.** Predicting 30 minutes ahead from
  5-second sensor readings is ambitious.  The persistence baseline
  frequently performs comparably to the RF model on smooth synthetic data.
  Real-world accuracy will vary with actual greenhouse dynamics.

- **Single greenhouse.** The MVP supports one `greenhouse_id` per instance.

- **No authentication.** The API has no access control.  Do not expose it
  directly to the internet without adding authentication.

- **SQLite concurrency.** SQLite is adequate for a single-server MVP but
  will become a bottleneck under high write rates.  Migrate to PostgreSQL
  for production.

- **Simulated data only by default.** Set `SIMULATION_MODE=false` and
  configure `SERIAL_PORT` to enable real hardware.

- **The LCD is a display, not a sensor.** The readings it shows come from
  the DHT22 on the same Arduino; the LCD contributes no data of its own to
  the backend.  It mirrors temperature, humidity and the fan state only —
  the web dashboard remains the full interface.

- **Forecasts need real data to become trustworthy.** In hardware mode the
  forecaster keeps using generated data until at least 50 live DHT22
  samples are stored, then retrains on the real readings.

- **Arduino firmware not automatically tested.** Compilation requires
  Arduino IDE or `avr-gcc` with the DHT and ArduinoJson libraries.

---

## Contributors

Vane Meta Apeli    Emmanuella Omondi
