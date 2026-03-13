"""
Prometheus 数据源客户端

提供 Prometheus HTTP API 的 Python 封装。
"""

import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin

import requests
import pandas as pd

from smart_threshold.datasource.models import (
    DataSourceConfig,
    MetricQuery,
    TimeRange,
    MetricData,
    MetricMetadata,
    LabelValues,
    QueryResult,
    DataSourceType,
)


class PrometheusDataSource:
    """
    Prometheus 数据源

    使用示例:
    >>> config = DataSourceConfig(
    ...     name="local-prometheus",
    ...     source_type=DataSourceType.PROMETHEUS,
    ...     url="http://localhost:9090"
    ... )
    >>> client = PrometheusDataSource(config)
    >>> metrics = client.list_metrics()
    >>> data = client.query_range("up", TimeRange(...))
    """

    def __init__(self, config: DataSourceConfig):
        """
        初始化 Prometheus 数据源

        Args:
            config: 数据源配置
        """
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(config.headers)

        if config.auth_token:
            self.session.headers.update({
                "Authorization": f"Bearer {config.auth_token}"
            })

    def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        发起 HTTP 请求

        Args:
            endpoint: API 端点
            params: 查询参数

        Returns:
            响应 JSON 数据
        """
        url = urljoin(self.config.url, endpoint)

        try:
            response = self.session.get(
                url,
                params=params,
                timeout=self.config.default_timeout
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Prometheus 请求失败: {str(e)}")

    def list_metrics(self) -> List[MetricMetadata]:
        """
        列出所有指标

        Returns:
            指标元数据列表
        """
        # 使用 label-values(metric_name, __name__) 获取所有指标名称
        # 或使用 /api/v1/label/__name__/values
        result = self._make_request("/api/v1/label/__name__/values")

        if result["status"] != "success":
            return []

        metric_names = result.get("data", [])
        metadata_list = []

        for name in metric_names:
            # 获取指标的元数据（如果 Prometheus 支持）
            metadata_list.append(MetricMetadata(
                name=name,
                type="unknown",  # 需要额外的 API 调用获取
                help="",
                labels=[]
            ))

        return metadata_list

    def get_metric_metadata(self, metric_name: str) -> Optional[MetricMetadata]:
        """
        获取指标元数据

        Args:
            metric_name: 指标名称

        Returns:
            指标元数据
        """
        # 尝试获取元数据（Prometheus 2.13+）
        try:
            result = self._make_request(
                "/api/v1/metadata",
                params={"metric": metric_name}
            )

            if result["status"] == "success" and result.get("data"):
                data = result["data"].get(metric_name, [{}])[0]
                return MetricMetadata(
                    name=metric_name,
                    type=data.get("type", "unknown"),
                    help=data.get("help", ""),
                    labels=data.get("help", "").split()  # 简化处理
                )
        except Exception:
            pass

        return MetricMetadata(
            name=metric_name,
            type="unknown",
            help="",
            labels=[]
        )

    def list_label_names(self) -> List[str]:
        """
        列出所有标签名称

        Returns:
            标签名称列表
        """
        result = self._make_request("/api/v1/labels")

        if result["status"] != "success":
            return []

        return result.get("data", [])

    def get_label_values(self, label_name: str) -> LabelValues:
        """
        获取标签的所有可能值

        Args:
            label_name: 标签名称

        Returns:
            标签值
        """
        result = self._make_request(f"/api/v1/label/{label_name}/values")

        values = []
        if result["status"] == "success":
            values = result.get("data", [])

        return LabelValues(label=label_name, values=values)

    def get_endpoints(self) -> List[str]:
        """
        获取所有 endpoint 列表

        Returns:
            endpoint 列表
        """
        # Prometheus 中 endpoint 作为一个普通标签存储
        result = self.get_label_values("endpoint")
        return result.values

    def get_time_range(self, endpoint: Optional[str] = None) -> Dict[str, Optional[datetime]]:
        """
        获取数据的时间范围

        Prometheus 不直接支持此功能，返回 None 表示不可用。
        对于 Prometheus，建议使用查询时间范围。

        Args:
            endpoint: 可选的端点过滤（Prometheus 中忽略）

        Returns:
            包含 min_time 和 max_time 的字典（均为 None）
        """
        return {"min_time": None, "max_time": None}

    def query_instant(
        self,
        query: str,
        timestamp: Optional[datetime] = None
    ) -> QueryResult:
        """
        即时查询

        Args:
            query: PromQL 查询
            timestamp: 查询时间点（默认为当前时间）

        Returns:
            查询结果
        """
        start_time = time.time()

        params = {"query": query}
        if timestamp:
            params["time"] = timestamp.timestamp()

        try:
            result = self._make_request("/api/v1/query", params)
            execution_time = time.time() - start_time

            if result["status"] != "success":
                return QueryResult(
                    success=False,
                    error=result.get("error", "Unknown error"),
                    execution_time=execution_time
                )

            data = self._parse_query_result(result.get("data", {}))

            return QueryResult(
                success=True,
                data=data,
                execution_time=execution_time
            )

        except Exception as e:
            return QueryResult(
                success=False,
                error=str(e),
                execution_time=time.time() - start_time
            )

    def query_range(
        self,
        query: str,
        time_range: TimeRange
    ) -> QueryResult:
        """
        范围查询

        Args:
            query: PromQL 查询
            time_range: 时间范围

        Returns:
            查询结果
        """
        start_time = time.time()

        params = {
            "query": query,
            "start": time_range.start.timestamp(),
            "end": time_range.end.timestamp(),
            "step": time_range.step
        }

        try:
            result = self._make_request("/api/v1/query_range", params)
            execution_time = time.time() - start_time

            if result["status"] != "success":
                return QueryResult(
                    success=False,
                    error=result.get("error", "Unknown error"),
                    execution_time=execution_time
                )

            data = self._parse_query_result(result.get("data", {}))

            return QueryResult(
                success=True,
                data=data,
                execution_time=execution_time
            )

        except Exception as e:
            return QueryResult(
                success=False,
                error=str(e),
                execution_time=time.time() - start_time
            )

    def _parse_query_result(self, data: Dict[str, Any]) -> List[MetricData]:
        """
        解析查询结果

        Args:
            data: 原始查询结果

        Returns:
            指标数据列表
        """
        result_type = data.get("resultType", "")
        raw_results = data.get("result", [])

        metric_data_list = []

        for raw in raw_results:
            metric = raw.get("metric", {})
            labels = {k: v for k, v in metric.items() if k != "__name__"}

            # 生成指标名称
            metric_name = metric.get("__name__", "unknown")
            if labels:
                label_str = ", ".join([f'{k}="{v}"' for k, v in labels.items()])
                name = f"{metric_name}{{{label_str}}}"
            else:
                name = metric_name

            # 解析数据点
            values = raw.get("values", [])

            if result_type == "matrix":
                # 范围查询结果
                timestamps = []
                data_values = []

                for ts_str, val_str in values:
                    try:
                        timestamps.append(datetime.fromtimestamp(float(ts_str)))
                        data_values.append(float(val_str))
                    except (ValueError, TypeError):
                        continue

                if timestamps:
                    metric_data_list.append(MetricData(
                        name=name,
                        query="",  # 查询语句由调用方提供
                        labels=labels,
                        timestamps=timestamps,
                        values=data_values
                    ))

            elif result_type == "vector":
                # 即时查询结果
                if values:
                    ts_str, val_str = values[0]
                    metric_data_list.append(MetricData(
                        name=name,
                        query="",
                        labels=labels,
                        timestamps=[datetime.fromtimestamp(float(ts_str))],
                        values=[float(val_str)]
                    ))

        return metric_data_list

    def test_connection(self) -> Dict[str, Any]:
        """
        测试连接

        Returns:
            连接测试结果
        """
        try:
            start_time = time.time()
            result = self._make_request("/api/v1/status/config")
            execution_time = time.time() - start_time

            return {
                "success": True,
                "message": "连接成功",
                "execution_time": execution_time,
                "version": result.get("data", {}).get("global", {}).get("external_labels", {})
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"连接失败: {str(e)}",
                "execution_time": 0
            }

    def get_series(
        self,
        match: Optional[List[str]] = None,
        time_range: Optional[TimeRange] = None
    ) -> List[Dict[str, Any]]:
        """
        获取时序列表

        Args:
            match: 匹配器列表
            time_range: 时间范围

        Returns:
            时序列表
        """
        params = {}
        if match:
            params["match[]"] = match
        if time_range:
            params["start"] = time_range.start.timestamp()
            params["end"] = time_range.end.timestamp()

        result = self._make_request("/api/v1/series", params)

        if result["status"] != "success":
            return []

        return result.get("data", [])

    def to_dataframe(self, query_result: QueryResult) -> Optional[pd.DataFrame]:
        """
        将查询结果转换为 DataFrame

        Args:
            query_result: 查询结果

        Returns:
            DataFrame 或 None
        """
        if not query_result.success or not query_result.data:
            return None

        # 如果只有一个指标，直接返回 Series
        if len(query_result.data) == 1:
            metric = query_result.data[0]
            return pd.Series(
                metric.values,
                index=pd.DatetimeIndex(metric.timestamps),
                name=metric.name
            ).to_frame()

        # 多个指标，返回 DataFrame
        data_dict = {}
        for metric in query_result.data:
            data_dict[metric.name] = pd.Series(
                metric.values,
                index=pd.DatetimeIndex(metric.timestamps)
            )

        return pd.DataFrame(data_dict)


class MockPrometheusDataSource(PrometheusDataSource):
    """
    Mock Prometheus 数据源

    用于测试和演示，生成模拟数据而不是连接真实的 Prometheus。
    """

    def __init__(self, config: DataSourceConfig):
        super().__init__(config)
        self._mock_data = self._generate_mock_metrics()

    def _generate_mock_metrics(self) -> Dict[str, List[str]]:
        """生成模拟指标"""
        return {
            "qps": ["instance", "job", "endpoint"],
            "latency_ms": ["instance", "job", "quantile"],
            "error_rate": ["instance", "job", "error_type"],
            "cpu_usage": ["instance", "job", "cpu"],
            "memory_usage": ["instance", "job"],
            "disk_io": ["instance", "job", "device"],
            "network_traffic": ["instance", "job", "interface"],
        }

    def list_metrics(self) -> List[MetricMetadata]:
        """列出模拟指标"""
        metrics = []
        for name, labels in self._mock_data.items():
            metrics.append(MetricMetadata(
                name=name,
                type="gauge",
                help=f"Mock metric {name}",
                labels=labels
            ))
        return metrics

    def list_label_names(self) -> List[str]:
        """列出模拟标签"""
        all_labels = set()
        for labels in self._mock_data.values():
            all_labels.update(labels)
        return sorted(all_labels)

    def get_label_values(self, label_name: str) -> LabelValues:
        """获取模拟标签值"""
        # 返回一些通用的标签值
        common_values = {
            "instance": ["localhost:9090", "server1:8080", "server2:8080"],
            "job": ["prometheus", "api-server", "database"],
            "endpoint": ["/api/v1/query", "/metrics", "/health"],
            "quantile": ["0.5", "0.9", "0.99"],
            "error_type": ["timeout", "connection_refused", "internal_error"],
            "cpu": ["cpu0", "cpu1", "cpu2", "cpu3"],
            "device": ["sda", "sdb"],
            "interface": ["eth0", "eth1"],
        }
        return LabelValues(
            label=label_name,
            values=common_values.get(label_name, ["value1", "value2"])
        )

    def get_endpoints(self) -> List[str]:
        """获取模拟 endpoint 列表"""
        return ["/api/v1/query", "/metrics", "/health"]

    def get_time_range(self, endpoint: Optional[str] = None) -> Dict[str, Optional[datetime]]:
        """
        获取模拟数据的时间范围

        返回最近的模拟数据时间范围。

        Args:
            endpoint: 可选的端点过滤（模拟中忽略）

        Returns:
            包含 min_time 和 max_time 的字典
        """
        # Mock 数据源返回当前时间作为最新时间
        now = datetime.now()
        return {
            "min_time": now - timedelta(days=7),  # 模拟7天数据
            "max_time": now
        }

    def query_range(
        self,
        query: str,
        time_range: TimeRange
    ) -> QueryResult:
        """生成模拟范围查询数据"""
        # 生成模拟数据
        from smart_threshold.data.generator import DataGenerator, ScenarioType

        # 根据 query 选择场景类型
        if "qps" in query.lower():
            scenario = ScenarioType.QPS
        elif "latency" in query.lower() or "rt" in query.lower():
            scenario = ScenarioType.RT
        elif "error" in query.lower():
            scenario = ScenarioType.ERROR_COUNT
        else:
            scenario = ScenarioType.QPS

        # 转换频率格式：Prometheus 使用 "1m" 表示分钟，pandas 使用 "1min"
        freq_map = {
            "1m": "1min",
            "5m": "5min",
            "15m": "15min",
            "1h": "1h",
            "1d": "1D",
        }
        freq = freq_map.get(time_range.step, time_range.step)

        generator = DataGenerator(freq=freq, seed=42)

        # 计算需要生成的天数
        delta = time_range.end - time_range.start
        days = max(1, int(delta.total_seconds() / 86400) + 1)

        # 使用 time_range.start 作为起始日期生成数据
        data = generator.generate(
            scenario,
            days=days,
            start_date=time_range.start.strftime('%Y-%m-%d')
        )

        # 筛选时间范围（确保只返回请求范围内的数据）
        # 统一时区处理：转换为东八区 tz-naive 以便与 data.index 比较
        import pandas as pd
        from datetime import timedelta, timezone
        TZ_SHANGHAI = timezone(timedelta(hours=8))

        start_ts = pd.Timestamp(time_range.start)
        end_ts = pd.Timestamp(time_range.end)
        # 如果有时区信息，转换为东八区后去掉时区
        if start_ts.tz is not None:
            start_ts = start_ts.tz_convert(TZ_SHANGHAI).tz_localize(None)
        if end_ts.tz is not None:
            end_ts = end_ts.tz_convert(TZ_SHANGHAI).tz_localize(None)
        mask = (data.index >= start_ts) & (data.index <= end_ts)
        data = data[mask]

        return QueryResult(
            success=True,
            data=[MetricData(
                name=query,
                query=query,
                labels={},
                timestamps=data.index.tolist(),
                values=data.values.tolist()
            )],
            execution_time=0.1
        )

    def test_connection(self) -> Dict[str, Any]:
        """测试连接（总是成功）"""
        return {
            "success": True,
            "message": "Mock 数据源连接成功",
            "execution_time": 0.01,
            "version": {"mode": "mock"}
        }


def create_datasource(config: DataSourceConfig):
    """
    创建数据源实例

    Args:
        config: 数据源配置

    Returns:
        数据源实例 (PrometheusDataSource, MockPrometheusDataSource 或 TimescaleDBDataSource)
    """
    if config.source_type == DataSourceType.MOCK:
        return MockPrometheusDataSource(config)
    elif config.source_type == DataSourceType.TIMESCALEDB:
        from smart_threshold.datasource.timescaledb_client import TimescaleDBDataSource
        return TimescaleDBDataSource(config)
    return PrometheusDataSource(config)
