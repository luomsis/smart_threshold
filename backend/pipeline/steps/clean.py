"""
Data cleaning step.

Handles missing values, excludes specified periods, outlier detection, and smoothing.
"""

from datetime import datetime
from typing import Any, Optional

import numpy as np
import pandas as pd


def clean_data(
    data: pd.Series,
    exclude_periods: list[dict[str, str]] | None = None,
    interpolation_method: str = "linear",
    outlier_detection: dict | None = None,
    smoothing: dict | None = None,
) -> tuple[pd.Series, dict[str, Any]]:
    """
    Clean time series data.

    Steps:
    1. Remove excluded time periods
    2. Detect and handle outliers (optional)
    3. Interpolate missing values
    4. Apply smoothing (optional)

    Args:
        data: Time series data
        exclude_periods: List of {start, end} periods to exclude
        interpolation_method: Interpolation method for missing values
        outlier_detection: Outlier detection config {"method": "iqr/zscore", "action": "remove/interpolate", "threshold": 3.0}
        smoothing: Smoothing config {"method": "moving_avg", "window": 5}

    Returns:
        Tuple of (cleaned_data, cleaning_stats)
    """
    stats = {
        "original_count": len(data),
        "excluded_count": 0,
        "outliers_detected": 0,
        "outliers_removed": 0,
        "outliers_interpolated": 0,
        "interpolated_count": 0,
        "smoothing_applied": None,
        "final_count": len(data),
    }

    cleaned = data.copy()

    # Step 1: Exclude specified periods
    if exclude_periods:
        mask = pd.Series(True, index=cleaned.index)

        for period in exclude_periods:
            start = pd.Timestamp(period["start"])
            end = pd.Timestamp(period["end"])
            period_mask = (cleaned.index >= start) & (cleaned.index <= end)
            mask = mask & ~period_mask
            stats["excluded_count"] += period_mask.sum()

        cleaned = cleaned[mask]

    # Step 2: Outlier detection and handling
    if outlier_detection:
        method = outlier_detection.get("method", "iqr")
        action = outlier_detection.get("action", "remove")
        threshold = outlier_detection.get("threshold", 3.0)

        outliers = detect_outliers(cleaned, method=method, threshold=threshold)
        outlier_count = outliers.sum()
        stats["outliers_detected"] = int(outlier_count)

        if outlier_count > 0:
            if action == "remove":
                # Remove outlier points
                cleaned = cleaned[~outliers]
                stats["outliers_removed"] = int(outlier_count)
            elif action == "interpolate":
                # Replace outliers with NaN and interpolate
                cleaned[outliers] = np.nan
                cleaned = cleaned.interpolate(method=interpolation_method)
                cleaned = cleaned.ffill().bfill()
                stats["outliers_interpolated"] = int(outlier_count)

    # Step 3: Handle missing values
    # Check for NaN values
    nan_count = cleaned.isna().sum()

    if nan_count > 0:
        # Interpolate missing values
        if interpolation_method == "linear":
            cleaned = cleaned.interpolate(method="linear")
        elif interpolation_method == "time":
            cleaned = cleaned.interpolate(method="time")
        else:
            cleaned = cleaned.interpolate()

        # Fill any remaining NaN at edges
        cleaned = cleaned.ffill().bfill()

        stats["interpolated_count"] = int(nan_count)

    # Step 4: Apply smoothing
    if smoothing:
        smoothing_method = smoothing.get("method", "moving_avg")
        window = smoothing.get("window", 5)

        if smoothing_method == "moving_avg":
            # Apply centered moving average
            cleaned = cleaned.rolling(window=window, center=True).mean()
            # Remove NaN values created by rolling window
            cleaned = cleaned.dropna()
            stats["smoothing_applied"] = f"moving_avg(window={window})"

    # Step 5: Ensure no negative values for count metrics
    # (can be configured per metric type)
    cleaned[cleaned < 0] = 0

    stats["final_count"] = len(cleaned)
    stats["cleaned_percentage"] = (stats["original_count"] - stats["final_count"]) / stats["original_count"] * 100

    return cleaned, stats


def detect_outliers(
    data: pd.Series,
    method: str = "iqr",
    threshold: float = 3.0
) -> pd.Series:
    """
    Detect outliers in the data.

    Args:
        data: Time series data
        method: Detection method ("iqr", "zscore")
        threshold: Threshold for outlier detection

    Returns:
        Boolean series where True indicates outlier
    """
    if method == "iqr":
        q1 = data.quantile(0.25)
        q3 = data.quantile(0.75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        return (data < lower) | (data > upper)

    elif method == "zscore":
        mean = data.mean()
        std = data.std()
        z_scores = np.abs((data - mean) / (std + 1e-10))
        return z_scores > threshold

    return pd.Series(False, index=data.index)