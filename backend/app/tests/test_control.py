"""Control logic unit tests — FEAT-001 stub."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from app.models import ControlMode, ControlState, DataSource, SensorReading
from app.services.control_engine import _reactive_control, REACTIVE_FAN_ON_TEMP, REACTIVE_FAN_OFF_TEMP


def _make_state() -> ControlState:
    state = ControlState(
        greenhouse_id="test",
        mode=ControlMode.reactive,
        fan_on=False,
        manual_override=False,
    )
    return state


def _make_reading(temp: float) -> SensorReading:
    from datetime import datetime, timezone
    return SensorReading(
        greenhouse_id="test",
        timestamp=datetime.now(timezone.utc),
        temperature_c=temp,
        humidity_pct=60.0,
        data_source=DataSource.simulated,
    )


def test_reactive_turns_fan_on_above_threshold() -> None:
    state = _make_state()
    reading = _make_reading(REACTIVE_FAN_ON_TEMP + 1)
    _reactive_control(state, reading)
    assert state.fan_on is True
    assert state.recommended_action == "fan_on"


def test_reactive_turns_fan_off_below_hysteresis() -> None:
    state = _make_state()
    state.fan_on = True
    reading = _make_reading(REACTIVE_FAN_OFF_TEMP - 1)
    _reactive_control(state, reading)
    assert state.fan_on is False
    assert state.recommended_action == "fan_off"


def test_reactive_noop_between_thresholds() -> None:
    mid = (REACTIVE_FAN_ON_TEMP + REACTIVE_FAN_OFF_TEMP) / 2
    state = _make_state()
    reading = _make_reading(mid)
    _reactive_control(state, reading)
    assert state.recommended_action == "noop"
