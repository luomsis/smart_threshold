"""
Base algorithm abstract class with JSON Schema support.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar, Optional

import numpy as np
import pandas as pd


@dataclass
class AlgorithmResult:
    """
    Result from algorithm prediction.

    Attributes:
        timestamps: List of timestamps for each prediction point
        yhat: Predicted values (center line)
        yhat_upper: Upper bound values
        yhat_lower: Lower bound values
        metadata: Additional metadata (metrics, parameters used, etc.)
    """

    timestamps: list[datetime]
    yhat: np.ndarray
    yhat_upper: np.ndarray
    yhat_lower: np.ndarray
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamps": [ts.isoformat() for ts in self.timestamps],
            "yhat": self.yhat.tolist(),
            "yhat_upper": self.yhat_upper.tolist(),
            "yhat_lower": self.yhat_lower.tolist(),
            "metadata": self.metadata,
        }

    def to_echarts_format(self) -> dict[str, list]:
        """
        Convert to ECharts format for frontend visualization.

        Returns:
            Dictionary with 'timestamps', 'actual', 'upper', 'lower' arrays
        """
        return {
            "timestamps": [ts.strftime("%Y-%m-%d %H:%M:%S") for ts in self.timestamps],
            "predicted": self.yhat.tolist(),
            "upper": self.yhat_upper.tolist(),
            "lower": self.yhat_lower.tolist(),
        }


class BaseAlgorithm(ABC):
    """
    Abstract base class for threshold algorithms.

    All algorithms must implement:
    - get_param_schema(): Return JSON Schema for frontend form rendering
    - get_name(): Return display name
    - get_description(): Return description
    - fit(): Train the algorithm
    - predict(): Generate predictions

    The JSON Schema format follows JSON Schema draft-07 specification.
    Example:
        {
            "type": "object",
            "properties": {
                "sigma_multiplier": {
                    "type": "number",
                    "title": "Sigma Multiplier",
                    "description": "Number of standard deviations for threshold",
                    "default": 3.0,
                    "minimum": 1.0,
                    "maximum": 5.0
                }
            },
            "required": []
        }
    """

    # Algorithm identifier (lowercase, used in API)
    algorithm_id: ClassVar[str] = "base"

    # Default parameters
    default_params: ClassVar[dict[str, Any]] = {}

    def __init__(self, params: Optional[dict[str, Any]] = None):
        """
        Initialize algorithm with parameters.

        Args:
            params: Algorithm parameters (validated against schema)
        """
        self.params = {**self.default_params, **(params or {})}
        self._is_fitted = False
        self._training_data: Optional[pd.Series] = None

    @classmethod
    @abstractmethod
    def get_param_schema(cls) -> dict[str, Any]:
        """
        Return JSON Schema for algorithm parameters.

        This schema is used by the frontend to render dynamic forms.

        Returns:
            JSON Schema dictionary
        """
        pass

    @classmethod
    @abstractmethod
    def get_name(cls) -> str:
        """
        Return algorithm display name.

        Returns:
            Human-readable name
        """
        pass

    @classmethod
    @abstractmethod
    def get_description(cls) -> str:
        """
        Return algorithm description.

        Returns:
            Detailed description of the algorithm
        """
        pass

    @classmethod
    def get_algorithm_info(cls) -> dict[str, Any]:
        """
        Return complete algorithm information.

        Returns:
            Dictionary with id, name, description, and param_schema
        """
        return {
            "id": cls.algorithm_id,
            "name": cls.get_name(),
            "description": cls.get_description(),
            "param_schema": cls.get_param_schema(),
        }

    @abstractmethod
    def fit(self, data: pd.Series) -> "BaseAlgorithm":
        """
        Train the algorithm on historical data.

        Args:
            data: Time series data with DatetimeIndex

        Returns:
            self for method chaining
        """
        pass

    @abstractmethod
    def predict(self, periods: int = 1440, freq: str = "1min") -> AlgorithmResult:
        """
        Predict future threshold bounds.

        Args:
            periods: Number of periods to predict (default 1440 = 24 hours)
            freq: Time frequency (default "1min")

        Returns:
            AlgorithmResult with timestamps and bounds
        """
        pass

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate parameters against schema.

        Args:
            params: Parameters to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            import jsonschema
            jsonschema.validate(params, self.get_param_schema())
            return True, None
        except jsonschema.ValidationError as e:
            return False, str(e.message)
        except ImportError:
            # jsonschema not installed, skip validation
            return True, None

    def _validate_input(self, data: pd.Series) -> None:
        """Validate input data."""
        if len(data) == 0:
            raise ValueError("Input data cannot be empty")
        if not isinstance(data.index, pd.DatetimeIndex):
            raise ValueError("Data index must be DatetimeIndex")

    def _generate_future_timestamps(
        self,
        last_timestamp: pd.Timestamp,
        periods: int,
        freq: str = "1min"
    ) -> list[datetime]:
        """Generate future timestamps."""
        future_index = pd.date_range(
            start=last_timestamp + pd.Timedelta(freq),
            periods=periods,
            freq=freq
        )
        return future_index.tolist()

    @property
    def is_fitted(self) -> bool:
        """Check if algorithm is fitted."""
        return self._is_fitted