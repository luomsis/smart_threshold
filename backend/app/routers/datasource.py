"""
Global TimescaleDB data source API router.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query

from backend.app.schemas import (
    TimeRange,
    MetricMetadata,
    LabelValues,
    MetricData,
    MetricDataPoint,
    QueryResult,
    QueryRequest,
)
from backend.pipeline.steps.fetch import get_timescaledb_client

router = APIRouter()


@router.get(
    "/time-range",
    summary="获取数据时间范围",
    description="获取全局 TimescaleDB 中数据的时间范围",
)
async def get_time_range(
    endpoint: Optional[str] = Query(None, description="Endpoint 过滤"),
):
    """Get the time range of available data."""
    client = get_timescaledb_client()
    time_range = client.get_time_range(endpoint=endpoint)

    if time_range:
        return {
            "min_time": time_range.get("min_time"),
            "max_time": time_range.get("max_time"),
            "count": time_range.get("count", 0),
        }
    return {"min_time": None, "max_time": None, "count": 0}


@router.get(
    "/endpoints",
    response_model=LabelValues,
    summary="获取 Endpoint 列表",
    description="获取全局 TimescaleDB 中所有可用的 endpoint 值",
)
async def list_endpoints():
    """List all available endpoints."""
    client = get_timescaledb_client()
    endpoints = client.get_endpoints()
    return LabelValues(label="endpoint", values=endpoints)


@router.get(
    "/metrics",
    response_model=list[MetricMetadata],
    summary="获取指标列表",
    description="获取全局 TimescaleDB 中所有可用的指标",
)
async def list_metrics():
    """List all available metrics."""
    client = get_timescaledb_client()
    metrics = client.list_metrics()
    return metrics


@router.get(
    "/labels",
    response_model=list[str],
    summary="获取标签名称列表",
    description="获取全局 TimescaleDB 中所有可用的标签名称",
)
async def list_labels():
    """List all available label names."""
    client = get_timescaledb_client()
    labels = client.list_label_names()
    return labels


@router.get(
    "/labels/{label_name}",
    response_model=LabelValues,
    summary="获取标签值列表",
    description="获取指定标签的所有可用值",
)
async def get_label_values(label_name: str):
    """Get all values for a specific label."""
    client = get_timescaledb_client()
    result = client.get_label_values(label_name)
    return result


@router.post(
    "/query",
    response_model=QueryResult,
    summary="查询数据",
    description="从全局 TimescaleDB 查询时序数据",
)
async def query_data(request: QueryRequest):
    """Query time series data."""
    client = get_timescaledb_client()

    time_range = TimeRange(
        start=request.time_range.start,
        end=request.time_range.end,
        step=request.time_range.step,
    )

    result = client.query_range(
        query=request.query,
        time_range=time_range,
        endpoint=request.endpoint,
    )

    if result.success and result.data:
        # Convert to response format
        metric_data_list = []
        for metric_data in result.data:
            data_points = [
                MetricDataPoint(timestamp=ts, value=val)
                for ts, val in zip(metric_data.timestamps, metric_data.values)
            ]
            metric_data_list.append(MetricData(
                name=metric_data.name,
                query=metric_data.query,
                labels=metric_data.labels,
                data=data_points,
            ))

        return QueryResult(
            success=True,
            data=metric_data_list,
            execution_time=result.execution_time,
        )

    return QueryResult(
        success=False,
        error=result.error or "Query failed",
        execution_time=result.execution_time,
    )