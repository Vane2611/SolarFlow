"""Control engine: reactive and predictive fan control logic.

Two control modes:

* **Reactive** — fan on when temperature >= temp_max_c, off when it
  drops below temp_max_c - hysteresis_c.

* **Predictive** — look at the 10- and 15-minute forecasts; activate
  the fan early when a predicted exceedance is likely, and explain
  which forecast triggered the action.  Falls back to reactive when
  no forecasts are available.

Safety constraints:
* Manual override is honoured while active (override_expires_at in
  the future).
* Minimum fan run time (120 s) and minimum fan off time (60 s) prevent
  rapid cycling.  If the minimum time has not yet elapsed the engine
  keeps the current state and explains why.
* Every decision calls ``hardware_interface.send_command()``.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import ControlMode, ControlState, ForecastRecord, SensorReading
from app.services.hardware import hardware_interface

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
REACTIVE_FAN_ON_TEMP: float = 32.0   # default temp_max_c for tomatoes
REACTIVE_FAN_OFF_TEMP: float = 29.0  # default temp_max_c - hysteresis_c

# Predictive mode: horizons to examine (minutes)
_PREDICTIVE_HORIZONS = (10, 15)

# Default crop config used by reactive_control helper (tests + legacy shim)
_DEFAULT_CROP_CONFIG: dict[str, Any] = {
    "temp_max_c": REACTIVE_FAN_ON_TEMP,
    "temp_warn_c": 30.0,
    "humidity_max_pct": 85.0,
    "humidity_min_pct": 50.0,
    "hysteresis_c": 2.0,
    "min_fan_run_seconds": 120,
    "min_fan_off_seconds": 60,
}


# ---------------------------------------------------------------------------
# DB helper (shared with router)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# ControlEngine
# ---------------------------------------------------------------------------

class ControlEngine:
    """Stateless tick-based control engine.

    The engine reads and writes ``ControlState`` rows from the database
    on every tick; it does not hold mutable state itself so that
    multiple workers can share the same instance safely.
    """

    def tick(
        self,
        db: Session,
        reading: SensorReading,
        forecasts: list[ForecastRecord],
        crop_config: dict[str, Any] | None = None,
    ) -> tuple[ControlState, str]:
        """Evaluate the current reading and forecasts, update control state.

        Parameters
        ----------
        db:
            Active SQLAlchemy session.
        reading:
            The latest sensor reading.
        forecasts:
            ForecastRecord rows available for this greenhouse (any
            horizon); the engine selects the horizons it needs.
        crop_config:
            Dict with keys ``temp_max_c``, ``temp_warn_c``,
            ``humidity_max_pct``, ``humidity_min_pct``,
            ``hysteresis_c``, ``min_fan_run_seconds``,
            ``min_fan_off_seconds``.
            Falls back to ``_DEFAULT_CROP_CONFIG`` for missing keys.

        Returns
        -------
        tuple[ControlState, str]
            The updated ``ControlState`` ORM row and the human-readable
            action reason string.
        """
        cfg = {**_DEFAULT_CROP_CONFIG, **(crop_config or {})}
        state = _get_or_create_state(db, reading.greenhouse_id)
        now = datetime.now(timezone.utc)

        # ------------------------------------------------------------------
        # 1. Expire stale manual override
        # ------------------------------------------------------------------
        # SQLite returns naive datetimes; make comparison timezone-safe.
        def _as_aware(dt: datetime) -> datetime:
            return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)

        if (
            state.manual_override
            and state.override_expires_at is not None
            and _as_aware(state.override_expires_at) <= now
        ):
            state.manual_override = False
            state.override_expires_at = None
            logger.debug("Manual override expired for %s.", reading.greenhouse_id)

        # ------------------------------------------------------------------
        # 2. Choose control action
        # ------------------------------------------------------------------
        desired_fan_on: bool = state.fan_on  # default: keep current state
        reason: str

        if state.manual_override:
            # Manual override active — respect current fan state
            desired_fan_on = state.fan_on
            expires_iso = (
                state.override_expires_at.isoformat()
                if state.override_expires_at
                else "indefinitely"
            )
            reason = (
                f"Manual override active until {expires_iso} — "
                f"fan {'ON' if state.fan_on else 'OFF'}."
            )
        elif state.mode == ControlMode.predictive:
            desired_fan_on, reason = self._predictive_decision(
                reading, forecasts, state, cfg
            )
        else:
            # Reactive (default) — also covers ControlMode.manual when no
            # override is active (treat as reactive in that edge case)
            desired_fan_on, reason = self._reactive_decision(reading, state, cfg)

        # ------------------------------------------------------------------
        # 3. Enforce minimum run / off times
        # ------------------------------------------------------------------
        desired_fan_on, reason = self._enforce_timing(
            state, desired_fan_on, reason, cfg, now
        )

        # ------------------------------------------------------------------
        # 4. Issue hardware command
        # ------------------------------------------------------------------
        if desired_fan_on != state.fan_on:
            hw_cmd = "fan_on" if desired_fan_on else "fan_off"
        else:
            hw_cmd = "noop"

        try:
            hardware_interface.send_command(hw_cmd)
        except ValueError:
            # Should never happen — we only pass allowlisted strings
            logger.error("Attempted to send non-allowlisted command '%s'.", hw_cmd)

        # ------------------------------------------------------------------
        # 5. Persist updated state
        # ------------------------------------------------------------------
        state.fan_on = desired_fan_on
        state.recommended_action = hw_cmd
        state.action_reason = reason
        state.updated_at = now

        db.commit()
        db.refresh(state)
        return state, reason

    # ------------------------------------------------------------------
    # Decision helpers
    # ------------------------------------------------------------------

    def _reactive_decision(
        self,
        reading: SensorReading,
        state: ControlState,
        cfg: dict,
    ) -> tuple[bool, str]:
        temp = reading.temperature_c
        fan_on_threshold: float = cfg["temp_max_c"]
        fan_off_threshold: float = cfg["temp_max_c"] - cfg["hysteresis_c"]

        if temp >= fan_on_threshold:
            return True, (
                f"Reactive: temperature {temp:.1f}°C ≥ threshold {fan_on_threshold}°C — "
                "fan on."
            )
        if temp < fan_off_threshold and state.fan_on:
            return False, (
                f"Reactive: temperature {temp:.1f}°C < hysteresis {fan_off_threshold}°C — "
                "fan off."
            )
        return state.fan_on, (
            f"Reactive: temperature {temp:.1f}°C — no change required."
        )

    def _predictive_decision(
        self,
        reading: SensorReading,
        forecasts: list[ForecastRecord],
        state: ControlState,
        cfg: dict,
    ) -> tuple[bool, str]:
        if not forecasts:
            # Fallback to reactive — no forecasts available
            fan_on, reason = self._reactive_decision(reading, state, cfg)
            return fan_on, (
                "Predictive fallback to reactive: no forecast available. " + reason
            )

        temp_max: float = cfg["temp_max_c"]
        temp_warn: float = cfg["temp_warn_c"]

        # Collect forecasts for the relevant short horizons
        relevant = [
            f for f in forecasts
            if f.horizon_minutes in _PREDICTIVE_HORIZONS
        ]

        if not relevant:
            # No short-horizon forecasts; fall back to reactive
            fan_on, reason = self._reactive_decision(reading, state, cfg)
            return fan_on, (
                "Predictive fallback to reactive: no short-horizon forecasts available. "
                + reason
            )

        # Early activation: if any short-horizon forecast exceeds warn - 1
        # AND current temp is already above warn - 3
        early_trigger = [
            f for f in relevant
            if f.predicted_temperature_c > (temp_warn - 1.0)
            and reading.temperature_c > (temp_warn - 3.0)
        ]

        if early_trigger:
            worst = max(early_trigger, key=lambda f: f.predicted_temperature_c)
            return True, (
                f"Predictive: forecast at {worst.horizon_minutes} min predicts "
                f"{worst.predicted_temperature_c:.1f}°C (warn threshold {temp_warn}°C). "
                f"Current temp {reading.temperature_c:.1f}°C. Fan activated early. "
                "Note: outdoor conditions unknown — fan effect on humidity not guaranteed."
            )

        # Predicted exceedance of hard max
        max_trigger = [
            f for f in relevant
            if f.predicted_temperature_c >= temp_max
        ]
        if max_trigger:
            worst = max(max_trigger, key=lambda f: f.predicted_temperature_c)
            return True, (
                f"Predictive: forecast at {worst.horizon_minutes} min predicts "
                f"{worst.predicted_temperature_c:.1f}°C ≥ crop maximum {temp_max}°C. "
                f"Current temp {reading.temperature_c:.1f}°C. Fan activated proactively. "
                "Note: outdoor conditions unknown — fan effect on humidity not guaranteed."
            )

        # No predictive trigger — fall back to reactive to avoid needless running
        fan_on, reason = self._reactive_decision(reading, state, cfg)
        return fan_on, (
            "Predictive: forecasts within normal range — applying reactive logic. " + reason
        )

    def _enforce_timing(
        self,
        state: ControlState,
        desired_fan_on: bool,
        reason: str,
        cfg: dict,
        now: datetime,
    ) -> tuple[bool, str]:
        """Prevent rapid fan cycling by enforcing minimum run/off times."""
        min_run = cfg["min_fan_run_seconds"]
        min_off = cfg["min_fan_off_seconds"]

        # Calculate elapsed seconds since last state change.
        # SQLite stores naive datetimes; normalise before subtracting.
        if state.updated_at:
            updated_at = (
                state.updated_at
                if state.updated_at.tzinfo is not None
                else state.updated_at.replace(tzinfo=timezone.utc)
            )
            elapsed = (now - updated_at).total_seconds()
        else:
            elapsed = 9999.0

        if state.fan_on and not desired_fan_on:
            # Trying to turn fan off — check minimum run time
            if elapsed < min_run:
                remaining = int(min_run - elapsed)
                return True, (
                    f"{reason} — minimum run time not elapsed ({remaining}s remaining); "
                    "keeping fan on."
                )

        if not state.fan_on and desired_fan_on:
            # Trying to turn fan on — check minimum off time
            if elapsed < min_off:
                remaining = int(min_off - elapsed)
                return False, (
                    f"{reason} — minimum off time not elapsed ({remaining}s remaining); "
                    "keeping fan off."
                )

        return desired_fan_on, reason


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
control_engine = ControlEngine()


# ---------------------------------------------------------------------------
# Legacy shim — backward-compatible free function used by main.py (FEAT-001)
# ---------------------------------------------------------------------------

def evaluate(db: Session, reading: SensorReading) -> ControlState:
    """Backward-compatible wrapper for the scheduler tick."""
    from app.config import settings
    from app.models import ForecastRecord
    from datetime import timedelta

    crop_config = {
        "temp_max_c": settings.TEMP_MAX_C,
        "temp_warn_c": settings.TEMP_WARN_C,
        "humidity_max_pct": settings.HUMIDITY_MAX_PCT,
        "humidity_min_pct": settings.HUMIDITY_MIN_PCT,
        "hysteresis_c": settings.HYSTERESIS_C,
        "min_fan_run_seconds": settings.MIN_FAN_RUN_SECONDS,
        "min_fan_off_seconds": settings.MIN_FAN_OFF_SECONDS,
    }

    # Fetch recent short-horizon forecasts from DB
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
    forecasts = (
        db.query(ForecastRecord)
        .filter(
            ForecastRecord.greenhouse_id == reading.greenhouse_id,
            ForecastRecord.created_at >= cutoff,
        )
        .all()
    )

    state, _ = control_engine.tick(db, reading, forecasts, crop_config)
    return state


# ---------------------------------------------------------------------------
# Legacy helpers — kept for test_control.py compatibility
# ---------------------------------------------------------------------------

def _reactive_control(state: ControlState, reading: SensorReading) -> None:
    """In-place reactive control used by existing unit tests."""
    temp = reading.temperature_c
    if temp >= REACTIVE_FAN_ON_TEMP:
        state.fan_on = True
        state.recommended_action = "fan_on"
        state.action_reason = (
            f"Reactive mode: temperature {temp}°C "
            f"≥ threshold {REACTIVE_FAN_ON_TEMP}°C."
        )
    elif temp < REACTIVE_FAN_OFF_TEMP and state.fan_on:
        state.fan_on = False
        state.recommended_action = "fan_off"
        state.action_reason = (
            f"Reactive mode: temperature {temp}°C "
            f"< hysteresis {REACTIVE_FAN_OFF_TEMP}°C — fan off."
        )
    else:
        state.recommended_action = "noop"
        state.action_reason = (
            f"Reactive mode: temperature {temp}°C — no action needed."
        )
