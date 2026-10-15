"""Pydantic v2 schemas for request/response validation."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, computed_field


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

    # Frontend-facing aliases so the UI receives `temperature` and `humidity`
    @computed_field  # type: ignore[misc]
    @property
    def temperature(self) -> float:
        return self.temperature_c

    @computed_field  # type: ignore[misc]
    @property
    def humidity(self) -> float:
        return self.humidity_pct

    @computed_field  # type: ignore[misc]
    @property
    def sensor_status(self) -> str:
        """Always 'ok' for DB-persisted readings; hardware layer would set 'error'."""
        return "ok"


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


# Frontend-facing forecast point with normalised field names
class ForecastPointOut(BaseModel):
    horizon_minutes: int
    predicted_temperature: float
    predicted_humidity: float
    confidence: float = 1.0


# Frontend-facing ForecastRecord wrapper — groups all horizons under one object
class ForecastRecordGrouped(BaseModel):
    id: int
    timestamp: datetime  # generated_at of the prediction run
    greenhouse_id: str
    model_version: str
    data_is_synthetic: bool
    forecasts: list[ForecastPointOut]
    metrics: list["ModelMetricsFrontend"] = []


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

    # Frontend expects `timestamp` and `is_active` at top level; created_at IS timestamp
    @computed_field  # type: ignore[misc]
    @property
    def timestamp(self) -> datetime:
        return self.created_at


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

    # Frontend-facing aliases
    @computed_field  # type: ignore[misc]
    @property
    def fan_state(self) -> str:
        return "on" if self.fan_on else "off"

    @computed_field  # type: ignore[misc]
    @property
    def last_action(self) -> str:
        return self.recommended_action or "noop"

    @computed_field  # type: ignore[misc]
    @property
    def last_action_reason(self) -> str:
        return self.action_reason or ""

    @computed_field  # type: ignore[misc]
    @property
    def manual_override_active(self) -> bool:
        return self.manual_override

    @computed_field  # type: ignore[misc]
    @property
    def manual_override_expires_at(self) -> datetime | None:
        return self.override_expires_at


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
# Analytics Summary (aggregated KPIs per mode)
# ---------------------------------------------------------------------------


class ModeKPIs(BaseModel):
    """Aggregated KPIs for a single control mode over the requested window."""

    mode: str
    sample_count: int
    # Fan
    total_fan_runtime_minutes: float
    avg_fan_runtime_minutes: float
    # Temperature exceedance
    total_temp_exceedance_minutes: float
    avg_temp_exceedance_minutes: float
    # Humidity exceedance
    total_humidity_exceedance_minutes: float
    # Response time
    avg_response_time_seconds: float | None
    # Derived efficiency score: 0–100 (higher = better)
    # Formula: 100 - clamp(temp_exc_min / window_minutes * 100, 0, 50)
    #                - clamp(avg_response_s / 30 * 50, 0, 50)
    efficiency_score: float


class AnalyticsSummaryResponse(BaseModel):
    """Top-level analytics summary returned by GET /api/analytics/summary."""

    greenhouse_id: str
    window_hours: int
    generated_at: datetime
    modes: list[ModeKPIs]
    # Ordered by captured_at ASC for the time-series chart
    time_series: list[AnalyticsSnapshotOut]


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


# Frontend expects ModelMetrics with fields: horizon_minutes, temp_mae, temp_rmse,
# humidity_mae, humidity_rmse (flat — uses random_forest values as primary).
class ModelMetricsFrontend(BaseModel):
    horizon_minutes: int
    temp_mae: float
    temp_rmse: float
    humidity_mae: float
    humidity_rmse: float


class PredictionsResponse(BaseModel):
    """Response for /api/predictions — shaped to match the frontend type."""

    greenhouse_id: str
    generated_at: datetime
    # Flat list kept for internal use / analytics
    forecasts: list[ForecastRecordOut]
    model_metrics: list[ModelMetrics]
    data_is_synthetic: bool
    note: str = (
        "Model performance is unvalidated — predictions are based on simulated data."
    )
    # Grouped format expected by the frontend
    latest: ForecastRecordGrouped | None = None
    model_version: str = "rf-v1"


class HealthResponse(BaseModel):
    status: str
    version: str
    simulation_mode: bool
    db_ok: bool = True
    scheduler_ok: bool = True


class DeviceStatusResponse(BaseModel):
    greenhouse_id: str
    simulation_mode: bool
    last_reading_at: datetime | None
    serial_port: str | None
    connected: bool
    last_error: str | None
    last_command: str | None = None
    last_command_at: str | None = None
    firmware_version: str | None = None
    uptime_seconds: float | None = None

    @computed_field  # type: ignore[misc]
    @property
    def connection_status(self) -> str:
        """Derived connection status string expected by the frontend."""
        if self.connected:
            return "connected"
        if self.simulation_mode:
            return "simulated"
        return "disconnected"
