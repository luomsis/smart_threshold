"""
Datasource 模块

提供 TimescaleDB 数据源集成功能。
"""

from smart_threshold.datasource.timescaledb_client import TimescaleDBDataSource
from smart_threshold.datasource.models import (
    DataSourceConfig,
    DataSourceType,
    MetricQuery,
    TimeRange,
    MetricData,
    MetricMetadata,
    LabelValues,
    QueryResult,
)

__all__ = [
    "TimescaleDBDataSource",
    "DataSourceConfig",
    "DataSourceType",
    "MetricQuery",
    "TimeRange",
    "MetricData",
    "MetricMetadata",
    "LabelValues",
    "QueryResult",
]