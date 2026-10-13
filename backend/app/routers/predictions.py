"""Predictions router: forecast temperature and humidity."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ForecastRecord, SensorReading
from app.schemas import (
    ForecastRecordOut,
    ModelMetrics,
    PredictionsResponse,
    SingleModelMetrics,
)
from app.services.forecasting import HORIZONS, forecasting_service

router = APIRouter(prefix="/predictions", tags=["predictions"])

_RECENT_READINGS_LIMIT = 60
_SYNTHETIC_NOTE = (
    "UNVALIDATED — model trained on synthetic data. "
    "Metrics are real (computed from a chronological test split) but reflect "
    "synthetic data distributions only."
)
_REAL_NOTE = (
    "Model trained on real greenhouse readings. "
    "Metrics computed from a chronological train/test split."
)


@router.get("", response_model=PredictionsResponse)
def get_predictions(
    greenhouse_id: str = Query(default="greenhouse-01"),
    db: Session = Depends(get_db),
) -> PredictionsResponse:
    """Return forecasts for horizons [10, 15, 30] minutes with model metrics.

    The ``data_is_synthetic`` flag is ``true`` whenever the model was trained
    on synthetic data rather than real greenhouse readings.  Predictions are
    always labelled ``is_validated=False`` in that case.
    """
    # Ensure the service is trained (lazy init if needed)
    if not forecasting_service.is_trained:
        forecasting_service.train(db=db)

    # Fetch the most recent readings to feed into the RF predictor
    recent: list[SensorReading] = (
        db.query(SensorReading)
        .filter(SensorReading.greenhouse_id == greenhouse_id)
        .order_by(SensorReading.timestamp.desc())
        .limit(_RECENT_READINGS_LIMIT)
        .all()
    )

    now = datetime.now(timezone.utc)
    data_is_synthetic = forecasting_service.trained_on_synthetic

    if not recent:
        return PredictionsResponse(
            greenhouse_id=greenhouse_id,
            generated_at=now,
            forecasts=[],
            model_metrics=[],
            data_is_synthetic=data_is_synthetic,
            note=_SYNTHETIC_NOTE if data_is_synthetic else _REAL_NOTE,
        )

    # Generate forecast records
    forecast_orm: list[ForecastRecord] = forecasting_service.predict(
        recent_readings=recent,
        horizons=HORIZONS,
    )

    # Persist forecast records to DB
    for record in forecast_orm:
        db.add(record)
    db.flush()

    forecast_out: list[ForecastRecordOut] = [
        ForecastRecordOut.model_validate(r) for r in forecast_orm
    ]

    db.commit()

    # Build metrics list from the service
    raw_metrics = forecasting_service.get_metrics()
    model_metrics: list[ModelMetrics] = []
    for horizon in HORIZONS:
        horizon_data = raw_metrics.get(horizon, {})
        baseline_data = horizon_data.get("baseline", {})
        rf_data = horizon_data.get("random_forest", {})
        model_metrics.append(
            ModelMetrics(
                horizon_minutes=horizon,
                baseline=SingleModelMetrics(
                    mae_temperature=baseline_data.get("mae_temperature"),
                    rmse_temperature=baseline_data.get("rmse_temperature"),
                    mae_humidity=baseline_data.get("mae_humidity"),
                    rmse_humidity=baseline_data.get("rmse_humidity"),
                ),
                random_forest=SingleModelMetrics(
                    mae_temperature=rf_data.get("mae_temperature"),
                    rmse_temperature=rf_data.get("rmse_temperature"),
                    mae_humidity=rf_data.get("mae_humidity"),
                    rmse_humidity=rf_data.get("rmse_humidity"),
                ),
            )
        )

    return PredictionsResponse(
        greenhouse_id=greenhouse_id,
        generated_at=now,
        forecasts=forecast_out,
        model_metrics=model_metrics,
        data_is_synthetic=data_is_synthetic,
        note=_SYNTHETIC_NOTE if data_is_synthetic else _REAL_NOTE,
    )
