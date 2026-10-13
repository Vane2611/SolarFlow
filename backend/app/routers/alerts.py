"""Alerts router: current and historical risk alerts."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Alert
from app.schemas import AlertOut

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
def get_alerts(
    greenhouse_id: str = Query(default="greenhouse-01"),
    active_only: bool = Query(default=True),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[AlertOut]:
    """Return alerts ordered by creation time, newest first."""
    query = db.query(Alert).filter(Alert.greenhouse_id == greenhouse_id)
    if active_only:
        query = query.filter(Alert.is_active.is_(True))
    alerts = query.order_by(Alert.created_at.desc()).limit(limit).all()
    return alerts  # type: ignore[return-value]
