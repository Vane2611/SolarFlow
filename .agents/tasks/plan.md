# Implementation Plan — SolarFlow MVP

This plan is decomposed into 5 sequential features. Each feature leaves the codebase in a buildable state. See the FEAT-NNN.json files in `.agents/tasks/features/` for full step details.

---

## FEAT-001 — Backend Foundation

- [ ] 1. Create `backend/requirements.txt` with all Python dependencies (fastapi, uvicorn, sqlalchemy, pydantic-settings, apscheduler, pandas, scikit-learn, numpy, pyserial, python-dotenv, pytest, httpx).
      Files: `backend/requirements.txt`
      Verify: `cd backend && pip install -r requirements.txt` — completes without errors.

- [ ] 2. Create `backend/.env.example` with DATABASE_URL, SIMULATION_MODE, SIMULATION_INTERVAL_SECONDS, GREENHOUSE_ID, LOG_LEVEL.
      Files: `backend/.env.example`
      Verify: file exists and lists all required keys.

- [ ] 3. Create all Python package `__init__.py` stubs: `backend/app/__init__.py`, `backend/app/routers/__init__.py`, `backend/app/services/__init__.py`, `backend/app/tests/__init__.py`.
      Files: four `__init__.py` files as listed.
      Verify: `python -c "import app"` from backend/ succeeds.

- [ ] 4. Create `backend/app/config.py` using pydantic-settings `BaseSettings`. Export singleton `settings`.
      Files: `backend/app/config.py`
      Verify: `python -c "from app.config import settings; print(settings.GREENHOUSE_ID)"` prints default value.

- [ ] 5. Create `backend/app/database.py` with SQLAlchemy engine, `SessionLocal`, `Base`, `get_db()` dependency, and `create_all()`.
      Files: `backend/app/database.py`
      Verify: `python -c "from app.database import create_all; create_all(); print('OK')"` creates `solarflow.db`.

- [ ] 6. Create `backend/app/models.py` with ORM models: `SensorReading`, `ForecastRecord`, `Alert`, `ControlState`, `AnalyticsSnapshot`.
      Files: `backend/app/models.py`
      Verify: `python -c "from app.models import SensorReading, ForecastRecord, Alert, ControlState"` imports cleanly.

- [ ] 7. Create `backend/app/schemas.py` with Pydantic v2 output models and request bodies for all domains.
      Files: `backend/app/schemas.py`
      Verify: `python -c "from app.schemas import SensorReadingOut, PredictionsResponse, ManualOverrideRequest"` imports cleanly.

- [ ] 8. Create `backend/app/services/simulator.py` with `GreenhouseSimulator` class that produces realistic simulated `SensorReading` rows.
      Files: `backend/app/services/simulator.py`
      Verify: `python -c "from app.services.simulator import GreenhouseSimulator; s=GreenhouseSimulator(); r=s.next_reading(); print(r.temperature_c)"` prints a float.

- [ ] 9. Create all 6 API routers with correct endpoints and Pydantic response models.
      Files: `backend/app/routers/readings.py`, `predictions.py`, `alerts.py`, `control.py`, `analytics.py`, `devices.py`
      Verify: `python -c "from app.routers import readings, predictions, alerts, control, analytics, devices"` imports without error.

- [ ] 10. Create `backend/main.py` — FastAPI app, CORS, router includes, APScheduler startup, `/api/health` endpoint.
       Files: `backend/main.py`
       Verify: `cd backend && uvicorn main:app --port 8000` starts; PowerShell `Invoke-RestMethod http://localhost:8000/api/health` returns `{status: ok}`.

---

## FEAT-002 — ML Forecasting Module

*Depends on FEAT-001. Independent of FEAT-003.*

- [ ] 11. Create `backend/app/services/forecasting.py` with `generate_synthetic_training_data()`, `build_feature_matrix()`, `train_models()`, and `ForecastingService` class. Label all synthetic/unvalidated data clearly.
       Files: `backend/app/services/forecasting.py`
       Verify: `python -c "from app.services.forecasting import ForecastingService; fs=ForecastingService(); fs.train(); print(fs.get_metrics())"` prints a dict with MAE/RMSE values.

