"""
Tests for pipeline steps.
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from backend.pipeline.steps.fetch import fetch_data
from backend.pipeline.steps.clean import clean_data, detect_outliers
from backend.pipeline.steps.train import train_model, get_algorithm_info
from backend.pipeline.steps.validate import validate_model, simulate_alerts
from backend.pipeline.steps.output import generate_output, format_for_echarts
from smart_threshold.algorithms import AlgorithmResult


class TestFetchStep:
    """Test data fetching step."""

    def test_fetch_with_invalid_datasource(self):
        """Should return error for invalid datasource."""
        config = {
            "name": "invalid",
            "source_type": "prometheus",
            "url": "http://nonexistent:9090",
        }

        end = datetime.now()
        start = end - timedelta(hours=1)

        data, error = fetch_data(
            datasource_config=config,
            metric_id="qps",
            train_start=start,
            train_end=end,
            step="1m",
        )

        # Should get an error for non-existent Prometheus
        assert error is not None or data is None


class TestCleanStep:
    """Test data cleaning step."""

    @pytest.fixture
    def sample_data(self):
        """Generate sample data with missing values."""
        dates = pd.date_range(start="2024-01-01", periods=100, freq="1min")
        values = np.random.randn(100)
        values[50] = np.nan  # Add missing value
        return pd.Series(values, index=dates)

    def test_clean_interpolates_missing(self, sample_data):
        """Should interpolate missing values."""
        cleaned, stats = clean_data(sample_data)

        assert cleaned.isna().sum() == 0
        assert stats["interpolated_count"] == 1

    def test_clean_excludes_periods(self, sample_data):
        """Should exclude specified periods."""
        exclude = [
            {"start": "2024-01-01 00:30:00", "end": "2024-01-01 00:40:00"}
        ]

        cleaned, stats = clean_data(sample_data, exclude_periods=exclude)

        assert stats["excluded_count"] == 11  # 11 minutes excluded

    def test_detect_outliers_iqr(self, sample_data):
        """Should detect outliers using IQR method."""
        # Add outlier
        sample_data.iloc[0] = 1000

        outliers = detect_outliers(sample_data, method="iqr")

        assert outliers.iloc[0] == True

    def test_detect_outliers_zscore(self, sample_data):
        """Should detect outliers using z-score method."""
        # Add outlier
        sample_data.iloc[0] = 1000

        outliers = detect_outliers(sample_data, method="zscore", threshold=3.0)

        assert outliers.iloc[0] == True


class TestTrainStep:
    """Test model training step."""

    @pytest.fixture
    def sample_data(self):
        """Generate sample time series data."""
        dates = pd.date_range(start="2024-01-01", periods=2000, freq="1min")
        values = np.random.normal(100, 10, 2000)
        return pd.Series(values, index=dates)

    def test_train_three_sigma(self, sample_data):
        """Should train three sigma algorithm."""
        model, result, error = train_model(
            data=sample_data,
            algorithm="three_sigma",
            algorithm_params={"sigma_multiplier": 3.0},
        )

        assert error is None
        assert model is not None
        assert result is not None
        assert len(result.yhat) == 1440

    def test_train_moving_average(self, sample_data):
        """Should train moving average algorithm."""
        model, result, error = train_model(
            data=sample_data,
            algorithm="moving_average",
            algorithm_params={"percentile": 99.0},
        )

        assert error is None
        assert result is not None

    def test_train_unknown_algorithm(self, sample_data):
        """Should return error for unknown algorithm."""
        model, result, error = train_model(
            data=sample_data,
            algorithm="unknown_algo",
        )

        assert error is not None
        assert "Unknown algorithm" in error

    def test_train_insufficient_data(self):
        """Should return error for insufficient data."""
        dates = pd.date_range(start="2024-01-01", periods=50, freq="1min")
        data = pd.Series(np.random.randn(50), index=dates)

        model, result, error = train_model(
            data=data,
            algorithm="three_sigma",
        )

        assert error is not None
        assert "Insufficient data" in error

    def test_get_algorithm_info(self):
        """Should return algorithm info."""
        info = get_algorithm_info("three_sigma")

        assert info is not None
        assert info["id"] == "three_sigma"


class TestValidateStep:
    """Test model validation step."""

    @pytest.fixture
    def sample_data(self):
        """Generate sample data."""
        dates = pd.date_range(start="2024-01-01", periods=1000, freq="1min")
        values = np.random.normal(100, 10, 1000)
        return pd.Series(values, index=dates)

    @pytest.fixture
    def sample_prediction(self):
        """Generate sample prediction result."""
        timestamps = pd.date_range(
            start="2024-01-01",
            periods=1440,
            freq="1min"
        ).tolist()
        return AlgorithmResult(
            timestamps=timestamps,
            yhat=np.full(1440, 100.0),
            yhat_upper=np.full(1440, 130.0),
            yhat_lower=np.full(1440, 70.0),
            metadata={"algorithm": "test"},
        )

    def test_validate_model(self, sample_data, sample_prediction):
        """Should validate model and return metrics."""
        metrics = validate_model(
            train_data=sample_data,
            prediction=sample_prediction,
        )

        assert "rmse" in metrics
        assert "mae" in metrics
        assert "coverage" in metrics
        assert "false_alerts" in metrics
        assert 0 <= metrics["coverage"] <= 1

    def test_validate_with_test_data(self, sample_data, sample_prediction):
        """Should validate with separate test data."""
        test_dates = pd.date_range(start="2024-01-02", periods=500, freq="1min")
        test_data = pd.Series(np.random.normal(100, 10, 500), index=test_dates)

        metrics = validate_model(
            train_data=sample_data,
            prediction=sample_prediction,
            test_data=test_data,
        )

        assert metrics["test_samples"] == 500

    def test_simulate_alerts(self, sample_data):
        """Should simulate alerts correctly."""
        upper = np.full(1000, 130.0)
        lower = np.full(1000, 70.0)

        # Add values that exceed bounds
        sample_data.iloc[0] = 150  # Exceeds upper
        sample_data.iloc[1] = 50   # Below lower

        result = simulate_alerts(sample_data, upper, lower)

        assert result["upper_breaches"] >= 1
        assert result["lower_breaches"] >= 1
        assert "alert_rate" in result


class TestOutputStep:
    """Test output generation step."""

    @pytest.fixture
    def sample_prediction(self):
        """Generate sample prediction."""
        timestamps = pd.date_range(
            start="2024-01-01",
            periods=1440,
            freq="1min"
        ).tolist()
        return AlgorithmResult(
            timestamps=timestamps,
            yhat=np.random.normal(100, 5, 1440),
            yhat_upper=np.random.normal(130, 5, 1440),
            yhat_lower=np.random.normal(70, 5, 1440),
            metadata={"algorithm": "test"},
        )

    def test_generate_output(self, sample_prediction):
        """Should generate output correctly."""
        train_stats = {"mean": 100.0, "std": 10.0}
        validation_metrics = {"rmse": 5.0, "coverage": 0.95}

        output = generate_output(
            prediction=sample_prediction,
            train_data_stats=train_stats,
            validation_metrics=validation_metrics,
        )

        assert "upper_bounds" in output
        assert "lower_bounds" in output
        assert "preview_data" in output
        assert len(output["upper_bounds"]) == 1440
        assert len(output["lower_bounds"]) == 1440

    def test_generate_output_uses_prediction_length(self):
        """Should use actual prediction length instead of forcing 1440."""
        timestamps = pd.date_range(
            start="2024-01-01",
            periods=100,
            freq="1min"
        ).tolist()
        prediction = AlgorithmResult(
            timestamps=timestamps,
            yhat=np.full(100, 100.0),
            yhat_upper=np.full(100, 130.0),
            yhat_lower=np.full(100, 70.0),
            metadata={"algorithm": "test"},
        )

        output = generate_output(
            prediction=prediction,
            train_data_stats={},
            validation_metrics={},
        )

        # Should preserve actual prediction length
        assert len(output["upper_bounds"]) == 100
        assert len(output["lower_bounds"]) == 100
        assert len(output["predicted"]) == 100

    def test_format_for_echarts(self):
        """Should format data for ECharts."""
        timestamps = pd.date_range(start="2024-01-01", periods=100, freq="1min")
        actual = np.random.randn(100).tolist()
        predicted = np.full(100, 0.0)
        upper = np.full(100, 1.0)
        lower = np.full(100, -1.0)

        result = format_for_echarts(
            timestamps=timestamps.tolist(),
            actual_values=actual,
            predicted=predicted,
            upper=upper,
            lower=lower,
        )

        assert "xAxis" in result
        assert "series" in result
        assert len(result["series"]) == 4  # actual, predicted, upper, lower