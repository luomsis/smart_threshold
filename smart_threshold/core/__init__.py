"""
Core module

包含核心算法和功能：
- FeatureAnalyzer: 特征分析器
- ModelRouter: 模型路由器，自动选择预测算法
- ParamOptimizer: 参数优化器
"""

from smart_threshold.core.feature_analyzer import FeatureExtractor, FeatureResult
from smart_threshold.core.model_router import ModelRouter, AlgorithmType
from smart_threshold.core.param_optimizer import ParamOptimizer, OptimizationResult
from smart_threshold.core.backtest_optimizer import BacktestOptimizer  # 向后兼容

__all__ = [
    "FeatureExtractor",
    "FeatureResult",
    "ModelRouter",
    "AlgorithmType",
    "ParamOptimizer",
    "OptimizationResult",
    "BacktestOptimizer",  # 向后兼容
]
