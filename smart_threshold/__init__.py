"""
SmartThreshold - DB 监控算法自动选型系统

智能阈值系统，能够根据时序数据的特征自动选择最合适的动态阈值算法。
"""

__version__ = "0.1.0"
__author__ = "SmartThreshold Team"

from smart_threshold.core.feature_analyzer import FeatureExtractor, FeatureResult
from smart_threshold.core.model_router import ModelRouter, AlgorithmType
from smart_threshold.data.generator import DataGenerator, ScenarioType
from smart_threshold.config import ConfigManager
from smart_threshold.core.backtest_optimizer import BacktestOptimizer

__all__ = [
    "FeatureExtractor",
    "FeatureResult",
    "ModelRouter",
    "AlgorithmType",
    "DataGenerator",
    "ScenarioType",
    "ConfigManager",
    "BacktestOptimizer",
]
