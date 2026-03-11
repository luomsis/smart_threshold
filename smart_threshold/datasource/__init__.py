"""
Datasource 模块

提供 Prometheus 和 TimescaleDB 数据源集成功能。
"""

from smart_threshold.datasource.prometheus_client import (
    PrometheusDataSource,
    MockPrometheusDataSource,
    create_datasource,
)
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
    "PrometheusDataSource",
    "MockPrometheusDataSource",
    "TimescaleDBDataSource",
    "create_datasource",
    "DataSourceConfig",
    "DataSourceType",
    "MetricQuery",
    "TimeRange",
    "MetricData",
    "MetricMetadata",
    "LabelValues",
    "QueryResult",
]
