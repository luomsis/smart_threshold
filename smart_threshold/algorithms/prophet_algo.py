"""
Prophet Algorithm.

Uses Facebook Prophet for time series forecasting.
Suitable for seasonal data like QPS and traffic metrics.
"""

import warnings
from typing import Any, ClassVar, Optional

import numpy as np
import pandas as pd

from smart_threshold.algorithms.base import BaseAlgorithm, AlgorithmResult
from smart_threshold.algorithms.registry import register_algorithm


@register_algorithm
class ProphetAlgorithm(BaseAlgorithm):
    """
    Prophet-based threshold algorithm.

    Uses Facebook Prophet for seasonal time series forecasting.
    Automatically detects daily, weekly, and yearly seasonality.

    Suitable for:
    - QPS (queries per second)
    - Connection counts
    - Traffic metrics with clear daily patterns
    """

    algorithm_id: ClassVar[str] = "prophet"
    default_params: ClassVar[dict[str, Any]] = {
        "daily_seasonality": True,
        "weekly_seasonality": False,
        "yearly_seasonality": False,
        "seasonality_mode": "additive",
        "interval_width": 0.95,
        "n_changepoints": 25,
        "changepoint_prior_scale": 0.05,
    }

    @classmethod
    def get_param_schema(cls) -> dict[str, Any]:
        """Return JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "daily_seasonality": {
                    "type": "boolean",
                    "title": "Daily Seasonality",
                    "description": "Enable daily seasonality pattern detection.",
                    "default": True,
                },
                "weekly_seasonality": {
                    "type": "boolean",
                    "title": "Weekly Seasonality",
                    "description": "Enable weekly seasonality pattern detection.",
                    "default": False,
                },
                "yearly_seasonality": {
                    "type": "boolean",
                    "title": "Yearly Seasonality",
                    "description": "Enable yearly seasonality pattern detection.",
                    "default": False,
                },
                "seasonality_mode": {
                    "type": "string",
                    "title": "Seasonality Mode",
                    "description": "Additive or multiplicative seasonality. "
                                   "Use multiplicative for data where variance grows with level.",
                    "default": "additive",
                    "enum": ["additive", "multiplicative"],
                },
                "interval_width": {
                    "type": "number",
                    "title": "Interval Width",
                    "description": "Width of the uncertainty intervals. "
                                   "0.95 means 95% confidence interval.",
                    "default": 0.95,
                    "minimum": 0.8,
                    "maximum": 0.99,
                },
                "n_changepoints": {
                    "type": "integer",
                    "title": "Number of Changepoints",
                    "description": "Number of potential changepoints in trend.",
                    "default": 25,
                    "minimum": 5,
                    "maximum": 100,
                },
                "changepoint_prior_scale": {
                    "type": "number",
                    "title": "Changepoint Prior Scale",
                    "description": "Flexibility of the trend. Higher values allow more trend changes.",
                    "default": 0.05,
                    "minimum": 0.001,
                    "maximum": 0.5,
                },
            },
            "required": [],
        }

    @classmethod
    def get_name(cls) -> str:
        return "Prophet"

    @classmethod
    def get_description(cls) -> str:
        return (
            "Uses Facebook Prophet for time series forecasting. "
            "Automatically detects seasonal patterns (daily, weekly, yearly). "
            "Best for QPS, connection counts, and traffic metrics with clear patterns."
        )

    def __init__(self, params: Optional[dict[str, Any]] = None):
        super().__init__(params)
        self._model: Optional[Any] = None
        self._fallback_mean: Optional[float] = None
        self._fallback_std: Optional[float] = None
        self._last_timestamp: Optional[pd.Timestamp] = None
        self._use_fallback: bool = False

    def fit(self, data: pd.Series) -> "ProphetAlgorithm":
        """Train Prophet model."""
        self._validate_input(data)
        self._training_data = data.copy()
        self._last_timestamp = data.index[-1]

        # Remove timezone from index if present (Prophet doesn't support timezone)
        index = data.index
        if index.tz is not None:
            # Convert to timezone-naive by removing tz info
            index = index.tz_localize(None)

        df = pd.DataFrame({"ds": index, "y": data.values})

        try:
            from prophet import Prophet

            # Build Prophet params
            prophet_params = {
                "daily_seasonality": self.params.get("daily_seasonality", True),
                "weekly_seasonality": self.params.get("weekly_seasonality", False),
                "yearly_seasonality": self.params.get("yearly_seasonality", False),
                "seasonality_mode": self.params.get("seasonality_mode", "additive"),
                "interval_width": self.params.get("interval_width", 0.95),
                "n_changepoints": self.params.get("n_changepoints", 25),
                "changepoint_prior_scale": self.params.get("changepoint_prior_scale", 0.05),
            }

            self._model = Prophet(**prophet_params)
            self._model.fit(df)
            self._use_fallback = False

        except Exception as e:
            import traceback
            error_msg = f"Prophet training failed: {e}\n{traceback.format_exc()}"
            warnings.warn(error_msg)
            print(f"[Prophet] Training failed: {e}")
            print(f"[Prophet] Traceback: {traceback.format_exc()}")
            self._fallback_mean = float(data.mean())
            self._fallback_std = float(data.std())
            self._model = None
            self._use_fallback = True

        self._is_fitted = True
        return self

    def predict(self, periods: int = 1440, freq: str = "1min") -> AlgorithmResult:
        """Generate threshold predictions."""
        if not self._is_fitted:
            raise ValueError("Algorithm must be fitted before prediction")

        timestamps = self._generate_future_timestamps(self._last_timestamp, periods, freq)

        if self._model is not None and not self._use_fallback:
            return self._predict_with_prophet(periods, freq, timestamps)
        else:
            return self._predict_with_fallback(periods, timestamps)

    def _predict_with_prophet(
        self,
        periods: int,
        freq: str,
        timestamps: list
    ) -> AlgorithmResult:
        """Use Prophet for prediction."""
        future = self._model.make_future_dataframe(periods=periods, freq=freq)
        forecast = self._model.predict(future)
        pred_data = forecast.tail(periods)

        return AlgorithmResult(
            timestamps=timestamps,
            yhat=pred_data["yhat"].values,
            yhat_upper=pred_data["yhat_upper"].values,
            yhat_lower=pred_data["yhat_lower"].values,
            metadata={
                "algorithm": self.algorithm_id,
                "interval_width": self.params.get("interval_width", 0.95),
                "use_fallback": False,
            }
        )

    def _predict_with_fallback(
        self,
        periods: int,
        timestamps: list
    ) -> AlgorithmResult:
        """Use simple statistics as fallback."""
        sigma = 1.96  # 95% confidence
        if self.params.get("interval_width", 0.95) >= 0.99:
            sigma = 2.576

        yhat = np.full(periods, self._fallback_mean)
        yhat_upper = np.full(periods, self._fallback_mean + sigma * self._fallback_std)
        yhat_lower = np.full(periods, max(0, self._fallback_mean - sigma * self._fallback_std))

        return AlgorithmResult(
            timestamps=timestamps,
            yhat=yhat,
            yhat_upper=yhat_upper,
            yhat_lower=yhat_lower,
            metadata={
                "algorithm": "prophet_fallback",
                "use_fallback": True,
                "mean": float(self._fallback_mean),
                "std": float(self._fallback_std),
            }
        )