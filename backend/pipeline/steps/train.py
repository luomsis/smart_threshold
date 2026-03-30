"""
Model training step.

Trains the selected algorithm on cleaned data.
"""

from typing import Any

import pandas as pd

from smart_threshold.algorithms import AlgorithmRegistry, BaseAlgorithm, AlgorithmResult


def train_model(
    data: pd.Series,
    algorithm: str,
    algorithm_params: dict[str, Any] | None = None,
) -> tuple[BaseAlgorithm | None, AlgorithmResult | None, str | None]:
    """
    Train a threshold model.

    Args:
        data: Cleaned time series data
        algorithm: Algorithm ID (e.g., "three_sigma", "prophet")
        algorithm_params: Algorithm parameters

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

        # Generate prediction (24 hours = 1440 minutes)
        result = model.predict(periods=1440, freq="1min")

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