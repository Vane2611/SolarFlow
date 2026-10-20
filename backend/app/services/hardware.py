"""Hardware communication interface.

Provides a modular, allowlist-gated interface for talking to the SolarFlow
Arduino sensor node over USB-serial.  Both directions of the link are
handled:

* **Host → Arduino** — control commands.  Only the three commands in
  ALLOWED_COMMANDS may ever be dispatched; any other string raises
  ValueError *before* touching the serial port.  This is non-negotiable.
* **Arduino → host** — sensor readings, acknowledgements and error
  reports, consumed by a background reader thread.

A single background thread owns the serial port: it writes queued commands
and reads incoming lines, so no other thread ever touches the port
concurrently.  Callers submit a command with ``send_command()`` and wait
for the matching acknowledgement; readers collect DHT22 samples with
``poll_readings()``.

In simulation mode (default when no serial port is configured) commands are
logged and a synthetic success response is returned.
"""

from __future__ import annotations

import json
import logging
import queue
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Literal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Command allowlist — the ONLY strings that may reach hardware
# ---------------------------------------------------------------------------
ALLOWED_COMMANDS: frozenset[str] = frozenset({"fan_on", "fan_off", "noop"})

AllowedCommand = Literal["fan_on", "fan_off", "noop"]

# ---------------------------------------------------------------------------
# Timing and buffering constants
# ---------------------------------------------------------------------------
ACK_TIMEOUT_SECONDS = 2.0      # How long to wait for a command acknowledgement
SERIAL_POLL_SECONDS = 0.2      # Serial read timeout — also the I/O poll period
MAX_PENDING_READINGS = 100     # Cap on buffered, not-yet-consumed readings


