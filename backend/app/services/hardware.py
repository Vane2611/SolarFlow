"""Hardware communication interface.

Provides a modular, allowlist-gated interface for sending commands to
the Arduino relay controller over serial.  Only the three commands in
ALLOWED_COMMANDS may ever be dispatched — any other string raises
ValueError *before* touching the serial port.  This is non-negotiable.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Literal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Command allowlist — the ONLY strings that may reach hardware
# ---------------------------------------------------------------------------
ALLOWED_COMMANDS: frozenset[str] = frozenset({"fan_on", "fan_off", "noop"})

AllowedCommand = Literal["fan_on", "fan_off", "noop"]


class HardwareInterface:
    """Sends control commands to connected Arduino hardware.

    In simulation mode (default when no serial port is configured)
    commands are logged and a synthetic success response is returned.
    In real mode a JSON line is written to the serial port and the
    one-line JSON response is returned.

    Security guarantee: ``send_command`` validates the command string
    against ALLOWED_COMMANDS and raises ValueError before any I/O
    occurs.  Never pass raw user input to this method.
    """

    def __init__(self, port: str | None = None, baud_rate: int = 9600) -> None:
        self.port = port
        self.baud_rate = baud_rate
        self._serial = None  # serial.Serial instance, populated on connect()
        self.last_error: str | None = None
        self._last_command: str | None = None
        self._last_command_at: datetime | None = None

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    @property
    def simulation_mode(self) -> bool:
        """True when no real serial port is open."""
        return not self.connected

    @property
    def connected(self) -> bool:
        """True only when a serial port is open and not closed."""
        return self._serial is not None and self._serial.is_open

    def is_connected(self) -> bool:
        """Callable alias for the ``connected`` property."""
        return self.connected

    def connect(self) -> bool:
        """Attempt to open the serial port.  Returns True on success."""
        if self.port is None:
            self.last_error = "No serial port configured."
            return False
        try:
            import serial  # type: ignore[import]

            self._serial = serial.Serial(self.port, self.baud_rate, timeout=1)
            logger.info(
                "Connected to Arduino on %s at %d baud.", self.port, self.baud_rate
            )
            self.last_error = None
            return True
        except Exception as exc:
            self.last_error = str(exc)
            logger.warning("Could not connect to hardware: %s", exc)
            return False

    def disconnect(self) -> None:
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._serial = None

    # ------------------------------------------------------------------
    # Command dispatch — allowlist enforced here
    # ------------------------------------------------------------------

    def send_command(self, command: str) -> dict:
        """Send a validated command string to the Arduino.

        Parameters
        ----------
        command:
            Must be one of ALLOWED_COMMANDS.  Any other value raises
            ValueError immediately — nothing is sent to hardware.

        Returns
        -------
        dict
            ``{"success": True, "simulated": True, "command": command}``
            in simulation mode, or the parsed JSON response from the
            Arduino in real mode.

        Raises
        ------
        ValueError
            If *command* is not in ALLOWED_COMMANDS.
        """
        # ----------------------------------------------------------------
        # SECURITY: validate before any I/O
        # ----------------------------------------------------------------
        if command not in ALLOWED_COMMANDS:
            raise ValueError(
                f"Command '{command}' is not in the hardware allowlist "
                f"{sorted(ALLOWED_COMMANDS)}.  Only 'fan_on', 'fan_off', "
                "and 'noop' are permitted."
            )

        now = datetime.now(timezone.utc)
        self._last_command = command
        self._last_command_at = now

        if command == "noop":
            logger.debug("noop — no hardware action taken.")
            return {"success": True, "simulated": self.simulation_mode, "command": command}

        # ----------------------------------------------------------------
        # Simulation mode: log and return synthetic response
        # ----------------------------------------------------------------
        if not self.connected:
            logger.info(
                "[SIMULATED] Hardware command: %s (no serial port open)", command
            )
            return {"success": True, "simulated": True, "command": command}

        # ----------------------------------------------------------------
        # Real mode: write JSON line, read one-line JSON response
        # ----------------------------------------------------------------
        try:
            payload = json.dumps({"cmd": command}) + "\n"
            self._serial.write(payload.encode())
            self._serial.flush()
            raw = self._serial.readline().decode().strip()
            response: dict = json.loads(raw) if raw else {"success": True, "command": command}
            logger.info("Hardware command '%s' → %s", command, response)
            return response
        except Exception as exc:
            self.last_error = str(exc)
            logger.error("Failed to send command '%s': %s", command, exc)
            return {"success": False, "simulated": False, "command": command, "error": str(exc)}

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        """Return a status snapshot for the devices endpoint."""
        return {
            "connected": self.connected,
            "simulation_mode": self.simulation_mode,
            "last_command": self._last_command,
            "last_command_at": (
                self._last_command_at.isoformat() if self._last_command_at else None
            ),
            "last_error": self.last_error,
            "port": self.port,
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
hardware_interface = HardwareInterface()
