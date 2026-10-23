"""Greenhouse advisory recommendations."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Alert, ControlState, ForecastRecord, SensorReading
from app.schemas import AdvisoryRecommendation, AdvisoryResponse
from app.services.advisory import generate_recommendations

router = APIRouter(prefix="/advisory", tags=["advisory"])


@router.get("", response_model=AdvisoryResponse)
def get_advisory(
    greenhouse_id: str = Query(default="greenhouse-01"),
    db: Session = Depends(get_db),
) -> AdvisoryResponse:
    """Return ranked recommendations for the current greenhouse state."""
    reading = (
        db.query(SensorReading)
        .filter(SensorReading.greenhouse_id == greenhouse_id)
        .order_by(SensorReading.timestamp.desc())
        .first()
    )
    forecasts = (
        db.query(ForecastRecord)
        .filter(ForecastRecord.greenhouse_id == greenhouse_id)
        .order_by(ForecastRecord.created_at.desc())
        .limit(10)
        .all()
    )
    active_alerts = (
        db.query(Alert)
        .filter(Alert.greenhouse_id == greenhouse_id, Alert.is_active.is_(True))
        .all()
    )
    control_state = (
        db.query(ControlState)
        .filter(ControlState.greenhouse_id == greenhouse_id)
        .order_by(ControlState.updated_at.desc())
        .first()
    )
    summary, recommendations, basis = generate_recommendations(
        reading, forecasts, active_alerts, control_state
    )
    return AdvisoryResponse(
        greenhouse_id=greenhouse_id,
        generated_at=datetime.now(timezone.utc),
        summary=summary,
        recommendations=[
            AdvisoryRecommendation.model_validate(recommendation.__dict__)
            for recommendation in recommendations
        ],
        data_basis=basis,
    )
