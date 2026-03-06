"""
预测器工厂

使用工厂模式创建预测器实例，降低模型路由与具体预测器类之间的耦合。
"""

from typing import Dict, Type, Optional
from smart_threshold.core.predictors.base import BasePredictor
from smart_threshold.core.predictors.prophet_predictor import ProphetPredictor
from smart_threshold.core.predictors.welford_predictor import WelfordPredictor
from smart_threshold.core.predictors.static_predictor import StaticPredictor


class PredictorType:
    """预测器类型常量"""
    PROPHET = "prophet"
    WELFORD = "welford"
    STATIC = "static"


class PredictorFactory:
    """
    预测器工厂

    负责创建和管理预测器实例，使用注册模式避免直接依赖具体类。
    """

    # 预测器注册表
    _predictors: Dict[str, Type[BasePredictor]] = {
        PredictorType.PROPHET: ProphetPredictor,
        PredictorType.WELFORD: WelfordPredictor,
        PredictorType.STATIC: StaticPredictor,
    }

    @classmethod
    def register(cls, predictor_type: str, predictor_class: Type[BasePredictor]) -> None:
        """
        注册新的预测器类型

        Args:
            predictor_type: 预测器类型标识
            predictor_class: 预测器类
        """
        cls._predictors[predictor_type] = predictor_class

    @classmethod
    def create(cls, predictor_type: str, **kwargs) -> BasePredictor:
        """
        创建预测器实例

        Args:
            predictor_type: 预测器类型
            **kwargs: 传递给预测器构造函数的参数

        Returns:
            预测器实例

        Raises:
            ValueError: 未知的预测器类型
        """
        predictor_class = cls._predictors.get(predictor_type)
        if predictor_class is None:
            raise ValueError(f"未知的预测器类型: {predictor_type}")
        return predictor_class(**kwargs)

    @classmethod
    def list_types(cls) -> list[str]:
        """获取所有已注册的预测器类型"""
        return list(cls._predictors.keys())

    @classmethod
    def is_registered(cls, predictor_type: str) -> bool:
        """检查预测器类型是否已注册"""
        return predictor_type in cls._predicters

    @classmethod
    def get_predictor_class(cls, predictor_type: str) -> Optional[Type[BasePredictor]]:
        """获取预测器类"""
        return cls._predictors.get(predictor_type)


# 便捷函数
def create_predictor(predictor_type: str, **kwargs) -> BasePredictor:
    """创建预测器的便捷函数"""
    return PredictorFactory.create(predictor_type, **kwargs)
