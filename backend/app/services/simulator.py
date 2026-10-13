"""Greenhouse sensor simulator.

Produces realistic diurnal temperature and humidity variations without
a fixed random seed — readings evolve naturally with wall-clock time.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from app.models import DataSource, SensorReading


class GreenhouseSimulator:
    """Stateful simulator for a single greenhouse compartment."""

    # Tomato growing range targets
    _BASE_TEMP = 26.0       # °C midpoint
    _DIURNAL_AMP = 7.0      # °C peak-to-peak amplitude (±3.5 °C)
    _BASE_HUMIDITY = 68.0   # % midpoint
    _HUMIDITY_AMP = 14.0    # % peak-to-peak (anticorrelated with temp)

    # Occasional spike parameters
    _SPIKE_PERIOD_SECONDS = 600   # evaluate spike roughly every 10 min
    _SPIKE_MAGNITUDE_TEMP = 4.0   # °C transient spike amplitude
    _SPIKE_DURATION_SECONDS = 90  # how long the spike lasts

    def __init__(self, greenhouse_id: str) -> None:
        self.greenhouse_id = greenhouse_id

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _diurnal_phase(ts: datetime) -> float:
        """Return a value in [0, 2π] representing position in the day."""
        seconds_since_midnight = (
            ts.hour * 3600 + ts.minute * 60 + ts.second
        )
        return (seconds_since_midnight / 86400.0) * 2.0 * math.pi

    @staticmethod
    def _spike_factor(ts: datetime, period: int, duration: int) -> float:
        """Return a 0-to-1 spike factor driven purely by wall-clock time."""
        epoch_seconds = int(ts.timestamp())
        cycle_position = epoch_seconds % period
        if cycle_position < duration:
            # Smooth half-sine bump within the spike window
            return math.sin(math.pi * cycle_position / duration)
        return 0.0

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def next_reading(self) -> SensorReading:
        """Return a new SensorReading ORM instance with simulated values."""
        now = datetime.now(timezone.utc)
        phase = self._diurnal_phase(now)

        # Temperature: highest around solar noon (phase ≈ π/2 past midnight
        # shifted to peak at ~14:00 local → offset of π/3)
        temp_offset = math.sin(phase - math.pi / 3.0)
        temperature = (
            self._BASE_TEMP
            + (self._DIURNAL_AMP / 2.0) * temp_offset
            + self._SPIKE_MAGNITUDE_TEMP
            * self._spike_factor(now, self._SPIKE_PERIOD_SECONDS, self._SPIKE_DURATION_SECONDS)
        )

        # Humidity: anticorrelated with temperature
        humidity = (
            self._BASE_HUMIDITY
            - (self._HUMIDITY_AMP / 2.0) * temp_offset
        )

        # Small second-order noise via a faster sine harmonic
        noise_phase = phase * 12.0  # 12 oscillations per day
        temperature += 0.5 * math.sin(noise_phase + 1.3)
        humidity += 1.2 * math.sin(noise_phase + 2.7)

        # Clamp to realistic greenhouse ranges
        temperature = max(10.0, min(50.0, temperature))
        humidity = max(20.0, min(98.0, humidity))

        return SensorReading(
            greenhouse_id=self.greenhouse_id,
            timestamp=now,
            temperature_c=round(temperature, 2),
            humidity_pct=round(humidity, 2),
            data_source=DataSource.simulated,
        )
