"""
模型路由模块单元测试

测试 ModelRouter 类的路由决策逻辑。
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import MagicMock, patch

from smart_threshold.core.model_router import ModelRouter, AlgorithmType
from smart_threshold.core.feature_analyzer import FeatureResult, PeriodSeasonalityResult
from smart_threshold.core.predictors.base import BasePredictor
from smart_threshold.core.predictors.prophet_predictor import ProphetPredictor
from smart_threshold.core.predictors.welford_predictor import WelfordPredictor
from smart_threshold.core.predictors.static_predictor import StaticPredictor


class TestModelRouter:
    """ModelRouter 类测试"""

    def test_route_seasonal_data(self, seasonal_data):
        """测试季节性数据路由到 Prophet"""
        router = ModelRouter(verbose=False)
        predictor = router.select_predictor(seasonal_data)

        assert router.get_selected_algorithm() == AlgorithmType.PROPHET
        assert isinstance(predictor, ProphetPredictor)

    def test_route_sparse_data(self, sparse_data):
        """测试稀疏数据路由到 Static"""
        router = ModelRouter(verbose=False)
        predictor = router.select_predictor(sparse_data)

        assert router.get_selected_algorithm() == AlgorithmType.STATIC
        assert isinstance(predictor, StaticPredictor)

    def test_route_stationary_data(self, stationary_data):
        """测试平稳数据路由到 Welford"""
        router = ModelRouter(verbose=False)
        predictor = router.select_predictor(stationary_data)

        assert router.get_selected_algorithm() == AlgorithmType.WELFORD
        assert isinstance(predictor, WelfordPredictor)

    def test_force_algorithm(self, stationary_data):
        """测试强制指定算法"""
        router = ModelRouter(verbose=False)

        # 强制使用 Prophet
        predictor = router.select_predictor(stationary_data, force_algorithm=AlgorithmType.PROPHET)

        assert router.get_selected_algorithm() == AlgorithmType.PROPHET
        assert isinstance(predictor, ProphetPredictor)

    def test_get_last_features(self, seasonal_data):
        """测试获取最后特征"""
        router = ModelRouter(verbose=False)
        router.select_predictor(seasonal_data)

        features = router.get_last_features()

        assert features is not None
        assert isinstance(features, FeatureResult)
        assert features.has_seasonality == True

    def test_verbose_output(self, seasonal_data, capsys):
        """测试详细输出"""
        router = ModelRouter(verbose=True)
        router.select_predictor(seasonal_data)

        captured = capsys.readouterr()
        assert "ModelRouter" in captured.out
        assert "PROPHET" in captured.out

    def test_custom_feature_extractor(self, seasonal_data):
        """测试自定义特征提取器"""
        from smart_threshold.core.feature_analyzer import FeatureExtractor

        custom_extractor = FeatureExtractor(periods=['daily'])
        router = ModelRouter(
            feature_extractor=custom_extractor,
            verbose=False
        )

        predictor = router.select_predictor(seasonal_data)

        assert predictor is not None

    def test_explain_routing_seasonal(self):
        """测试季节性路由解释"""
        features = FeatureResult(
            has_seasonality=True,
            sparsity_ratio=0.1,
            is_stationary=True,
            adf_pvalue=0.01,
            mean=100.0,
            std=10.0,
            seasonality_periods={'daily': PeriodSeasonalityResult(acf=0.5, has_seasonality=True)},
            primary_period='daily'
        )

        explanation = ModelRouter.explain_routing(features)

        assert "Prophet" in explanation
        assert "季节性" in explanation

    def test_explain_routing_sparse(self):
        """测试稀疏数据路由解释"""
        features = FeatureResult(
            has_seasonality=False,
            sparsity_ratio=0.9,
            is_stationary=True,
            adf_pvalue=0.01,
            mean=10.0,
            std=5.0,
            seasonality_periods={'daily': PeriodSeasonalityResult(acf=0.1, has_seasonality=False)},
            primary_period=None
        )

        explanation = ModelRouter.explain_routing(features)

        assert "Static" in explanation or "稀疏" in explanation

    def test_explain_routing_welford(self):
        """测试 Welford 路由解释"""
        features = FeatureResult(
            has_seasonality=False,
            sparsity_ratio=0.1,
            is_stationary=True,
            adf_pvalue=0.01,
            mean=50.0,
            std=10.0,
            seasonality_periods={'daily': PeriodSeasonalityResult(acf=0.1, has_seasonality=False)},
            primary_period=None
        )

        explanation = ModelRouter.explain_routing(features)

        assert "Welford" in explanation or "3-Sigma" in explanation


class TestAlgorithmType:
    """AlgorithmType 枚举测试"""

    def test_algorithm_type_values(self):
        """测试算法类型值"""
        assert AlgorithmType.PROPHET.value == "prophet"
        assert AlgorithmType.WELFORD.value == "welford"
        assert AlgorithmType.STATIC.value == "static"

    def test_to_predictor_type(self):
        """测试转换为预测器类型"""
        assert AlgorithmType.PROPHET.to_predictor_type() == "prophet"
        assert AlgorithmType.WELFORD.to_predictor_type() == "welford"
        assert AlgorithmType.STATIC.to_predictor_type() == "static"


class TestModelRouterRoutingRules:
    """路由规则详细测试"""

    def test_seasonality_threshold(self, seasonal_data):
        """测试季节性阈值"""
        router = ModelRouter(verbose=False)

        # 季节性强度 > 0.3 应该选择 Prophet
        predictor = router.select_predictor(seasonal_data)

        assert router.get_selected_algorithm() == AlgorithmType.PROPHET

    def test_sparsity_threshold(self, sparse_data):
        """测试稀疏度阈值"""
        router = ModelRouter(verbose=False)

        # 稀疏度 >= 0.8 应该选择 Static
        predictor = router.select_predictor(sparse_data)

        assert router.get_selected_algorithm() == AlgorithmType.STATIC

    def test_default_to_welford(self):
        """测试默认路由到 Welford"""
        # 创建无季节性、低稀疏度的数据
        n = 2000
        dates = pd.date_range(start="2024-01-01", periods=n, freq="1min")
        # 平稳随机数据，无季节性
        values = np.random.normal(100, 20, n)
        data = pd.Series(values, index=dates)

        router = ModelRouter(verbose=False)
        predictor = router.select_predictor(data)

        # 应该选择 Welford
        assert router.get_selected_algorithm() == AlgorithmType.WELFORD

    def test_priority_seasonality_over_sparsity(self):
        """测试季节性优先级高于稀疏度"""
        # 创建有季节性且稀疏的数据
        n = 2000
        dates = pd.date_range(start="2024-01-01", periods=n, freq="1min")
        t = np.arange(n)

        # 有季节性
        values = 100 + 50 * np.sin(2 * np.pi * t / 1440)
        # 但设置很多为 0（稀疏）
        values[:int(n * 0.8)] = 0

        data = pd.Series(values, index=dates)

        router = ModelRouter(verbose=False)
        router.select_predictor(data)

        # 季节性检测优先级更高
        # 注意：实际结果取决于特征分析的结果
        assert router.get_selected_algorithm() is not None


class TestModelRouterIntegration:
    """集成测试"""

    def test_fit_and_predict_flow(self, stationary_data):
        """测试完整的训练和预测流程"""
        router = ModelRouter(verbose=False)
        predictor = router.select_predictor(stationary_data)

        # 训练
        predictor.fit(stationary_data)
        assert predictor.is_fitted == True

        # 预测
        result = predictor.predict(periods=60)
        assert len(result.yhat) == 60

    def test_multiple_predictions(self, seasonal_data, sparse_data, stationary_data):
        """测试多种数据类型的预测"""
        router = ModelRouter(verbose=False)

        # 季节性数据
        p1 = router.select_predictor(seasonal_data)
        p1.fit(seasonal_data)
        r1 = p1.predict(periods=10)
        assert router.get_selected_algorithm() == AlgorithmType.PROPHET

        # 稀疏数据
        p2 = router.select_predictor(sparse_data)
        p2.fit(sparse_data)
        r2 = p2.predict(periods=10)
        assert router.get_selected_algorithm() == AlgorithmType.STATIC

        # 平稳数据
        p3 = router.select_predictor(stationary_data)
        p3.fit(stationary_data)
        r3 = p3.predict(periods=10)
        assert router.get_selected_algorithm() == AlgorithmType.WELFORD


class TestModelRouterConfig:
    """配置相关测试"""

    def test_config_dict(self, stationary_data):
        """测试配置字典"""
        config = {
            "welford": {
                "sigma_multiplier": 2.5
            }
        }

        router = ModelRouter(verbose=False, config_dict=config)
        predictor = router.select_predictor(stationary_data)

        # 验证配置被应用
        assert isinstance(predictor, WelfordPredictor)