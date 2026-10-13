"""Unit tests for the ML forecasting module (FEAT-002)."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from app.models import DataSource, SensorReading
from app.services.forecasting import (
    HORIZONS,
    ForecastingService,
    build_feature_matrix,
    generate_synthetic_training_data,
    train_models,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_readings(n: int = 60, greenhouse_id: str = "test-gh") -> list[SensorReading]:
    """Return n SensorReading objects (not DB-persisted)."""
    base = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    from datetime import timedelta

    return [
        SensorReading(
            id=i,
            greenhouse_id=greenhouse_id,
            timestamp=base + timedelta(seconds=i * 5),
            temperature_c=25.0 + i * 0.05,
            humidity_pct=65.0 - i * 0.05,
            data_source=DataSource.simulated,
        )
        for i in range(n)
    ]


@pytest.fixture(scope="module")
def small_df() -> pd.DataFrame:
    """4 hours of synthetic data — fast enough for feature/train tests."""
    return generate_synthetic_training_data(n_hours=4)


@pytest.fixture(scope="module")
def trained_service() -> ForecastingService:
    """One trained ForecastingService instance shared across all tests in this module.

    Uses 4 h of synthetic data to keep the test run under ~30 s.
    The training is done via generate_synthetic_training_data so that the
    models are real — not mocked — and metrics are genuinely computed.
    """
    fs = ForecastingService()
    # Override: train on a small but real synthetic dataset
    df = generate_synthetic_training_data(n_hours=4)
    from app.services.forecasting import train_models

    with fs._lock:
        fs._model_store = train_models(df)
        fs._trained = True
        fs._trained_on_synthetic = True
    return fs


# ---------------------------------------------------------------------------
# Synthetic data generator
# ---------------------------------------------------------------------------


class TestGenerateSyntheticData:
    def test_returns_dataframe(self) -> None:
        df = generate_synthetic_training_data(n_hours=1)
        assert isinstance(df, pd.DataFrame)

    def test_required_columns(self) -> None:
        df = generate_synthetic_training_data(n_hours=1)
        assert set(df.columns) >= {"timestamp", "temperature_c", "humidity_pct"}

    def test_row_count(self) -> None:
        # 2 hours × 3600 s / 5 s interval = 1440 rows
        df = generate_synthetic_training_data(n_hours=2)
        assert len(df) == 1440

    def test_temperature_range(self) -> None:
        df = generate_synthetic_training_data(n_hours=2)
        assert df["temperature_c"].between(10.0, 50.0).all()

    def test_humidity_range(self) -> None:
        df = generate_synthetic_training_data(n_hours=2)
        assert df["humidity_pct"].between(20.0, 98.0).all()

    def test_reproducible_with_fixed_seed(self) -> None:
        df1 = generate_synthetic_training_data(n_hours=1)
        df2 = generate_synthetic_training_data(n_hours=1)
        assert df1["temperature_c"].equals(df2["temperature_c"])


# ---------------------------------------------------------------------------
# Feature matrix builder
# ---------------------------------------------------------------------------


class TestBuildFeatureMatrix:
    def test_returns_three_items(self, small_df: pd.DataFrame) -> None:
        result = build_feature_matrix(small_df, horizon_minutes=10)
        assert len(result) == 3

    def test_X_is_dataframe(self, small_df: pd.DataFrame) -> None:
        X, _, _ = build_feature_matrix(small_df, horizon_minutes=10)
        assert isinstance(X, pd.DataFrame)

    def test_no_nan_in_X(self, small_df: pd.DataFrame) -> None:
        X, y_temp, y_humid = build_feature_matrix(small_df, horizon_minutes=10)
        assert not X.isnull().any().any()
        assert not y_temp.isnull().any()
        assert not y_humid.isnull().any()

    def test_feature_count(self, small_df: pd.DataFrame) -> None:
        X, _, _ = build_feature_matrix(small_df, horizon_minutes=10)
        # hour_of_day(1) + 5 temp lags + 5 humid lags
        # + roll_mean_6 + roll_mean_12 + roll_std_6 + roll_std_12 (×2 for temp+humid = 8)
        # + temperature_c + humidity_pct (2) = 21
        assert X.shape[1] == 21

    def test_X_y_same_length(self, small_df: pd.DataFrame) -> None:
        X, y_temp, y_humid = build_feature_matrix(small_df, horizon_minutes=15)
        assert len(X) == len(y_temp) == len(y_humid)

    def test_different_horizons_yield_different_targets(
        self, small_df: pd.DataFrame
    ) -> None:
        _, y10, _ = build_feature_matrix(small_df, horizon_minutes=10)
        _, y30, _ = build_feature_matrix(small_df, horizon_minutes=30)
        assert not y10.equals(y30)


# ---------------------------------------------------------------------------
# Model trainer
# ---------------------------------------------------------------------------


class TestTrainModels:
    def test_returns_dict_for_all_horizons(self, small_df: pd.DataFrame) -> None:
        store = train_models(small_df)
        for horizon in HORIZONS:
            assert horizon in store

    def test_metrics_present_for_each_horizon(self, small_df: pd.DataFrame) -> None:
        store = train_models(small_df)
        for horizon in HORIZONS:
            metrics = store[horizon]["metrics"]
            assert "baseline" in metrics
            assert "random_forest" in metrics

    def test_metrics_are_non_negative_floats(self, small_df: pd.DataFrame) -> None:
        store = train_models(small_df)
        for horizon in HORIZONS:
            for model_key in ("baseline", "random_forest"):
                m = store[horizon]["metrics"][model_key]
                for key in (
                    "mae_temperature",
                    "rmse_temperature",
                    "mae_humidity",
                    "rmse_humidity",
                ):
                    val = m[key]
                    assert isinstance(val, float), (
                        f"{horizon}/{model_key}/{key} is not float"
                    )
                    assert val >= 0.0, f"{horizon}/{model_key}/{key} is negative"

    def test_rmse_gte_mae(self, small_df: pd.DataFrame) -> None:
        """RMSE must be >= MAE by definition."""
        store = train_models(small_df)
        for horizon in HORIZONS:
            for model_key in ("baseline", "random_forest"):
                m = store[horizon]["metrics"][model_key]
                assert m["rmse_temperature"] >= m["mae_temperature"] - 1e-9
                assert m["rmse_humidity"] >= m["mae_humidity"] - 1e-9

    def test_rf_models_fitted(self, small_df: pd.DataFrame) -> None:
        store = train_models(small_df)
        for horizon in HORIZONS:
            assert store[horizon]["rf_temp"] is not None
            assert store[horizon]["rf_humid"] is not None


# ---------------------------------------------------------------------------
# ForecastingService — uses the module-scoped pre-trained instance
# ---------------------------------------------------------------------------


class TestForecastingService:
    def test_is_trained(self, trained_service: ForecastingService) -> None:
        assert trained_service.is_trained

    def test_trained_on_synthetic(self, trained_service: ForecastingService) -> None:
        assert trained_service.trained_on_synthetic

    def test_get_metrics_returns_dict(self, trained_service: ForecastingService) -> None:
        metrics = trained_service.get_metrics()
        assert isinstance(metrics, dict)
        for horizon in HORIZONS:
            assert horizon in metrics

    def test_metrics_not_fabricated(self, trained_service: ForecastingService) -> None:
        """All metric values must be real computed floats, not None."""
        metrics = trained_service.get_metrics()
        for horizon in HORIZONS:
            for model_key in ("baseline", "random_forest"):
                m = metrics[horizon][model_key]
                for key in (
                    "mae_temperature",
                    "rmse_temperature",
                    "mae_humidity",
                    "rmse_humidity",
                ):
                    assert m[key] is not None, (
                        f"Fabricated None metric at horizon={horizon} "
                        f"model={model_key} key={key}"
                    )
                    assert isinstance(m[key], float)

    def test_predict_returns_correct_count(
        self, trained_service: ForecastingService
    ) -> None:
        readings = _make_readings(60)
        records = trained_service.predict(readings, horizons=HORIZONS)
        assert len(records) == len(HORIZONS)

    def test_predict_all_horizons_present(
        self, trained_service: ForecastingService
    ) -> None:
        readings = _make_readings(60)
        records = trained_service.predict(readings, horizons=HORIZONS)
        returned_horizons = {r.horizon_minutes for r in records}
        assert returned_horizons == set(HORIZONS)

    def test_predictions_have_numeric_values(
        self, trained_service: ForecastingService
    ) -> None:
        readings = _make_readings(60)
        records = trained_service.predict(readings, horizons=HORIZONS)
        for r in records:
            assert isinstance(r.predicted_temperature_c, float)
            assert isinstance(r.predicted_humidity_pct, float)
            assert 10.0 <= r.predicted_temperature_c <= 50.0
            assert 20.0 <= r.predicted_humidity_pct <= 98.0

    def test_predictions_marked_not_validated(
        self, trained_service: ForecastingService
    ) -> None:
        """Synthetic-trained models must mark is_validated=False."""
        readings = _make_readings(60)
        records = trained_service.predict(readings, horizons=HORIZONS)
        for r in records:
            assert r.is_validated is False, (
                "Predictions from synthetic-trained models must be is_validated=False"
            )

    def test_predict_empty_readings(
        self, trained_service: ForecastingService
    ) -> None:
        records = trained_service.predict([], horizons=HORIZONS)
        assert records == []

    def test_predict_few_readings_falls_back_to_persistence(
        self, trained_service: ForecastingService
    ) -> None:
        """With <12 readings, the service falls back to persistence baseline."""
        readings = _make_readings(5)
        records = trained_service.predict(readings, horizons=HORIZONS)
        # Persistence: all horizons predict the last known temp/humid
        last = readings[-1]
        for r in records:
            assert r.predicted_temperature_c == pytest.approx(
                last.temperature_c, abs=0.01
            )
            assert r.predicted_humidity_pct == pytest.approx(
                last.humidity_pct, abs=0.01
            )
