"""
模型路由器

根据时序数据的特征自动选择最合适的预测算法。

路由规则：
├── 有季节性 → Prophet (适合周期性数据如 QPS)
├── 无季节性 AND 低稀疏性 → Welford 3-Sigma (适合高波动数据如 RT)
└── 高稀疏性 → Static/Percentile (适合稀疏数据如错误计数)
"""

from enum import Enum
from typing import Optional
import pandas as pd

from smart_threshold.core.feature_analyzer import FeatureExtractor, FeatureResult
from smart_threshold.core.predictors.base import BasePredictor, PredictionResult
from smart_threshold.core.predictors.factory import PredictorFactory, PredictorType
from smart_threshold.config import ConfigManager
from smart_threshold.core.param_optimizer import ParamOptimizer


class AlgorithmType(Enum):
    """算法类型枚举"""

    PROPHET = "prophet"
    WELFORD = "welford"
    STATIC = "static"

    # 映射到 PredictorType
    def to_predictor_type(self) -> str:
        """转换为 PredictorType"""
        return self.value


class ModelRouter:
    """
    模型路由器

    根据数据特征自动选择最合适的预测算法。

    使用示例:
    >>> router = ModelRouter()
    >>> predictor = router.select_predictor(data)
    >>> predictor.fit(data)
    >>> result = predictor.predict(periods=1440)
    """

    # 特征阈值配置
    SEASONALITY_THRESHOLD = 0.3  # ACF 阈值
    SPARSITY_THRESHOLD = 0.8  # 稀疏度阈值

    def __init__(
        self,
        feature_extractor: Optional[FeatureExtractor] = None,
        verbose: bool = True,
        config_path: Optional[str] = None,
        config_dict: Optional[dict] = None,
        enable_auto_optimize: bool = False,
    ):
        """
        初始化模型路由器

        Args:
            feature_extractor: 自定义特征提取器（可选）
            verbose: 是否打印选择信息
            config_path: YAML 配置文件路径（可选）
            config_dict: 配置字典（可选）
            enable_auto_optimize: 是否启用自动优化
        """
        self.feature_extractor = feature_extractor or FeatureExtractor()
        self.verbose = verbose
        self._selected_algorithm: Optional[AlgorithmType] = None
        self._last_features: Optional[FeatureResult] = None

        # 配置管理
        self.config_manager = ConfigManager(config_path=config_path, config_dict=config_dict)
        self.enable_auto_optimize = enable_auto_optimize

        # 参数优化器
        if enable_auto_optimize:
            backtest_config = self.config_manager.get_backtest_config()
            self.optimizer = ParamOptimizer(
                scan_range=tuple(backtest_config.get("scan_range", [1.5, 4.0])),
                scan_step=backtest_config.get("scan_step", 0.1),
                target_coverage=backtest_config.get("target_coverage", 0.98),
                max_anomaly_rate=backtest_config.get("max_anomaly_rate", 0.02),
            )
        else:
            self.optimizer = None

    def select_predictor(
        self,
        data: pd.Series,
        force_algorithm: Optional[AlgorithmType] = None,
    ) -> BasePredictor:
        """
        根据数据特征选择预测器

        Args:
            data: 时序数据
            force_algorithm: 强制使用指定算法（用于测试或特殊场景）

        Returns:
            BasePredictor: 选定的预测器实例
        """
        # 如果强制指定算法
        if force_algorithm is not None:
            self._selected_algorithm = force_algorithm
            # 获取特征（用于参数工厂）
            features = self.feature_extractor.analyze(data)
            self._last_features = features
            predictor = self._create_predictor_with_config(force_algorithm, features)
            if self.verbose:
                print(f"[ModelRouter] 强制使用算法: {force_algorithm.value}")
            return predictor

        # 分析数据特征
        features = self.feature_extractor.analyze(data)
        self._last_features = features

        # 根据特征选择算法
        algorithm = self._route_by_features(features)
        self._selected_algorithm = algorithm

        # 创建预测器（带配置）
        predictor = self._create_predictor_with_config(algorithm, features)

        if self.verbose:
            self._log_selection(features, algorithm)

        return predictor

    def _create_predictor_with_config(
        self, algorithm: AlgorithmType, features: FeatureResult
    ) -> BasePredictor:
        """
        使用参数工厂和配置管理创建预测器

        Args:
            algorithm: 算法类型
            features: 特征分析结果

        Returns:
            BasePredictor: 预测器实例
        """
        # 1. 获取参数工厂生成的默认配置
        factory_config = self._get_factory_config(algorithm, features)

        # 2. 应用配置覆盖（YAML < 运行时覆盖 < 参数工厂）
        final_config = self.config_manager.get_final_config(
            algorithm.value, factory_config
        )

        # 3. 创建预测器
        predictor = self._create_predictor(algorithm, **final_config)

        # 4. 可选: 自动优化
        if self.enable_auto_optimize and predictor.is_fitted:
            predictor = self._auto_optimize_predictor(predictor, features)

        return predictor

    def _get_factory_config(self, algorithm: AlgorithmType, features: FeatureResult) -> dict:
        """
        从参数工厂获取配置

        Args:
            algorithm: 算法类型
            features: 特征分析结果

        Returns:
            配置字典
        """
        if algorithm == AlgorithmType.PROPHET:
            return ProphetPredictor.get_default_config(features)
        elif algorithm == AlgorithmType.WELFORD:
            return WelfordPredictor.get_default_config(features)
        elif algorithm == AlgorithmType.STATIC:
            return StaticPredictor.get_default_config(features)
        else:
            return {}

    def _auto_optimize_predictor(
        self, predictor: BasePredictor, features: FeatureResult
    ) -> BasePredictor:
        """
        自动优化预测器参数

        Args:
            predictor: 预测器实例
            features: 特征分析结果

        Returns:
            优化后的预测器
        """
        if isinstance(predictor, WelfordPredictor) and self.optimizer:
            # 需要训练数据才能优化
            # 这里返回原始预测器，优化在 fit 后进行
            pass

        return predictor

    def optimize_predictor(
        self, predictor: BasePredictor, train_data: pd.Series, verbose: bool = False
    ) -> BasePredictor:
        """
        优化已训练的预测器

        Args:
            predictor: 已训练的预测器
            train_data: 训练数据
            verbose: 是否打印优化信息

        Returns:
            优化后的预测器
        """
        if not self.enable_auto_optimize or self.optimizer is None:
            return predictor

        if isinstance(predictor, WelfordPredictor):
            result = self.optimizer.optimize_sigma(predictor, train_data, verbose=verbose)

            if verbose and result.best_sigma != predictor._get_sigma_multiplier():
                # 创建新的预测器使用优化后的 sigma
                old_sigma = predictor._get_sigma_multiplier()
                if self.verbose:
                    print(f"\n[ModelRouter] 自动优化: {old_sigma:.2f}σ → {result.best_sigma:.2f}σ")
                    print(f"  覆盖率: {result.coverage:.1%}, 异常率: {result.anomaly_rate:.1%}")

                # 更新预测器的 sigma
                # 注意：这需要直接修改内部状态
                return self._create_predictor(
                    AlgorithmType.WELFORD,
                    sigma_multiplier=result.best_sigma,
                )

        return predictor

    def _route_by_features(self, features: FeatureResult) -> AlgorithmType:
        """
        根据特征路由到对应算法

        路由规则:
        1. 有季节性 → Prophet
        2. 无季节性 AND 低稀疏性 → Welford
        3. 高稀疏性 → Static

        Args:
            features: 特征分析结果

        Returns:
            AlgorithmType: 选定的算法类型
        """
        # 规则 1: 有季节性 → Prophet
        if features.has_seasonality:
            return AlgorithmType.PROPHET

        # 规则 2: 高稀疏性 → Static
        if features.sparsity_ratio >= self.SPARSITY_THRESHOLD:
            return AlgorithmType.STATIC

        # 规则 3: 默认 → Welford
        return AlgorithmType.WELFORD

    def _create_predictor(
        self, algorithm: AlgorithmType, **kwargs
    ) -> BasePredictor:
        """
        创建预测器实例（使用工厂模式）

        Args:
            algorithm: 算法类型
            **kwargs: 传递给预测器的额外参数

        Returns:
            BasePredictor: 预测器实例
        """
        # 使用工厂创建预测器，降低耦合
        predictor_type = algorithm.to_predictor_type()
        return PredictorFactory.create(predictor_type, **kwargs)

    def _log_selection(
        self, features: FeatureResult, algorithm: AlgorithmType
    ) -> None:
        """打印选择信息"""
        print(f"\n{'='*60}")
        print(f"[ModelRouter] 算法选型结果")
        print(f"{'='*60}")
        print(f"  季节性:     {features.has_seasonality} (ACF={features.seasonality_strength:.3f})")
        print(f"  稀疏度:     {features.sparsity_ratio:.1%}")
        print(f"  平稳性:     {features.is_stationary} (p={features.adf_pvalue:.4f})")
        print(f"  均值:       {features.mean:.2f}")
        print(f"  标准差:     {features.std:.2f}")
        print(f"{'='*60}")
        print(f"  → 选择算法: {algorithm.value.upper()}")
        print(f"{'='*60}\n")

    def get_selected_algorithm(self) -> Optional[AlgorithmType]:
        """获取当前选择的算法"""
        return self._selected_algorithm

    def get_last_features(self) -> Optional[FeatureResult]:
        """获取最后一次的特征分析结果"""
        return self._last_features

    @staticmethod
    def explain_routing(features: FeatureResult) -> str:
        """
        解释路由决策

        Args:
            features: 特征分析结果

        Returns:
            路由决策的解释文本
        """
        reasons = []

        if features.has_seasonality:
            reasons.append(
                f"✓ 检测到季节性 (ACF={features.seasonality_strength:.3f} > "
                f"{ModelRouter.SEASONALITY_THRESHOLD})，使用 Prophet 处理周期模式"
            )
        elif features.sparsity_ratio >= ModelRouter.SPARSITY_THRESHOLD:
            reasons.append(
                f"✓ 数据高度稀疏 (稀疏度={features.sparsity_ratio:.1%} > "
                f"{ModelRouter.SPARSITY_THRESHOLD:.0%})，使用 Static 百分位数法"
            )
        else:
            reasons.append(
                f"✓ 数据无明显季节性且非稀疏 (稀疏度={features.sparsity_ratio:.1%})，"
                f"使用 Welford 3-Sigma 处理高波动"
            )

        return "\n".join(reasons)
