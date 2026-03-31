"""
Datasource 客户端单元测试

测试 PrometheusDataSource 和 TimescaleDBDataSource 的功能。
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
from smart_threshold.datasource.prometheus_client import (
    PrometheusDataSource,
    create_datasource,
)


class TestDataSourceConfig:
    """数据源配置测试"""

    def test_config_default_values(self):
        """测试默认配置值"""
        config = DataSourceConfig(
            name="test",
            source_type=DataSourceType.PROMETHEUS,
            url="http://localhost:9090"
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
            name="test-prometheus",
            source_type=DataSourceType.PROMETHEUS,
            url="http://prometheus:9090",
            enabled=False,
            auth_token="test-token",
            headers={"X-Custom": "value"},
            default_timeout=60
        )
        assert config.name == "test-prometheus"
        assert config.source_type == DataSourceType.PROMETHEUS
        assert config.url == "http://prometheus:9090"
        assert config.enabled is False
        assert config.auth_token == "test-token"
        assert config.headers == {"X-Custom": "value"}
        assert config.default_timeout == 60


class TestPrometheusDataSource:
    """Prometheus 数据源测试"""

    @pytest.fixture
    def prometheus_config(self):
        """创建 Prometheus 配置"""
        return DataSourceConfig(
            name="prometheus-test",
            source_type=DataSourceType.PROMETHEUS,
            url="http://localhost:9090"
        )

    def test_init(self, prometheus_config):
        """测试初始化"""
        client = PrometheusDataSource(prometheus_config)
        assert client.config == prometheus_config
        assert client.session is not None

    def test_init_with_auth_token(self):
        """测试带认证令牌的初始化"""
        config = DataSourceConfig(
            name="prometheus-auth",
            source_type=DataSourceType.PROMETHEUS,
            url="http://localhost:9090",
            auth_token="my-token"
        )
        client = PrometheusDataSource(config)
        assert "Authorization" in client.session.headers
        assert client.session.headers["Authorization"] == "Bearer my-token"

    @patch('requests.Session.get')
    def test_list_metrics(self, mock_get, prometheus_config):
        """测试列出指标（Mock HTTP 响应）"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "success",
            "data": ["up", "cpu_usage", "memory_usage"]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        client = PrometheusDataSource(prometheus_config)
        metrics = client.list_metrics()

        assert len(metrics) == 3
        assert metrics[0].name == "up"
        assert metrics[1].name == "cpu_usage"

    @patch('requests.Session.get')
    def test_get_endpoints(self, mock_get, prometheus_config):
        """测试获取 endpoint 列表"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "success",
            "data": ["/api/v1/query", "/metrics", "/health"]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        client = PrometheusDataSource(prometheus_config)
        endpoints = client.get_endpoints()

        assert len(endpoints) == 3
        assert "/api/v1/query" in endpoints

    @patch('requests.Session.get')
    def test_list_label_names(self, mock_get, prometheus_config):
        """测试列出标签名称"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "success",
            "data": ["instance", "job", "endpoint"]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        client = PrometheusDataSource(prometheus_config)
        labels = client.list_label_names()

        assert len(labels) == 3
        assert "instance" in labels

    @patch('requests.Session.get')
    def test_get_label_values(self, mock_get, prometheus_config):
        """测试获取标签值"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "success",
            "data": ["server1", "server2", "server3"]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        client = PrometheusDataSource(prometheus_config)
        result = client.get_label_values("instance")

        assert isinstance(result, LabelValues)
        assert result.label == "instance"
        assert len(result.values) == 3


class TestCreateDatasource:
    """数据源工厂函数测试"""

    def test_create_prometheus_datasource(self):
        """测试创建 Prometheus 数据源"""
        config = DataSourceConfig(
            name="prometheus",
            source_type=DataSourceType.PROMETHEUS,
            url="http://localhost:9090"
        )
        ds = create_datasource(config)
        assert isinstance(ds, PrometheusDataSource)

    def test_create_timescaledb_datasource(self):
        """测试创建 TimescaleDB 数据源"""
        config = DataSourceConfig(
            name="timescaledb",
            source_type=DataSourceType.TIMESCALEDB,
            url="postgresql://localhost:5432/test"
        )
        ds = create_datasource(config)
        # TimescaleDB 数据源在单独的模块中
        from smart_threshold.datasource.timescaledb_client import TimescaleDBDataSource
        assert isinstance(ds, TimescaleDBDataSource)


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