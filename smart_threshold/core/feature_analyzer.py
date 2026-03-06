"""
特征分析模块

实现时序数据特征提取，包括：
- 季节性（Seasonality）：使用自相关函数（ACF）检测周期性模式
- 稀疏性（Sparsity）：计算零值或极小值的占比
- 平稳性（Stationarity）：使用 ADF 检验判断数据平稳性
"""

from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.tsa.stattools import acf, adfuller


@dataclass
class FeatureResult:
    """特征分析结果"""

    has_seasonality: bool  # 是否具有季节性
    seasonality_strength: float  # 季节性强度 (ACF 值)
    sparsity_ratio: float  # 稀疏度 (0-1)
    is_stationary: bool  # 是否平稳
    adf_pvalue: float  # ADF 检验 p-value
    mean: float  # 均值
    std: float  # 标准差

    def __repr__(self) -> str:
        return (
            f"FeatureResult(seasonality={self.has_seasonality}, "
            f"sparsity={self.sparsity_ratio:.2%}, "
            f"stationary={self.is_stationary})"
        )


class FeatureExtractor:
    """
    时序数据特征提取器

    使用示例:
    >>> extractor = FeatureExtractor(daily_period_lags=1440)
    >>> result = extractor.analyze(data)
    """

    # 默认配置
    SEASONALITY_THRESHOLD = 0.3  # ACF 阈值，超过此值认为有季节性
    SPARSITY_THRESHOLD = 0.8  # 稀疏度阈值，超过此值认为是稀疏数据
    STATIONARY_PVALUE = 0.05  # ADF 检验 p-value 阈值

    def __init__(
        self,
        daily_period_lags: int = 1440,
        min_value_threshold: Optional[float] = None,
        acf_nlags: int = 2000,
    ):
        """
        初始化特征提取器

        Args:
            daily_period_lags: 日周期的 lag 数量（默认 1440 分钟 = 1 天）
            min_value_threshold: 判定为"零值"的最小值阈值（None 表示自动判断）
            acf_nlags: ACF 计算的最大 lag 数
        """
        self.daily_period_lags = daily_period_lags
        self.min_value_threshold = min_value_threshold
        self.acf_nlags = min(acf_nlags, daily_period_lags * 2)

    def analyze(self, data: pd.Series | np.ndarray) -> FeatureResult:
        """
        分析时序数据的特征

        Args:
            data: 时序数据，可以是 pandas Series 或 numpy array

        Returns:
            FeatureResult: 特征分析结果
        """
        # 转换为 numpy array
        if isinstance(data, pd.Series):
            values = data.values
        else:
            values = np.array(data)

        # 移除 NaN 值
        values = values[~np.isnan(values)]

        if len(values) < 100:
            raise ValueError(f"数据量不足，至少需要 100 个数据点，当前仅 {len(values)} 个")

        # 并行计算各项特征
        has_seasonality, seasonality_strength = self._detect_seasonality(values)
        sparsity_ratio = self._calculate_sparsity(values)
        is_stationary, adf_pvalue = self._detect_stationarity(values)

        return FeatureResult(
            has_seasonality=has_seasonality,
            seasonality_strength=seasonality_strength,
            sparsity_ratio=sparsity_ratio,
            is_stationary=is_stationary,
            adf_pvalue=adf_pvalue,
            mean=float(np.mean(values)),
            std=float(np.std(values)),
        )

    def _detect_seasonality(self, values: np.ndarray) -> Tuple[bool, float]:
        """
        检测季节性

        使用自相关函数（ACF）检查在日周期位置的自相关性。

        Args:
            values: 时序数据

        Returns:
            (has_seasonality, acf_value): 是否有季节性及其强度
        """
        try:
            # 计算 ACF，确保 nlags 不超过数据长度的一半
            nlags = min(self.acf_nlags, len(values) // 2 - 1)
            if nlags < self.daily_period_lags:
                # 数据不足，无法检测日周期
                return False, 0.0

            autocorr = acf(values, nlags=nlags, fft=True)

            # 获取日周期位置的自相关系数
            seasonality_idx = min(self.daily_period_lags, len(autocorr) - 1)
            acf_value = autocorr[seasonality_idx]

            has_seasonality = acf_value > self.SEASONALITY_THRESHOLD

            return has_seasonality, float(acf_value)

        except Exception:
            # ACF 计算失败时，使用备用方法：简单周期检测
            return self._simple_seasonality_check(values)

    def _simple_seasonality_check(self, values: np.ndarray) -> Tuple[bool, float]:
        """
        简单的季节性检测（备用方法）

        比较相隔一个周期的数据点之间的相关性。
        """
        period = self.daily_period_lags
        if len(values) < 2 * period:
            return False, 0.0

        # 提取两个周期的数据
        first_period = values[:-period]
        second_period = values[period:]

        # 计算相关性
        if len(first_period) == 0 or len(second_period) == 0:
            return False, 0.0

        min_len = min(len(first_period), len(second_period))
        correlation = np.corrcoef(first_period[:min_len], second_period[:min_len])[0, 1]

        if np.isnan(correlation):
            return False, 0.0

        has_seasonality = abs(correlation) > self.SEASONALITY_THRESHOLD

        return has_seasonality, float(abs(correlation))

    def _calculate_sparsity(self, values: np.ndarray) -> float:
        """
        计算稀疏度

        稀疏度定义为：零值或接近零值的数据点占比。

        Args:
            values: 时序数据

        Returns:
            sparsity_ratio: 稀疏度 (0-1)
        """
        if self.min_value_threshold is None:
            # 自动判断阈值：使用非零数据中位数的 1%
            non_zero_values = values[values > 0]
            if len(non_zero_values) > 0:
                threshold = np.median(non_zero_values) * 0.01
            else:
                threshold = 1e-6
        else:
            threshold = self.min_value_threshold

        sparse_count = np.sum(values <= threshold)
        sparsity_ratio = sparse_count / len(values)

        return float(sparsity_ratio)

    def _detect_stationarity(self, values: np.ndarray) -> Tuple[bool, float]:
        """
        检测平稳性

        使用 Augmented Dickey-Fuller 检验。

        Args:
            values: 时序数据

        Returns:
            (is_stationary, p_value): 是否平稳及检验 p-value
        """
        try:
            # ADF 检验
            result = adfuller(values, maxlag=int(len(values) ** 0.25))

            # result[0]: test statistic
            # result[1]: p-value
            # result[4]: critical values

            p_value = result[1]
            is_stationary = p_value < self.STATIONARY_PVALUE

            return is_stationary, float(p_value)

        except Exception:
            # ADF 检验失败时，使用简化的方差检验
            return self._simple_stationarity_check(values)

    def _simple_stationarity_check(self, values: np.ndarray) -> Tuple[bool, float]:
        """
        简单的平稳性检测（备用方法）

        使用滑动窗口方差检测数据是否有明显的趋势偏移。
        """
        if len(values) < 50:
            # 数据量太少，假设平稳
            return True, 0.01

        # 将数据分为前后两半
        mid = len(values) // 2
        first_half = values[:mid]
        second_half = values[mid:]

        # 比较均值差异（使用 t 检验）
        _, p_value = stats.ttest_ind(first_half, second_half, equal_var=False)

        # p-value < 0.05 表示两半部分均值有显著差异，即不平稳
        is_stationary = p_value >= 0.05

        return is_stationary, float(p_value)
