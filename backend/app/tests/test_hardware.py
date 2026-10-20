"""Tests for the serial hardware interface and live reading ingestion."""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from typing import Any, Iterator

import pytest

from app.models import DataSource
from app.services.hardware import ALLOWED_COMMANDS, HardwareInterface


# ---------------------------------------------------------------------------
# Fake serial port
# ---------------------------------------------------------------------------


class FakeSerial:
    """Minimal stand-in for ``serial.Serial``.

    ``feed()`` injects a line as if the Arduino had sent it; ``write()``
    records the command and echoes back a matching acknowledgement.
    """

    def __init__(self) -> None:
        self.is_open = True
        self._rx = bytearray()
        self._tx = bytearray()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Test helpers
    # ------------------------------------------------------------------
    def feed(self, payload: str) -> None:
        """Simulate a line arriving from the Arduino."""
        with self._lock:
            self._rx.extend(payload.encode())

    def written(self) -> list[str]:
        """Every line the host has written to the port."""
        with self._lock:
            return [line for line in self._tx.decode().splitlines() if line]

    # ------------------------------------------------------------------
    # serial.Serial interface
    # ------------------------------------------------------------------
    def readline(self) -> bytes:
        time.sleep(0.02)
        with self._lock:
            index = self._rx.find(b"\n")
            if index == -1:
                return b""
            line = bytes(self._rx[: index + 1])
            del self._rx[: index + 1]
            return line

    def write(self, data: bytes) -> int:
        with self._lock:
            self._tx.extend(data)

        try:
            command = json.loads(data.decode().strip())["cmd"]
        except Exception:
            return len(data)

        self.feed(json.dumps({"type": "ack", "cmd": command, "ok": True}) + "\n")
        return len(data)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        self.is_open = False


@pytest.fixture
def hw(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[HardwareInterface, FakeSerial]]:
    """A HardwareInterface connected to a fake serial port."""
    import serial

    fake = FakeSerial()
    monkeypatch.setattr(serial, "Serial", lambda *args, **kwargs: fake)

    interface = HardwareInterface(port="COM_TEST")
    assert interface.connect() is True

    yield interface, fake

    interface.disconnect()


def wait_for_readings(
    interface: HardwareInterface, count: int = 1, timeout: float = 5.0
) -> list[dict]:
    """Block until *count* readings have arrived, then return them."""
    deadline = time.monotonic() + timeout
    collected: list[dict] = []

    while time.monotonic() < deadline:
        collected.extend(interface.poll_readings())
        if len(collected) >= count:
            break
        time.sleep(0.05)

    return collected


# ---------------------------------------------------------------------------
# Reader thread
# ---------------------------------------------------------------------------


class TestSerialReader:
    def test_reading_message_is_ingested(self, hw: tuple[HardwareInterface, FakeSerial]) -> None:
        interface, fake = hw
        fake.feed(
            json.dumps(
                {"type": "reading", "temp": 25.4, "humidity": 68.2, "ts": 12345}
            )
            + "\n"
        )

        readings = wait_for_readings(interface)

        assert len(readings) == 1
        assert readings[0]["temperature_c"] == pytest.approx(25.4)
        assert readings[0]["humidity_pct"] == pytest.approx(68.2)
        assert readings[0]["device_ts"] == 12345
        assert isinstance(readings[0]["received_at"], datetime)

    def test_partial_line_is_buffered_until_newline(
        self, hw: tuple[HardwareInterface, FakeSerial]
    ) -> None:
        interface, fake = hw
        payload = json.dumps(
            {"type": "reading", "temp": 19.5, "humidity": 55.0, "ts": 7}
        )

        # Deliver the message in two pieces with no trailing newline yet.
        fake.feed(payload[:20])
        time.sleep(0.1)
        assert interface.poll_readings() == []

        fake.feed(payload[20:] + "\n")

        readings = wait_for_readings(interface)
        assert len(readings) == 1
        assert readings[0]["temperature_c"] == pytest.approx(19.5)

    def test_poll_readings_drains_the_buffer(
        self, hw: tuple[HardwareInterface, FakeSerial]
    ) -> None:
        interface, fake = hw
        for index in range(3):
            fake.feed(
                json.dumps(
                    {"type": "reading", "temp": 20.0 + index, "humidity": 50.0, "ts": index}
                )
                + "\n"
            )

        readings = wait_for_readings(interface, count=3)

        assert len(readings) == 3
        assert interface.poll_readings() == []

    def test_malformed_reading_is_ignored(
        self, hw: tuple[HardwareInterface, FakeSerial]
    ) -> None:
        interface, fake = hw
        fake.feed(json.dumps({"type": "reading", "temp": "hot", "humidity": 50}) + "\n")
        fake.feed(
            json.dumps({"type": "reading", "temp": 21.0, "humidity": 50.0}) + "\n"
        )

        readings = wait_for_readings(interface)

        assert len(readings) == 1
        assert readings[0]["temperature_c"] == pytest.approx(21.0)

    def test_non_json_line_is_ignored(
        self, hw: tuple[HardwareInterface, FakeSerial]
    ) -> None:
        interface, fake = hw
        fake.feed("this is not json\n")
        fake.feed(
            json.dumps({"type": "reading", "temp": 22.0, "humidity": 51.0}) + "\n"
        )

        readings = wait_for_readings(interface)

        assert len(readings) == 1
        assert readings[0]["temperature_c"] == pytest.approx(22.0)

    def test_error_message_sets_last_error(
        self, hw: tuple[HardwareInterface, FakeSerial]
    ) -> None:
        interface, fake = hw
        fake.feed(json.dumps({"type": "error", "code": "sensor_fail"}) + "\n")

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and "sensor_fail" not in (interface.last_error or ""):
            time.sleep(0.05)

        assert "sensor_fail" in (interface.last_error or "")

    def test_startup_message_records_firmware_version(
        self, hw: tuple[HardwareInterface, FakeSerial]
    ) -> None:
        interface, fake = hw
        fake.feed(json.dumps({"type": "startup", "version": "1.1.0"}) + "\n")

        deadline = time.monotonic() + 5.0
        while (
            time.monotonic() < deadline
            and interface.get_status()["firmware_version"] is None
        ):
            time.sleep(0.05)

        assert interface.get_status()["firmware_version"] == "1.1.0"


