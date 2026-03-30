"""
Thresholds API router.

Publish and retrieve threshold data from Redis.
"""

from fastapi import APIRouter, HTTPException, Depends

from backend.redis_client import get_redis
from backend.db import get_db
from backend.models.job import Job, JobStatus
from backend.app.schemas import (
    ThresholdPublishRequest,
    ThresholdPublishResponse,
    ThresholdGetResponse,
)

router = APIRouter()


@router.post(
    "/publish",
    response_model=ThresholdPublishResponse,
    summary="发布阈值到 Redis",
    description="将训练完成的阈值结果发布到 Redis 缓存。存储 upper/lower 数组（各 1440 个点），供实时告警引擎使用。Redis key 格式：threshold:{metric_id}:upper/lower",
)
async def publish_threshold(
    request: ThresholdPublishRequest,
    db = Depends(get_db),
):
    # Get job with results
    job = db.query(Job).filter(Job.id == request.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {request.job_id}")

    if job.status != JobStatus.SUCCESS.value:
        raise HTTPException(
            status_code=400,
            detail=f"Job has not completed successfully: {job.status}"
        )

    if not job.upper_bounds or not job.lower_bounds:
        raise HTTPException(
            status_code=400,
            detail="Job does not have threshold results"
        )

    # Publish to Redis
    redis = get_redis()
    redis.set_threshold(
        metric_id=request.metric_id,
        upper_bounds=job.upper_bounds,
        lower_bounds=job.lower_bounds,
        ttl=request.ttl,
    )

    return ThresholdPublishResponse(
        success=True,
        metric_id=request.metric_id,
        message=f"Threshold published for {request.metric_id}",
    )


@router.get(
    "/{metric_id}",
    response_model=ThresholdGetResponse,
    summary="获取指标的阈值",
    description="从 Redis 缓存获取指定指标的当前阈值。返回 upper/lower 数组。",
)
async def get_threshold(metric_id: str):
    redis = get_redis()
    result = redis.get_threshold(metric_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No threshold found for metric: {metric_id}"
        )

    return ThresholdGetResponse(
        metric_id=metric_id,
        upper=result["upper"],
        lower=result["lower"],
    )


@router.delete(
    "/{metric_id}",
    summary="删除指标的阈值缓存",
    description="从 Redis 缓存删除指定指标的阈值数据。",
)
async def delete_threshold(metric_id: str):
    redis = get_redis()
    deleted = redis.delete_threshold(metric_id)

    return {
        "success": deleted,
        "metric_id": metric_id,
        "message": "Threshold deleted" if deleted else "Threshold not found",
    }


@router.get(
    "",
    summary="获取所有缓存的阈值列表",
    description="列出 Redis 中所有已缓存阈值的 metric_id。",
)
async def list_cached_thresholds():
    redis = get_redis()
    client = redis.client

    # Scan for threshold keys
    keys = client.keys("threshold:*:upper")

    # Extract metric_ids
    metric_ids = []
    for key in keys:
        # threshold:{metric_id}:upper -> metric_id
        parts = key.split(":")
        if len(parts) >= 2:
            metric_ids.append(parts[1])

    return {
        "count": len(metric_ids),
        "metric_ids": sorted(metric_ids),
    }