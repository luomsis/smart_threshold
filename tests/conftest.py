"""
pytest 配置和共享 fixtures
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta


@pytest.fixture
def random_seed():
    """固定随机种子，确保测试可重复"""
    np.random.seed(42)
    return 42


@pytest.fixture
def sample_timestamps():
    """生成示例时间戳索引（7 天，每分钟一个点）"""
    start = datetime(2024, 1, 1)
    periods = 7 * 1440  # 7 天，每天 1440 分钟
    return pd.date_range(start=start, periods=periods, freq="1min")


@pytest.fixture
def seasonal_data(sample_timestamps):
    """生成季节性数据（模拟 QPS）"""
    n = len(sample_timestamps)
    t = np.arange(n)

    # 24 小时正弦波周期
    daily_cycle = np.sin(2 * np.pi * t / 1440)

    # 基础值 + 周期 + 噪声
    values = 1000 + 300 * daily_cycle + np.random.normal(0, 50, n)

    return pd.Series(values, index=sample_timestamps, name="seasonal_qps")


@pytest.fixture
def sparse_data(sample_timestamps):
    """生成稀疏数据（模拟错误计数）"""
    n = len(sample_timestamps)
    values = np.zeros(n)

    # 5% 的数据点有值
    error_indices = np.random.choice(n, int(n * 0.05), replace=False)
    values[error_indices] = np.random.poisson(5, len(error_indices))

    return pd.Series(values, index=sample_timestamps, name="error_count")


@pytest.fixture
def stationary_data(sample_timestamps):
    """生成平稳数据（模拟 RT）"""
    n = len(sample_timestamps)

    # 平稳数据：均值 50，标准差 10
    values = np.random.normal(50, 10, n)
    values = np.maximum(values, 0)  # 确保非负

    return pd.Series(values, index=sample_timestamps, name="rt")


@pytest.fixture
def non_stationary_data(sample_timestamps):
    """生成非平稳数据（有趋势）"""
    n = len(sample_timestamps)
    t = np.arange(n)

    # 线性趋势
    trend = 0.01 * t
    values = 50 + trend + np.random.normal(0, 5, n)

    return pd.Series(values, index=sample_timestamps, name="trending")


@pytest.fixture
def small_data():
    """生成少量数据（用于边界测试）"""
    dates = pd.date_range(start="2024-01-01", periods=50, freq="1min")
    values = np.random.randn(50)
    return pd.Series(values, index=dates)


@pytest.fixture
def empty_data():
    """生成空数据"""
    return pd.Series([], dtype=float)


@pytest.fixture
def minimal_data():
    """生成最小数据量（刚好满足 100 点要求）"""
    dates = pd.date_range(start="2024-01-01", periods=100, freq="1min")
    values = np.random.randn(100)
    return pd.Series(values, index=dates)