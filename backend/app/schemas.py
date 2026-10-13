"""Pydantic v2 schemas for request/response validation."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Shared config — enable ORM mode for all output models
# ---------------------------------------------------------------------------


class _ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# SensorReading
# ---------------------------------------------------------------------------


class SensorReadingOut(_ORMBase):
    id: int
    greenhouse_id: str
    timestamp: datetime
    temperature_c: float
    humidity_pct: float
    data_source: str
    created_at: datetime


# ---------------------------------------------------------------------------
# ForecastRecord
# ---------------------------------------------------------------------------


class ForecastRecordOut(_ORMBase):
    id: int
    greenhouse_id: str
    created_at: datetime
    horizon_minutes: int
    predicted_temperature_c: float
    predicted_humidity_pct: float
    model_version: str
    is_validated: bool


# ---------------------------------------------------------------------------
# Alert
# ---------------------------------------------------------------------------


class AlertOut(_ORMBase):
    id: int
    greenhouse_id: str
    created_at: datetime
    resolved_at: datetime | None
    risk_level: str
    alert_type: str
    message: str
    is_active: bool


# ---------------------------------------------------------------------------
# ControlState
# ---------------------------------------------------------------------------


class ControlStateOut(_ORMBase):
    id: int
    greenhouse_id: str
    updated_at: datetime
    mode: str
    fan_on: bool
    manual_override: bool
    override_expires_at: datetime | None
    recommended_action: str | None
    action_reason: str | None


# ---------------------------------------------------------------------------
# AnalyticsSnapshot
# ---------------------------------------------------------------------------


class AnalyticsSnapshotOut(_ORMBase):
    id: int
    greenhouse_id: str
    captured_at: datetime
    mode: str
    fan_runtime_seconds: float
    temp_exceedance_seconds: float
    humidity_exceedance_seconds: float
    avg_response_time_seconds: float | None


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class ControlModeRequest(BaseModel):
    mode: Literal["reactive", "predictive", "manual"]


class ManualOverrideRequest(BaseModel):
    action: Literal["fan_on", "fan_off", "noop"]
    duration_seconds: int = 300


# ---------------------------------------------------------------------------
# Composite responses
# ---------------------------------------------------------------------------


class SingleModelMetrics(BaseModel):
    """MAE/RMSE for one model type at one horizon."""

    mae_temperature: float | None = None
    rmse_temperature: float | None = None
    mae_humidity: float | None = None
    rmse_humidity: float | None = None


class ModelMetrics(BaseModel):
    """Evaluation metrics for a single forecast horizon, covering both models."""

    horizon_minutes: int
    baseline: SingleModelMetrics = SingleModelMetrics()
    random_forest: SingleModelMetrics = SingleModelMetrics()


class PredictionsResponse(BaseModel):
    greenhouse_id: str
    generated_at: datetime
    forecasts: list[ForecastRecordOut]
    model_metrics: list[ModelMetrics]
    data_is_synthetic: bool
    note: str = (
        "Model performance is unvalidated — predictions are based on simulated data."
    )


class HealthResponse(BaseModel):
    status: str
    version: str
    simulation_mode: bool


class DeviceStatusResponse(BaseModel):
    greenhouse_id: str
    simulation_mode: bool
    last_reading_at: datetime | None
    serial_port: str | None
    connected: bool
    last_error: str | None
