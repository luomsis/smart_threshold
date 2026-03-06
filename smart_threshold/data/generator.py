"""
Mock 数据生成器

生成三种典型 DB 监控场景的时序数据：
1. QPS 场景：带 24 小时周期 + 线性增长 + 噪声
2. RT 场景：平稳 + 随机尖峰
3. 错误数场景：稀疏数据，大部分为 0
"""

from enum import Enum
from typing import Optional
import numpy as np
import pandas as pd


class ScenarioType(Enum):
    """场景类型枚举"""

    QPS = "qps"
    RT = "rt"
    ERROR_COUNT = "error_count"


class DataGenerator:
    """
    DB 监控数据生成器

    生成模拟的数据库时序数据，用于测试和演示。
    """

    def __init__(self, freq: str = "1min", seed: Optional[int] = None):
        """
        初始化数据生成器

        Args:
            freq: 采样频率（默认 1 分钟）
            seed: 随机种子（用于可复现的生成）
        """
        self.freq = freq
        self.rng = np.random.default_rng(seed)

    def generate(
        self,
        scenario: ScenarioType,
        days: int = 7,
        start_date: Optional[str] = None,
    ) -> pd.Series:
        """
        生成指定场景的时序数据

        Args:
            scenario: 场景类型
            days: 生成天数（默认 7 天）
            start_date: 起始日期（默认今天）

        Returns:
            pd.Series: 时序数据，index 为时间戳
        """
        # 生成时间索引
        if start_date is None:
            start_date = pd.Timestamp.now().normalize() - pd.Timedelta(days=days)
        else:
            start_date = pd.Timestamp(start_date)

        # 使用 periods 参数生成指定数量的数据点
        # days * 1440 = 天数 * 每天分钟数
        periods = days * 1440  # 1 分钟采样率
        index = pd.date_range(start=start_date, periods=periods, freq=self.freq)

        # 根据场景类型生成数据
        if scenario == ScenarioType.QPS:
            values = self._generate_qps(len(index), index)
        elif scenario == ScenarioType.RT:
            values = self._generate_rt(len(index), index)
        elif scenario == ScenarioType.ERROR_COUNT:
            values = self._generate_error_count(len(index))
        else:
            raise ValueError(f"未知的场景类型: {scenario}")

        return pd.Series(values, index=index, name=scenario.value)

    def _generate_qps(self, n_points: int, index: pd.DatetimeIndex) -> np.ndarray:
        """
        生成 QPS 数据

        特点：
        - 24 小时正弦波周期
        - 线性增长趋势（模拟扩容）
        - 随机噪声

        Args:
            n_points: 数据点数量
            index: 时间索引

        Returns:
            QPS 数值数组
        """
        # 时间（分钟）
        t = np.arange(n_points)

        # 基础周期（1440 分钟 = 1 天）
        daily_period = 1440
        daily_cycle = np.sin(2 * np.pi * t / daily_period)

        # 双峰模式：白天高、晚上低，加上小波动
        hour_of_day = (t / 60) % 24
        # 业务高峰在 10:00 和 15:00
        business_cycle = (
            0.5 * np.sin(2 * np.pi * (hour_of_day - 6) / 24)
            + 0.3 * np.sin(4 * np.pi * (hour_of_day - 6) / 24)
        )

        # 线性增长（模拟扩容）
        growth = 0.005 * t

        # 基础 QPS 水平
        base_qps = 1000

        # 组合所有因素
        qps = base_qps + 300 * business_cycle + growth

        # 添加噪声
        noise = self.rng.normal(0, 50, n_points)
        qps += noise

        # 确保 QPS 非负
        qps = np.maximum(qps, 0)

        return qps

    def _generate_rt(self, n_points: int, index: pd.DatetimeIndex) -> np.ndarray:
        """
        生成 RT（响应时间）数据

        特点：
        - 均值平稳（约 50ms）
        - 偶尔出现尖峰（5% 概率）
        - 尖峰持续时间短

        Args:
            n_points: 数据点数量
            index: 时间索引

        Returns:
            RT 数值数组（毫秒）
        """
        # 基础 RT
        base_rt = 50

        # 正常波动
        rt = self.rng.normal(base_rt, 10, n_points)

        # 注入尖峰（5% 概率）
        spike_mask = self.rng.random(n_points) < 0.05

        # 尖峰持续 1-5 分钟
        spike_locations = np.where(spike_mask)[0]
        for loc in spike_locations:
            duration = self.rng.integers(1, 6)
            end = min(loc + duration, n_points)
            # 尖峰值：200-400ms
            spike_value = self.rng.normal(300, 50)
            rt[loc:end] = spike_value

        # 确保 RT 非负
        rt = np.maximum(rt, 0)

        return rt

    def _generate_error_count(self, n_points: int) -> np.ndarray:
        """
        生成错误计数数据

        特点：
        - 大部分时间为 0（95%）
        - 偶尔出现离散的错误

        Args:
            n_points: 数据点数量

        Returns:
            错误计数数组
        """
        # 初始化全为 0
        errors = np.zeros(n_points, dtype=int)

        # 5% 的时间点有错误
        error_mask = self.rng.random(n_points) < 0.05
        error_count = np.sum(error_mask)

        # 这些错误点的值服从 Poisson 分布
        errors[error_mask] = self.rng.poisson(lam=5, size=error_count)

        return errors

    def generate_all(
        self, days: int = 7, start_date: Optional[str] = None
    ) -> dict[ScenarioType, pd.Series]:
        """
        生成所有场景的数据

        Args:
            days: 生成天数
            start_date: 起始日期

        Returns:
            字典，key 为场景类型，value 为对应的时序数据
        """
        return {
            scenario: self.generate(scenario, days, start_date)
            for scenario in ScenarioType
        }

    def add_anomaly(
        self, data: pd.Series, anomaly_ratio: float = 0.01, magnitude: float = 3.0
    ) -> pd.Series:
        """
        向数据中注入异常值

        Args:
            data: 原始数据
            anomaly_ratio: 异常比例（默认 1%）
            magnitude: 异常倍数（相对于标准差）

        Returns:
            带异常值的数据
        """
        data_copy = data.copy()
        n = len(data_copy)
        n_anomalies = int(n * anomaly_ratio)

        # 随机选择异常点
        anomaly_indices = self.rng.choice(n, n_anomalies, replace=False)

        # 计算标准差
        std = data.std()
        mean = data.mean()

        # 注入异常
        for idx in anomaly_indices:
            # 50% 概率向上异常，50% 向下异常
            if self.rng.random() < 0.5:
                data_copy.iloc[idx] = mean + magnitude * std + self.rng.normal(0, std)
            else:
                data_copy.iloc[idx] = max(0, mean - magnitude * std - self.rng.normal(0, std))

        return data_copy
