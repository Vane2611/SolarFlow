"""SQLAlchemy ORM models for SolarFlow."""

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class DataSource(str, enum.Enum):
    real = "real"
    simulated = "simulated"


class RiskLevel(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class ControlMode(str, enum.Enum):
    reactive = "reactive"
    predictive = "predictive"
    manual = "manual"


# ---------------------------------------------------------------------------
# ORM models
# ---------------------------------------------------------------------------


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    greenhouse_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    temperature_c: Mapped[float] = mapped_column(Float, nullable=False)
    humidity_pct: Mapped[float] = mapped_column(Float, nullable=False)
    data_source: Mapped[DataSource] = mapped_column(
        Enum(DataSource), nullable=False, default=DataSource.simulated
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class ForecastRecord(Base):
    __tablename__ = "forecast_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    greenhouse_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    horizon_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    predicted_temperature_c: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_humidity_pct: Mapped[float] = mapped_column(Float, nullable=False)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False, default="persistence-v1")
    is_validated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    greenhouse_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ControlState(Base):
    __tablename__ = "control_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    greenhouse_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    mode: Mapped[ControlMode] = mapped_column(
        Enum(ControlMode), nullable=False, default=ControlMode.reactive
    )
    fan_on: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    manual_override: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    override_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    recommended_action: Mapped[str | None] = mapped_column(String(32), nullable=True)
    action_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class AnalyticsSnapshot(Base):
    __tablename__ = "analytics_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    greenhouse_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    fan_runtime_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    temp_exceedance_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    humidity_exceedance_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_response_time_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
