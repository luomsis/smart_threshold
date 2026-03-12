"""
SmartThreshold - DB 监控算法自动选型系统

智能阈值系统，能够根据时序数据的特征自动选择最合适的动态阈值算法。
"""

__version__ = "0.1.0"
__author__ = "SmartThreshold Team"

# 核心功能
from smart_threshold.core.feature_analyzer import FeatureExtractor, FeatureResult
from smart_threshold.core.model_router import ModelRouter, AlgorithmType
from smart_threshold.core.param_optimizer import ParamOptimizer, OptimizationResult

# 数据生成
from smart_threshold.data.generator import DataGenerator, ScenarioType

# 配置管理
from smart_threshold.config import ConfigManager

# 向后兼容别名
from smart_threshold.core.param_optimizer import ParamOptimizer as BacktestOptimizer

__all__ = [
    # 核心功能
    "FeatureExtractor",
    "FeatureResult",
    "ModelRouter",
    "AlgorithmType",
    "ParamOptimizer",
    "OptimizationResult",
    # 数据生成
    "DataGenerator",
    "ScenarioType",
    # 配置管理
    "ConfigManager",
    # 向后兼容
    "BacktestOptimizer",
]