class HardwareInterface:
    """Talks to the Arduino sensor node over a serial port.

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
        # Background I/O state
        # ------------------------------------------------------------------
        self._io_thread: threading.Thread | None = None
        self._stop = threading.Event()

        self._tx_queue: queue.Queue[str] = queue.Queue()
        self._ack_queue: queue.Queue[dict] = queue.Queue()

        self._state_lock = threading.Lock()
        self._pending_readings: deque[dict] = deque(maxlen=MAX_PENDING_READINGS)
        self._readings_received = 0
        self._last_reading: dict | None = None
        self._last_reading_at: datetime | None = None
        self._firmware_version: str | None = None
        self._connected_at: datetime | None = None

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

    def configure(self, port: str | None, baud_rate: int) -> None:
        """Set the serial port and baud rate.

        Must be called before :meth:`connect`.  Used to apply the
        ``SERIAL_PORT`` / ``SERIAL_BAUD`` settings to the module-level
        singleton at start-up.
        """
        self.port = port
        self.baud_rate = baud_rate

    def connect(self) -> bool:
        """Attempt to open the serial port.  Returns True on success.

        On success a background thread is started that owns the port: it
        writes queued commands and dispatches incoming messages.
        """
        if self.port is None:
            self.last_error = "No serial port configured."
            return False
        try:
            import serial  # type: ignore[import]

            self._serial = serial.Serial(
                self.port, self.baud_rate, timeout=SERIAL_POLL_SECONDS
            )
            logger.info(
                "Connected to Arduino on %s at %d baud.", self.port, self.baud_rate
            )
            self.last_error = None
            self._connected_at = datetime.now(timezone.utc)
            self._start_io_thread()
            return True
        except Exception as exc:
            self.last_error = str(exc)
            logger.warning("Could not connect to hardware: %s", exc)
            return False

    def disconnect(self) -> None:
        """Stop the I/O thread and close the serial port."""
        self._stop.set()

        thread = self._io_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)
        self._io_thread = None

        if self._serial and self._serial.is_open:
            try:
                self._serial.close()
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Error while closing serial port: %s", exc)
        self._serial = None
        self._connected_at = None

    # ------------------------------------------------------------------
    # Background I/O
    # ------------------------------------------------------------------
    def _start_io_thread(self) -> None:
        """Start the thread that owns the serial port."""
        self._stop.clear()
        self._io_thread = threading.Thread(
            target=self._io_loop, daemon=True, name="solarflow-serial"
        )
        self._io_thread.start()

    def _io_loop(self) -> None:
        """Read incoming lines and write queued commands.

        Runs in the background for as long as the serial port is open.
        Partial lines are buffered until their terminating newline
        arrives, so a read timeout can never split a JSON message.
        """
        buffer = bytearray()

        while not self._stop.is_set():
            self._flush_tx()

            try:
                raw = self._serial.readline()  # type: ignore[union-attr]
            except Exception as exc:
                if not self._stop.is_set():
                    self.last_error = str(exc)
                    logger.warning("Serial read failed: %s", exc)
                break

            if not raw:
                continue

            buffer.extend(raw)
            while b"\n" in buffer:
                line, _, remainder = buffer.partition(b"\n")
                buffer = bytearray(remainder)
                self._handle_line(line)

        logger.debug("Serial I/O thread exiting.")

    def _flush_tx(self) -> None:
        """Write every queued command to the serial port."""
        while True:
            try:
                command = self._tx_queue.get_nowait()
            except queue.Empty:
                return

            try:
                payload = json.dumps({"cmd": command}) + "\n"
                self._serial.write(payload.encode())  # type: ignore[union-attr]
                self._serial.flush()  # type: ignore[union-attr]
                logger.debug("Sent command '%s' to Arduino.", command)
            except Exception as exc:
                self.last_error = str(exc)
                logger.error("Failed to write command '%s': %s", command, exc)
                return

    def _handle_line(self, raw: bytes) -> None:
        """Decode and dispatch one newline-terminated message."""
        line = raw.decode("utf-8", errors="replace").strip()
        if not line:
            return

        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            logger.debug("Ignoring non-JSON line from Arduino: %r", line)
            return

        if isinstance(message, dict):
            self._dispatch(message)

    def _dispatch(self, message: dict) -> None:
        """Route an incoming message to its handler."""
        msg_type = message.get("type")

        if msg_type == "reading":
            self._handle_reading(message)
        elif msg_type == "ack":
            self._ack_queue.put(message)
        elif msg_type == "error":
            code = message.get("code", "unknown")
            self.last_error = f"Arduino reported: {code}"
            logger.warning("Arduino reported an error: %s", code)
        elif msg_type == "startup":
            version = message.get("version")
            if version:
                self._firmware_version = str(version)
                logger.info("Arduino firmware %s reported ready.", version)
        else:
            logger.debug("Ignoring unknown message type: %r", msg_type)

    def _handle_reading(self, message: dict) -> None:
        """Store a DHT22 reading in the pending buffer."""
        temp = message.get("temp")
        humidity = message.get("humidity")

        if not isinstance(temp, (int, float)) or not isinstance(humidity, (int, float)):
            logger.warning("Ignoring malformed reading message: %r", message)
            return

        reading: dict[str, Any] = {
            "temperature_c": float(temp),
            "humidity_pct": float(humidity),
            "device_ts": message.get("ts"),
            "received_at": datetime.now(timezone.utc),
        }

        with self._state_lock:
            self._pending_readings.append(reading)
            self._last_reading = reading
            self._last_reading_at = reading["received_at"]
            self._readings_received += 1

        logger.debug(
            "Hardware reading: %.1f °C / %.1f %%",
            reading["temperature_c"],
            reading["humidity_pct"],
        )

    def _wait_for_ack(self, command: str) -> dict | None:
        """Wait for the acknowledgement matching *command*."""
        deadline = time.monotonic() + ACK_TIMEOUT_SECONDS

        while time.monotonic() < deadline:
            try:
                ack = self._ack_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            # "?" is the placeholder the firmware uses for a command it
            # could not parse — treat it as the response to this command.
            if ack.get("cmd") in (command, "?"):
                return ack

        return None

    # ------------------------------------------------------------------
    # Sensor readings
    # ------------------------------------------------------------------
    def poll_readings(self) -> list[dict]:
        """Return every reading received since the previous call.

        Each item is a dict with the keys ``temperature_c``,
        ``humidity_pct``, ``device_ts`` and ``received_at``.  The buffer
        is cleared, so each reading is handed out exactly once.
        """
        with self._state_lock:
            readings = list(self._pending_readings)
            self._pending_readings.clear()
        return readings

    @property
    def latest_reading(self) -> dict | None:
        """The most recent reading received, or None."""
        with self._state_lock:
            return self._last_reading

    @property
    def readings_received(self) -> int:
        """Total number of readings received since the port was opened."""
        with self._state_lock:
            return self._readings_received

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
            in simulation mode, or the parsed acknowledgement from the
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
        # Real mode: queue the command and wait for its acknowledgement
        # ----------------------------------------------------------------
        try:
            # Discard any acknowledgement left over from a previous call
            # so it cannot be mistaken for the response to this one.
            while True:
                try:
                    self._ack_queue.get_nowait()
                except queue.Empty:
                    break

            self._tx_queue.put(command)
            ack = self._wait_for_ack(command)

            if ack is None:
                message = (
                    f"No acknowledgement for '{command}' within "
                    f"{ACK_TIMEOUT_SECONDS:.0f}s."
                )
                self.last_error = message
                logger.error(message)
                return {
                    "success": False,
                    "simulated": False,
                    "command": command,
                    "error": message,
                }

            logger.info("Hardware command '%s' → %s", command, ack)
            return ack
        except Exception as exc:
            self.last_error = str(exc)
            logger.error("Failed to send command '%s': %s", command, exc)
            return {"success": False, "simulated": False, "command": command, "error": str(exc)}

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------
    def get_status(self) -> dict:
        """Return a status snapshot for the devices endpoint."""
        with self._state_lock:
            last_reading = self._last_reading
            last_reading_at = self._last_reading_at
            readings_received = self._readings_received

        uptime = None
        if self._connected_at is not None:
            uptime = (
                datetime.now(timezone.utc) - self._connected_at
            ).total_seconds()

        return {
            "connected": self.connected,
            "simulation_mode": self.simulation_mode,
            "last_command": self._last_command,
            "last_command_at": (
                self._last_command_at.isoformat() if self._last_command_at else None
            ),
            "last_error": self.last_error,
            "port": self.port,
            "baud_rate": self.baud_rate,
            "firmware_version": self._firmware_version,
            "readings_received": readings_received,
            "last_reading_at": (
                last_reading_at.isoformat() if last_reading_at else None
            ),
            "last_reading": last_reading,
            "uptime_seconds": uptime,
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
hardware_interface = HardwareInterface()
