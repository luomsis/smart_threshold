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
        # 持久化到文件
        _save_datasources(_datasources)
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