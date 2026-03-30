"""
数据填充脚本

为 TimescaleDB 中缺少数据的指标生成并插入模拟数据。
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from smart_threshold.datasource import (
    DataSourceConfig,
    DataSourceType,
)
from smart_threshold.datasource.timescaledb_client import TimescaleDBDataSource


# 数据库配置
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "database": "postgres",
    "user": "postgres",
    "password": "postgres",
}

# 指标与场景映射
METRIC_SCENARIOS = {
    "cpu_usage_percent": "rt",           # 平稳 + 尖峰
    "memory_usage_percent": "rt",        # 平稳 + 尖峰
    "disk_usage_percent": "rt",          # 平稳 + 尖峰
    "connections_active": "qps",         # 周期性
    "connections_idle": "qps",           # 周期性
    "queries_per_second": "qps",         # 周期性
    "slow_queries_count": "error",       # 稀疏
    "replication_lag_seconds": "rt",     # 平稳 + 尖峰
    "replication_status": "rt",          # 平稳
}


def generate_qps_data(n_points: int, base: float = 100, amplitude: float = 50) -> np.ndarray:
    """生成周期性 QPS 数据"""
    rng = np.random.default_rng()
    t = np.arange(n_points)

    # 24 小时周期
    daily_period = 1440
    hour_of_day = (t / 60) % 24

    # 双峰模式：10:00 和 15:00 高峰
    business_cycle = (
        0.5 * np.sin(2 * np.pi * (hour_of_day - 6) / 24)
        + 0.3 * np.sin(4 * np.pi * (hour_of_day - 6) / 24)
    )

    # 组合
    values = base + amplitude * business_cycle

    # 添加噪声
    noise = rng.normal(0, amplitude * 0.1, n_points)
    values += noise

    return np.maximum(values, 0)


def generate_rt_data(n_points: int, base: float = 50, std: float = 10, spike_prob: float = 0.05) -> np.ndarray:
    """生成响应时间数据（平稳 + 尖峰）"""
    rng = np.random.default_rng()

    # 基础值 + 正常波动
    values = rng.normal(base, std, n_points)

    # 注入尖峰
    spike_mask = rng.random(n_points) < spike_prob
    spike_locations = np.where(spike_mask)[0]

    for loc in spike_locations:
        duration = rng.integers(1, 6)
        end = min(loc + duration, n_points)
        spike_value = rng.normal(base * 3, std * 2)
        values[loc:end] = spike_value

    return np.maximum(values, 0)


def generate_error_data(n_points: int, error_prob: float = 0.05) -> np.ndarray:
    """生成稀疏错误数据"""
    rng = np.random.default_rng()

    # 初始化全为 0
    values = np.zeros(n_points, dtype=float)

    # 部分时间点有错误
    error_mask = rng.random(n_points) < error_prob
    error_count = np.sum(error_mask)

    # 错误值服从 Poisson 分布
    values[error_mask] = rng.poisson(lam=5, size=error_count)

    return values


def generate_data(scenario: str, n_points: int, base: float = None) -> np.ndarray:
    """根据场景类型生成数据"""
    if scenario == "qps":
        return generate_qps_data(n_points, base=base or 100, amplitude=50)
    elif scenario == "rt":
        return generate_rt_data(n_points, base=base or 50, std=10)
    elif scenario == "error":
        return generate_error_data(n_points)
    else:
        raise ValueError(f"未知场景: {scenario}")


def get_metric_base_value(metric: str) -> float:
    """获取指标的基础值"""
    bases = {
        "cpu_usage_percent": 45,
        "memory_usage_percent": 60,
        "disk_usage_percent": 55,
        "connections_active": 150,
        "connections_idle": 50,
        "queries_per_second": 500,
        "slow_queries_count": 0,  # error type
        "replication_lag_seconds": 0.5,
        "replication_status": 1,
    }
    return bases.get(metric, 50)


def main():
    """主函数"""
    print("=" * 60)
    print("TimescaleDB 数据填充脚本")
    print("=" * 60)

    # 连接数据库
    config = DataSourceConfig(
        name="timescaledb-local",
        source_type=DataSourceType.TIMESCALEDB,
        url=f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}",
        db_host=DB_CONFIG["host"],
        db_port=DB_CONFIG["port"],
        db_name=DB_CONFIG["database"],
        db_user=DB_CONFIG["user"],
        db_password=DB_CONFIG["password"],
    )

    client = TimescaleDBDataSource(config)

    # 获取所有 endpoint 和 metric 组合
    endpoints = client.get_endpoints()
    print(f"\n发现 {len(endpoints)} 个 endpoints")

    # 获取时间范围（使用已有数据的时间范围）
    time_range = client.get_time_range()
    if time_range["min_time"] and time_range["max_time"]:
        start_time = time_range["min_time"]
        end_time = time_range["max_time"]
        print(f"数据时间范围: {start_time} ~ {end_time}")
    else:
        # 默认生成最近 7 天的数据
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=7)
        print(f"使用默认时间范围: {start_time} ~ {end_time}")

    # 计算数据点数量（每分钟一个点）
    n_points = int((end_time - start_time).total_seconds() / 60)
    print(f"生成 {n_points} 个数据点")

    # 生成时间戳
    timestamps = pd.date_range(start=start_time, periods=n_points, freq="1min").to_list()

    # 统计
    total_inserted = 0
    skipped = 0

    # 为每个 endpoint 和 metric 组合检查并生成数据
    for endpoint in endpoints:
        print(f"\n处理 endpoint: {endpoint}")

        for metric, scenario in METRIC_SCENARIOS.items():
            # 检查是否已有数据
            sql = """
                SELECT COUNT(p.time)
                FROM series_points p
                JOIN series_meta m ON p.series_id = m.id
                WHERE m.endpoint = %s AND m.metric = %s
            """
            result = client._execute_query(sql, (endpoint, metric))
            existing_count = result[0][0] if result else 0

            if existing_count > 0:
                print(f"  ✓ {metric}: 已有 {existing_count} 个数据点，跳过")
                skipped += 1
                continue

            # 生成数据
            base_value = get_metric_base_value(metric)
            values = generate_data(scenario, n_points, base=base_value)

            # 插入数据
            labels = {"unit": "count"} if metric in ["connections_active", "connections_idle", "queries_per_second", "slow_queries_count"] else {"unit": "percent"}

            success = client.insert_data(
                metric=metric,
                labels=labels,
                timestamps=timestamps,
                values=values.tolist(),
                endpoint=endpoint
            )

            if success:
                print(f"  ✓ {metric}: 插入 {n_points} 个数据点")
                total_inserted += 1
            else:
                print(f"  ✗ {metric}: 插入失败")

    # 关闭连接
    client.close()

    print("\n" + "=" * 60)
    print(f"完成！插入 {total_inserted} 个指标，跳过 {skipped} 个已有数据")
    print("=" * 60)


if __name__ == "__main__":
    main()