- [ ] 12. Wire `ForecastingService` into the predictions router and APScheduler job. Train in background thread at startup.
       Files: `backend/app/routers/predictions.py`, `backend/main.py`
       Verify: `GET /api/predictions` returns forecasts for horizons 10, 15, 30 with `data_is_synthetic: true` and real metric numbers.

---

## FEAT-003 — Control Engine, Alert Engine, Hardware Interface

*Depends on FEAT-001. Independent of FEAT-002 (reads forecasts from DB).*

- [ ] 13. Create `backend/app/services/alert_engine.py` with `AlertEngine` class. Generates Alert rows for current and predicted temperature/humidity violations.
       Files: `backend/app/services/alert_engine.py`
       Verify: `python -c "from app.services.alert_engine import AlertEngine; print('OK')"` imports cleanly.

- [ ] 14. Create `backend/app/services/hardware.py` with `ALLOWED_COMMANDS` frozenset and `HardwareInterface` class. Enforce allowlist — reject any command not in `{'fan_on','fan_off','noop'}`.
       Files: `backend/app/services/hardware.py`
       Verify: `python -c "from app.services.hardware import HardwareInterface; h=HardwareInterface(); print(h.send_command('fan_on'))"` prints simulated ack; `h.send_command('bad')` raises ValueError.

- [ ] 15. Create `backend/app/services/control_engine.py` with `ControlEngine` — reactive mode, predictive mode, manual override, minimum run/off times, and safe fallback when forecasts are unavailable.
       Files: `backend/app/services/control_engine.py`
       Verify: `python -c "from app.services.control_engine import ControlEngine; print('OK')"` imports cleanly.

- [ ] 16. Wire alert_engine and control_engine into the APScheduler job in `main.py`. Update devices router to use hardware_interface. Update control router to call hardware_interface for manual override.
       Files: `backend/main.py`, `backend/app/routers/control.py`, `backend/app/routers/devices.py`
       Verify: `POST /api/control/manual-override {action: fan_on}` returns 200; `POST` with `{action: rm -rf /}` returns 422.

---

## FEAT-004 — React/Vite/TypeScript Frontend

*Depends on FEAT-001/002/003 for a live API. Can be built statically without a running backend.*

