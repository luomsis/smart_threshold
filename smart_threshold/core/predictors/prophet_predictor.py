"""
Prophet 预测器

使用 Facebook Prophet 进行时间序列预测。
适合具有明显季节性的数据（如 QPS）。

容错机制：当 Prophet 失败时，自动降级为简单的滑动平均算法。
"""

import warnings
from typing import Optional
import numpy as np
import pandas as pd

from smart_threshold.core.predictors.base import BasePredictor, PredictionResult
from smart_threshold.core.feature_analyzer import FeatureResult


class ProphetPredictor(BasePredictor):
    """
    基于 Prophet 的时间序列预测器

    特点：
    - 自动检测和处理季节性（日、周、年）
    - 对异常值具有鲁棒性
    - 支持趋势变化点检测

    适用场景：
    - QPS（每秒查询数）
    - 连接数
    - 流量指标
    """

    # Prophet 默认参数
    DEFAULT_PARAMS = {
        "daily_seasonality": True,
        "weekly_seasonality": False,
        "yearly_seasonality": False,
        "seasonality_mode": "additive",
        "interval_width": 0.95,  # 置信区间宽度
        "n_changepoints": 25,  # 趋势变化点数量
        "changepoint_range": 0.8,  # 变化点范围
        "changepoint_prior_scale": 0.05,
        "seasonality_prior_scale": 10.0,
        "holidays_prior_scale": 10.0,
    }

    @staticmethod
    def get_default_config(features: FeatureResult) -> dict:
        """
        根据数据特征生成默认配置

        参数工厂方法：根据特征分析结果动态调整 Prophet 参数

        Args:
            features: 特征分析结果

        Returns:
            配置字典
        """
        config = ProphetPredictor.DEFAULT_PARAMS.copy()

        # 根据平稳性调整 changepoint 参数
        if not features.is_stationary:
            # 数据有趋势，增加 changepoint 灵敏度
            config["changepoint_prior_scale"] = 0.1
            config["n_changepoints"] = 35

        # 根据季节性强度调整季节性先验
        if features.seasonality_strength > 0.7:
            # 强季节性，增加季节性先验权重
            config["seasonality_prior_scale"] = 15.0
        elif features.seasonality_strength < 0.5:
            # 弱季节性，降低季节性先验权重
            config["seasonality_prior_scale"] = 5.0

        # 根据数据波动性调整
        cv = features.std / (features.mean + 1e-6)
        if cv > 0.3:
            # 高波动数据，使用乘性模式
            config["seasonality_mode"] = "multiplicative"

        # 根据数据量调整 changepoint 范围
        # 如果数据量大（>7天），缩小 changepoint 范围避免过拟合
        # 这里假设 features 不包含数据量信息，保持默认

        return config

    def __init__(
        self,
        confidence_level: float = 0.95,
        use_fallback: bool = True,
        **prophet_params,
    ):
        """
        初始化 Prophet 预测器

        Args:
            confidence_level: 置信水平
            use_fallback: 是否在 Prophet 失败时使用降级方案
            **prophet_params: Prophet 的额外参数
        """
        super().__init__(confidence_level=confidence_level)
        self.use_fallback = use_fallback
        self.params = {**self.DEFAULT_PARAMS, **prophet_params}
        self.params["interval_width"] = confidence_level

        self._model: Optional[object] = None
        self._fallback_mean: Optional[float] = None
        self._fallback_std: Optional[float] = None
        self._last_timestamp: Optional[pd.Timestamp] = None

    def fit(self, data: pd.Series) -> None:
        """
        训练 Prophet 模型

        Args:
            data: 训练数据，index 为时间戳
        """
        self._validate_input(data)
        self._training_data = data.copy()
        self._last_timestamp = data.index[-1]

        # 准备 Prophet 格式的数据
        df = pd.DataFrame({"ds": data.index, "y": data.values})

        try:
            # 尝试导入 Prophet
            from prophet import Prophet

            # 创建并训练模型
            self._model = Prophet(**self.params)
            self._model.fit(df)
            self.is_fitted = True

        except Exception as e:
            warnings.warn(f"Prophet 训练失败: {e}，使用降级方案")
            if self.use_fallback:
                self._fit_fallback(data)
            else:
                raise

    def predict(self, periods: int, freq: str = "1min") -> PredictionResult:
        """
        预测未来数据

        Args:
            periods: 预测的时间点数量
            freq: 时间频率

        Returns:
            PredictionResult: 预测结果
        """
        if not self.is_fitted:
            raise ValueError("模型尚未训练，请先调用 fit()")

        if self._model is not None:
            return self._predict_with_prophet(periods, freq)
        else:
            return self._predict_with_fallback(periods, freq)

    def _predict_with_prophet(
        self, periods: int, freq: str
    ) -> PredictionResult:
        """使用 Prophet 进行预测"""
        # 生成未来时间
        future = self._model.make_future_dataframe(periods=periods, freq=freq)

        # 预测
        forecast = self._model.predict(future)

        # 提取预测部分
        pred_data = forecast.tail(periods)

        return PredictionResult(
            ds=pd.DatetimeIndex(pred_data["ds"]),
            yhat=pred_data["yhat"].values,
            yhat_upper=pred_data["yhat_upper"].values,
            yhat_lower=pred_data["yhat_lower"].values,
            algorithm="Prophet",
            confidence_level=self.confidence_level,
        )

    def _fit_fallback(self, data: pd.Series) -> None:
        """训练降级方案（滑动平均）"""
        self._model = None
        self._fallback_mean = float(data.mean())
        self._fallback_std = float(data.std())
        self.is_fitted = True

    def _predict_with_fallback(
        self, periods: int, freq: str
    ) -> PredictionResult:
        """使用降级方案进行预测"""
        # 生成时间索引
        future_index = self._generate_future_index(
            self._last_timestamp, periods, freq
        )

        # 简单预测：使用均值作为预测值
        z_score = 1.96 if self.confidence_level == 0.95 else 2.576

        yhat = np.full(periods, self._fallback_mean)
        yhat_upper = np.full(periods, self._fallback_mean + z_score * self._fallback_std)
        yhat_lower = np.full(periods, max(0, self._fallback_mean - z_score * self._fallback_std))

        return PredictionResult(
            ds=future_index,
            yhat=yhat,
            yhat_upper=yhat_upper,
            yhat_lower=yhat_lower,
            algorithm="MovingAverage (Fallback)",
            confidence_level=self.confidence_level,
        )
