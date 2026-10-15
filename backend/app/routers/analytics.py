"""Analytics router: reactive vs predictive mode comparison and KPI summary."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AnalyticsSnapshot
from app.schemas import (
    AnalyticsSnapshotOut,
    AnalyticsSummaryResponse,
    ModeKPIs,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _secs_to_mins(s: float) -> float:
    return round(s / 60.0, 2)


def _efficiency_score(
    temp_exceedance_minutes: float,
    window_minutes: float,
    avg_response_seconds: float | None,
) -> float:
    """Compute a 0–100 efficiency score.

    Deductions:
      * Up to 50 pts for time the greenhouse spent above the temperature limit.
        Penalty = clamp(temp_exc / window * 100, 0, 50)
      * Up to 50 pts for slow fan response time.
        Penalty = clamp(avg_response_s / 30 * 50, 0, 50)
        (A response ≥ 30 s gets full penalty; 0 s gets none.)
    """
    if window_minutes <= 0:
        return 100.0

    temp_penalty = min(50.0, (temp_exceedance_minutes / window_minutes) * 100.0)
    if avg_response_seconds is not None:
        resp_penalty = min(50.0, (avg_response_seconds / 30.0) * 50.0)
    else:
        resp_penalty = 0.0  # unknown = no penalty

    score = 100.0 - temp_penalty - resp_penalty
    return round(max(0.0, score), 1)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/comparison", response_model=list[AnalyticsSnapshotOut])
def get_comparison(
    greenhouse_id: str = Query(default="greenhouse-01"),
    hours: int = Query(default=24, ge=1, le=168),
    db: Session = Depends(get_db),
) -> list[AnalyticsSnapshotOut]:
    """Return raw analytics snapshots for reactive vs predictive comparison.

    Returns snapshots from the last *hours* hours, oldest first.
    """
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


@router.get("/summary", response_model=AnalyticsSummaryResponse)
def get_summary(
    greenhouse_id: str = Query(default="greenhouse-01"),
    hours: int = Query(default=24, ge=1, le=168),
    db: Session = Depends(get_db),
) -> AnalyticsSummaryResponse:
    """Return aggregated KPIs per control mode plus the raw time-series rows.

    KPIs are computed by aggregating every AnalyticsSnapshot row for each
    mode captured within the last *hours* hours.  Each snapshot row already
    contains a rolling-window accumulation (see main.py _write_analytics_snapshot),
    so the most-recent snapshot per mode gives the most accurate cumulative
    picture.  We also expose average stats across all snapshots so the UI
    can show trend information.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    window_minutes = hours * 60.0

    all_rows = (
        db.query(AnalyticsSnapshot)
        .filter(
            AnalyticsSnapshot.greenhouse_id == greenhouse_id,
            AnalyticsSnapshot.captured_at >= cutoff,
        )
        .order_by(AnalyticsSnapshot.captured_at.asc())
        .all()
    )

    # Group by mode
    by_mode: dict[str, list[AnalyticsSnapshot]] = {}
    for row in all_rows:
        by_mode.setdefault(row.mode, []).append(row)

    mode_kpis: list[ModeKPIs] = []
    for mode, rows in by_mode.items():
        n = len(rows)

        # Use the most-recent row as the authoritative cumulative total
        # (each row's fan_runtime_seconds is already a rolling-window sum)
        latest = rows[-1]
        total_fan_runtime_min = _secs_to_mins(latest.fan_runtime_seconds)
        total_temp_exc_min = _secs_to_mins(latest.temp_exceedance_seconds)
        total_hum_exc_min = _secs_to_mins(latest.humidity_exceedance_seconds)

        # Average over all snapshots gives a per-tick picture
        avg_fan_min = _secs_to_mins(
            sum(r.fan_runtime_seconds for r in rows) / n
        )
        avg_temp_exc_min = _secs_to_mins(
            sum(r.temp_exceedance_seconds for r in rows) / n
        )

        # Average response time — skip rows where it is None
        resp_values = [r.avg_response_time_seconds for r in rows if r.avg_response_time_seconds is not None]
        avg_resp_s = round(sum(resp_values) / len(resp_values), 2) if resp_values else None

        efficiency = _efficiency_score(total_temp_exc_min, window_minutes, avg_resp_s)

        mode_kpis.append(
            ModeKPIs(
                mode=mode,
                sample_count=n,
                total_fan_runtime_minutes=total_fan_runtime_min,
                avg_fan_runtime_minutes=avg_fan_min,
                total_temp_exceedance_minutes=total_temp_exc_min,
                avg_temp_exceedance_minutes=avg_temp_exc_min,
                total_humidity_exceedance_minutes=total_hum_exc_min,
                avg_response_time_seconds=avg_resp_s,
                efficiency_score=efficiency,
            )
        )

    # Sort: reactive first, then predictive, then manual
    order = {"reactive": 0, "predictive": 1, "manual": 2}
    mode_kpis.sort(key=lambda k: order.get(k.mode, 99))

    return AnalyticsSummaryResponse(
        greenhouse_id=greenhouse_id,
        window_hours=hours,
        generated_at=datetime.now(timezone.utc),
        modes=mode_kpis,
        time_series=all_rows,  # type: ignore[arg-type]
    )
