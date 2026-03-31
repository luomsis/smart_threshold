"""
特征分析模块

实现时序数据特征提取，包括：
- 季节性（Seasonality）：使用自相关函数（ACF）检测周期性模式，支持多周期检测
- 稀疏性（Sparsity）：计算零值或极小值的占比
- 平稳性（Stationarity）：使用 ADF 检验判断数据平稳性
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple, Dict, List
import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.tsa.stattools import acf, adfuller


@dataclass
class PeriodSeasonalityResult:
    """单个周期的季节性检测结果"""
    acf: float  # ACF 值
    has_seasonality: bool  # 是否有该周期季节性


@dataclass
class FeatureResult:
    """特征分析结果"""

    has_seasonality: bool  # 是否具有季节性（任一周期有季节性即为 True）
    sparsity_ratio: float  # 稀疏度 (0-1)
    is_stationary: bool  # 是否平稳
    adf_pvalue: float  # ADF 检验 p-value
    mean: float  # 均值
    std: float  # 标准差
    seasonality_periods: Dict[str, 'PeriodSeasonalityResult'] = field(default_factory=dict)  # 各周期的检测结果
    primary_period: Optional[str] = None  # 主周期（ACF 最高的周期）

    def __repr__(self) -> str:
        periods_str = ", ".join(
            f"{k}: {v.acf:.2f}" for k, v in self.seasonality_periods.items()
        ) if self.seasonality_periods else "none"
        return (
            f"FeatureResult(seasonality={self.has_seasonality}, "
            f"primary={self.primary_period}, "
            f"periods=[{periods_str}], "
            f"sparsity={self.sparsity_ratio:.2%}, "
            f"stationary={self.is_stationary})"
        )


class FeatureExtractor:
    """
    时序数据特征提取器

    支持多周期季节性检测：
    - hourly: 60 分钟（小时周期）
    - daily: 1440 分钟（日周期）
    - weekly: 10080 分钟（周周期）
    - monthly: 43200 分钟（月周期，约 30 天）

    使用示例:
    >>> extractor = FeatureExtractor(periods=['daily', 'weekly'])
    >>> result = extractor.analyze(data)
    >>> print(result.seasonality_periods['daily'].has_seasonality)
    """

    # 多周期定义（分钟数）
    PERIODS = {
        'hourly': 60,      # 小时周期
        'daily': 1440,     # 日周期
        'weekly': 10080,   # 周周期
        'monthly': 43200,  # 月周期 (30天)
    }

    # 默认配置
    SEASONALITY_THRESHOLD = 0.3  # ACF 阈值，超过此值认为有季节性
    SPARSITY_THRESHOLD = 0.8  # 稀疏度阈值，超过此值认为是稀疏数据
    STATIONARY_PVALUE = 0.05  # ADF 检验 p-value 阈值

    def __init__(
        self,
        periods: List[str] = ['daily', 'weekly'],
        min_value_threshold: Optional[float] = None,
        acf_nlags: int = 20000,
    ):
        """
        初始化特征提取器

        Args:
            periods: 要检测的周期列表，可选值: 'hourly', 'daily', 'weekly', 'monthly'
            min_value_threshold: 判定为"零值"的最小值阈值（None 表示自动判断）
            acf_nlags: ACF 计算的最大 lag 数
        """
        # 验证 periods 参数
        valid_periods = set(self.PERIODS.keys())
        for p in periods:
            if p not in valid_periods:
                raise ValueError(f"Invalid period '{p}'. Valid options: {valid_periods}")

        self.periods_to_check = periods
        self.min_value_threshold = min_value_threshold

        # 计算最大需要的 lag 数
        max_period_lags = max(self.PERIODS[p] for p in periods)
        self.acf_nlags = min(acf_nlags, max_period_lags * 2)

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
        has_seasonality, seasonality_periods, primary_period = self._detect_seasonality(values)
        sparsity_ratio = self._calculate_sparsity(values)
        is_stationary, adf_pvalue = self._detect_stationarity(values)

        return FeatureResult(
            has_seasonality=has_seasonality,
            seasonality_periods=seasonality_periods,
            primary_period=primary_period,
            sparsity_ratio=sparsity_ratio,
            is_stationary=is_stationary,
            adf_pvalue=adf_pvalue,
            mean=float(np.mean(values)),
            std=float(np.std(values)),
        )

    def _acf_at_lag(self, values: np.ndarray, lag: int) -> float:
        """
        计算指定 lag 处的 ACF 值

        Args:
            values: 时序数据
            lag: Lag 数

        Returns:
            ACF 值
        """
        try:
            # 使用简单方法计算特定 lag 的 ACF
            if len(values) < 2 * lag:
                return 0.0

            # 提取两个序列
            first = values[:-lag]
            second = values[lag:]

            # 计算相关性
            min_len = min(len(first), len(second))
            correlation = np.corrcoef(first[:min_len], second[:min_len])[0, 1]

            if np.isnan(correlation):
                return 0.0

            return float(abs(correlation))
        except Exception:
            return 0.0

    def _detect_seasonality(self, values: np.ndarray) -> Tuple[bool, Dict[str, PeriodSeasonalityResult], Optional[str]]:
        """
        检测多周期季节性

        使用自相关函数（ACF）检查各周期位置的自相关性。

        Args:
            values: 时序数据

        Returns:
            (has_seasonality, seasonality_periods, primary_period):
                是否有季节性，各周期结果，主周期
        """
        results: Dict[str, PeriodSeasonalityResult] = {}

        # 计算整体 ACF 以优化性能
        try:
            nlags = min(self.acf_nlags, len(values) // 2 - 1)
            if nlags < 10:
                # 数据太少，逐个计算
                for period_name in self.periods_to_check:
                    period_lags = self.PERIODS[period_name]
                    acf_value = self._acf_at_lag(values, period_lags)
                    results[period_name] = PeriodSeasonalityResult(
                        acf=acf_value,
                        has_seasonality=acf_value > self.SEASONALITY_THRESHOLD
                    )
            else:
                # 使用 statsmodels.acf 计算
                autocorr = acf(values, nlags=nlags, fft=True)

                for period_name in self.periods_to_check:
                    period_lags = self.PERIODS[period_name]

                    if period_lags < len(autocorr):
                        acf_value = autocorr[period_lags]
                    else:
                        # Lag 超出范围，使用备用方法
                        acf_value = self._acf_at_lag(values, period_lags)

                    results[period_name] = PeriodSeasonalityResult(
                        acf=float(abs(acf_value)),
                        has_seasonality=abs(acf_value) > self.SEASONALITY_THRESHOLD
                    )

        except Exception:
            # ACF 计算失败时，逐个周期使用简单方法
            for period_name in self.periods_to_check:
                period_lags = self.PERIODS[period_name]
                acf_value = self._acf_at_lag(values, period_lags)
                results[period_name] = PeriodSeasonalityResult(
                    acf=acf_value,
                    has_seasonality=acf_value > self.SEASONALITY_THRESHOLD
                )

        # 综合判断：任一周期有显著季节性则认为有季节性
        has_seasonality = any(r.has_seasonality for r in results.values())

        # 找出主周期（ACF 最高的周期）
        primary_period = None
        if has_seasonality:
            valid_periods = {k: v for k, v in results.items() if v.has_seasonality}
            if valid_periods:
                primary_period = max(valid_periods.items(), key=lambda x: x[1].acf)[0]

        return has_seasonality, results, primary_period

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
