"""Analytics router: reactive vs predictive mode comparison."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AnalyticsSnapshot
from app.schemas import AnalyticsSnapshotOut

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/comparison", response_model=list[AnalyticsSnapshotOut])
def get_comparison(
    greenhouse_id: str = Query(default="greenhouse-01"),
    hours: int = Query(default=24, ge=1, le=168),
    db: Session = Depends(get_db),
) -> list[AnalyticsSnapshotOut]:
    """Return analytics snapshots for reactive vs predictive comparison.

    Returns snapshots from the last *hours* hours, oldest first.
    """
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    snapshots = (
        db.query(AnalyticsSnapshot)
        .filter(
            AnalyticsSnapshot.greenhouse_id == greenhouse_id,
            AnalyticsSnapshot.captured_at >= cutoff,
        )
        .order_by(AnalyticsSnapshot.captured_at.asc())
        .all()
    )
    return snapshots  # type: ignore[return-value]
