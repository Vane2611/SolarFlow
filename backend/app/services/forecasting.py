"""ML forecasting module: synthetic training data, persistence baseline,
Random Forest regression forecaster, and ForecastingService.

IMPORTANT: All models trained on synthetic data are clearly labelled
``is_validated=False``. Metrics are computed from a chronological
train/test split — never fabricated.
"""

from __future__ import annotations

import logging
import math
import threading
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from app.models import ForecastRecord, SensorReading

logger = logging.getLogger(__name__)

HORIZONS = [10, 15, 30]
# Readings are emitted every SIMULATION_INTERVAL_SECONDS (default 5 s).
# Lag features expressed in reading steps; 1 step ≈ 5 s.
_READING_INTERVAL_SECONDS = 5
_MIN_REAL_READINGS = 50  # below this threshold, use synthetic data


# ---------------------------------------------------------------------------
# (a) Synthetic training data generator
# ---------------------------------------------------------------------------


def generate_synthetic_training_data(n_hours: int = 24) -> pd.DataFrame:
    """Return a DataFrame of synthetic sensor readings spanning ``n_hours``.

    Columns: timestamp (UTC), temperature_c, humidity_pct.

    Uses sinusoidal diurnal patterns with realistic additive noise.
    The data is entirely synthetic and unvalidated — do NOT use these
    values to make claims about real greenhouse conditions or model accuracy
    in production contexts.
    """
    interval_seconds = _READING_INTERVAL_SECONDS
    n_samples = int(n_hours * 3600 / interval_seconds)

    # Anchor to a round start time in the past
    start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    timestamps = [
        start + timedelta(seconds=i * interval_seconds) for i in range(n_samples)
    ]

    rng = np.random.default_rng(seed=42)  # fixed seed for reproducibility of training data

    temps: list[float] = []
    humids: list[float] = []

    for ts in timestamps:
        seconds_since_midnight = ts.hour * 3600 + ts.minute * 60 + ts.second
        phase = (seconds_since_midnight / 86400.0) * 2.0 * math.pi

        # Peak around 14:00 (phase offset ≈ π/3 before peak)
        temp_offset = math.sin(phase - math.pi / 3.0)
        temp = 26.0 + 3.5 * temp_offset + float(rng.normal(0.0, 0.4))

        # Occasional simulated spikes (every ~10 min, lasting ~90 s)
        epoch = int(ts.timestamp())
        spike_cycle = epoch % 600
        if spike_cycle < 90:
            temp += 4.0 * math.sin(math.pi * spike_cycle / 90)

        # High-frequency harmonic noise
        noise_phase = phase * 12.0
        temp += 0.5 * math.sin(noise_phase + 1.3)

        # Humidity anticorrelated with temperature, with independent noise
        humidity = 68.0 - 7.0 * temp_offset + float(rng.normal(0.0, 0.8))
        humidity += 1.2 * math.sin(noise_phase + 2.7)

        temps.append(max(10.0, min(50.0, round(temp, 2))))
        humids.append(max(20.0, min(98.0, round(humidity, 2))))

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "temperature_c": temps,
            "humidity_pct": humids,
        }
    )


# ---------------------------------------------------------------------------
# (b) Feature matrix builder
# ---------------------------------------------------------------------------


