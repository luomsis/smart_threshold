"""
Three Sigma Algorithm.

Uses Welford's online algorithm for computing mean and standard deviation.
Suitable for high-variance, non-seasonal data like response times.
"""

from typing import Any, ClassVar, Optional

import numpy as np
import pandas as pd

from smart_threshold.algorithms.base import BaseAlgorithm, AlgorithmResult
from smart_threshold.algorithms.registry import register_algorithm


@register_algorithm
class ThreeSigmaAlgorithm(BaseAlgorithm):
    """
    Three Sigma threshold algorithm.

    Uses Welford's online algorithm for numerical stability.
    Threshold: mean ± sigma_multiplier * std

    Suitable for:
    - Response time (RT)
    - Latency metrics
    - High-variance non-seasonal data
    """

    algorithm_id: ClassVar[str] = "three_sigma"
    default_params: ClassVar[dict[str, Any]] = {
        "sigma_multiplier": 3.0,
        "use_rolling_window": False,
        "window_size": 1440,
    }

    # Sigma to confidence level mapping
    SIGMA_TO_CONFIDENCE = {
        1.0: 0.68,
        1.645: 0.90,
        1.96: 0.95,
        2.0: 0.9545,
        2.576: 0.99,
        3.0: 0.997,
        3.5: 0.9995,
    }

    @classmethod
    def get_param_schema(cls) -> dict[str, Any]:
        """Return JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "sigma_multiplier": {
                    "type": "number",
                    "title": "Sigma Multiplier",
                    "description": "Number of standard deviations for threshold width. "
                                   "Higher values = wider bounds = fewer alerts.",
                    "default": 3.0,
                    "minimum": 1.0,
                    "maximum": 5.0,
                    "multipleOf": 0.1,
                },
                "use_rolling_window": {
                    "type": "boolean",
                    "title": "Use Rolling Window",
                    "description": "Use a rolling window instead of all data. "
                                   "Recommended for data with trends.",
                    "default": False,
                },
                "window_size": {
                    "type": "integer",
                    "title": "Window Size",
                    "description": "Rolling window size in minutes (only used if rolling window is enabled).",
                    "default": 1440,
                    "minimum": 60,
                    "maximum": 10080,  # 7 days
                },
            },
            "required": [],
        }

    @classmethod
    def get_name(cls) -> str:
        return "Three Sigma"

    @classmethod
    def get_description(cls) -> str:
        return (
            "Uses Welford's online algorithm to compute mean and standard deviation. "
            "Threshold is mean ± N × σ. Best for high-variance, non-seasonal data "
            "like response times and latency metrics."
        )

    def __init__(self, params: Optional[dict[str, Any]] = None):
        super().__init__(params)
        self._mean: float = 0.0
        self._std: float = 0.0
        self._count: int = 0
        self._last_timestamp: Optional[pd.Timestamp] = None

    def fit(self, data: pd.Series) -> "ThreeSigmaAlgorithm":
        """Train using Welford's algorithm."""
        self._validate_input(data)
        self._training_data = data.copy()
        self._last_timestamp = data.index[-1]

        values = data.values

        if self.params.get("use_rolling_window", False):
            window = min(self.params.get("window_size", 1440), len(values))
            values = values[-window:]

        # Welford's online algorithm
        count = 0
        mean = 0.0
        m2 = 0.0

        for x in values:
            count += 1
            delta = x - mean
            mean += delta / count
            delta2 = x - mean
            m2 += delta * delta2

        self._mean = mean
        self._count = count

        if count > 1:
            self._std = np.sqrt(m2 / count)
        else:
            self._std = 0.0

        self._is_fitted = True
        return self

    def predict(self, periods: int = 1440, freq: str = "1min") -> AlgorithmResult:
        """Generate threshold predictions."""
        if not self._is_fitted:
            raise ValueError("Algorithm must be fitted before prediction")

        sigma = self.params.get("sigma_multiplier", 3.0)
        timestamps = self._generate_future_timestamps(self._last_timestamp, periods, freq)

        # Constant threshold
        yhat = np.full(periods, self._mean)
        yhat_upper = np.full(periods, self._mean + sigma * self._std)
        yhat_lower = np.full(periods, max(0, self._mean - sigma * self._std))

        confidence = self._sigma_to_confidence(sigma)

        return AlgorithmResult(
            timestamps=timestamps,
            yhat=yhat,
            yhat_upper=yhat_upper,
            yhat_lower=yhat_lower,
            metadata={
                "algorithm": self.algorithm_id,
                "sigma_multiplier": sigma,
                "mean": float(self._mean),
                "std": float(self._std),
                "confidence_level": confidence,
            }
        )

    def _sigma_to_confidence(self, sigma: float) -> float:
        """Convert sigma to confidence level."""
        for s, cl in sorted(self.SIGMA_TO_CONFIDENCE.items()):
            if sigma <= s:
                return cl
        from scipy import stats
        return 2 * stats.norm.cdf(sigma) - 1