"""Control router: mode switching and manual override."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import ControlMode, ControlState
from app.schemas import ControlModeRequest, ControlStateOut, ManualOverrideRequest

router = APIRouter(prefix="/control", tags=["control"])


def _get_or_create_state(db: Session) -> ControlState:
    state = (
        db.query(ControlState)
        .filter(ControlState.greenhouse_id == settings.GREENHOUSE_ID)
        .order_by(ControlState.updated_at.desc())
        .first()
    )
    if state is None:
        state = ControlState(
            greenhouse_id=settings.GREENHOUSE_ID,
            mode=ControlMode.reactive,
            fan_on=False,
            manual_override=False,
        )
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


@router.get("/mode", response_model=ControlStateOut)
def get_control_mode(db: Session = Depends(get_db)) -> ControlStateOut:
    """Return the current control state."""
    return _get_or_create_state(db)  # type: ignore[return-value]


@router.post("/mode", response_model=ControlStateOut)
def set_control_mode(
    body: ControlModeRequest,
    db: Session = Depends(get_db),
) -> ControlStateOut:
    """Switch between reactive, predictive, and manual modes."""
    state = _get_or_create_state(db)
    state.mode = ControlMode(body.mode)
    state.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(state)
    return state  # type: ignore[return-value]


@router.post("/manual-override", response_model=ControlStateOut)
def manual_override(
    body: ManualOverrideRequest,
    db: Session = Depends(get_db),
) -> ControlStateOut:
    """Apply a manual override action.

    Only 'fan_on', 'fan_off', and 'noop' are accepted.
    Any other value is rejected by Pydantic with HTTP 422 before this
    handler is reached.
    """
    state = _get_or_create_state(db)
    now = datetime.now(timezone.utc)

    if body.action == "fan_on":
        state.fan_on = True
    elif body.action == "fan_off":
        state.fan_on = False
    # 'noop' leaves fan_on unchanged

    state.manual_override = True
    state.override_expires_at = now + timedelta(seconds=body.duration_seconds)
    state.recommended_action = body.action
    state.action_reason = (
        f"Manual override: '{body.action}' for {body.duration_seconds}s."
    )
    state.updated_at = now

    db.commit()
    db.refresh(state)
    return state  # type: ignore[return-value]