def build_feature_matrix(
    df: pd.DataFrame,
    horizon_minutes: int,
) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Build lag/rolling features and create prediction targets.

    Parameters
    ----------
    df:
        DataFrame with columns ``temperature_c``, ``humidity_pct``, and
        ``timestamp``.  Must be sorted ascending by time.
    horizon_minutes:
        How many minutes ahead to predict.  The number of rows to shift is
        computed as ``ceil(horizon_minutes * 60 / _READING_INTERVAL_SECONDS)``.

    Returns
    -------
    X : pd.DataFrame
        Feature matrix (rows without NaN only).
    y_temp : pd.Series
        Target temperature values aligned with X.
    y_humidity : pd.Series
        Target humidity values aligned with X.
    """
    df = df.copy().reset_index(drop=True)

    # Derive hour-of-day from timestamp if available
    if "timestamp" in df.columns:
        df["hour_of_day"] = pd.to_datetime(df["timestamp"]).dt.hour + (
            pd.to_datetime(df["timestamp"]).dt.minute / 60.0
        )
    else:
        df["hour_of_day"] = 0.0

    # Lag features: 1, 2, 3, 6, 12 readings back
    for lag in [1, 2, 3, 6, 12]:
        df[f"temp_lag_{lag}"] = df["temperature_c"].shift(lag)
        df[f"humid_lag_{lag}"] = df["humidity_pct"].shift(lag)

    # Rolling statistics over 6 and 12 reading windows
    for window in [6, 12]:
        df[f"temp_roll_mean_{window}"] = (
            df["temperature_c"].shift(1).rolling(window).mean()
        )
        df[f"temp_roll_std_{window}"] = (
            df["temperature_c"].shift(1).rolling(window).std()
        )
        df[f"humid_roll_mean_{window}"] = (
            df["humidity_pct"].shift(1).rolling(window).mean()
        )
        df[f"humid_roll_std_{window}"] = (
            df["humidity_pct"].shift(1).rolling(window).std()
        )

    # Prediction targets shifted forward by horizon steps
    horizon_steps = math.ceil(horizon_minutes * 60 / _READING_INTERVAL_SECONDS)
    df["target_temp"] = df["temperature_c"].shift(-horizon_steps)
    df["target_humid"] = df["humidity_pct"].shift(-horizon_steps)

    # Drop rows with any NaN (from lags or target shift)
    df.dropna(inplace=True)

    feature_cols = (
        ["hour_of_day"]
        + [f"temp_lag_{l}" for l in [1, 2, 3, 6, 12]]
        + [f"humid_lag_{l}" for l in [1, 2, 3, 6, 12]]
        + [f"temp_roll_mean_{w}" for w in [6, 12]]
        + [f"temp_roll_std_{w}" for w in [6, 12]]
        + [f"humid_roll_mean_{w}" for w in [6, 12]]
        + [f"humid_roll_std_{w}" for w in [6, 12]]
        + ["temperature_c", "humidity_pct"]
    )

    X = df[feature_cols].reset_index(drop=True)
    y_temp = df["target_temp"].reset_index(drop=True)
    y_humid = df["target_humid"].reset_index(drop=True)

    return X, y_temp, y_humid


# ---------------------------------------------------------------------------
# (c) Model trainer
# ---------------------------------------------------------------------------


def train_models(df: pd.DataFrame) -> dict:
    """Train persistence baseline and Random Forest for each horizon.

    Uses a strict chronological 80/20 split — no shuffling — to avoid
    leaking future information into training.

    Returns a ``model_store`` dict keyed by horizon with sub-keys:
    ``rf_temp``, ``rf_humid``, ``metrics``.

    Metrics are computed from the held-out test split only.
    """
    model_store: dict[int, dict] = {}

    for horizon in HORIZONS:
        X, y_temp, y_humid = build_feature_matrix(df, horizon)

        n = len(X)
        if n < 20:
            logger.warning(
                "Horizon %d min: only %d samples after feature engineering — skipping.",
                horizon,
                n,
            )
            model_store[horizon] = {"rf_temp": None, "rf_humid": None, "metrics": {}}
            continue

        # Strict chronological split (no shuffle)
        split_idx = int(n * 0.8)
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_temp_train, y_temp_test = y_temp.iloc[:split_idx], y_temp.iloc[split_idx:]
        y_humid_train, y_humid_test = y_humid.iloc[:split_idx], y_humid.iloc[split_idx:]

        # ---- Persistence baseline: predict last known value ----
        # The "last known" temperature is the most recent lag-1 feature.
        persistence_temp = X_test["temp_lag_1"].values
        persistence_humid = X_test["humid_lag_1"].values

        baseline_mae_temp = float(mean_absolute_error(y_temp_test, persistence_temp))
        baseline_rmse_temp = float(
            math.sqrt(mean_squared_error(y_temp_test, persistence_temp))
        )
        baseline_mae_humid = float(mean_absolute_error(y_humid_test, persistence_humid))
        baseline_rmse_humid = float(
            math.sqrt(mean_squared_error(y_humid_test, persistence_humid))
        )

        # ---- Random Forest ----
        rf_temp = RandomForestRegressor(
            n_estimators=100, random_state=42, n_jobs=-1
        )
        rf_temp.fit(X_train, y_temp_train)
        rf_humid = RandomForestRegressor(
            n_estimators=100, random_state=42, n_jobs=-1
        )
        rf_humid.fit(X_train, y_humid_train)

        rf_pred_temp = rf_temp.predict(X_test)
        rf_pred_humid = rf_humid.predict(X_test)

        rf_mae_temp = float(mean_absolute_error(y_temp_test, rf_pred_temp))
        rf_rmse_temp = float(
            math.sqrt(mean_squared_error(y_temp_test, rf_pred_temp))
        )
        rf_mae_humid = float(mean_absolute_error(y_humid_test, rf_pred_humid))
        rf_rmse_humid = float(
            math.sqrt(mean_squared_error(y_humid_test, rf_pred_humid))
        )

        model_store[horizon] = {
            "rf_temp": rf_temp,
            "rf_humid": rf_humid,
            "metrics": {
                "baseline": {
                    "mae_temperature": round(baseline_mae_temp, 4),
                    "rmse_temperature": round(baseline_rmse_temp, 4),
                    "mae_humidity": round(baseline_mae_humid, 4),
                    "rmse_humidity": round(baseline_rmse_humid, 4),
                },
                "random_forest": {
                    "mae_temperature": round(rf_mae_temp, 4),
                    "rmse_temperature": round(rf_rmse_temp, 4),
                    "mae_humidity": round(rf_mae_humid, 4),
                    "rmse_humidity": round(rf_rmse_humid, 4),
                },
            },
        }

        logger.info(
            "Horizon %d min — baseline MAE temp=%.3f°C, RF MAE temp=%.3f°C",
            horizon,
            baseline_mae_temp,
            rf_mae_temp,
        )

    return model_store


# ---------------------------------------------------------------------------
# (d) ForecastingService singleton
# ---------------------------------------------------------------------------


class ForecastingService:
    """Singleton forecasting service.

    Lazily trains on first use.  Uses synthetic data if fewer than
    ``_MIN_REAL_READINGS`` real readings are available in the database.

    All predictions produced from synthetic-data-trained models are marked
    ``is_validated=False``.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._model_store: dict[int, dict] = {}
        self._trained = False
        self._trained_on_synthetic = True
        self._model_version = "rf-v1"

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(self, db: "Session | None" = None) -> None:
        """Train (or re-train) models.

        If ``db`` is provided and contains sufficient real readings, those
        are used.  Otherwise falls back to synthetic data.
        """
        df: pd.DataFrame | None = None
        use_synthetic = True

        if db is not None:
            readings = (
                db.query(SensorReading)
                .order_by(SensorReading.timestamp.asc())
                .all()
            )
            if len(readings) >= _MIN_REAL_READINGS:
                df = pd.DataFrame(
                    [
                        {
                            "timestamp": r.timestamp,
                            "temperature_c": r.temperature_c,
                            "humidity_pct": r.humidity_pct,
                        }
                        for r in readings
                    ]
                )
                use_synthetic = False
                logger.info(
                    "Training on %d real readings.", len(readings)
                )

        if df is None:
            logger.info(
                "Fewer than %d real readings — training on 24 h synthetic data.",
                _MIN_REAL_READINGS,
            )
            df = generate_synthetic_training_data(n_hours=24)
            use_synthetic = True

        with self._lock:
            self._model_store = train_models(df)
            self._trained = True
            self._trained_on_synthetic = use_synthetic
            logger.info(
                "ForecastingService training complete (synthetic=%s).",
                use_synthetic,
            )

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(
        self,
        recent_readings: list[SensorReading],
        horizons: list[int] | None = None,
    ) -> list[ForecastRecord]:
        """Generate ForecastRecord instances for the requested horizons.

        Falls back to persistence baseline if training has not yet completed
        or if RF models are unavailable for a horizon.
        """
        if not self._trained:
            self.train()  # lazy initialisation on first call

        if horizons is None:
            horizons = HORIZONS

        if len(recent_readings) == 0:
            return []

        # Build a small DataFrame from the supplied readings
        df_recent = pd.DataFrame(
            [
                {
                    "timestamp": r.timestamp,
                    "temperature_c": r.temperature_c,
                    "humidity_pct": r.humidity_pct,
                }
                for r in sorted(recent_readings, key=lambda r: r.timestamp)
            ]
        )

        greenhouse_id = recent_readings[-1].greenhouse_id
        now = datetime.now(timezone.utc)
        is_validated = not self._trained_on_synthetic

        records: list[ForecastRecord] = []

        for horizon in horizons:
            predicted_temp, predicted_humid = self._predict_single(
                df_recent, horizon
            )
            records.append(
                ForecastRecord(
                    greenhouse_id=greenhouse_id,
                    horizon_minutes=horizon,
                    predicted_temperature_c=round(predicted_temp, 2),
                    predicted_humidity_pct=round(predicted_humid, 2),
                    model_version=self._model_version,
                    is_validated=is_validated,
                    created_at=now,
                )
            )

        return records

    def _predict_single(
        self, df_recent: pd.DataFrame, horizon: int
    ) -> tuple[float, float]:
        """Return (predicted_temperature_c, predicted_humidity_pct).

        Uses the RF model for the horizon if available, otherwise falls
        back to the persistence baseline (last known value).
        """
        last_temp = float(df_recent["temperature_c"].iloc[-1])
        last_humid = float(df_recent["humidity_pct"].iloc[-1])

        with self._lock:
            entry = self._model_store.get(horizon, {})

        rf_temp = entry.get("rf_temp")
        rf_humid = entry.get("rf_humid")

        if rf_temp is None or rf_humid is None or len(df_recent) < 12:
            # Not enough history for lag/rolling features — use persistence
            return last_temp, last_humid

        try:
            X, _, _ = build_feature_matrix(df_recent.copy(), horizon)
            if len(X) == 0:
                return last_temp, last_humid
            X_last = X.iloc[[-1]]  # most recent feature row
            temp_pred = float(rf_temp.predict(X_last)[0])
            humid_pred = float(rf_humid.predict(X_last)[0])
            # Clamp to physical limits
            temp_pred = max(10.0, min(50.0, temp_pred))
            humid_pred = max(20.0, min(98.0, humid_pred))
            return temp_pred, humid_pred
        except Exception:
            logger.exception(
                "RF prediction failed for horizon %d min — falling back to persistence.",
                horizon,
            )
            return last_temp, last_humid

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> dict:
        """Return per-horizon MAE/RMSE for both baseline and random_forest.

        Returns an empty dict if training has not yet completed.
        Metrics come from the chronological test split — never fabricated.
        """
        if not self._trained:
            return {}

        with self._lock:
            return {
                horizon: entry.get("metrics", {})
                for horizon, entry in self._model_store.items()
            }

    @property
    def is_trained(self) -> bool:
        return self._trained

    @property
    def trained_on_synthetic(self) -> bool:
        return self._trained_on_synthetic


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

forecasting_service = ForecastingService()
