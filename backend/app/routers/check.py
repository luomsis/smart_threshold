"""
Real-time anomaly check API router.

Provides endpoint for enterprise monitoring systems to check if a current value
is anomalous based on pre-computed thresholds stored in Redis.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, status

from backend.app.schemas import CheckRequest, CheckResponse
from backend.redis_client import get_redis

router = APIRouter()


def get_threshold_index(timestamp: Optional[datetime]) -> int:
    """
    Calculate threshold index (0-1439) based on timestamp.

    Thresholds are stored as 1440 points representing one day (1-minute resolution).
    The index corresponds to the minute of day (0 = 00:00, 1439 = 23:59).

    Args:
        timestamp: Optional timestamp, defaults to current time if None

    Returns:
        Index in range [0, 1439]
    """
    if timestamp is None:
        timestamp = datetime.utcnow()

    # Calculate minute of day
    minute_of_day = timestamp.hour * 60 + timestamp.minute
    return min(max(minute_of_day, 0), 1439)


@router.post(
    "/check",
    response_model=CheckResponse,
    summary="实时异常判断",
    description="""
    判断当前值是否异常。

    企业监控系统调用此接口进行实时告警判断：
    - 从 Redis 获取该 metric_id 的阈值数组（1440 个点，代表一天）
    - 根据 timestamp 选择对应时间点的阈值（若无 timestamp 则使用当前分钟）
    - 判断 current_value 是否超出阈值范围
    - 返回异常状态和严重程度

    严重程度判断：
    - normal: 值在阈值范围内
    - warning: 值超出阈值范围，偏离 <= 50%
    - critical: 值超出阈值范围，偏离 > 50%
    """
)
async def check_anomaly(request: CheckRequest):
    """Check if current value is anomalous based on threshold."""
    redis = get_redis()

    # Get threshold from Redis
    threshold = redis.get_threshold(request.metric_id)

    if not threshold:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No threshold found for metric_id: {request.metric_id}"
        )

    # Get upper and lower arrays
    upper_bounds = threshold.get("upper", [])
    lower_bounds = threshold.get("lower", [])

    if not upper_bounds or not lower_bounds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Threshold data incomplete for metric_id: {request.metric_id}"
        )

    # Select threshold index based on timestamp
    idx = get_threshold_index(request.timestamp)

    # Validate index
    if idx >= len(upper_bounds) or idx >= len(lower_bounds):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Threshold index {idx} out of bounds (array length: {len(upper_bounds)}"
        )

    upper = upper_bounds[idx]
    lower = lower_bounds[idx]

    # Handle edge cases where threshold might be 0 or None
    if upper is None or lower is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Threshold value is None at index {idx}"
        )

    # Check if value is anomalous
    is_anomaly = request.current_value > upper or request.current_value < lower

    # Calculate deviation and severity
    deviation_percent = 0.0
    severity = "normal"

    if request.current_value > upper:
        # Value exceeds upper threshold
        if upper > 0:
            deviation_percent = (request.current_value - upper) / upper * 100
        else:
            # If upper is 0, use absolute deviation
            deviation_percent = abs(request.current_value - upper) * 100 if request.current_value != 0 else 0

        severity = "critical" if deviation_percent > 50 else "warning"

    elif request.current_value < lower:
        # Value below lower threshold
        if lower > 0:
            deviation_percent = (lower - request.current_value) / lower * 100
        else:
            # If lower is 0, any positive deviation is considered
            deviation_percent = abs(lower - request.current_value) * 100 if request.current_value != 0 else 0

        severity = "critical" if deviation_percent > 50 else "warning"

    return CheckResponse(
        metric_id=request.metric_id,
        is_anomaly=is_anomaly,
        severity=severity,
        threshold_used={"upper": upper, "lower": lower},
        deviation_percent=round(deviation_percent, 2) if deviation_percent else None
    )