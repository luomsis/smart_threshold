"""
预测器基类

定义所有预测器的通用接口和数据结构。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import pandas as pd
import numpy as np


@dataclass
class PredictionResult:
    """
    预测结果

    Attributes:
        ds: 时间戳索引
        yhat: 预测值（中线）
        yhat_upper: 预测上限
        yhat_lower: 预测下限
        algorithm: 使用的算法名称
        confidence_level: 置信水平 (默认 0.95)
    """

    ds: pd.DatetimeIndex
    yhat: np.ndarray
    yhat_upper: np.ndarray
    yhat_lower: np.ndarray
    algorithm: str
    confidence_level: float = 0.95

    def to_dataframe(self) -> pd.DataFrame:
        """转换为 DataFrame 格式"""
        return pd.DataFrame(
            {
                "ds": self.ds,
                "yhat": self.yhat,
                "yhat_upper": self.yhat_upper,
                "yhat_lower": self.yhat_lower,
            }
        )

    def __repr__(self) -> str:
        return (
            f"PredictionResult(algorithm={self.algorithm}, "
            f"points={len(self.yhat)}, "
            f"confidence={self.confidence_level})"
        )


class BasePredictor(ABC):
    """
    预测器基类

    所有预测器都需要实现 fit 和 predict 方法。
    """

    def __init__(self, confidence_level: float = 0.95):
        """
        初始化预测器

        Args:
            confidence_level: 置信水平，默认 0.95（对应 2-sigma）
        """
        self.confidence_level = confidence_level
        self.is_fitted = False
        self._training_data: Optional[pd.Series] = None

    @abstractmethod
    def fit(self, data: pd.Series) -> None:
        """
        训练预测器

        Args:
            data: 训练数据，index 为时间戳
        """
        pass

    @abstractmethod
    def predict(self, periods: int, freq: str = "1min") -> PredictionResult:
        """
        预测未来数据

        Args:
            periods: 预测的时间点数量
            freq: 时间频率（如 "1min", "5min", "1H"）

        Returns:
            PredictionResult: 预测结果
        """
        pass

    def _validate_input(self, data: pd.Series) -> None:
        """验证输入数据"""
        if len(data) == 0:
            raise ValueError("输入数据不能为空")
        if not isinstance(data.index, pd.DatetimeIndex):
            raise ValueError("数据的 index 必须是 DatetimeIndex")

    def _generate_future_index(
        self, last_timestamp: pd.Timestamp, periods: int, freq: str = "1min"
    ) -> pd.DatetimeIndex:
        """生成未来的时间索引"""
        return pd.date_range(
            start=last_timestamp + pd.Timedelta(freq), periods=periods, freq=freq
        )
