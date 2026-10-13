"""Alert engine: evaluates sensor readings and forecast records, raises and
resolves alerts stored in the database.

Deduplication rule: if an alert of the same type is already active for
the greenhouse, the existing row is updated rather than a new one created.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import Alert, ForecastRecord, RiskLevel, SensorReading

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default crop configuration (tomato defaults)
# ---------------------------------------------------------------------------
_DEFAULT_CROP_CONFIG: dict[str, Any] = {
    "temp_max_c": 32.0,
    "temp_warn_c": 30.0,
    "humidity_max_pct": 85.0,
    "humidity_min_pct": 50.0,
}

# How far ahead (minutes) to look in forecast records for risk assessment
_FORECAST_LOOKAHEAD_MINUTES: int = 30


class AlertEngine:
    """Evaluate sensor readings and forecasts against crop thresholds.

    All alerts are persisted to the database.  Existing active alerts of
    the same type are updated in place so the UI shows current conditions
    without duplicate rows.
    """

    def evaluate(
        self,
        db: Session,
        reading: SensorReading,
        forecasts: list[ForecastRecord],
        crop_config: dict[str, Any] | None = None,
    ) -> list[Alert]:
        """Evaluate one reading + associated forecasts and persist alerts.

        Parameters
        ----------
        db:
            Active SQLAlchemy session.
        reading:
            The most recent sensor reading.
        forecasts:
            ForecastRecord rows with horizon_minutes ≤ 30 (the caller
            should supply only relevant forecasts, but the engine filters
            to ≤ 30 min internally as well).
        crop_config:
            Dict with keys ``temp_max_c``, ``temp_warn_c``,
            ``humidity_max_pct``, ``humidity_min_pct``.
            Falls back to ``_DEFAULT_CROP_CONFIG`` for any missing key.

        Returns
        -------
        list[Alert]
            All alert rows that are currently active after evaluation.
        """
        cfg = {**_DEFAULT_CROP_CONFIG, **(crop_config or {})}
        new_or_updated: list[Alert] = []

        new_or_updated.extend(self._check_current_temperature(db, reading, cfg))
        new_or_updated.extend(self._check_current_humidity(db, reading, cfg))
        new_or_updated.extend(self._check_forecast_temperature(db, reading, forecasts, cfg))
        new_or_updated.extend(self._check_forecast_humidity(db, reading, forecasts, cfg))

        return new_or_updated

    # ------------------------------------------------------------------
    # Current-reading checks
    # ------------------------------------------------------------------

    def _check_current_temperature(
        self, db: Session, reading: SensorReading, cfg: dict
    ) -> list[Alert]:
        temp = reading.temperature_c
        alert_type = "high_temperature"
        results: list[Alert] = []

        if temp > cfg["temp_max_c"]:
            msg = (
                f"Temperature {temp:.1f}°C exceeds the maximum limit "
                f"{cfg['temp_max_c']}°C for this crop."
            )
            alert = self._upsert_alert(db, reading, alert_type, RiskLevel.high, msg)
            results.append(alert)
        elif temp > cfg["temp_warn_c"]:
            msg = (
                f"Temperature {temp:.1f}°C is above the warning level "
                f"{cfg['temp_warn_c']}°C — approaching the crop limit."
            )
            alert = self._upsert_alert(db, reading, alert_type, RiskLevel.medium, msg)
            results.append(alert)
        else:
            self._resolve_alerts(db, reading.greenhouse_id, alert_type)

        return results

    def _check_current_humidity(
        self, db: Session, reading: SensorReading, cfg: dict
    ) -> list[Alert]:
        hum = reading.humidity_pct
        results: list[Alert] = []

        if hum > cfg["humidity_max_pct"]:
            alert = self._upsert_alert(
                db, reading, "high_humidity", RiskLevel.medium,
                f"Humidity {hum:.1f}% exceeds the maximum {cfg['humidity_max_pct']}% "
                "— risk of fungal disease.",
            )
            results.append(alert)
        else:
            self._resolve_alerts(db, reading.greenhouse_id, "high_humidity")

        if hum < cfg["humidity_min_pct"]:
            alert = self._upsert_alert(
                db, reading, "low_humidity", RiskLevel.medium,
                f"Humidity {hum:.1f}% is below the minimum {cfg['humidity_min_pct']}% "
                "— risk of water stress.",
            )
            results.append(alert)
        else:
            self._resolve_alerts(db, reading.greenhouse_id, "low_humidity")

        return results

    # ------------------------------------------------------------------
    # Forecast-based checks
    # ------------------------------------------------------------------

    def _check_forecast_temperature(
        self,
        db: Session,
        reading: SensorReading,
        forecasts: list[ForecastRecord],
        cfg: dict,
    ) -> list[Alert]:
        alert_type = "predicted_overheat"
        relevant = [
            f for f in forecasts
            if f.horizon_minutes <= _FORECAST_LOOKAHEAD_MINUTES
            and f.predicted_temperature_c > cfg["temp_max_c"]
        ]
        if not relevant:
            self._resolve_alerts(db, reading.greenhouse_id, alert_type)
            return []

        worst = max(relevant, key=lambda f: f.predicted_temperature_c)
        msg = (
            f"Forecast: temperature predicted to reach {worst.predicted_temperature_c:.1f}°C "
            f"in {worst.horizon_minutes} min — exceeds crop maximum {cfg['temp_max_c']}°C. "
            "Current reading: "
            f"{reading.temperature_c:.1f}°C."
        )
        alert = self._upsert_alert(db, reading, alert_type, RiskLevel.high, msg)
        return [alert]

    def _check_forecast_humidity(
        self,
        db: Session,
        reading: SensorReading,
        forecasts: list[ForecastRecord],
        cfg: dict,
    ) -> list[Alert]:
        alert_type = "predicted_high_humidity"
        relevant = [
            f for f in forecasts
            if f.horizon_minutes <= _FORECAST_LOOKAHEAD_MINUTES
            and f.predicted_humidity_pct > cfg["humidity_max_pct"]
        ]
        if not relevant:
            self._resolve_alerts(db, reading.greenhouse_id, alert_type)
            return []

        worst = max(relevant, key=lambda f: f.predicted_humidity_pct)
        msg = (
            f"Forecast: humidity predicted to reach {worst.predicted_humidity_pct:.1f}% "
            f"in {worst.horizon_minutes} min — exceeds crop maximum "
            f"{cfg['humidity_max_pct']}%."
        )
        alert = self._upsert_alert(db, reading, alert_type, RiskLevel.medium, msg)
        return [alert]

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------

    def _upsert_alert(
        self,
        db: Session,
        reading: SensorReading,
        alert_type: str,
        risk_level: RiskLevel,
        message: str,
    ) -> Alert:
        """Create a new alert or update the existing active one."""
        existing = (
            db.query(Alert)
            .filter(
                Alert.greenhouse_id == reading.greenhouse_id,
                Alert.alert_type == alert_type,
                Alert.is_active.is_(True),
            )
            .first()
        )
        if existing:
            existing.risk_level = risk_level
            existing.message = message
            db.commit()
            db.refresh(existing)
            return existing

        alert = Alert(
            greenhouse_id=reading.greenhouse_id,
            risk_level=risk_level,
            alert_type=alert_type,
            message=message,
            is_active=True,
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        logger.info(
            "Alert created: [%s] %s — %s", risk_level.value, alert_type, message
        )
        return alert

    def _resolve_alerts(
        self, db: Session, greenhouse_id: str, alert_type: str
    ) -> None:
        now = datetime.now(timezone.utc)
        rows = (
            db.query(Alert)
            .filter(
                Alert.greenhouse_id == greenhouse_id,
                Alert.alert_type == alert_type,
                Alert.is_active.is_(True),
            )
            .all()
        )
        for row in rows:
            row.is_active = False
            row.resolved_at = now
        if rows:
            db.commit()
            logger.debug("Resolved %d alert(s) of type '%s'.", len(rows), alert_type)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
alert_engine = AlertEngine()


# ---------------------------------------------------------------------------
# Legacy shim — called by main.py scheduler tick from FEAT-001
# ---------------------------------------------------------------------------
def evaluate_reading(db: Session, reading: SensorReading) -> None:
    """Backward-compatible wrapper used by the scheduler tick in main.py."""
    from app.config import settings

    crop_config = {
        "temp_max_c": settings.TEMP_MAX_C,
        "temp_warn_c": settings.TEMP_WARN_C,
        "humidity_max_pct": settings.HUMIDITY_MAX_PCT,
        "humidity_min_pct": settings.HUMIDITY_MIN_PCT,
    }

    # Fetch recent forecasts from DB for this greenhouse
    from app.models import ForecastRecord
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=_FORECAST_LOOKAHEAD_MINUTES * 2)
    forecasts = (
        db.query(ForecastRecord)
        .filter(
            ForecastRecord.greenhouse_id == reading.greenhouse_id,
            ForecastRecord.created_at >= cutoff,
            ForecastRecord.horizon_minutes <= _FORECAST_LOOKAHEAD_MINUTES,
        )
        .all()
    )

    alert_engine.evaluate(db, reading, forecasts, crop_config)
