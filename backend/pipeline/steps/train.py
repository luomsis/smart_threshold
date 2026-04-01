"""
Model training step.

Trains the selected algorithm on cleaned data.
"""

from typing import Any

import pandas as pd

from smart_threshold.algorithms import AlgorithmRegistry, BaseAlgorithm, AlgorithmResult


def parse_step_to_freq(step: str) -> str:
    """
    Convert step string to Prophet frequency format.

    Args:
        step: Step string like "1m", "5m", "15m", "1h"

    Returns:
        Prophet frequency string like "1min", "5min", "15min", "H"
    """
    step_map = {
        "1m": "1min",
        "5m": "5min",
        "15m": "15min",
        "30m": "30min",
        "1h": "H",
        "1d": "D",
    }
    return step_map.get(step, step)


def train_model(
    data: pd.Series,
    algorithm: str,
    algorithm_params: dict[str, Any] | None = None,
    periods: int = 1440,
    step: str = "1m",
) -> tuple[BaseAlgorithm | None, AlgorithmResult | None, str | None]:
    """
    Train a threshold model.

    Args:
        data: Cleaned time series data
        algorithm: Algorithm ID (e.g., "three_sigma", "prophet")
        algorithm_params: Algorithm parameters
        periods: Number of periods to predict (default: 1440 = 24 hours)
        step: Data sampling interval (e.g., "1m", "5m", "15m")

    Returns:
        Tuple of (trained_model, prediction_result, error_message)
    """
    try:
        # Validate data
        if len(data) < 100:
            return None, None, f"Insufficient data: {len(data)} points (minimum 100 required)"

        # Get algorithm
        algo_class = AlgorithmRegistry.get(algorithm)
        if algo_class is None:
            return None, None, f"Unknown algorithm: {algorithm}"

        # Create and train model
        model = algo_class(algorithm_params or {})

        # Validate parameters
        is_valid, error = model.validate_params(algorithm_params or {})
        if not is_valid:
            return None, None, f"Invalid parameters: {error}"

        # Fit model
        model.fit(data)

        # Convert step to Prophet frequency format
        freq = parse_step_to_freq(step)

        # Generate prediction
        result = model.predict(periods=periods, freq=freq)

        return model, result, None

    except Exception as e:
        import traceback
        return None, None, f"Training failed: {str(e)}\n{traceback.format_exc()}"


def get_algorithm_info(algorithm: str) -> dict[str, Any] | None:
    """
    Get information about an algorithm.

    Args:
        algorithm: Algorithm ID

    Returns:
        Algorithm info dict or None
    """
    algo_class = AlgorithmRegistry.get(algorithm)
    if algo_class is None:
        return None
    return algo_class.get_algorithm_info()