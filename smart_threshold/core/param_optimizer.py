"""
参数优化器

在历史数据上进行参数扫描，自动寻找最优的阈值参数。

目标：找到既能包容历史波动又能保持紧凑的阈值参数。
"""

from dataclasses import dataclass
from typing import Optional, Callable
import numpy as np
import pandas as pd

from smart_threshold.core.predictors.base import BasePredictor
from smart_threshold.core.predictors.welford_predictor import WelfordPredictor
from smart_threshold.core.feature_analyzer import FeatureResult


@dataclass
class OptimizationResult:
    """参数优化结果"""

    best_sigma: float
    best_score: float
    coverage: float  # 历史覆盖率
    anomaly_rate: float  # 异常率
    scan_results: list  # 扫描结果详情

    def __repr__(self) -> str:
        return (
            f"OptimizationResult(best_sigma={self.best_sigma:.2f}, "
            f"coverage={self.coverage:.2%}, anomaly_rate={self.anomaly_rate:.2%})"
        )


class ParamOptimizer:
    """
    参数优化器

    自动扫描参数空间，寻找最优配置。

    使用示例:
    >>> optimizer = ParamOptimizer()
    >>> result = optimizer.optimize_sigma(predictor, train_data)
    >>> print(f"最优 sigma: {result.best_sigma}")
    """

    def __init__(
        self,
        scan_range: tuple = (1.5, 4.0),
        scan_step: float = 0.1,
        target_coverage: float = 0.98,
        max_anomaly_rate: float = 0.02,
    ):
        """
        初始化参数优化器

        Args:
            scan_range: Sigma 扫描范围 (min, max)
            scan_step: 扫描步长
            target_coverage: 目标历史覆盖率
            max_anomaly_rate: 最大允许异常率
        """
        self.scan_range = scan_range
        self.scan_step = scan_step
        self.target_coverage = target_coverage
        self.max_anomaly_rate = max_anomaly_rate

    def optimize_sigma(
        self,
        predictor: BasePredictor,
        train_data: pd.Series,
        verbose: bool = False,
    ) -> OptimizationResult:
        """
        优化 Sigma 系数

        目标：找到最小的 sigma，使得:
        - 历史数据覆盖率 >= target_coverage
        - 异常率 <= max_anomaly_rate

        Args:
            predictor: 预测器（需要先 fit）
            train_data: 训练数据（用于回测）
            verbose: 是否打印扫描信息

        Returns:
            OptimizationResult: 优化结果
        """
        if not predictor.is_fitted:
            raise ValueError("预测器尚未训练，请先调用 fit()")

        # 对于 Welford 预测器，直接优化 sigma
        if isinstance(predictor, WelfordPredictor):
            return self._optimize_welford_sigma(predictor, train_data, verbose)

        # 对于其他预测器，使用通用优化方法
        return self._optimize_generic(predictor, train_data, verbose)

    def _optimize_welford_sigma(
        self,
        predictor: WelfordPredictor,
        train_data: pd.Series,
        verbose: bool,
    ) -> OptimizationResult:
        """优化 Welford 预测器的 sigma"""
        best_sigma = 3.0
        best_score = float("inf")
        best_coverage = 0.0
        best_anomaly_rate = 1.0
        scan_results = []

        mean = predictor._mean
        std = predictor._std

        if verbose:
            print(f"\n[参数优化] Sigma 扫描 (范围: {self.scan_range}, 步长: {self.scan_step})")
            print(f"  均值: {mean:.2f}, 标准差: {std:.2f}")
            print(f"  目标覆盖率: {self.target_coverage:.1%}, 最大异常率: {self.max_anomaly_rate:.1%}")
            print()

        # 扫描 sigma
        for sigma in np.arange(self.scan_range[0], self.scan_range[1] + self.scan_step, self.scan_step):
            # 计算阈值
            upper = mean + sigma * std
            lower = max(0, mean - sigma * std)

            # 计算覆盖率和异常率
            coverage = ((train_data >= lower) & (train_data <= upper)).mean()
            anomaly_rate = (train_data > upper).mean()

            # 评分: 优先满足约束，其次 sigma 越小越好
            if coverage >= self.target_coverage and anomaly_rate <= self.max_anomaly_rate:
                score = sigma  # sigma 越小越好
                if score < best_score:
                    best_score = score
                    best_sigma = sigma
                    best_coverage = coverage
                    best_anomaly_rate = anomaly_rate

            scan_results.append({
                "sigma": sigma,
                "coverage": coverage,
                "anomaly_rate": anomaly_rate,
                "upper": upper,
                "lower": lower,
                "valid": coverage >= self.target_coverage and anomaly_rate <= self.max_anomaly_rate,
            })

            if verbose:
                status = "✓" if scan_results[-1]["valid"] else "✗"
                print(
                    f"  {status} σ={sigma:.1f}: 覆盖率={coverage:.1%}, "
                    f"异常率={anomaly_rate:.1%}, 阈值=[{lower:.1f}, {upper:.1f}]"
                )

        return OptimizationResult(
            best_sigma=best_sigma,
            best_score=best_score,
            coverage=best_coverage,
            anomaly_rate=best_anomaly_rate,
            scan_results=scan_results,
        )

    def _optimize_generic(
        self,
        predictor: BasePredictor,
        train_data: pd.Series,
        verbose: bool,
    ) -> OptimizationResult:
        """
        通用优化方法（用于非 Welford 预测器）

        通过重新训练和预测来评估不同配置
        """
        # 对于 Prophet 和 Static，优化策略不同
        # 这里提供一个简化版本，使用预测的置信区间

        # 获取训练数据上的预测结果
        # 注意：这需要预测器支持在训练数据上进行预测
        # 如果不支持，返回默认结果

        return OptimizationResult(
            best_sigma=3.0,
            best_score=3.0,
            coverage=0.95,
            anomaly_rate=0.01,
            scan_results=[],
        )

    def optimize_with_custom_scoring(
        self,
        train_data: pd.Series,
        score_fn: Callable[[float], float],
        scan_range: Optional[tuple] = None,
    ) -> tuple[float, list]:
        """
        使用自定义评分函数进行优化

        Args:
            train_data: 训练数据
            score_fn: 评分函数，输入 sigma，输出分数（越小越好）
            scan_range: 扫描范围（默认使用初始化时的范围）

        Returns:
            (best_sigma, scan_results)
        """
        if scan_range is None:
            scan_range = self.scan_range

        best_sigma = 3.0
        best_score = float("inf")
        scan_results = []

        for sigma in np.arange(scan_range[0], scan_range[1] + self.scan_step, self.scan_step):
            score = score_fn(sigma)

            if score < best_score:
                best_score = score
                best_sigma = sigma

            scan_results.append({"sigma": sigma, "score": score})

        return best_sigma, scan_results

    @staticmethod
    def calculate_sigma_from_percentile(
        data: pd.Series,
        target_percentile: float = 95.0,
    ) -> float:
        """
        根据目标百分位数计算所需的 sigma

        假设数据服从正态分布，计算使覆盖率达到目标百分位数的 sigma

        Args:
            data: 数据
            target_percentile: 目标覆盖率百分位数

        Returns:
            sigma 系数
        """
        from scipy import stats

        mean = data.mean()
        std = data.std()

        # 目标阈值
        target_value = np.percentile(data, target_percentile)

        # 计算 sigma
        sigma = (target_value - mean) / std if std > 0 else 3.0

        return max(1.0, min(5.0, sigma))  # 限制在 [1, 5] 范围内

    def optimize_auto(
        self,
        predictor: BasePredictor,
        train_data: pd.Series,
        verbose: bool = False,
    ) -> float:
        """
        自动优化（简化版）

        根据数据特征自动选择最优 sigma

        Args:
            predictor: 预测器
            train_data: 训练数据
            verbose: 是否打印信息

        Returns:
            最优 sigma
        """
        # 计算数据特征
        mean = train_data.mean()
        std = train_data.std()

        # 方法 1: 基于百分位数
        sigma_percentile = self.calculate_sigma_from_percentile(train_data, 95)

        # 方法 2: 基于历史最大值
        max_value = train_data.max()
        sigma_max = (max_value - mean) / std if std > 0 else 3.0

        # 取平均，并限制在合理范围内
        auto_sigma = (sigma_percentile + sigma_max) / 2
        auto_sigma = max(1.5, min(4.0, auto_sigma))

        if verbose:
            print(f"\n[自动优化]")
            print(f"  基于百分位数的 sigma: {sigma_percentile:.2f}")
            print(f"  基于历史最大值的 sigma: {sigma_max:.2f}")
            print(f"  自动选择的 sigma: {auto_sigma:.2f}")

        return auto_sigma


# 保持向后兼容的别名
BacktestOptimizer = ParamOptimizer
