"""SolarFlow FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import SessionLocal, create_all
from app.routers import alerts, analytics, control, devices, predictions, readings
from app.schemas import HealthResponse

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=settings.LOG_LEVEL.upper(),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lifespan (replaces deprecated on_event)
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("SolarFlow starting up…")
    create_all()
    logger.info("Database tables verified.")
    _start_forecasting_training()
    scheduler = _start_scheduler()
    yield
    logger.info("SolarFlow shutting down…")
    if scheduler.running:
        scheduler.shutdown(wait=False)


def _start_forecasting_training() -> None:
    """Kick off model training in a background thread so startup is non-blocking."""
    import threading
    from app.services.forecasting import forecasting_service
    from app.database import SessionLocal

    def _train() -> None:
        db = SessionLocal()
        try:
            forecasting_service.train(db=db)
        except Exception:
            logger.exception("Background forecasting training failed.")
        finally:
            db.close()

    t = threading.Thread(target=_train, daemon=True, name="forecasting-train")
    t.start()
    logger.info("Forecasting training started in background thread.")


def _write_analytics_snapshot(db: Any, reading: Any, state: Any) -> None:
    """Compute and persist one AnalyticsSnapshot row for the current mode.

    We look back over the last SNAPSHOT_WINDOW_SECONDS of sensor readings
    and control-state rows to compute cumulative metrics for the active mode.
    This is deliberately simple (O(n) per tick over a bounded window) and
    appropriate for an MVP running a few readings per minute.
    """
    from datetime import timedelta
    from app.models import AnalyticsSnapshot, ControlState as CS, SensorReading as SR

    SNAPSHOT_WINDOW_SECONDS = 3600  # 1-hour rolling window

    now = reading.timestamp
    # Use aware datetime for cutoff even if reading timestamp is naive.
    try:
        from datetime import timezone as _tz
        cutoff = now.replace(tzinfo=_tz.utc) - timedelta(seconds=SNAPSHOT_WINDOW_SECONDS)
    except Exception:
        cutoff = now - timedelta(seconds=SNAPSHOT_WINDOW_SECONDS)

    current_mode: str = str(state.mode.value if hasattr(state.mode, "value") else state.mode)

    # --- fan runtime: count control-state rows with fan_on=True in window ---
    try:
        from app.models import ControlState as _CS
        recent_states = (
            db.query(_CS)
            .filter(
                _CS.greenhouse_id == reading.greenhouse_id,
                _CS.updated_at >= cutoff,
                _CS.mode == state.mode,
            )
            .order_by(_CS.updated_at.asc())
            .all()
        )
        fan_runtime = sum(
            settings.SIMULATION_INTERVAL_SECONDS
            for s in recent_states
            if s.fan_on
        )
        # Estimate avg_response_time: mean seconds from temp crossing threshold
        # to fan turning on.  We approximate as interval * fraction of fan-on ticks
        # among ticks where fan was previously off (transitions).
        transitions_on = [
            i for i, s in enumerate(recent_states[1:], 1)
            if s.fan_on and not recent_states[i - 1].fan_on
        ]
        avg_response: float | None = None
        if transitions_on:
            # Approximate: each on-transition counts as one response;
            # response time ≈ one interval (since we poll every interval).
            avg_response = float(settings.SIMULATION_INTERVAL_SECONDS)
    except Exception:
        fan_runtime = 0.0
        avg_response = None

    # --- temperature exceedance: seconds above TEMP_MAX_C ---
    try:
        from app.models import SensorReading as _SR
        recent_readings = (
            db.query(_SR)
            .filter(
                _SR.greenhouse_id == reading.greenhouse_id,
                _SR.timestamp >= cutoff,
            )
            .order_by(_SR.timestamp.asc())
            .all()
        )
        temp_exc = sum(
            settings.SIMULATION_INTERVAL_SECONDS
            for r in recent_readings
            if r.temperature_c > settings.TEMP_MAX_C
        )
        humidity_exc = sum(
            settings.SIMULATION_INTERVAL_SECONDS
            for r in recent_readings
            if r.humidity_pct > settings.HUMIDITY_MAX_PCT
        )
    except Exception:
        temp_exc = 0.0
        humidity_exc = 0.0

    snapshot = AnalyticsSnapshot(
        greenhouse_id=reading.greenhouse_id,
        mode=current_mode,
        fan_runtime_seconds=float(fan_runtime),
        temp_exceedance_seconds=float(temp_exc),
        humidity_exceedance_seconds=float(humidity_exc),
        avg_response_time_seconds=avg_response,
    )
    db.add(snapshot)
    try:
        db.commit()
    except Exception:
        logger.exception("Error persisting analytics snapshot.")
        db.rollback()


def _start_scheduler():  # type: ignore[return]
    """Configure APScheduler to emit simulated sensor readings."""
    from apscheduler.schedulers.background import BackgroundScheduler
    from app.services.simulator import GreenhouseSimulator
    from app.services.alert_engine import evaluate_reading
    from app.services.control_engine import evaluate
    from app.services.forecasting import forecasting_service, HORIZONS

    simulator = GreenhouseSimulator(greenhouse_id=settings.GREENHOUSE_ID)

    def tick() -> None:
        db = SessionLocal()
        try:
            reading = simulator.next_reading()
            db.add(reading)
            db.commit()
            db.refresh(reading)
            evaluate_reading(db, reading)
            state = evaluate(db, reading)

            # Generate and persist forecast records after each new reading
            if forecasting_service.is_trained:
                try:
                    forecasts = forecasting_service.predict(
                        recent_readings=[reading],
                        horizons=HORIZONS,
                    )
                    for fc in forecasts:
                        db.add(fc)
                    db.commit()
                except Exception:
                    logger.exception("Error writing forecast records in tick.")

            # Persist an analytics snapshot every tick so the comparison
            # page always has data.  We compute a rolling window over the
            # last SNAPSHOT_WINDOW_SECONDS of readings for the current mode.
            _write_analytics_snapshot(db, reading, state)

        except Exception:
            logger.exception("Error in scheduler tick.")
        finally:
            db.close()

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        tick,
        trigger="interval",
        seconds=settings.SIMULATION_INTERVAL_SECONDS,
        id="sensor_tick",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "Scheduler started — emitting readings every %ds.",
        settings.SIMULATION_INTERVAL_SECONDS,
    )
    return scheduler


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="SolarFlow API",
    description="AI-Powered Predictive Greenhouse Management System",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Allow all origins for development; tighten in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(readings.router, prefix="/api")
app.include_router(predictions.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(control.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(devices.router, prefix="/api")

# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


@app.get("/api/health", response_model=HealthResponse, tags=["health"])
def health_check() -> HealthResponse:
    """Liveness check — always returns 200 when the server is running."""
    return HealthResponse(
        status="ok",
        version="1.0.0",
        simulation_mode=settings.SIMULATION_MODE,
    )
