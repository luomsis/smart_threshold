"""
Data source API router.
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, status

from backend.app.schemas import (
    DataSourceConfigCreate,
    DataSourceConfigResponse,
    DataSourceType,
    MetricMetadata,
    LabelValues,
    QueryRequest,
    QueryResult,
    MetricData,
    MetricDataPoint,
)

router = APIRouter()

# In-memory data source storage
_datasources: Dict[str, DataSourceConfigResponse] = {}


def _get_datasource_instance(ds_id: str):
    """Get datasource instance by ID."""
    from smart_threshold.datasource import create_datasource, DataSourceConfig as DsConfig, DataSourceType as DsType

    ds_config = _datasources.get(ds_id)
    if not ds_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DataSource {ds_id} not found"
        )

    # Convert schema DataSourceType to datasource DataSourceType
    source_type_map = {
        "prometheus": DsType.PROMETHEUS,
        "influxdb": DsType.INFLUXDB,
        "mock": DsType.MOCK,
    }
    source_type = source_type_map.get(ds_config.source_type.value, DsType.MOCK)

    config = DsConfig(
        name=ds_config.name,
        source_type=source_type,
        url=ds_config.url,
        enabled=ds_config.enabled,
        auth_token=ds_config.auth_token,
        headers=ds_config.headers,
        default_timeout=ds_config.default_timeout,
    )
    return create_datasource(config), ds_config


@router.get("", response_model=List[DataSourceConfigResponse])
async def list_datasources():
    """List all data sources."""
    # Initialize mock datasource if empty
    if not _datasources:
        mock_id = str(uuid.uuid4())
        _datasources[mock_id] = DataSourceConfigResponse(
            id=mock_id,
            name="Mock 数据源",
            source_type=DataSourceType.MOCK,
            url="mock://localhost",
            enabled=True,
        )
    return list(_datasources.values())


@router.post("", response_model=DataSourceConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_datasource(config: DataSourceConfigCreate):
    """Create a new data source."""
    ds_id = str(uuid.uuid4())
    ds_response = DataSourceConfigResponse(
        id=ds_id,
        **config.model_dump(),
    )
    _datasources[ds_id] = ds_response
    return ds_response


@router.get("/{ds_id}", response_model=DataSourceConfigResponse)
async def get_datasource(ds_id: str):
    """Get data source by ID."""
    ds = _datasources.get(ds_id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DataSource {ds_id} not found"
        )
    return ds


@router.delete("/{ds_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_datasource(ds_id: str):
    """Delete a data source."""
    if ds_id not in _datasources:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DataSource {ds_id} not found"
        )
    del _datasources[ds_id]


@router.get("/{ds_id}/metrics", response_model=List[MetricMetadata])
async def list_metrics(ds_id: str):
    """List available metrics from data source."""
    ds, _ = _get_datasource_instance(ds_id)
    metrics = ds.list_metrics()
    return [
        MetricMetadata(
            name=m.name,
            type=m.type,
            help=m.help,
            labels=m.labels,
        )
        for m in metrics
    ]


@router.get("/{ds_id}/labels", response_model=List[str])
async def list_labels(ds_id: str):
    """List available label names from data source."""
    ds, _ = _get_datasource_instance(ds_id)
    return ds.list_label_names()


@router.get("/{ds_id}/labels/{label_name}", response_model=LabelValues)
async def get_label_values(ds_id: str, label_name: str):
    """Get values for a specific label."""
    ds, _ = _get_datasource_instance(ds_id)
    result = ds.get_label_values(label_name)
    return LabelValues(label=result.label, values=result.values)


@router.post("/{ds_id}/query", response_model=QueryResult)
async def query_data(ds_id: str, request: QueryRequest):
    """Query data from data source."""
    ds, _ = _get_datasource_instance(ds_id)

    from smart_threshold.datasource import TimeRange as DsTimeRange
    time_range = DsTimeRange(
        start=request.time_range.start,
        end=request.time_range.end,
        step=request.time_range.step,
    )

    result = ds.query_range(request.query, time_range)

    if not result.success:
        return QueryResult(
            success=False,
            error=result.error,
            execution_time=result.execution_time,
        )

    metric_data_list = []
    for md in result.data:
        metric_data_list.append(MetricData(
            name=md.name,
            query=md.query,
            labels=md.labels,
            data=[MetricDataPoint(timestamp=ts, value=val)
                  for ts, val in zip(md.timestamps, md.values)],
        ))

    return QueryResult(
        success=True,
        data=metric_data_list,
        execution_time=result.execution_time,
    )