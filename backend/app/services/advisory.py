"""Transparent greenhouse advice generation.

The advisory interface is deliberately isolated from the API so a hosted AI
provider can replace or augment these rules later without changing the UI
contract. Recommendations are based only on current, persisted system data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config import settings


@dataclass(frozen=True)
class Recommendation:
    id: str
    priority: str
    category: str
    title: str
    action: str
    reason: str
    confidence: float


def generate_recommendations(
    reading: Any | None,
    forecasts: list[Any],
    active_alerts: list[Any],
    control_state: Any | None,
) -> tuple[str, list[Recommendation], list[str]]:
    """Generate ranked, actionable advice from the latest greenhouse state."""
    recommendations: list[Recommendation] = []
    basis: list[str] = []

    if reading is None:
        recommendations.append(
            Recommendation(
                id="sensor-data",
                priority="high",
                category="monitoring",
                title="Check sensor connectivity",
                action="Inspect the sensor connection and wait for a fresh reading.",
                reason="There is no current greenhouse reading available to assess conditions.",
                confidence=1.0,
            )
        )
        return "Sensor data is unavailable; verify the connection before changing settings.", recommendations, basis

    temp = float(reading.temperature_c)
    humidity = float(reading.humidity_pct)
    basis.append(f"Current reading: {temp:.1f}°C and {humidity:.1f}% humidity")

    if temp > settings.TEMP_MAX_C:
        recommendations.append(
            Recommendation(
                id="cool-greenhouse",
                priority="urgent",
                category="temperature",
                title="Cool the greenhouse now",
                action="Keep ventilation or the fan running and inspect vents for obstructions.",
                reason=f"Temperature is {temp:.1f}°C, above the {settings.TEMP_MAX_C:.1f}°C crop limit.",
                confidence=0.98,
            )
        )
    elif temp > settings.TEMP_WARN_C:
        recommendations.append(
            Recommendation(
                id="prepare-cooling",
                priority="high",
                category="ventilation",
                title="Prepare additional ventilation",
                action="Open available vents or enable predictive ventilation before temperatures rise further.",
                reason=f"Temperature is {temp:.1f}°C and approaching the {settings.TEMP_MAX_C:.1f}°C limit.",
                confidence=0.9,
            )
        )

    if humidity > settings.HUMIDITY_MAX_PCT:
        recommendations.append(
            Recommendation(
                id="reduce-humidity",
                priority="high",
                category="humidity",
                title="Reduce greenhouse humidity",
                action="Increase ventilation and avoid watering until humidity returns to the target range.",
                reason=f"Humidity is {humidity:.1f}%, above the {settings.HUMIDITY_MAX_PCT:.1f}% limit and may encourage fungal disease.",
                confidence=0.96,
            )
        )
    elif humidity < settings.HUMIDITY_MIN_PCT:
        recommendations.append(
            Recommendation(
                id="restore-humidity",
                priority="medium",
                category="humidity",
                title="Restore humidity gradually",
                action="Check irrigation and add water only according to the crop schedule.",
                reason=f"Humidity is {humidity:.1f}%, below the {settings.HUMIDITY_MIN_PCT:.1f}% minimum.",
                confidence=0.9,
            )
        )

    risky_forecasts = [
        forecast for forecast in forecasts
        if forecast.predicted_temperature_c > settings.TEMP_MAX_C
        or forecast.predicted_humidity_pct > settings.HUMIDITY_MAX_PCT
    ]
    if risky_forecasts:
        next_risk = min(risky_forecasts, key=lambda item: item.horizon_minutes)
        basis.append(f"Forecast risk within {next_risk.horizon_minutes} minutes")
        if temp <= settings.TEMP_MAX_C and next_risk.predicted_temperature_c > settings.TEMP_MAX_C:
            recommendations.append(
                Recommendation(
                    id="forecast-heat",
                    priority="high",
                    category="temperature",
                    title="Act before forecast heat arrives",
                    action="Use predictive ventilation and confirm the fan is available.",
                    reason=f"Temperature is forecast to reach {next_risk.predicted_temperature_c:.1f}°C in {next_risk.horizon_minutes} minutes.",
                    confidence=0.86,
                )
            )

    if active_alerts:
        basis.append(f"{len(active_alerts)} active system alert(s)")
    if control_state is not None and bool(control_state.manual_override):
        recommendations.append(
            Recommendation(
                id="review-manual-override",
                priority="medium",
                category="monitoring",
                title="Review the manual override",
                action="Confirm the override is still intentional and restore automation when safe.",
                reason="Manual control is active, so automatic protection may be limited.",
                confidence=0.99,
            )
        )

    if not recommendations:
        recommendations.append(
            Recommendation(
                id="maintain-conditions",
                priority="low",
                category="general",
                title="Maintain current conditions",
                action="Continue monitoring; no immediate intervention is recommended.",
                reason="Temperature and humidity are within the configured crop limits.",
                confidence=0.82,
            )
        )

    priority_order = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
    recommendations.sort(key=lambda item: priority_order[item.priority])
    highest = recommendations[0].priority
    summary = (
        "Immediate attention is recommended."
        if highest in {"urgent", "high"}
        else "Conditions are stable; review the recommendations below."
    )
    return summary, recommendations, basis
