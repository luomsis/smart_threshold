"""
Moving Average Algorithm.

Uses percentile-based thresholds for sparse data.
Suitable for error counts and low-frequency metrics.
"""

from typing import Any, ClassVar, Optional

import numpy as np
import pandas as pd

from smart_threshold.algorithms.base import BaseAlgorithm, AlgorithmResult
from smart_threshold.algorithms.registry import register_algorithm


@register_algorithm
class MovingAverageAlgorithm(BaseAlgorithm):
    """
    Moving Average / Percentile threshold algorithm.

    For sparse data, traditional time series forecasting performs poorly.
    This algorithm uses percentile-based thresholds which are more robust.

    Suitable for:
    - Error counts
    - Alert counts
    - Low-frequency metrics (mostly zeros)
    """

    algorithm_id: ClassVar[str] = "moving_average"
    default_params: ClassVar[dict[str, Any]] = {
        "percentile": 99.0,
        "window_size": 1440,
        "lower_bound": 0.0,
    }

    @classmethod
    def get_param_schema(cls) -> dict[str, Any]:
        """Return JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "percentile": {
                    "type": "number",
                    "title": "Upper Percentile",
                    "description": "Percentile to use as upper threshold. "
                                   "99 means the threshold will exclude the top 1% of values.",
                    "default": 99.0,
                    "minimum": 90.0,
                    "maximum": 100.0,
                },
                "window_size": {
                    "type": "integer",
                    "title": "Window Size",
                    "description": "Number of recent data points to consider. "
                                   "0 means use all data.",
                    "default": 1440,
                    "minimum": 0,
                    "maximum": 10080,
                },
                "lower_bound": {
                    "type": "number",
                    "title": "Lower Bound",
                    "description": "Minimum value for lower threshold. "
                                   "Use 0 for count-based metrics.",
                    "default": 0.0,
                    "minimum": 0,
                },
            },
            "required": [],
        }

    @classmethod
    def get_name(cls) -> str:
        return "Moving Average"

    @classmethod
    def get_description(cls) -> str:
        return (
            "Uses percentile-based thresholds for sparse or low-frequency data. "
            "Best for error counts, alert counts, and metrics that are mostly zero. "
            "The threshold is set at the specified percentile of historical values."
        )

    def __init__(self, params: Optional[dict[str, Any]] = None):
        super().__init__(params)
        self._median: float = 0.0
        self._upper_threshold: float = 0.0
        self._max_value: float = 0.0
        self._last_timestamp: Optional[pd.Timestamp] = None

    def fit(self, data: pd.Series) -> "MovingAverageAlgorithm":
        """Compute percentile-based statistics."""
        self._validate_input(data)
        self._training_data = data.copy()
        self._last_timestamp = data.index[-1]

        # Apply window if specified
        values = data.values
        window = self.params.get("window_size", 1440)
        if window > 0 and len(values) > window:
            values = values[-window:]

        percentile = self.params.get("percentile", 99.0)

        self._median = float(np.median(values))
        self._upper_threshold = float(np.percentile(values, percentile))
        self._max_value = float(np.max(values))

        self._is_fitted = True
        return self

    def predict(self, periods: int = 1440, freq: str = "1min") -> AlgorithmResult:
        """Generate threshold predictions."""
        if not self._is_fitted:
            raise ValueError("Algorithm must be fitted before prediction")

        timestamps = self._generate_future_timestamps(self._last_timestamp, periods, freq)
        lower_bound = self.params.get("lower_bound", 0.0)

        # Static threshold
        yhat = np.full(periods, self._median)
        yhat_upper = np.full(periods, self._upper_threshold)
        yhat_lower = np.full(periods, lower_bound)

        return AlgorithmResult(
            timestamps=timestamps,
            yhat=yhat,
            yhat_upper=yhat_upper,
            yhat_lower=yhat_lower,
            metadata={
                "algorithm": self.algorithm_id,
                "percentile": self.params.get("percentile", 99.0),
                "median": float(self._median),
                "upper_threshold": float(self._upper_threshold),
                "max_value": float(self._max_value),
            }
        )