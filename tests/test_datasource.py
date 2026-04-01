"""
Datasource 客户端单元测试

测试 TimescaleDBDataSource 的功能。
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from smart_threshold.datasource.models import (
    DataSourceConfig,
    DataSourceType,
    TimeRange,
    MetricMetadata,
    LabelValues,
    QueryResult,
)
from smart_threshold.datasource.timescaledb_client import TimescaleDBDataSource


class TestDataSourceConfig:
    """数据源配置测试"""

    def test_config_default_values(self):
        """测试默认配置值"""
        config = DataSourceConfig(
            name="test",
            source_type=DataSourceType.TIMESCALEDB,
            url="postgresql://localhost:5432/postgres"
        )
        assert config.enabled is True
        assert config.default_timeout == 30
        assert config.db_host == "localhost"
        assert config.db_port == 5432
        assert config.db_name == "postgres"
        assert config.db_user == "postgres"
        assert config.db_password == ""

    def test_config_custom_values(self):
        """测试自定义配置值"""
        config = DataSourceConfig(
            name="test-timescaledb",
            source_type=DataSourceType.TIMESCALEDB,
            url="postgresql://timescaledb:5432/metrics",
            enabled=False,
            db_host="timescaledb",
            db_port=5432,
            db_name="metrics",
            db_user="admin",
            db_password="secret",
            default_timeout=60
        )
        assert config.name == "test-timescaledb"
        assert config.source_type == DataSourceType.TIMESCALEDB
        assert config.url == "postgresql://timescaledb:5432/metrics"
        assert config.enabled is False
        assert config.default_timeout == 60


class TestTimescaleDBDataSource:
    """TimescaleDB 数据源测试"""

    @pytest.fixture
    def timescaledb_config(self):
        """创建 TimescaleDB 配置"""
        return DataSourceConfig(
            name="timescaledb-test",
            source_type=DataSourceType.TIMESCALEDB,
            url="postgresql://localhost:5432/postgres",
            db_host="localhost",
            db_port=5432,
            db_name="postgres",
            db_user="postgres",
            db_password="postgres"
        )

    def test_init(self, timescaledb_config):
        """测试初始化"""
        client = TimescaleDBDataSource(timescaledb_config)
        assert client.config == timescaledb_config
        assert client._conn is None

    def test_parse_url(self, timescaledb_config):
        """测试 URL 解析"""
        client = TimescaleDBDataSource(timescaledb_config)
        assert client._db_host == "localhost"
        assert client._db_port == 5432
        assert client._db_name == "postgres"


class TestTimeRange:
    """时间范围测试"""

    def test_time_range_defaults(self):
        """测试默认时间范围"""
        start = datetime(2026, 1, 1, 0, 0, 0)
        end = datetime(2026, 1, 2, 0, 0, 0)
        time_range = TimeRange(start=start, end=end)
        assert time_range.step == "1m"

    def test_to_duration_str(self):
        """测试持续时间字符串转换"""
        start = datetime(2026, 1, 1, 0, 0, 0)
        end = datetime(2026, 1, 1, 2, 30, 0)
        time_range = TimeRange(start=start, end=end)
        duration = time_range.to_duration_str()
        assert duration == "2h30m"


class TestMetricData:
    """指标数据测试"""

    def test_to_series(self):
        """测试转换为 pandas Series"""
        from smart_threshold.datasource.models import MetricData
        import pandas as pd

        timestamps = [
            datetime(2026, 1, 1, 0, 0, 0),
            datetime(2026, 1, 1, 0, 1, 0),
            datetime(2026, 1, 1, 0, 2, 0),
        ]
        values = [10.0, 20.0, 30.0]

        metric_data = MetricData(
            name="test_metric",
            query="test_metric",
            labels={"instance": "localhost"},
            timestamps=timestamps,
            values=values
        )

        series = metric_data.to_series()
        assert isinstance(series, pd.Series)
        assert len(series) == 3
        assert series.name == "test_metric"
        assert list(series.values) == values


class TestQueryResult:
    """查询结果测试"""

    def test_success_result(self):
        """测试成功结果"""
        from smart_threshold.datasource.models import MetricData

        result = QueryResult(
            success=True,
            data=[MetricData(
                name="test",
                query="test",
                labels={},
                timestamps=[datetime.now()],
                values=[1.0]
            )],
            execution_time=0.1
        )
        assert result.success is True
        assert result.data is not None
        assert result.error is None

    def test_error_result(self):
        """测试错误结果"""
        result = QueryResult(
            success=False,
            error="Connection failed",
            execution_time=0.0
        )
        assert result.success is False
        assert result.error == "Connection failed"
        assert result.data is None


class TestLabelValues:
    """标签值测试"""

    def test_label_values(self):
        """测试标签值数据类"""
        lv = LabelValues(
            label="instance",
            values=["localhost:9090", "server1:8080"]
        )
        assert lv.label == "instance"
        assert len(lv.values) == 2
        assert "localhost:9090" in lv.values

    def test_empty_values(self):
        """测试空值列表"""
        lv = LabelValues(label="empty_label", values=[])
        assert lv.label == "empty_label"
        assert len(lv.values) == 0


class TestMetricMetadata:
    """指标元数据测试"""

    def test_metric_metadata(self):
        """测试指标元数据"""
        meta = MetricMetadata(
            name="cpu_usage",
            type="gauge",
            help="CPU usage percentage",
            labels=["instance", "job"]
        )
        assert meta.name == "cpu_usage"
        assert meta.type == "gauge"
        assert "instance" in meta.labels

    def test_default_values(self):
        """测试空值列表"""
        meta = MetricMetadata(
            name="test_metric",
            type="unknown",
            help="",
            labels=[]
        )
        assert meta.name == "test_metric"
        assert meta.type == "unknown"
        assert meta.help == ""
        assert meta.labels == []