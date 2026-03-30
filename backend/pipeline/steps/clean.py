"""
Data cleaning step.

Handles missing values and excludes specified periods.
"""

from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd


def clean_data(
    data: pd.Series,
    exclude_periods: list[dict[str, str]] | None = None,
    interpolation_method: str = "linear",
) -> tuple[pd.Series, dict[str, Any]]:
    """
    Clean time series data.

    Steps:
    1. Remove excluded time periods
    2. Interpolate missing values
    3. Remove obvious outliers (optional)

    Args:
        data: Time series data
        exclude_periods: List of {start, end} periods to exclude
        interpolation_method: Interpolation method for missing values

    Returns:
        Tuple of (cleaned_data, cleaning_stats)
    """
    stats = {
        "original_count": len(data),
        "excluded_count": 0,
        "interpolated_count": 0,
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

    # Step 2: Handle missing values
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

    # Step 3: Ensure no negative values for count metrics
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