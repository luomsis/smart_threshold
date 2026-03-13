"""
Data source API router.
"""

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, status

from backend.app.schemas import (
    DataSourceConfigCreate,
    DataSourceConfigUpdate,
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

# 配置文件路径
CONFIG_DIR = Path(__file__).parent.parent.parent.parent / "config"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
DATASOURCES_FILE = CONFIG_DIR / "datasources.json"


def _load_datasources() -> Dict[str, DataSourceConfigResponse]:
    """从 JSON 文件加载数据源配置"""
    if not DATASOURCES_FILE.exists():
        return {}

    try:
        with open(DATASOURCES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        result = {}
        for ds_data in data:
            # 将字符串转换为枚举
            if isinstance(ds_data.get("source_type"), str):
                ds_data["source_type"] = DataSourceType(ds_data["source_type"])
            result[ds_data["id"]] = DataSourceConfigResponse(**ds_data)
        return result
    except Exception as e:
        print(f"加载数据源配置失败: {e}")
        return {}


def _save_datasources(datasources: Dict[str, DataSourceConfigResponse]) -> None:
    """保存数据源配置到 JSON 文件"""
    data = []
    for ds in datasources.values():
        ds_dict = ds.model_dump()
        # 将枚举转换为字符串
        if hasattr(ds_dict.get("source_type"), "value"):
            ds_dict["source_type"] = ds_dict["source_type"].value
        data.append(ds_dict)

    with open(DATASOURCES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# 启动时加载数据源
_datasources = _load_datasources()


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
        "timescaledb": DsType.TIMESCALEDB,
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
        db_host=ds_config.db_host,
        db_port=ds_config.db_port,
        db_name=ds_config.db_name,
        db_user=ds_config.db_user,
        db_password=ds_config.db_password,
    )
    return create_datasource(config), ds_config


@router.get("", response_model=List[DataSourceConfigResponse])
async def list_datasources():
    """List all data sources."""
    return list(_datasources.values())


@router.get("/default", response_model=DataSourceConfigResponse)
async def get_default_datasource():
    """Get the default data source.

    Returns the first enabled datasource.
    If only one datasource exists, it is the default.
    """
    if not _datasources:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No data source found"
        )

    # If only one datasource, it's the default
    if len(_datasources) == 1:
        return list(_datasources.values())[0]

    # Find first enabled datasource
    for ds in _datasources.values():
        if ds.enabled:
            return ds

    # If no enabled, return first one
    return list(_datasources.values())[0]


@router.get("/{ds_id}/endpoints", response_model=LabelValues)
async def list_endpoints(ds_id: str):
    """List all endpoints for a data source.

    Endpoint is a special label stored as an independent column in TimescaleDB,
    not in the labels JSON field. This method uses the dedicated get_endpoints()
    method for cleaner separation.
    """
    ds, _ = _get_datasource_instance(ds_id)
    try:
        values = ds.get_endpoints()
        return LabelValues(label="endpoint", values=values)
    except Exception:
        # Return empty if endpoint doesn't exist
        return LabelValues(label="endpoint", values=[])


@router.get("/{ds_id}/time-range")
async def get_time_range(ds_id: str, endpoint: Optional[str] = None):
    """Get the time range of available data.

    Returns the earliest and latest timestamps in the data source.
    This is useful for setting default query time ranges based on actual data.
    """
    ds, _ = _get_datasource_instance(ds_id)
    try:
        result = ds.get_time_range(endpoint)
        return {
            "min_time": result["min_time"].isoformat() if result["min_time"] else None,
            "max_time": result["max_time"].isoformat() if result["max_time"] else None
        }
    except Exception as e:
        return {"min_time": None, "max_time": None}


@router.get("/{ds_id}/endpoints/{endpoint}/metrics", response_model=List[MetricMetadata])
async def list_endpoint_metrics(ds_id: str, endpoint: str):
    """List available metrics for a specific endpoint."""
    ds, _ = _get_datasource_instance(ds_id)
    metrics = ds.list_metrics()
    # Filter metrics that have the endpoint label with the specified value
    filtered_metrics = []
    for m in metrics:
        # Check if metric has endpoint label
        if "endpoint" in m.labels:
            filtered_metrics.append(MetricMetadata(
                name=m.name,
                type=m.type,
                help=m.help,
                labels=m.labels,
            ))
    # If no endpoint filtering needed, return all metrics
    if not filtered_metrics and metrics:
        return [
            MetricMetadata(
                name=m.name,
                type=m.type,
                help=m.help,
                labels=m.labels,
            )
            for m in metrics
        ]
    return filtered_metrics


@router.post("", response_model=DataSourceConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_datasource(config: DataSourceConfigCreate):
    """Create a new data source."""
    ds_id = str(uuid.uuid4())
    ds_response = DataSourceConfigResponse(
        id=ds_id,
        **config.model_dump(),
    )
    _datasources[ds_id] = ds_response
    # 持久化到文件
    _save_datasources(_datasources)
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


@router.put("/{ds_id}", response_model=DataSourceConfigResponse)
async def update_datasource(ds_id: str, updates: DataSourceConfigUpdate):
    """Update data source."""
    if ds_id not in _datasources:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DataSource {ds_id} not found"
        )

    # 获取现有配置
    existing = _datasources[ds_id]
    existing_dict = existing.model_dump()

    # 过滤掉 None 值并更新
    update_dict = {k: v for k, v in updates.model_dump().items() if v is not None}
    existing_dict.update(update_dict)

    # 创建更新后的配置
    updated = DataSourceConfigResponse(**existing_dict)
    _datasources[ds_id] = updated

    # 持久化到文件
    _save_datasources(_datasources)
    return updated


@router.delete("/{ds_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_datasource(ds_id: str):
    """Delete a data source."""
    if ds_id not in _datasources:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DataSource {ds_id} not found"
        )
    del _datasources[ds_id]
    # 持久化到文件
    _save_datasources(_datasources)


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

    # 传递 endpoint 参数给数据源
    result = ds.query_range(
        request.query,
        time_range,
        endpoint=request.endpoint
    )

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