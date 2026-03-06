"""
预测器模块

包含多种动态阈值预测算法：
- BasePredictor: 预测器基类
- ProphetPredictor: 基于 Prophet 的时间序列预测（适合周期性数据）
- WelfordPredictor: 基于 Welford 在线算法的动态阈值（适合高波动数据）
- StaticPredictor: 基于百分位数的静态阈值（适合稀疏数据）
"""

from smart_threshold.core.predictors.base import BasePredictor, PredictionResult
from smart_threshold.core.predictors.prophet_predictor import ProphetPredictor
from smart_threshold.core.predictors.welford_predictor import WelfordPredictor
from smart_threshold.core.predictors.static_predictor import StaticPredictor

__all__ = [
    "BasePredictor",
    "PredictionResult",
    "ProphetPredictor",
    "WelfordPredictor",
    "StaticPredictor",
]