- [ ] 17. Scaffold Vite + React + TypeScript project in `frontend/` and install npm dependencies (recharts, react-router-dom, lucide-react).
       Files: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/index.html`
       Verify: `cd frontend && npm install` succeeds.

- [ ] 18. Create `frontend/src/types/index.ts` — all TypeScript interfaces matching backend schemas. Strict types, no `any`.
       Files: `frontend/src/types/index.ts`
       Verify: `cd frontend && npx tsc --noEmit` — no errors in types file.

- [ ] 19. Create `frontend/src/api/client.ts` — typed fetch wrappers for all 10 API endpoints.
       Files: `frontend/src/api/client.ts`
       Verify: `cd frontend && npx tsc --noEmit` — no errors.

- [ ] 20. Create `frontend/src/hooks/usePolling.ts` — generic polling hook with error handling and cleanup.
       Files: `frontend/src/hooks/usePolling.ts`
       Verify: TypeScript compiles cleanly.

- [ ] 21. Create `frontend/src/index.css` — agricultural tech color scheme, responsive base styles.
       Files: `frontend/src/index.css`
       Verify: file exists.

- [ ] 22. Create layout components: `Sidebar.tsx` (nav with 7 links, icons, active state, mobile collapse) and `Header.tsx` (title, last-update, simulation badge, connection status).
       Files: `frontend/src/components/layout/Sidebar.tsx`, `frontend/src/components/layout/Header.tsx`
       Verify: `cd frontend && npx tsc --noEmit` — no errors.

- [ ] 23. Create overview components: `CurrentConditions.tsx` (temp + humidity with color coding), `ForecastRisk.tsx` (risk summary with UNVALIDATED badge), `TopAlert.tsx` (highest-priority active alert).
       Files: `frontend/src/components/overview/CurrentConditions.tsx`, `ForecastRisk.tsx`, `TopAlert.tsx`
       Verify: TypeScript compiles cleanly.

- [ ] 24. Create `frontend/src/components/monitoring/LiveChart.tsx` — Recharts LineChart with dual Y-axes, threshold reference lines at 30°C (warn) and 32°C (max), responsive container.
       Files: `frontend/src/components/monitoring/LiveChart.tsx`
       Verify: TypeScript compiles cleanly; chart imports from recharts resolve.

- [ ] 25. Create `frontend/src/components/predictions/ForecastChart.tsx` — ComposedChart with actual + forecast data, threshold lines, MAE/RMSE table, SYNTHETIC/UNVALIDATED label when applicable.
       Files: `frontend/src/components/predictions/ForecastChart.tsx`
       Verify: TypeScript compiles cleanly.

- [ ] 26. Create remaining components: `AlertList.tsx`, `ControlPanel.tsx`, `ComparisonChart.tsx`, `DeviceHealth.tsx`.
       Files: `frontend/src/components/alerts/AlertList.tsx`, `automation/ControlPanel.tsx`, `analytics/ComparisonChart.tsx`, `devices/DeviceHealth.tsx`
       Verify: TypeScript compiles cleanly.

- [ ] 27. Create all 7 page components using usePolling and domain components.
       Files: `frontend/src/pages/Overview.tsx`, `Monitoring.tsx`, `Predictions.tsx`, `Alerts.tsx`, `Automation.tsx`, `Analytics.tsx`, `DeviceHealth.tsx`
       Verify: TypeScript compiles cleanly.

- [ ] 28. Create `frontend/src/App.tsx` (React Router with all 7 routes + layout) and `frontend/src/main.tsx` (StrictMode entry point).
       Files: `frontend/src/App.tsx`, `frontend/src/main.tsx`
       Verify: `cd frontend && npm run build` — zero TypeScript errors, Vite build succeeds.

---

## FEAT-005 — Firmware, Tests, and README

*Depends on FEAT-001/002/003 (tests import backend). Independent of FEAT-004.*

- [ ] 29. Create `firmware/solarflow_sensor/solarflow_sensor.ino` — DHT22 reading + relay control + JSON serial protocol + command listener + watchdog pattern.
       Files: `firmware/solarflow_sensor/solarflow_sensor.ino`
       Verify: file compiles in Arduino IDE (or syntax-check with `arduino-cli compile --fqbn arduino:avr:uno firmware/solarflow_sensor` if available).

- [ ] 30. Create `firmware/PROTOCOL.md` — baud rate, JSON schemas, wiring diagram, safety notes.
       Files: `firmware/PROTOCOL.md`
       Verify: file exists and documents all message types.

- [ ] 31. Create `backend/app/tests/test_forecasting.py` — pytest tests for synthetic data generation, feature matrix, chronological split, model metrics, ForecastingService.predict().
       Files: `backend/app/tests/test_forecasting.py`
       Verify: `cd backend && pytest app/tests/test_forecasting.py -v` — all tests pass.

- [ ] 32. Create `backend/app/tests/test_control.py` — pytest tests for reactive mode, hysteresis, predictive mode early activation, manual override, command allowlist enforcement, fallback.
       Files: `backend/app/tests/test_control.py`
       Verify: `cd backend && pytest app/tests/test_control.py -v` — all tests pass.

- [ ] 33. Create `backend/app/tests/test_api.py` — pytest tests using FastAPI TestClient for all key endpoints.
       Files: `backend/app/tests/test_api.py`
       Verify: `cd backend && pytest app/tests/test_api.py -v` — all tests pass.

- [ ] 34. Overwrite `README.md` at workspace root with full documentation: overview, architecture, prerequisites, setup, run commands, API reference table, ML explanation, control logic, hardware wiring, limitations, testing instructions.
       Files: `README.md`
       Verify: `cd backend && pytest app/tests/ -v` — all tests across all three test files pass.

---

## Convergence

After all 5 FEATs are implemented, a fixer+reviewer loop runs the full integration verification:

```
cd backend && pip install -r requirements.txt
cd backend && pytest app/tests/ -v --tb=short
cd frontend && npm install && npm run build && npx tsc --noEmit
```

All tests must pass and the Vite build must succeed with zero TypeScript errors.
