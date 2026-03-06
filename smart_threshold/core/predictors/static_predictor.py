"""
Static 预测器

使用百分位数法生成静态阈值，适合稀疏数据或低频指标。

适用场景：
- 错误计数
- 报警数量
- 大部分时间为 0 的低频指标
"""

from typing import Literal
import numpy as np
import pandas as pd

from smart_threshold.core.predictors.base import BasePredictor, PredictionResult
from smart_threshold.core.feature_analyzer import FeatureResult


class StaticPredictor(BasePredictor):
    """
    基于百分位数的静态阈值预测器

    对于稀疏数据，传统的时间序列预测效果不佳。
    使用百分位数法可以更稳健地设置阈值。

    策略：
    - 中位数作为基准值
    - 高百分位数（如 95th, 99th）作为上限
    - 0 作为下限（因为计数不能为负）
    """

    @staticmethod
    def get_default_config(features: FeatureResult) -> dict:
        """
        根据数据特征生成默认配置

        参数工厂方法：根据特征分析结果动态调整 Static 参数

        Args:
            features: 特征分析结果

        Returns:
            配置字典
        """
        config = {
            "upper_percentile": 99.0,
            "confidence_level": 0.99,
            "lower_bound": 0.0,
        }

        # 根据稀疏度调整百分位数
        if features.sparsity_ratio > 0.98:
            # 极度稀疏（98%+ 为 0），使用 100th（最大值）
            config["upper_percentile"] = 100.0
        elif features.sparsity_ratio > 0.95:
            # 高度稀疏（95%+ 为 0），使用 99.5th
            config["upper_percentile"] = 99.5
        elif features.sparsity_ratio > 0.90:
            # 中等稀疏，使用 99th
            config["upper_percentile"] = 99.0
        else:
            # 低稀疏度，可以使用更低的百分位数
            config["upper_percentile"] = 95.0

        return config

    def __init__(
        self,
        upper_percentile: float = 99.0,
        confidence_level: float = 0.99,
        lower_bound: float = 0.0,
    ):
        """
        初始化 Static 预测器

        Args:
            upper_percentile: 上限百分位数 (0-100)
            confidence_level: 置信水平（仅用于报告）
            lower_bound: 下限值（默认 0）
        """
        super().__init__(confidence_level=confidence_level)
        self.upper_percentile = upper_percentile
        self.lower_bound = lower_bound

        # 统计量
        self._median: float = 0.0
        self._upper_threshold: float = 0.0
        self._max_value: float = 0.0
        self._last_timestamp: pd.Timestamp = None

    def fit(self, data: pd.Series) -> None:
        """
        训练预测器

        Args:
            data: 训练数据，index 为时间戳
        """
        self._validate_input(data)
        self._training_data = data.copy()
        self._last_timestamp = data.index[-1]

        values = data.values

        # 计算统计量
        self._median = float(np.median(values))
        self._upper_threshold = float(np.percentile(values, self.upper_percentile))
        self._max_value = float(np.max(values))

        self.is_fitted = True

    def predict(self, periods: int, freq: str = "1min") -> PredictionResult:
        """
        预测未来数据

        对于静态阈值，所有时间点的预测值相同。

        Args:
            periods: 预测的时间点数量
            freq: 时间频率

        Returns:
            PredictionResult: 预测结果
        """
        if not self.is_fitted:
            raise ValueError("模型尚未训练，请先调用 fit()")

        # 生成时间索引
        future_index = self._generate_future_index(
            self._last_timestamp, periods, freq
        )

        # 静态阈值：所有时间点的值相同
        yhat = np.full(periods, self._median)
        yhat_upper = np.full(periods, self._upper_threshold)
        yhat_lower = np.full(periods, self.lower_bound)

        return PredictionResult(
            ds=future_index,
            yhat=yhat,
            yhat_upper=yhat_upper,
            yhat_lower=yhat_lower,
            algorithm=f"Static P{self.upper_percentile:.0f}",
            confidence_level=self.confidence_level,
        )

    def get_threshold(self) -> dict:
        """
        获取阈值信息

        Returns:
            包含阈值信息的字典
        """
        if not self.is_fitted:
            raise ValueError("模型尚未训练，请先调用 fit()")

        return {
            "median": self._median,
            "upper_threshold": self._upper_threshold,
            "lower_bound": self.lower_bound,
            "max_value": self._max_value,
            "upper_percentile": self.upper_percentile,
        }

    def get_anomalies(self, data: pd.Series) -> pd.Series:
        """
        检测异常值（超过上限的值）

        Args:
            data: 待检测数据

        Returns:
            布尔 Series，True 表示异常
        """
        if not self.is_fitted:
            raise ValueError("模型尚未训练，请先调用 fit()")

        return data > self._upper_threshold
