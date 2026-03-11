"""
Datasource 数据模型
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum


class DataSourceType(Enum):
    """数据源类型"""
    PROMETHEUS = "prometheus"
    INFLUXDB = "influxdb"
    MOCK = "mock"
    TIMESCALEDB = "timescaledb"


@dataclass
class TimeRange:
    """时间范围"""
    start: datetime
    end: datetime
    step: str = "1m"  # 查询步长

    def to_duration_str(self) -> str:
        """转换为持续时间字符串"""
        delta = self.end - self.start
        total_seconds = int(delta.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours}h{minutes}m"


@dataclass
class DataSourceConfig:
    """数据源配置"""
    name: str
    source_type: DataSourceType
    url: str
    enabled: bool = True
    auth_token: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    default_timeout: int = 30
    # TimescaleDB 特定配置
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "postgres"
    db_user: str = "postgres"
    db_password: str = ""


@dataclass
class LabelMatcher:
    """标签匹配器"""
    label: str
    value: str
    operator: str = "="  # =, !=, =~, !~


@dataclass
class MetricQuery:
    """指标查询"""
    name: str
    query: str
    label_matchers: List[LabelMatcher] = field(default_factory=list)

    def build_query(self) -> str:
        """构建 PromQL 查询"""
        if self.label_matchers:
            labels = ", ".join([
                f'{m.label}{m.operator}"{m.value}"'
                for m in self.label_matchers
            ])
            return f'{self.query}{{{labels}}}'
        return self.query


@dataclass
class MetricData:
    """指标数据"""
    name: str
    query: str
    labels: Dict[str, str]
    timestamps: List[datetime]
    values: List[float]

    def to_series(self) -> 'pd.Series':
        """转换为 pandas Series"""
        import pandas as pd
        return pd.Series(
            self.values,
            index=pd.DatetimeIndex(self.timestamps),
            name=self.name
        )


@dataclass
class MetricMetadata:
    """指标元数据"""
    name: str
    type: str  # gauge, counter, histogram, summary
    help: str
    labels: List[str]


@dataclass
class LabelValues:
    """标签值"""
    label: str
    values: List[str]


@dataclass
class QueryResult:
    """查询结果"""
    success: bool
    data: Optional[List[MetricData]] = None
    error: Optional[str] = None
    execution_time: float = 0.0