# ---------------------------------------------------------------------------
# Command dispatch over a real (fake) port
# ---------------------------------------------------------------------------


class TestCommandDispatch:
    def test_command_is_written_and_acknowledged(
        self, hw: tuple[HardwareInterface, FakeSerial]
    ) -> None:
        interface, fake = hw

        result = interface.send_command("fan_on")

        assert result["ok"] is True
        assert result["cmd"] == "fan_on"
        assert fake.written() == [json.dumps({"cmd": "fan_on"})]

    def test_unlisted_command_raises_before_any_io(
        self, hw: tuple[HardwareInterface, FakeSerial]
    ) -> None:
        interface, fake = hw

        with pytest.raises(ValueError, match="not in the hardware allowlist"):
            interface.send_command("rm -rf /")

        assert fake.written() == []

    def test_every_allowed_command_is_accepted(
        self, hw: tuple[HardwareInterface, FakeSerial]
    ) -> None:
        interface, _fake = hw

        for command in sorted(ALLOWED_COMMANDS):
            if command == "noop":
                # noop short-circuits before any I/O by design
                result = interface.send_command(command)
            else:
                result = interface.send_command(command)
            assert result.get("ok") is True or result.get("success") is True


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


class TestStatus:
    def test_status_exposes_hardware_details(
        self, hw: tuple[HardwareInterface, FakeSerial]
    ) -> None:
        interface, fake = hw
        fake.feed(
            json.dumps({"type": "reading", "temp": 25.0, "humidity": 60.0}) + "\n"
        )
        wait_for_readings(interface)

        status = interface.get_status()

        assert status["connected"] is True
        assert status["simulation_mode"] is False
        assert status["readings_received"] == 1
        assert status["last_reading_at"] is not None
        assert status["uptime_seconds"] is not None

    def test_disconnect_stops_the_reader(
        self, hw: tuple[HardwareInterface, FakeSerial]
    ) -> None:
        interface, _fake = hw

        interface.disconnect()

        assert interface.connected is False
        assert interface.is_connected() is False


# ---------------------------------------------------------------------------
# Conversion of hardware samples into persisted readings
# ---------------------------------------------------------------------------


class TestCollectReadings:
    def test_hardware_readings_become_real_sensor_rows(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import main

        class StubInterface:
            connected = True

            def poll_readings(self) -> list[dict]:
                return [
                    {
                        "temperature_c": 27.5,
                        "humidity_pct": 63.0,
                        "device_ts": 42,
                        "received_at": datetime(2026, 10, 20, 9, 30, tzinfo=timezone.utc),
                    }
                ]

        monkeypatch.setattr(main, "hardware_interface", StubInterface())
        monkeypatch.setattr(main.settings, "SIMULATION_MODE", False)

        readings = main._collect_readings(simulator=object())

        assert len(readings) == 1
        assert readings[0].data_source == DataSource.real
        assert readings[0].temperature_c == pytest.approx(27.5)
        assert readings[0].humidity_pct == pytest.approx(63.0)

    def test_simulator_is_used_when_hardware_is_disconnected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import main

        class StubInterface:
            connected = False

            def poll_readings(self) -> list[dict]:
                raise AssertionError("must not poll hardware when disconnected")

        monkeypatch.setattr(main, "hardware_interface", StubInterface())
        monkeypatch.setattr(main.settings, "SIMULATION_MODE", False)

        from app.services.simulator import GreenhouseSimulator

        simulator = GreenhouseSimulator(greenhouse_id="greenhouse-01")
        readings = main._collect_readings(simulator=simulator)

        assert len(readings) == 1
        assert readings[0].data_source == DataSource.simulated
