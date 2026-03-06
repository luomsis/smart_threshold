"""
Welford 3-Sigma 预测器

使用 Welford 在线算法计算均值和标准差，适用于高波动、无周期的数据。

Welford 算法优势：
- 数值稳定性好
- 适合流式计算
- 对大数溢出有保护

适用场景：
- RT（响应时间）
- 延迟指标
- 无明显周期的高波动数据
"""

import numpy as np
import pandas as pd
from scipy import stats

from smart_threshold.core.predictors.base import BasePredictor, PredictionResult
from smart_threshold.core.feature_analyzer import FeatureResult


class WelfordPredictor(BasePredictor):
    """
    基于 Welford 算法的动态阈值预测器

    使用 3-Sigma 原则生成动态阈值：
    - 上限: mean + 3 * std
    - 下限: max(0, mean - 3 * std)

    可根据置信水平调整 sigma 倍数：
    - 1-sigma: ~68% 置信区间
    - 2-sigma: ~95% 置信区间
    - 3-sigma: ~99.7% 置信区间
    """

    # Sigma 倍数对应的置信水平
    SIGMA_TO_CONFIDENCE = {
        1.0: 0.68,
        1.645: 0.90,
        1.96: 0.95,
        2.0: 0.9545,
        2.576: 0.99,
        3.0: 0.997,
        3.5: 0.9995,
    }

    # 置信水平对应的 sigma 倍数
    CONFIDENCE_TO_SIGMA = {
        0.68: 1.0,
        0.90: 1.645,
        0.95: 1.96,
        0.99: 2.576,
        0.997: 3.0,
    }

    def __init__(
        self,
        sigma_multiplier: float = 3.0,
        confidence_level: float = None,
        use_rolling_window: bool = False,
        window_size: int = 1440,
    ):
        """
        初始化 Welford 预测器

        Args:
            sigma_multiplier: Sigma 倍数（默认 3.0，对应 99.7% 置信区间）
            confidence_level: 置信水平（已废弃，使用 sigma_multiplier）
            use_rolling_window: 是否使用滚动窗口
            window_size: 滚动窗口大小（分钟）
        """
        # 兼容旧参数：如果提供了 confidence_level，计算 sigma_multiplier
        if confidence_level is not None:
            # 查找最接近的 sigma 倍数
            sigma_multiplier = self._confidence_to_sigma(confidence_level)

        self.sigma_multiplier = sigma_multiplier
        self.use_rolling_window = use_rolling_window
        self.window_size = window_size

        # 计算对应的置信水平
        cl = self._sigma_to_confidence(sigma_multiplier)
        super().__init__(confidence_level=cl)

        # 统计量
        self._mean: float = 0.0
        self._std: float = 0.0
        self._count: int = 0
        self._last_timestamp: pd.Timestamp = None

    def fit(self, data: pd.Series) -> None:
        """
        训练预测器

        使用 Welford 在线算法计算均值和标准差。

        Args:
            data: 训练数据，index 为时间戳
        """
        self._validate_input(data)
        self._training_data = data.copy()
        self._last_timestamp = data.index[-1]

        values = data.values

        if self.use_rolling_window:
            # 使用滚动窗口（适合有趋势的数据）
            self._fit_rolling(values)
        else:
            # 使用全局统计（适合平稳数据）
            self._fit_global(values)

        self.is_fitted = True

    def _fit_global(self, values: np.ndarray) -> None:
        """使用 Welford 算法计算全局统计量"""
        count = 0
        mean = 0.0
        m2 = 0.0  # 平方和的累积

        for x in values:
            count += 1
            delta = x - mean
            mean += delta / count
            delta2 = x - mean
            m2 += delta * delta2

        self._mean = mean
        self._count = count

        if count > 1:
            self._std = np.sqrt(m2 / count)
        else:
            self._std = 0.0

    def _fit_rolling(self, values: np.ndarray) -> None:
        """使用滚动窗口计算统计量"""
        window = min(self.window_size, len(values))
        recent_values = values[-window:]

        self._mean = float(np.mean(recent_values))
        self._std = float(np.std(recent_values, ddof=1))
        self._count = len(recent_values)

    def predict(self, periods: int, freq: str = "1min") -> PredictionResult:
        """
        预测未来数据

        对于平稳数据，预测值等于训练均值。
        对于有趋势的数据，建议使用滚动窗口模式。

        Args:
            periods: 预测的时间点数量
            freq: 时间频率

        Returns:
            PredictionResult: 预测结果
        """
        if not self.is_fitted:
            raise ValueError("模型尚未训练，请先调用 fit()")

        # 获取 sigma 倍数
        sigma_multiplier = self._get_sigma_multiplier()

        # 生成时间索引
        future_index = self._generate_future_index(
            self._last_timestamp, periods, freq
        )

        # 计算阈值
        yhat = np.full(periods, self._mean)
        yhat_upper = self._mean + sigma_multiplier * self._std
        yhat_lower = max(0, self._mean - sigma_multiplier * self._std)

        yhat_upper_arr = np.full(periods, yhat_upper)
        yhat_lower_arr = np.full(periods, yhat_lower)

        return PredictionResult(
            ds=future_index,
            yhat=yhat,
            yhat_upper=yhat_upper_arr,
            yhat_lower=yhat_lower_arr,
            algorithm=f"Welford {sigma_multiplier}-Sigma",
            confidence_level=self.confidence_level,
        )

    def _get_sigma_multiplier(self) -> float:
        """获取 sigma 倍数"""
        return self.sigma_multiplier

    @staticmethod
    def _sigma_to_confidence(sigma: float) -> float:
        """将 sigma 倍数转换为置信水平"""
        # 查找预定义的置信水平
        for s, cl in sorted(WelfordPredictor.SIGMA_TO_CONFIDENCE.items()):
            if sigma <= s:
                return cl
        # 如果找不到，使用正态分布计算
        return 2 * stats.norm.cdf(sigma) - 1

    @staticmethod
    def _confidence_to_sigma(confidence: float) -> float:
        """将置信水平转换为 sigma 倍数"""
        # 查找预定义的 sigma 倍数
        for cl, sigma in sorted(WelfordPredictor.CONFIDENCE_TO_SIGMA.items()):
            if confidence <= cl:
                return sigma
        # 如果找不到，使用正态分布分位数计算
        return stats.norm.ppf(1 - (1 - confidence) / 2)

    @staticmethod
    def get_default_config(features: FeatureResult) -> dict:
        """
        根据数据特征生成默认配置

        参数工厂方法：根据特征分析结果动态调整 Welford 参数

        Args:
            features: 特征分析结果

        Returns:
            配置字典
        """
        config = {
            "confidence_level": 0.997,
            "sigma_multiplier": 3.0,
            "use_rolling_window": False,
            "window_size": 1440,
        }

        # 根据变异系数 (CV) 调整 sigma
        # CV = std / mean，反映数据的相对波动性
        cv = features.std / (features.mean + 1e-6)

        if cv > 0.5:
            # 高波动数据，需要更宽松的阈值
            config["sigma_multiplier"] = 3.5
        elif cv > 0.3:
            config["sigma_multiplier"] = 3.0
        elif cv < 0.2:
            # 低波动数据，可以更紧凑
            config["sigma_multiplier"] = 2.5

        # 根据平稳性决定是否使用滚动窗口
        if not features.is_stationary:
            # 有趋势的数据，使用滚动窗口适应变化
            config["use_rolling_window"] = True
            config["window_size"] = 1440  # 1 天

        return config

    def get_anomalies(
        self, data: pd.Series, threshold_type: str = "upper"
    ) -> pd.Series:
        """
        检测异常值

        Args:
            data: 待检测数据
            threshold_type: 'upper', 'lower', 或 'both'

        Returns:
            布尔 Series，True 表示异常
        """
        if not self.is_fitted:
            raise ValueError("模型尚未训练，请先调用 fit()")

        sigma_multiplier = self._get_sigma_multiplier()
        upper_threshold = self._mean + sigma_multiplier * self._std
        lower_threshold = max(0, self._mean - sigma_multiplier * self._std)

        if threshold_type == "upper":
            return data > upper_threshold
        elif threshold_type == "lower":
            return data < lower_threshold
        else:  # both
            return (data > upper_threshold) | (data < lower_threshold)
