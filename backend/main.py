"""SolarFlow FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

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
            evaluate(db, reading)

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
