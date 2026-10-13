"""Predictions router: forecast temperature and humidity."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import PredictionsResponse
from app.services.forecasting import generate_predictions

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.get("", response_model=PredictionsResponse)
def get_predictions(
    greenhouse_id: str = Query(default="greenhouse-01"),
    db: Session = Depends(get_db),
) -> PredictionsResponse:
    """Return forecasts for horizons [10, 15, 30] minutes with model metrics."""
    return generate_predictions(db, greenhouse_id)
