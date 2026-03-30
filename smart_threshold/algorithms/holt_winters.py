"""
Holt-Winters Algorithm.

Uses triple exponential smoothing for forecasting.
Suitable for data with trend and seasonality.
"""

from typing import Any, ClassVar, Optional

import numpy as np
import pandas as pd

from smart_threshold.algorithms.base import BaseAlgorithm, AlgorithmResult
from smart_threshold.algorithms.registry import register_algorithm


@register_algorithm
class HoltWintersAlgorithm(BaseAlgorithm):
    """
    Holt-Winters (Triple Exponential Smoothing) algorithm.

    Combines level, trend, and seasonality components for forecasting.
    Suitable for data with both trend and seasonal patterns.

    Suitable for:
    - Metrics with trend and seasonality
    - Short-term forecasting
    - When Prophet is too heavy
    """

    algorithm_id: ClassVar[str] = "holt_winters"
    default_params: ClassVar[dict[str, Any]] = {
        "alpha": 0.3,        # Level smoothing
        "beta": 0.1,         # Trend smoothing
        "gamma": 0.1,        # Seasonal smoothing
        "seasonal_periods": 1440,  # Daily seasonality for minute data
        "confidence_multiplier": 1.96,
    }

    @classmethod
    def get_param_schema(cls) -> dict[str, Any]:
        """Return JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "alpha": {
                    "type": "number",
                    "title": "Alpha (Level Smoothing)",
                    "description": "Smoothing factor for level (0-1). "
                                   "Higher values = more weight on recent observations.",
                    "default": 0.3,
                    "minimum": 0.01,
                    "maximum": 1.0,
                },
                "beta": {
                    "type": "number",
                    "title": "Beta (Trend Smoothing)",
                    "description": "Smoothing factor for trend (0-1). "
                                   "Higher values = faster trend adaptation.",
                    "default": 0.1,
                    "minimum": 0.01,
                    "maximum": 1.0,
                },
                "gamma": {
                    "type": "number",
                    "title": "Gamma (Seasonal Smoothing)",
                    "description": "Smoothing factor for seasonality (0-1).",
                    "default": 0.1,
                    "minimum": 0.01,
                    "maximum": 1.0,
                },
                "seasonal_periods": {
                    "type": "integer",
                    "title": "Seasonal Periods",
                    "description": "Number of periods in a seasonal cycle. "
                                   "1440 = 1 day for minute data.",
                    "default": 1440,
                    "minimum": 2,
                    "maximum": 10080,
                },
                "confidence_multiplier": {
                    "type": "number",
                    "title": "Confidence Multiplier",
                    "description": "Multiplier for confidence interval width. "
                                   "1.96 = 95%, 2.576 = 99%.",
                    "default": 1.96,
                    "minimum": 1.0,
                    "maximum": 4.0,
                },
            },
            "required": [],
        }

    @classmethod
    def get_name(cls) -> str:
        return "Holt-Winters"

    @classmethod
    def get_description(cls) -> str:
        return (
            "Uses triple exponential smoothing (Holt-Winters) for forecasting. "
            "Captures level, trend, and seasonality components. "
            "Good alternative to Prophet when you need lighter-weight processing."
        )

    def __init__(self, params: Optional[dict[str, Any]] = None):
        super().__init__(params)
        self._model: Optional[Any] = None
        self._fitted_values: Optional[np.ndarray] = None
        self._residual_std: float = 0.0
        self._last_timestamp: Optional[pd.Timestamp] = None

    def fit(self, data: pd.Series) -> "HoltWintersAlgorithm":
        """Fit Holt-Winters model."""
        self._validate_input(data)
        self._training_data = data.copy()
        self._last_timestamp = data.index[-1]

        values = data.values
        seasonal_periods = self.params.get("seasonal_periods", 1440)

        # Check if we have enough data for seasonality
        if len(values) < 2 * seasonal_periods:
            # Fall back to simple exponential smoothing
            self._fit_simple(values)
        else:
            self._fit_hw(values, seasonal_periods)

        self._is_fitted = True
        return self

    def _fit_simple(self, values: np.ndarray) -> None:
        """Fit simple exponential smoothing as fallback."""
        alpha = self.params.get("alpha", 0.3)

        # Simple exponential smoothing
        level = values[0]
        fitted = [level]

        for i in range(1, len(values)):
            level = alpha * values[i] + (1 - alpha) * level
            fitted.append(level)

        self._fitted_values = np.array(fitted)
        self._residual_std = float(np.std(values - fitted))

    def _fit_hw(self, values: np.ndarray, seasonal_periods: int) -> None:
        """Fit Holt-Winters model using statsmodels."""
        try:
            from statsmodels.tsa.holtwinters import ExponentialSmoothing

            alpha = self.params.get("alpha", 0.3)
            beta = self.params.get("beta", 0.1)
            gamma = self.params.get("gamma", 0.1)

            model = ExponentialSmoothing(
                values,
                seasonal_periods=seasonal_periods,
                trend="add",
                seasonal="add",
                damped_trend=True
            )

            self._model = model.fit(
                smoothing_level=alpha,
                smoothing_trend=beta,
                smoothing_seasonal=gamma,
                optimized=False
            )

            self._fitted_values = self._model.fittedvalues
            self._residual_std = float(np.std(self._model.resid))

        except Exception:
            # Fall back to simple smoothing
            self._fit_simple(values)

    def predict(self, periods: int = 1440, freq: str = "1min") -> AlgorithmResult:
        """Generate threshold predictions."""
        if not self._is_fitted:
            raise ValueError("Algorithm must be fitted before prediction")

        timestamps = self._generate_future_timestamps(self._last_timestamp, periods, freq)
        multiplier = self.params.get("confidence_multiplier", 1.96)

        if self._model is not None:
            # Use Holt-Winters forecast
            forecast = self._model.forecast(periods)
            yhat = forecast.values
        else:
            # Use last fitted value
            last_level = self._fitted_values[-1]
            yhat = np.full(periods, last_level)

        yhat_upper = yhat + multiplier * self._residual_std
        yhat_lower = np.maximum(0, yhat - multiplier * self._residual_std)

        return AlgorithmResult(
            timestamps=timestamps,
            yhat=yhat,
            yhat_upper=yhat_upper,
            yhat_lower=yhat_lower,
            metadata={
                "algorithm": self.algorithm_id,
                "alpha": self.params.get("alpha", 0.3),
                "beta": self.params.get("beta", 0.1),
                "gamma": self.params.get("gamma", 0.1),
                "residual_std": float(self._residual_std),
            }
        )