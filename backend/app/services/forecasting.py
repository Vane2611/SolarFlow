"""Forecasting service: persistence baseline and Random Forest models.

FEAT-001 stub — full training pipeline implemented in FEAT-002.
Returns clearly-labelled unvalidated synthetic predictions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from app.models import ForecastRecord
from app.schemas import ForecastRecordOut, ModelMetrics, PredictionsResponse

HORIZONS = [10, 15, 30]
MODEL_VERSION = "persistence-v1"


def generate_predictions(db: "Session", greenhouse_id: str) -> PredictionsResponse:
    """Generate forecasts using the persistence baseline (last known value).

    Until sufficient historical data exists for training, this returns
    persistence predictions clearly labelled as unvalidated/synthetic.
    """
    from app.models import SensorReading

    latest: SensorReading | None = (
        db.query(SensorReading)
        .filter(SensorReading.greenhouse_id == greenhouse_id)
        .order_by(SensorReading.timestamp.desc())
        .first()
    )

    now = datetime.now(timezone.utc)

    if latest is None:
        # No data yet — return empty
        return PredictionsResponse(
            greenhouse_id=greenhouse_id,
            generated_at=now,
            forecasts=[],
            model_metrics=[],
            data_is_synthetic=True,
        )

    forecasts: list[ForecastRecordOut] = []
    metrics: list[ModelMetrics] = []

    for horizon in HORIZONS:
        record = ForecastRecord(
            greenhouse_id=greenhouse_id,
            horizon_minutes=horizon,
            predicted_temperature_c=latest.temperature_c,
            predicted_humidity_pct=latest.humidity_pct,
            model_version=MODEL_VERSION,
            is_validated=False,
        )
        db.add(record)
        db.flush()  # populate id
        forecasts.append(ForecastRecordOut.model_validate(record))
        metrics.append(
            ModelMetrics(
                horizon_minutes=horizon,
                mae_temperature=None,
                rmse_temperature=None,
                mae_humidity=None,
                rmse_humidity=None,
            )
        )

    db.commit()

    return PredictionsResponse(
        greenhouse_id=greenhouse_id,
        generated_at=now,
        forecasts=forecasts,
        model_metrics=metrics,
        data_is_synthetic=True,
        note=(
            "UNVALIDATED — persistence baseline only. "
            "Random Forest model training requires collected historical data (FEAT-002)."
        ),
    )
