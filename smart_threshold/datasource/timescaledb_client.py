"""
TimescaleDB 数据源客户端

提供 TimescaleDB (PostgreSQL 扩展) 的数据访问功能。

数据表结构:
- series_meta: 时序元数据表
- series_points: 时序数据点表 (TimescaleDB hypertable)

DDL 语句:

CREATE TABLE public.series_meta (
    id bigserial NOT NULL,
    endpoint text NOT NULL,
    metric text NOT NULL,
    labels jsonb NOT NULL DEFAULT '{}'::jsonb,
    labels_hash text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT series_meta_endpoint_metric_labels_hash_key UNIQUE (endpoint, metric, labels_hash),
    CONSTRAINT series_meta_pkey PRIMARY KEY (id)
);

CREATE INDEX idx_series_meta_labels_hash ON public.series_meta USING btree (labels_hash);
CREATE INDEX idx_series_meta_metric ON public.series_meta USING btree (metric);
CREATE INDEX series_meta_endpoint_idx ON public.series_meta USING btree (endpoint);
CREATE INDEX series_meta_endpoint_metric_idx ON public.series_meta USING btree (endpoint, metric);

CREATE TABLE public.series_points (
    "time" timestamptz NOT NULL,
    series_id int8 NOT NULL,
    value float8 NOT NULL,
    CONSTRAINT series_points_series_id_fkey FOREIGN KEY (series_id) REFERENCES public.series_meta(id)
);

CREATE INDEX series_points_series_time_idx ON public.series_points USING btree (series_id, "time" DESC);
CREATE INDEX series_points_time_idx ON public.series_points USING btree ("time" DESC);

-- TimescaleDB hypertable trigger
CREATE TRIGGER ts_insert_blocker BEFORE INSERT ON public.series_points
    FOR EACH ROW EXECUTE FUNCTION _timescaledb_functions.insert_blocker();

-- 创建 hypertable (需要手动执行)
-- SELECT create_hypertable('series_points', 'time', if_not_exists => TRUE);

字段说明:
- series_meta.endpoint: 端点标识（如 /api/metrics），独立列而非 labels 中的字段
- series_meta.metric: 指标名称
- series_meta.labels: 其他标签的 JSON 字段（如 host, region 等）
- series_meta.labels_hash: labels 的 MD5 哈希，用于唯一标识
- series_points.time: 数据点时间戳（UTC）
- series_points.value: 数据点值
"""

import time
import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any

import pandas as pd

from smart_threshold.datasource.models import (
    DataSourceConfig,
    TimeRange,
    MetricData,
    MetricMetadata,
    LabelValues,
    QueryResult,
)

# 东八区时区
TZ_SHANGHAI = timezone(timedelta(hours=8))


