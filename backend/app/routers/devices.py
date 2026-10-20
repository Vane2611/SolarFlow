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
    """Return connection status, last reading time, hardware status, and error state."""
    latest = (
        db.query(SensorReading)
        .filter(SensorReading.greenhouse_id == settings.GREENHOUSE_ID)
        .order_by(SensorReading.timestamp.desc())
        .first()
    )

    hw_status = hardware_interface.get_status()

    return DeviceStatusResponse(
        greenhouse_id=settings.GREENHOUSE_ID,
        simulation_mode=hw_status["simulation_mode"],
        last_reading_at=latest.timestamp if latest else None,
        serial_port=hw_status["port"],
        connected=hw_status["connected"],
        last_error=hw_status["last_error"],
        last_command=hw_status["last_command"],
        last_command_at=hw_status["last_command_at"],
        firmware_version=hw_status["firmware_version"],
        uptime_seconds=hw_status["uptime_seconds"],
    )
