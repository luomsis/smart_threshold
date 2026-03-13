"""
预测器工厂单元测试

测试 PredictorFactory 类的功能。
"""

import pytest
from smart_threshold.core.predictors.factory import (
    PredictorFactory,
    PredictorType,
    create_predictor
)
from smart_threshold.core.predictors.base import BasePredictor
from smart_threshold.core.predictors.prophet_predictor import ProphetPredictor
from smart_threshold.core.predictors.welford_predictor import WelfordPredictor
from smart_threshold.core.predictors.static_predictor import StaticPredictor


class TestPredictorType:
    """PredictorType 常量测试"""

    def test_predictor_type_values(self):
        """测试预测器类型值"""
        assert PredictorType.PROPHET == "prophet"
        assert PredictorType.WELFORD == "welford"
        assert PredictorType.STATIC == "static"


class TestPredictorFactory:
    """PredictorFactory 测试"""

    def test_create_prophet(self):
        """测试创建 Prophet 预测器"""
        predictor = PredictorFactory.create(PredictorType.PROPHET)

        assert isinstance(predictor, ProphetPredictor)
        assert isinstance(predictor, BasePredictor)

    def test_create_welford(self):
        """测试创建 Welford 预测器"""
        predictor = PredictorFactory.create(PredictorType.WELFORD)

        assert isinstance(predictor, WelfordPredictor)
        assert isinstance(predictor, BasePredictor)

    def test_create_static(self):
        """测试创建 Static 预测器"""
        predictor = PredictorFactory.create(PredictorType.STATIC)

        assert isinstance(predictor, StaticPredictor)
        assert isinstance(predictor, BasePredictor)

    def test_create_with_params(self):
        """测试带参数创建预测器"""
        predictor = PredictorFactory.create(
            PredictorType.WELFORD,
            sigma_multiplier=2.5,
            use_rolling_window=True
        )

        assert predictor.sigma_multiplier == 2.5
        assert predictor.use_rolling_window is True

    def test_create_unknown_type(self):
        """测试创建未知类型预测器"""
        with pytest.raises(ValueError, match="未知的预测器类型"):
            PredictorFactory.create("unknown_type")

    def test_list_types(self):
        """测试列出所有预测器类型"""
        types = PredictorFactory.list_types()

        assert PredictorType.PROPHET in types
        assert PredictorType.WELFORD in types
        assert PredictorType.STATIC in types
        assert len(types) == 3

    def test_is_registered(self):
        """测试检查预测器是否已注册"""
        assert PredictorFactory.is_registered(PredictorType.PROPHET) is True
        assert PredictorFactory.is_registered(PredictorType.WELFORD) is True
        assert PredictorFactory.is_registered(PredictorType.STATIC) is True
        assert PredictorFactory.is_registered("unknown") is False

    def test_get_predictor_class(self):
        """测试获取预测器类"""
        cls = PredictorFactory.get_predictor_class(PredictorType.PROPHET)

        assert cls == ProphetPredictor

    def test_get_predictor_class_unknown(self):
        """测试获取未知预测器类"""
        cls = PredictorFactory.get_predictor_class("unknown")

        assert cls is None

    def test_register_new_predictor(self):
        """测试注册新预测器"""
        # 创建一个自定义预测器类
        class CustomPredictor(BasePredictor):
            def fit(self, data):
                pass

            def predict(self, periods, freq="1min"):
                pass

        # 注册
        PredictorFactory.register("custom", CustomPredictor)

        # 验证
        assert PredictorFactory.is_registered("custom") is True

        # 创建实例
        predictor = PredictorFactory.create("custom")
        assert isinstance(predictor, CustomPredictor)


class TestCreatePredictorFunction:
    """create_predictor 便捷函数测试"""

    def test_create_predictor_prophet(self):
        """测试便捷函数创建 Prophet"""
        predictor = create_predictor("prophet")

        assert isinstance(predictor, ProphetPredictor)

    def test_create_predictor_welford(self):
        """测试便捷函数创建 Welford"""
        predictor = create_predictor("welford")

        assert isinstance(predictor, WelfordPredictor)

    def test_create_predictor_static(self):
        """测试便捷函数创建 Static"""
        predictor = create_predictor("static")

        assert isinstance(predictor, StaticPredictor)

    def test_create_predictor_with_params(self):
        """测试便捷函数带参数创建"""
        predictor = create_predictor(
            "welford",
            sigma_multiplier=2.0
        )

        assert predictor.sigma_multiplier == 2.0


class TestPredictorFactoryIntegration:
    """预测器工厂集成测试"""

    def test_factory_created_predictor_workflow(self, stationary_data):
        """测试工厂创建的预测器完整工作流"""
        # 使用工厂创建
        predictor = PredictorFactory.create("welford", sigma_multiplier=3.0)

        # 训练
        predictor.fit(stationary_data)
        assert predictor.is_fitted is True

        # 预测
        result = predictor.predict(periods=10)
        assert len(result.yhat) == 10

    def test_multiple_predictors_from_factory(self):
        """测试从工厂创建多个预测器"""
        predictors = [
            PredictorFactory.create("prophet"),
            PredictorFactory.create("welford"),
            PredictorFactory.create("static")
        ]

        types = [type(p) for p in predictors]

        assert ProphetPredictor in types
        assert WelfordPredictor in types
        assert StaticPredictor in types