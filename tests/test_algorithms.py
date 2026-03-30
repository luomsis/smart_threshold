"""
Tests for the algorithm module.
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from smart_threshold.algorithms import (
    AlgorithmRegistry,
    BaseAlgorithm,
    AlgorithmResult,
    ThreeSigmaAlgorithm,
    ProphetAlgorithm,
    MovingAverageAlgorithm,
    HoltWintersAlgorithm,
)


class TestAlgorithmRegistry:
    """Test algorithm registration and discovery."""

    def test_registry_has_algorithms(self):
        """Registry should have registered algorithms."""
        ids = AlgorithmRegistry.list_ids()
        assert "three_sigma" in ids
        assert "prophet" in ids
        assert "moving_average" in ids
        assert "holt_winters" in ids

    def test_get_algorithm(self):
        """Should retrieve algorithm by ID."""
        algo = AlgorithmRegistry.get("three_sigma")
        assert algo is not None
        assert algo.algorithm_id == "three_sigma"

    def test_get_nonexistent_algorithm(self):
        """Should return None for unknown algorithm."""
        algo = AlgorithmRegistry.get("unknown_algo")
        assert algo is None

    def test_create_algorithm(self):
        """Should create algorithm instance with params."""
        algo = AlgorithmRegistry.create("three_sigma", {"sigma_multiplier": 2.5})
        assert algo.params["sigma_multiplier"] == 2.5

    def test_get_all_info(self):
        """Should return info for all algorithms."""
        infos = AlgorithmRegistry.get_all_info()
        assert len(infos) >= 4

        for info in infos:
            assert "id" in info
            assert "name" in info
            assert "description" in info
            assert "param_schema" in info


class TestThreeSigmaAlgorithm:
    """Test Three Sigma algorithm."""

    @pytest.fixture
    def sample_data(self):
        """Generate sample time series data."""
        dates = pd.date_range(
            start="2024-01-01",
            periods=2000,
            freq="1min"
        )
        values = np.random.normal(100, 10, 2000)
        return pd.Series(values, index=dates)

    def test_get_param_schema(self):
        """Schema should be valid JSON Schema."""
        schema = ThreeSigmaAlgorithm.get_param_schema()
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "sigma_multiplier" in schema["properties"]

    def test_fit_and_predict(self, sample_data):
        """Should fit and predict correctly."""
        algo = ThreeSigmaAlgorithm({"sigma_multiplier": 3.0})
        algo.fit(sample_data)

        assert algo.is_fitted
        assert algo._mean > 0
        assert algo._std > 0

        result = algo.predict(periods=1440)
        assert len(result.timestamps) == 1440
        assert len(result.yhat) == 1440
        assert len(result.yhat_upper) == 1440
        assert len(result.yhat_lower) == 1440

    def test_threshold_values(self, sample_data):
        """Threshold should be mean ± sigma * std."""
        algo = ThreeSigmaAlgorithm({"sigma_multiplier": 3.0})
        algo.fit(sample_data)

        result = algo.predict(periods=100)

        # Upper should be greater than predicted
        assert all(result.yhat_upper >= result.yhat)
        # Lower should be less than predicted
        assert all(result.yhat_lower <= result.yhat)

    def test_rolling_window(self, sample_data):
        """Should use rolling window when configured."""
        algo = ThreeSigmaAlgorithm({
            "sigma_multiplier": 3.0,
            "use_rolling_window": True,
            "window_size": 500,
        })
        algo.fit(sample_data)

        assert algo.is_fitted
        result = algo.predict(periods=100)
        assert len(result.yhat) == 100


class TestMovingAverageAlgorithm:
    """Test Moving Average algorithm."""

    @pytest.fixture
    def sparse_data(self):
        """Generate sparse data (mostly zeros)."""
        dates = pd.date_range(
            start="2024-01-01",
            periods=2000,
            freq="1min"
        )
        values = np.zeros(2000)
        # Add some non-zero values
        values[::100] = np.random.randint(1, 10, 20)
        return pd.Series(values, index=dates)

    def test_fit_and_predict(self, sparse_data):
        """Should fit and predict correctly."""
        algo = MovingAverageAlgorithm({"percentile": 99.0})
        algo.fit(sparse_data)

        assert algo.is_fitted

        result = algo.predict(periods=1440)
        assert len(result.timestamps) == 1440
        assert result.metadata["percentile"] == 99.0

    def test_percentile_threshold(self, sparse_data):
        """Upper threshold should be at specified percentile."""
        percentile = 95.0
        algo = MovingAverageAlgorithm({"percentile": percentile})
        algo.fit(sparse_data)

        expected_upper = np.percentile(sparse_data.values, percentile)
        result = algo.predict(periods=10)

        assert abs(result.yhat_upper[0] - expected_upper) < 0.01


class TestHoltWintersAlgorithm:
    """Test Holt-Winters algorithm."""

    @pytest.fixture
    def seasonal_data(self):
        """Generate seasonal data with trend."""
        dates = pd.date_range(
            start="2024-01-01",
            periods=3000,
            freq="1min"
        )
        t = np.arange(3000)
        # Daily seasonality (1440 minutes)
        seasonal = 10 * np.sin(2 * np.pi * t / 1440)
        trend = 0.01 * t
        noise = np.random.normal(0, 1, 3000)
        values = 100 + seasonal + trend + noise
        return pd.Series(values, index=dates)

    def test_fit_and_predict(self, seasonal_data):
        """Should fit and predict correctly."""
        algo = HoltWintersAlgorithm({
            "alpha": 0.3,
            "beta": 0.1,
            "gamma": 0.1,
            "seasonal_periods": 1440,
        })
        algo.fit(seasonal_data)

        assert algo.is_fitted

        result = algo.predict(periods=1440)
        assert len(result.timestamps) == 1440

    def test_fallback_to_simple(self):
        """Should fallback to simple smoothing with insufficient data."""
        dates = pd.date_range(start="2024-01-01", periods=100, freq="1min")
        values = np.random.normal(50, 5, 100)
        data = pd.Series(values, index=dates)

        algo = HoltWintersAlgorithm({"seasonal_periods": 1440})
        algo.fit(data)

        assert algo.is_fitted
        # Should have used simple smoothing due to insufficient data


class TestAlgorithmResult:
    """Test AlgorithmResult dataclass."""

    def test_to_dict(self):
        """Should convert to dictionary."""
        now = datetime.now()
        result = AlgorithmResult(
            timestamps=[now, now + timedelta(minutes=1)],
            yhat=np.array([10.0, 11.0]),
            yhat_upper=np.array([15.0, 16.0]),
            yhat_lower=np.array([5.0, 6.0]),
            metadata={"algorithm": "test"},
        )

        d = result.to_dict()
        assert "timestamps" in d
        assert "yhat" in d
        assert len(d["yhat"]) == 2

    def test_to_echarts_format(self):
        """Should convert to ECharts format."""
        now = datetime.now()
        result = AlgorithmResult(
            timestamps=[now, now + timedelta(minutes=1)],
            yhat=np.array([10.0, 11.0]),
            yhat_upper=np.array([15.0, 16.0]),
            yhat_lower=np.array([5.0, 6.0]),
            metadata={"algorithm": "test"},
        )

        echarts = result.to_echarts_format()
        assert "timestamps" in echarts
        assert "predicted" in echarts
        assert "upper" in echarts
        assert "lower" in echarts
        assert len(echarts["timestamps"]) == 2


class TestAlgorithmValidation:
    """Test algorithm parameter validation."""

    def test_validate_valid_params(self):
        """Should pass validation with valid params."""
        algo = ThreeSigmaAlgorithm()
        is_valid, error = algo.validate_params({"sigma_multiplier": 3.0})
        assert is_valid
        assert error is None

    def test_validate_missing_optional_params(self):
        """Should pass with missing optional params."""
        algo = ThreeSigmaAlgorithm()
        is_valid, error = algo.validate_params({})
        assert is_valid