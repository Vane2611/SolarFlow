"""Hardware communication interface.

Provides a modular, allowlist-gated interface for sending commands to
the Arduino relay controller over serial. Only the three allowed
commands may be dispatched — arbitrary strings are rejected.

FEAT-001 stub — physical serial integration added in FEAT-004.
"""

from __future__ import annotations

import logging
from typing import Literal

logger = logging.getLogger(__name__)

# Strict command allowlist — never allow arbitrary strings
ALLOWED_COMMANDS: frozenset[str] = frozenset({"fan_on", "fan_off", "noop"})

AllowedCommand = Literal["fan_on", "fan_off", "noop"]


class HardwareInterface:
    """Sends control commands to connected Arduino hardware."""

    def __init__(self, port: str | None = None, baud_rate: int = 9600) -> None:
        self.port = port
        self.baud_rate = baud_rate
        self._serial = None  # serial.Serial instance, populated on connect()
        self.last_error: str | None = None

    @property
    def connected(self) -> bool:
        return self._serial is not None and self._serial.is_open

    def connect(self) -> bool:
        """Attempt to open the serial port. Returns True on success."""
        if self.port is None:
            self.last_error = "No serial port configured."
            return False
        try:
            import serial  # type: ignore[import]
            self._serial = serial.Serial(self.port, self.baud_rate, timeout=1)
            logger.info("Connected to Arduino on %s at %d baud.", self.port, self.baud_rate)
            return True
        except Exception as exc:
            self.last_error = str(exc)
            logger.warning("Could not connect to hardware: %s", exc)
            return False

    def disconnect(self) -> None:
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._serial = None

    def send_command(self, command: AllowedCommand) -> bool:
        """Send a validated command to the Arduino.

        Raises ValueError if the command is not in the allowlist.
        This is the only path through which hardware commands are issued.
        """
        if command not in ALLOWED_COMMANDS:
            raise ValueError(
                f"Command '{command}' is not in the hardware allowlist {ALLOWED_COMMANDS}."
            )
        if command == "noop":
            return True
        if not self.connected:
            logger.debug("Hardware not connected — command '%s' suppressed.", command)
            return False
        try:
            self._serial.write(f"{command}\n".encode())
            self._serial.flush()
            logger.info("Sent command to hardware: %s", command)
            return True
        except Exception as exc:
            self.last_error = str(exc)
            logger.error("Failed to send command '%s': %s", command, exc)
            return False


# Module-level singleton — replaced during hardware integration (FEAT-004)
hardware_interface = HardwareInterface()
