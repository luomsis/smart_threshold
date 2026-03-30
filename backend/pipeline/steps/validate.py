"""
Model validation step.

Calculates RMSE, MAE, MAPE and simulates false alerts.
"""

from typing import Any

import numpy as np
import pandas as pd

from smart_threshold.algorithms import AlgorithmResult


def validate_model(
    train_data: pd.Series,
    prediction: AlgorithmResult,
    test_data: pd.Series | None = None,
) -> dict[str, Any]:
    """
    Validate the trained model.

    Computes metrics on training data (and test data if available).

    Args:
        train_data: Training data used
        prediction: Prediction result from model
        test_data: Optional test data for out-of-sample validation

    Returns:
        Dictionary with validation metrics
    """
    metrics = {
        "train_samples": len(train_data),
        "test_samples": len(test_data) if test_data is not None else 0,
    }

    # Use training data for validation if no test data
    validation_data = test_data if test_data is not None else train_data

    # Align prediction with validation data
    # For training data validation, we compare against fitted values
    # For test data, we compare against predicted values

    if test_data is None:
        # In-sample validation
        # We need to get fitted values from the model
        # For now, compute simple statistics
        train_values = train_data.values
        train_mean = np.mean(train_values)
        train_std = np.std(train_values)

        # Compute coverage on training data
        # Using the prediction bounds
        upper = prediction.yhat_upper[0]  # For constant threshold algorithms
        lower = prediction.yhat_lower[0]

        in_bounds = ((train_values >= lower) & (train_values <= upper)).sum()
        coverage = in_bounds / len(train_values)

        # Compute false alert simulation
        false_alerts = (train_values > upper).sum()

        metrics["mae"] = float(np.mean(np.abs(train_values - train_mean)))
        metrics["rmse"] = float(np.sqrt(np.mean((train_values - train_mean) ** 2)))
        metrics["coverage"] = float(coverage)
        metrics["false_alerts"] = int(false_alerts)
        metrics["false_alert_rate"] = float(false_alerts / len(train_values))

        # MAPE calculation (avoid division by zero)
        non_zero_mask = train_values != 0
        if non_zero_mask.sum() > 0:
            mape = np.mean(np.abs((train_values[non_zero_mask] - train_mean) / train_values[non_zero_mask])) * 100
            metrics["mape"] = float(mape)
        else:
            metrics["mape"] = None

    else:
        # Out-of-sample validation
        test_values = test_data.values

        # Match prediction length to test data
        pred_len = min(len(test_values), len(prediction.yhat))
        test_values = test_values[:pred_len]

        yhat = prediction.yhat[:pred_len]
        upper = prediction.yhat_upper[:pred_len]
        lower = prediction.yhat_lower[:pred_len]

        # Compute metrics
        residuals = test_values - yhat

        metrics["mae"] = float(np.mean(np.abs(residuals)))
        metrics["rmse"] = float(np.sqrt(np.mean(residuals ** 2)))

        # MAPE
        non_zero_mask = test_values != 0
        if non_zero_mask.sum() > 0:
            mape = np.mean(np.abs(residuals[non_zero_mask] / test_values[non_zero_mask])) * 100
            metrics["mape"] = float(mape)
        else:
            metrics["mape"] = None

        # Coverage
        in_bounds = ((test_values >= lower) & (test_values <= upper)).sum()
        metrics["coverage"] = float(in_bounds / pred_len)

        # False alerts (values above upper bound)
        false_alerts = (test_values > upper).sum()
        metrics["false_alerts"] = int(false_alerts)
        metrics["false_alert_rate"] = float(false_alerts / pred_len)

    return metrics


def simulate_alerts(
    data: pd.Series,
    upper_bounds: np.ndarray,
    lower_bounds: np.ndarray,
) -> dict[str, Any]:
    """
    Simulate how many alerts would be triggered.

    Args:
        data: Historical data
        upper_bounds: Upper threshold bounds
        lower_bounds: Lower threshold bounds

    Returns:
        Alert simulation results
    """
    values = data.values
    n = min(len(values), len(upper_bounds), len(lower_bounds))

    upper_breaches = (values[:n] > upper_bounds[:n]).sum()
    lower_breaches = (values[:n] < lower_bounds[:n]).sum()

    return {
        "total_points": n,
        "upper_breaches": int(upper_breaches),
        "lower_breaches": int(lower_breaches),
        "total_alerts": int(upper_breaches + lower_breaches),
        "alert_rate": float((upper_breaches + lower_breaches) / n),
    }