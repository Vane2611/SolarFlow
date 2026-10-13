"""Devices router: hardware connection status."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import SensorReading
from app.schemas import DeviceStatusResponse
from app.services.hardware import hardware_interface

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("/status", response_model=DeviceStatusResponse)
def get_device_status(db: Session = Depends(get_db)) -> DeviceStatusResponse:
    """Return connection status, last reading time, and error state."""
    latest = (
        db.query(SensorReading)
        .filter(SensorReading.greenhouse_id == settings.GREENHOUSE_ID)
        .order_by(SensorReading.timestamp.desc())
        .first()
    )

    return DeviceStatusResponse(
        greenhouse_id=settings.GREENHOUSE_ID,
        simulation_mode=settings.SIMULATION_MODE,
        last_reading_at=latest.timestamp if latest else None,
        serial_port=hardware_interface.port,
        connected=hardware_interface.connected,
        last_error=hardware_interface.last_error,
    )
