"""Control engine: reactive and predictive fan control logic.

FEAT-001 stub — full predictive implementation in FEAT-003.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import ControlMode, ControlState, SensorReading

# Default reactive threshold for tomatoes
REACTIVE_FAN_ON_TEMP = 32.0   # °C — turn fan on above this
REACTIVE_FAN_OFF_TEMP = 29.0  # °C — turn fan off below this (hysteresis)


def _get_or_create_state(db: Session, greenhouse_id: str) -> ControlState:
    state = (
        db.query(ControlState)
        .filter(ControlState.greenhouse_id == greenhouse_id)
        .order_by(ControlState.updated_at.desc())
        .first()
    )
    if state is None:
        state = ControlState(
            greenhouse_id=greenhouse_id,
            mode=ControlMode.reactive,
            fan_on=False,
            manual_override=False,
        )
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


def evaluate(db: Session, reading: SensorReading) -> ControlState:
    """Update control state based on the latest sensor reading."""
    state = _get_or_create_state(db, reading.greenhouse_id)
    now = datetime.now(timezone.utc)

    # Expire manual override if its time has passed
    if (
        state.manual_override
        and state.override_expires_at is not None
        and state.override_expires_at <= now
    ):
        state.manual_override = False
        state.override_expires_at = None

    if state.manual_override:
        # Manual mode — honour the current fan_on value, don't change it
        state.recommended_action = "fan_on" if state.fan_on else "fan_off"
        state.action_reason = "Manual override active."
    elif state.mode == ControlMode.reactive:
        _reactive_control(state, reading)
    elif state.mode == ControlMode.predictive:
        # Predictive logic added in FEAT-003; fall back to reactive for now
        _reactive_control(state, reading)
        state.action_reason = (
            "[Predictive mode — forecasting not yet active, using reactive fallback] "
            + (state.action_reason or "")
        )

    state.updated_at = now
    db.commit()
    db.refresh(state)
    return state


def _reactive_control(state: ControlState, reading: SensorReading) -> None:
    if reading.temperature_c >= REACTIVE_FAN_ON_TEMP:
        state.fan_on = True
        state.recommended_action = "fan_on"
        state.action_reason = (
            f"Reactive mode: temperature {reading.temperature_c}°C "
            f"≥ threshold {REACTIVE_FAN_ON_TEMP}°C."
        )
    elif reading.temperature_c < REACTIVE_FAN_OFF_TEMP and state.fan_on:
        state.fan_on = False
        state.recommended_action = "fan_off"
        state.action_reason = (
            f"Reactive mode: temperature {reading.temperature_c}°C "
            f"< hysteresis {REACTIVE_FAN_OFF_TEMP}°C — fan off."
        )
    else:
        state.recommended_action = "noop"
        state.action_reason = (
            f"Reactive mode: temperature {reading.temperature_c}°C — no action needed."
        )