class TimescaleDBDataSource:
    """
    TimescaleDB 数据源

    使用示例:
    >>> config = DataSourceConfig(
    ...     name="timescaledb-local",
    ...     source_type=DataSourceType.TIMESCALEDB,
    ...     url="postgresql://localhost:5432/metrics",
    ...     db_host="localhost",
    ...     db_port=5432,
    ...     db_name="metrics",
    ...     db_user="postgres",
    ...     db_password="password"
    ... )
    >>> client = TimescaleDBDataSource(config)
    >>> metrics = client.list_metrics()
    >>> data = client.query_range("cpu_usage", TimeRange(...))
    """

    def __init__(self, config: DataSourceConfig):
        """
        初始化 TimescaleDB 数据源

        Args:
            config: 数据源配置
        """
        self.config = config
        self._conn = None
        self._parse_url()

    def _parse_url(self):
        """解析 URL 获取数据库连接参数"""
        url = self.config.url
        if url.startswith("postgresql://"):
            # 解析 postgresql://user:password@host:port/database
            import re
            pattern = r"postgresql://(?:(\w+)(?::(\w+))?@)?([\w.-]+)(?::(\d+))?/(\w+)"
            match = re.match(pattern, url)
            if match:
                user, password, host, port, database = match.groups()
                self._db_user = user or self.config.db_user
                self._db_password = password or self.config.db_password
                self._db_host = host or self.config.db_host
                self._db_port = int(port) if port else self.config.db_port
                self._db_name = database or self.config.db_name
            else:
                self._db_host = self.config.db_host
                self._db_port = self.config.db_port
                self._db_name = self.config.db_name
                self._db_user = self.config.db_user
                self._db_password = self.config.db_password
        else:
            self._db_host = self.config.db_host
            self._db_port = self.config.db_port
            self._db_name = self.config.db_name
            self._db_user = self.config.db_user
            self._db_password = self.config.db_password

    def _get_connection(self):
        """获取数据库连接"""
        if self._conn is None or self._conn.closed:
            try:
                import psycopg2
                self._conn = psycopg2.connect(
                    host=self._db_host,
                    port=self._db_port,
                    dbname=self._db_name,
                    user=self._db_user,
                    password=self._db_password,
                    connect_timeout=self.config.default_timeout
                )
            except ImportError:
                raise ImportError(
                    "psycopg2 is required for TimescaleDB support. "
                    "Install it with: pip install psycopg2-binary"
                )
        return self._conn

    def _execute_query(self, sql: str, params: tuple = None) -> List[tuple]:
        """
        执行 SQL 查询

        Args:
            sql: SQL 查询语句
            params: 查询参数

        Returns:
            查询结果列表
        """
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    def _execute_dict_query(self, sql: str, params: tuple = None) -> List[Dict[str, Any]]:
        """执行查询并返回字典列表"""
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute(sql, params)
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    def list_metrics(self, endpoint: Optional[str] = None) -> List[MetricMetadata]:
        """
        列出所有指标

        Args:
            endpoint: 可选的端点过滤

        Returns:
            指标元数据列表
        """
        sql = """
            SELECT DISTINCT metric, endpoint,
                   array_agg(DISTINCT key) as labels
            FROM series_meta, jsonb_object_keys(labels) as key
        """
        params = []
        if endpoint:
            sql += " WHERE endpoint = %s"
            params.append(endpoint)
        sql += " GROUP BY metric, endpoint ORDER BY metric"

        results = self._execute_query(sql, tuple(params) if params else None)

        metrics = []
        seen_metrics = set()
        for row in results:
            metric_name = row[0]
            if metric_name not in seen_metrics:
                seen_metrics.add(metric_name)
                metrics.append(MetricMetadata(
                    name=metric_name,
                    type="gauge",  # TimescaleDB 不存储类型信息，默认为 gauge
                    help=f"Metric from endpoint: {row[1]}",
                    labels=row[2] if row[2] else []
                ))
        return metrics

    def list_label_names(self) -> List[str]:
        """
        列出所有标签名称

        注意：endpoint 是独立列，不属于 labels，不在此列表中。
        如需获取 endpoint 列表，请使用 get_endpoints() 方法。

        Returns:
            标签名称列表
        """
        sql = """
            SELECT DISTINCT key
            FROM series_meta, jsonb_object_keys(labels) as key
            ORDER BY key
        """
        results = self._execute_query(sql)
        return [row[0] for row in results]

    def get_endpoints(self) -> List[str]:
        """
        获取所有 endpoint 列表

        endpoint 在 TimescaleDB 中是独立列，不是 labels JSON 中的字段。

        Returns:
            endpoint 列表
        """
        sql = """
            SELECT DISTINCT endpoint
            FROM series_meta
            ORDER BY endpoint
        """
        results = self._execute_query(sql)
        return [row[0] for row in results if row[0]]

    def get_label_values(self, label_name: str) -> LabelValues:
        """
        获取标签的所有值

        注意：endpoint 是独立列，不存储在 labels JSON 中。
        如需获取 endpoint 列表，请使用 get_endpoints() 方法。

        Args:
            label_name: 标签名称

        Returns:
            标签值列表
        """
        sql = """
            SELECT DISTINCT labels->>%s as value
            FROM series_meta
            WHERE labels ? %s
            ORDER BY value
        """
        results = self._execute_query(sql, (label_name, label_name))
        return LabelValues(
            label=label_name,
            values=[row[0] for row in results if row[0]]
        )

    def get_time_range(self, endpoint: Optional[str] = None) -> Dict[str, Optional[datetime]]:
        """
        获取数据的时间范围

        Args:
            endpoint: 可选的端点过滤

        Returns:
            包含 min_time 和 max_time 的字典
        """
        sql = """
            SELECT MIN(p.time), MAX(p.time)
            FROM series_points p
            JOIN series_meta m ON p.series_id = m.id
        """
        params = []

        if endpoint:
            sql += " WHERE m.endpoint = %s"
            params.append(endpoint)

        results = self._execute_query(sql, tuple(params) if params else None)
        if results and results[0]:
            return {
                "min_time": results[0][0],
                "max_time": results[0][1]
            }
        return {"min_time": None, "max_time": None}

    def query_range(
        self,
        query: str,
        time_range: TimeRange,
        labels: Optional[Dict[str, str]] = None,
        endpoint: Optional[str] = None
    ) -> QueryResult:
        """
        查询时间范围内的数据

        Args:
            query: 指标名称
            time_range: 时间范围
            labels: 可选的标签过滤
            endpoint: 可选的端点过滤

        Returns:
            查询结果
        """
        start_time = time.time()

        # 处理时区：统一转换为 UTC 进行查询
        # 数据库存储的是 UTC 时间，所以查询时需要用 UTC
        start_ts = pd.Timestamp(time_range.start)
        end_ts = pd.Timestamp(time_range.end)

        # 如果有时区信息，转换为 UTC
        if start_ts.tz is not None:
            start_ts = start_ts.tz_convert('UTC')
        if end_ts.tz is not None:
            end_ts = end_ts.tz_convert('UTC')

        # 移除时区信息以便与数据库中的 timestamptz 比较
        # PostgreSQL 会自动处理时区转换
        start_ts = start_ts.tz_localize(None) if start_ts.tz is not None else start_ts
        end_ts = end_ts.tz_localize(None) if end_ts.tz is not None else end_ts

        # 构建 SQL 查询
        sql = """
            SELECT p.time, p.value, m.labels
            FROM series_points p
            JOIN series_meta m ON p.series_id = m.id
            WHERE m.metric = %s
            AND p.time >= %s
            AND p.time <= %s
        """
        params = [query, start_ts, end_ts]

        if endpoint:
            sql += " AND m.endpoint = %s"
            params.append(endpoint)

        if labels:
            for key, value in labels.items():
                sql += f" AND m.labels->>%s = %s"
                params.extend([key, value])

        sql += " ORDER BY p.time"

        try:
            results = self._execute_dict_query(sql, tuple(params))

            if not results:
                return QueryResult(
                    success=True,
                    data=[],
                    execution_time=time.time() - start_time
                )

            # 转换为 pandas DataFrame 进行处理
            df = pd.DataFrame(results)
            df['time'] = pd.to_datetime(df['time'])

            # 将 labels 列转换为字符串以便分组（字典不可哈希）
            df['labels_str'] = df['labels'].apply(lambda x: json.dumps(x, sort_keys=True) if isinstance(x, dict) else str(x))

            # 按 labels_str 分组
            grouped = df.groupby('labels_str')

            metric_data_list = []
            for labels_str, group in grouped:
                # 解析 labels
                if isinstance(labels_str, str):
                    try:
                        labels_dict = json.loads(labels_str)
                    except json.JSONDecodeError:
                        labels_dict = {}
                else:
                    labels_dict = labels_str if isinstance(labels_str, dict) else {}

                metric_data_list.append(MetricData(
                    name=query,
                    query=query,
                    labels=labels_dict,
                    timestamps=group['time'].tolist(),
                    values=group['value'].tolist()
                ))

            return QueryResult(
                success=True,
                data=metric_data_list,
                execution_time=time.time() - start_time
            )

        except Exception as e:
            return QueryResult(
                success=False,
                error=str(e),
                execution_time=time.time() - start_time
            )

    def query_latest(
        self,
        query: str,
        labels: Optional[Dict[str, str]] = None,
        endpoint: Optional[str] = None
    ) -> QueryResult:
        """
        查询最新数据点

        Args:
            query: 指标名称
            labels: 可选的标签过滤
            endpoint: 可选的端点过滤

        Returns:
            查询结果
        """
        start_time = time.time()

        sql = """
            SELECT DISTINCT ON (m.id) p.time, p.value, m.labels
            FROM series_points p
            JOIN series_meta m ON p.series_id = m.id
            WHERE m.metric = %s
        """
        params = [query]

        if endpoint:
            sql += " AND m.endpoint = %s"
            params.append(endpoint)

        if labels:
            for key, value in labels.items():
                sql += f" AND m.labels->>%s = %s"
                params.extend([key, value])

        sql += " ORDER BY m.id, p.time DESC"

        try:
            results = self._execute_dict_query(sql, tuple(params))

            if not results:
                return QueryResult(
                    success=True,
                    data=[],
                    execution_time=time.time() - start_time
                )

            metric_data_list = []
            for row in results:
                labels_dict = json.loads(row['labels']) if isinstance(row['labels'], str) else row['labels']
                metric_data_list.append(MetricData(
                    name=query,
                    query=query,
                    labels=labels_dict,
                    timestamps=[row['time']],
                    values=[row['value']]
                ))

            return QueryResult(
                success=True,
                data=metric_data_list,
                execution_time=time.time() - start_time
            )

        except Exception as e:
            return QueryResult(
                success=False,
                error=str(e),
                execution_time=time.time() - start_time
            )

    def insert_data(
        self,
        metric: str,
        labels: Dict[str, str],
        timestamps: List[datetime],
        values: List[float],
        endpoint: str = "default"
    ) -> bool:
        """
        插入时序数据

        Args:
            metric: 指标名称
            labels: 标签字典
            timestamps: 时间戳列表
            values: 值列表
            endpoint: 端点名称

        Returns:
            是否成功
        """
        try:
            conn = self._get_connection()

            # 计算 labels_hash
            labels_json = json.dumps(labels, sort_keys=True)
            labels_hash = hashlib.md5(labels_json.encode()).hexdigest()

            # 获取或创建 series_meta
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id FROM series_meta
                    WHERE endpoint = %s AND metric = %s AND labels_hash = %s
                """, (endpoint, metric, labels_hash))
                result = cur.fetchone()

                if result:
                    series_id = result[0]
                else:
                    cur.execute("""
                        INSERT INTO series_meta (endpoint, metric, labels, labels_hash)
                        VALUES (%s, %s, %s, %s)
                        RETURNING id
                    """, (endpoint, metric, json.dumps(labels), labels_hash))
                    series_id = cur.fetchone()[0]

                # 插入数据点 (使用 COPY 命令提高性能)
                from io import StringIO
                import csv

                buffer = StringIO()
                writer = csv.writer(buffer)
                for ts, val in zip(timestamps, values):
                    writer.writerow([ts, series_id, val])
                buffer.seek(0)

                # 使用原生 SQL 插入 (TimescaleDB 会处理)
                for ts, val in zip(timestamps, values):
                    cur.execute("""
                        INSERT INTO series_points (time, series_id, value)
                        VALUES (%s, %s, %s)
                        ON CONFLICT DO NOTHING
                    """, (ts, series_id, val))

                conn.commit()

            return True

        except Exception as e:
            print(f"Error inserting data: {e}")
            return False

    def test_connection(self) -> Dict[str, Any]:
        """
        测试数据库连接

        Returns:
            连接测试结果
        """
        start_time = time.time()
        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'")
                result = cur.fetchone()
                version = result[0] if result else None

                if not version:
                    return {
                        "success": False,
                        "message": "TimescaleDB extension not found",
                        "execution_time": time.time() - start_time
                    }

                return {
                    "success": True,
                    "message": "TimescaleDB connection successful",
                    "execution_time": time.time() - start_time,
                    "version": {"timescaledb": version}
                }

        except Exception as e:
            return {
                "success": False,
                "message": str(e),
                "execution_time": time.time() - start_time
            }

    def close(self):
        """关闭数据库连接"""
        if self._conn and not self._conn.closed:
            self._conn.close()
            self._conn = None

    def __del__(self):
        """析构函数，确保连接关闭"""
        self.close()