"""
Output generation step.

Generates 24-hour threshold arrays and preview data for frontend.
"""

from datetime import datetime, timedelta
from typing import Any

import numpy as np

from smart_threshold.algorithms import AlgorithmResult


def generate_output(
    prediction: AlgorithmResult,
    train_data_stats: dict[str, float],
    validation_metrics: dict[str, Any],
) -> dict[str, Any]:
    """
    Generate output data for storage and visualization.

    Args:
        prediction: Algorithm prediction result
        train_data_stats: Statistics from training data
        validation_metrics: Validation metrics

    Returns:
        Output dictionary with threshold arrays and preview data
    """
    # Generate threshold arrays from prediction
    upper_bounds = prediction.yhat_upper.tolist()
    lower_bounds = prediction.yhat_lower.tolist()
    yhat = prediction.yhat.tolist()

    # Use actual prediction length
    target_length = len(yhat)

    # Generate timestamps for preview
    now = datetime.now()
    timestamps = [
        (now + timedelta(minutes=i)).strftime("%Y-%m-%d %H:%M:%S")
        for i in range(target_length)
    ]

    # Create preview data for ECharts (first 8 hours or all if less)
    preview_hours = min(480, target_length)  # 480 points = 8 hours at 1min interval
    preview_data = {
        "timestamps": timestamps[:preview_hours],
        "predicted": yhat[:preview_hours],
        "upper": upper_bounds[:preview_hours],
        "lower": lower_bounds[:preview_hours],
    }

    # Build output
    output = {
        "upper_bounds": upper_bounds,
        "lower_bounds": lower_bounds,
        "predicted": yhat,
        "preview_data": preview_data,
        "metadata": {
            "algorithm": prediction.metadata.get("algorithm", "unknown"),
            "generated_at": datetime.now().isoformat(),
            "train_data_stats": train_data_stats,
            "validation_metrics": validation_metrics,
            "prediction_metadata": prediction.metadata,
        }
    }

    return output


def format_for_echarts(
    timestamps: list[datetime],
    actual_values: list[float] | None,
    predicted: np.ndarray,
    upper: np.ndarray,
    lower: np.ndarray,
) -> dict[str, Any]:
    """
    Format data for ECharts visualization.

    Args:
        timestamps: Timestamps
        actual_values: Actual data values (optional)
        predicted: Predicted values
        upper: Upper bounds
        lower: Lower bounds

    Returns:
        ECharts-compatible data structure
    """
    ts_str = [ts.strftime("%Y-%m-%d %H:%M:%S") for ts in timestamps]

    result = {
        "xAxis": {"type": "category", "data": ts_str},
        "series": [
            {
                "name": "Predicted",
                "type": "line",
                "data": predicted.tolist(),
                "lineStyle": {"color": "#5470c6"},
            },
            {
                "name": "Upper Bound",
                "type": "line",
                "data": upper.tolist(),
                "lineStyle": {"color": "#91cc75", "type": "dashed"},
                "itemStyle": {"opacity": 0.5},
            },
            {
                "name": "Lower Bound",
                "type": "line",
                "data": lower.tolist(),
                "lineStyle": {"color": "#91cc75", "type": "dashed"},
                "itemStyle": {"opacity": 0.5},
            },
        ],
    }

    if actual_values is not None:
        result["series"].insert(0, {
            "name": "Actual",
            "type": "line",
            "data": actual_values,
            "lineStyle": {"color": "#ee6666"},
        })

    return result