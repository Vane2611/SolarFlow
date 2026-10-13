"""Readings router: latest and historical sensor data."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SensorReading
from app.schemas import SensorReadingOut

router = APIRouter(prefix="/readings", tags=["readings"])


@router.get("/latest", response_model=SensorReadingOut)
def get_latest_reading(
    greenhouse_id: str = Query(default="greenhouse-01"),
    db: Session = Depends(get_db),
) -> SensorReadingOut:
    """Return the most recent sensor reading for the specified greenhouse."""
    reading = (
        db.query(SensorReading)
        .filter(SensorReading.greenhouse_id == greenhouse_id)
        .order_by(SensorReading.timestamp.desc())
        .first()
    )
    if reading is None:
        raise HTTPException(status_code=404, detail="No readings available yet.")
    return reading  # type: ignore[return-value]


@router.get("/history", response_model=list[SensorReadingOut])
def get_reading_history(
    greenhouse_id: str = Query(default="greenhouse-01"),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[SensorReadingOut]:
    """Return up to *limit* readings, most recent first."""
    readings = (
        db.query(SensorReading)
        .filter(SensorReading.greenhouse_id == greenhouse_id)
        .order_by(SensorReading.timestamp.desc())
        .limit(limit)
        .all()
    )
    return readings  # type: ignore[return-value]
