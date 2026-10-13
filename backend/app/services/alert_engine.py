"""Alert engine: evaluates sensor readings and raises/resolves alerts.

FEAT-001 stub — full implementation in FEAT-003.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Alert, RiskLevel, SensorReading

# Crop-specific thresholds (tomato defaults)
TEMP_HIGH_CRITICAL = 38.0   # °C
TEMP_HIGH_WARNING = 35.0    # °C
HUMIDITY_HIGH_CRITICAL = 90.0  # %
HUMIDITY_HIGH_WARNING = 85.0   # %


def evaluate_reading(db: Session, reading: SensorReading) -> None:
    """Inspect the latest reading and create/resolve alerts as needed."""
    _check_temperature(db, reading)
    _check_humidity(db, reading)


def _check_temperature(db: Session, reading: SensorReading) -> None:
    alert_type = "high_temperature"
    if reading.temperature_c >= TEMP_HIGH_CRITICAL:
        _ensure_alert(db, reading, alert_type, RiskLevel.critical,
                      f"Temperature critical: {reading.temperature_c}°C ≥ {TEMP_HIGH_CRITICAL}°C")
    elif reading.temperature_c >= TEMP_HIGH_WARNING:
        _ensure_alert(db, reading, alert_type, RiskLevel.high,
                      f"Temperature high: {reading.temperature_c}°C ≥ {TEMP_HIGH_WARNING}°C")
    else:
        _resolve_alerts(db, reading.greenhouse_id, alert_type)


def _check_humidity(db: Session, reading: SensorReading) -> None:
    alert_type = "high_humidity"
    if reading.humidity_pct >= HUMIDITY_HIGH_CRITICAL:
        _ensure_alert(db, reading, alert_type, RiskLevel.critical,
                      f"Humidity critical: {reading.humidity_pct}% ≥ {HUMIDITY_HIGH_CRITICAL}%")
    elif reading.humidity_pct >= HUMIDITY_HIGH_WARNING:
        _ensure_alert(db, reading, alert_type, RiskLevel.high,
                      f"Humidity high: {reading.humidity_pct}% ≥ {HUMIDITY_HIGH_WARNING}%")
    else:
        _resolve_alerts(db, reading.greenhouse_id, alert_type)


def _ensure_alert(
    db: Session,
    reading: SensorReading,
    alert_type: str,
    risk_level: RiskLevel,
    message: str,
) -> None:
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
        # Update message and risk level in case conditions worsened
        existing.risk_level = risk_level
        existing.message = message
        db.commit()
    else:
        alert = Alert(
            greenhouse_id=reading.greenhouse_id,
            risk_level=risk_level,
            alert_type=alert_type,
            message=message,
            is_active=True,
        )
        db.add(alert)
        db.commit()


def _resolve_alerts(db: Session, greenhouse_id: str, alert_type: str) -> None:
    from datetime import datetime, timezone

    alerts = (
        db.query(Alert)
        .filter(
            Alert.greenhouse_id == greenhouse_id,
            Alert.alert_type == alert_type,
            Alert.is_active.is_(True),
        )
        .all()
    )
    now = datetime.now(timezone.utc)
    for alert in alerts:
        alert.is_active = False
        alert.resolved_at = now
    if alerts:
        db.commit()
