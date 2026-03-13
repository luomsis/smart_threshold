"""
预测器模块单元测试

测试 ProphetPredictor, WelfordPredictor, StaticPredictor 类。
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from smart_threshold.core.predictors.base import BasePredictor, PredictionResult
from smart_threshold.core.predictors.prophet_predictor import ProphetPredictor
from smart_threshold.core.predictors.welford_predictor import WelfordPredictor
from smart_threshold.core.predictors.static_predictor import StaticPredictor
from smart_threshold.core.feature_analyzer import FeatureResult


class TestBasePredictor:
    """BasePredictor 基类测试"""

    def test_validate_input_empty(self):
        """测试空数据验证"""
        predictor = ProphetPredictor()
        empty_data = pd.Series([], dtype=float)

        with pytest.raises(ValueError, match="输入数据不能为空"):
            predictor._validate_input(empty_data)

    def test_validate_input_no_datetime_index(self):
        """测试非时间索引验证"""
        predictor = ProphetPredictor()
        data = pd.Series([1, 2, 3])  # 没有 DatetimeIndex

        with pytest.raises(ValueError, match="DatetimeIndex"):
            predictor._validate_input(data)

    def test_generate_future_index(self):
        """测试生成未来时间索引"""
        predictor = ProphetPredictor()
        last_ts = pd.Timestamp("2024-01-01 12:00:00")

        future_index = predictor._generate_future_index(last_ts, periods=10, freq="1min")

        assert len(future_index) == 10
        assert future_index[0] == pd.Timestamp("2024-01-01 12:01:00")


class TestWelfordPredictor:
    """WelfordPredictor 测试"""

    @pytest.fixture
    def welford_predictor(self):
        """创建 Welford 预测器实例"""
        return WelfordPredictor(sigma_multiplier=3.0)

    def test_init_default_params(self):
        """测试默认参数初始化"""
        predictor = WelfordPredictor()

        assert predictor.sigma_multiplier == 3.0
        assert predictor.use_rolling_window == False
        assert predictor.window_size == 1440

    def test_init_custom_params(self):
        """测试自定义参数初始化"""
        predictor = WelfordPredictor(
            sigma_multiplier=2.5,
            use_rolling_window=True,
            window_size=720
        )

        assert predictor.sigma_multiplier == 2.5
        assert predictor.use_rolling_window == True
        assert predictor.window_size == 720

    def test_fit(self, welford_predictor, stationary_data):
        """测试训练方法"""
        welford_predictor.fit(stationary_data)

        assert welford_predictor.is_fitted == True
        assert welford_predictor._mean is not None
        assert welford_predictor._std is not None

    def test_fit_rolling_window(self, stationary_data):
        """测试滚动窗口训练"""
        predictor = WelfordPredictor(use_rolling_window=True, window_size=100)
        predictor.fit(stationary_data)

        assert predictor.is_fitted == True

    def test_predict_without_fit(self, welford_predictor):
        """测试未训练时预测"""
        with pytest.raises(ValueError, match="模型尚未训练"):
            welford_predictor.predict(periods=10)

    def test_predict(self, welford_predictor, stationary_data):
        """测试预测方法"""
        welford_predictor.fit(stationary_data)
        result = welford_predictor.predict(periods=60)

        assert isinstance(result, PredictionResult)
        assert len(result.yhat) == 60
        assert "Welford" in result.algorithm
        assert "Sigma" in result.algorithm

    def test_predict_thresholds(self, welford_predictor, stationary_data):
        """测试预测阈值计算"""
        welford_predictor.fit(stationary_data)
        result = welford_predictor.predict(periods=10)

        # 检查阈值关系
        assert np.all(result.yhat_upper >= result.yhat)
        assert np.all(result.yhat_lower <= result.yhat)
        assert np.all(result.yhat_lower >= 0)  # 下限不能为负

    def test_get_anomalies(self, welford_predictor, stationary_data):
        """测试异常检测"""
        welford_predictor.fit(stationary_data)

        # 注入异常值
        test_data = stationary_data.copy()
        test_data.iloc[0] = welford_predictor._mean + 5 * welford_predictor._std

        anomalies = welford_predictor.get_anomalies(test_data)

        assert anomalies.iloc[0] == True

    def test_get_anomalies_without_fit(self, welford_predictor):
        """测试未训练时异常检测"""
        data = pd.Series([1, 2, 3])
        data.index = pd.date_range(start="2024-01-01", periods=3, freq="1min")

        with pytest.raises(ValueError, match="模型尚未训练"):
            welford_predictor.get_anomalies(data)

    def test_sigma_to_confidence(self):
        """测试 sigma 到置信水平转换"""
        assert WelfordPredictor._sigma_to_confidence(1.0) == pytest.approx(0.68, rel=0.01)
        assert WelfordPredictor._sigma_to_confidence(2.0) == pytest.approx(0.9545, rel=0.01)
        assert WelfordPredictor._sigma_to_confidence(3.0) == pytest.approx(0.997, rel=0.01)

    def test_confidence_to_sigma(self):
        """测试置信水平到 sigma 转换"""
        assert WelfordPredictor._confidence_to_sigma(0.68) == pytest.approx(1.0, rel=0.01)
        assert WelfordPredictor._confidence_to_sigma(0.95) == pytest.approx(1.96, rel=0.05)

    def test_get_default_config_high_cv(self):
        """测试高变异系数的默认配置"""
        features = FeatureResult(
            has_seasonality=False,
            seasonality_strength=0.1,
            sparsity_ratio=0.1,
            is_stationary=True,
            adf_pvalue=0.01,
            mean=10.0,
            std=10.0  # CV = 1.0, 高波动
        )

        config = WelfordPredictor.get_default_config(features)

        assert config["sigma_multiplier"] == 3.5  # 高波动需要更宽松阈值

    def test_get_default_config_low_cv(self):
        """测试低变异系数的默认配置"""
        features = FeatureResult(
            has_seasonality=False,
            seasonality_strength=0.1,
            sparsity_ratio=0.1,
            is_stationary=True,
            adf_pvalue=0.01,
            mean=100.0,
            std=10.0  # CV = 0.1, 低波动
        )

        config = WelfordPredictor.get_default_config(features)

        assert config["sigma_multiplier"] == 2.5  # 低波动可以更紧凑

    def test_get_default_config_non_stationary(self):
        """测试非平稳数据的默认配置"""
        features = FeatureResult(
            has_seasonality=False,
            seasonality_strength=0.1,
            sparsity_ratio=0.1,
            is_stationary=False,  # 非平稳
            adf_pvalue=0.5,
            mean=100.0,
            std=20.0
        )

        config = WelfordPredictor.get_default_config(features)

        assert config["use_rolling_window"] == True


class TestStaticPredictor:
    """StaticPredictor 测试"""

    @pytest.fixture
    def static_predictor(self):
        """创建 Static 预测器实例"""
        return StaticPredictor(upper_percentile=99.0)

    def test_init_default_params(self):
        """测试默认参数初始化"""
        predictor = StaticPredictor()

        assert predictor.upper_percentile == 99.0
        assert predictor.lower_bound == 0.0

    def test_init_custom_params(self):
        """测试自定义参数初始化"""
        predictor = StaticPredictor(
            upper_percentile=95.0,
            lower_bound=10.0
        )

        assert predictor.upper_percentile == 95.0
        assert predictor.lower_bound == 10.0

    def test_fit(self, static_predictor, sparse_data):
        """测试训练方法"""
        static_predictor.fit(sparse_data)

        assert static_predictor.is_fitted == True
        assert static_predictor._median is not None
        assert static_predictor._upper_threshold is not None

    def test_predict_without_fit(self, static_predictor):
        """测试未训练时预测"""
        with pytest.raises(ValueError, match="模型尚未训练"):
            static_predictor.predict(periods=10)

    def test_predict(self, static_predictor, sparse_data):
        """测试预测方法"""
        static_predictor.fit(sparse_data)
        result = static_predictor.predict(periods=60)

        assert isinstance(result, PredictionResult)
        assert len(result.yhat) == 60
        assert "Static" in result.algorithm

    def test_predict_constant_values(self, static_predictor, sparse_data):
        """测试静态预测返回常量值"""
        static_predictor.fit(sparse_data)
        result = static_predictor.predict(periods=10)

        # 所有预测值应该相同
        assert np.all(result.yhat == result.yhat[0])
        assert np.all(result.yhat_upper == result.yhat_upper[0])

    def test_get_threshold(self, static_predictor, sparse_data):
        """测试获取阈值"""
        static_predictor.fit(sparse_data)
        threshold = static_predictor.get_threshold()

        assert "median" in threshold
        assert "upper_threshold" in threshold
        assert "lower_bound" in threshold
        assert "max_value" in threshold
        assert "upper_percentile" in threshold

    def test_get_anomalies(self, static_predictor, sparse_data):
        """测试异常检测"""
        static_predictor.fit(sparse_data)

        # 创建测试数据
        test_data = sparse_data.copy()
        test_data.iloc[0] = static_predictor._upper_threshold + 100

        anomalies = static_predictor.get_anomalies(test_data)

        assert anomalies.iloc[0] == True

    def test_get_default_config_high_sparsity(self):
        """测试高稀疏度的默认配置"""
        features = FeatureResult(
            has_seasonality=False,
            seasonality_strength=0.1,
            sparsity_ratio=0.98,  # 极高稀疏度
            is_stationary=True,
            adf_pvalue=0.01,
            mean=1.0,
            std=5.0
        )

        config = StaticPredictor.get_default_config(features)

        # 极高稀疏度应该使用更高的百分位数
        assert config["upper_percentile"] >= 99.5

    def test_get_default_config_medium_sparsity(self):
        """测试中等稀疏度的默认配置"""
        features = FeatureResult(
            has_seasonality=False,
            seasonality_strength=0.1,
            sparsity_ratio=0.92,  # 中等稀疏度
            is_stationary=True,
            adf_pvalue=0.01,
            mean=5.0,
            std=10.0
        )

        config = StaticPredictor.get_default_config(features)

        assert config["upper_percentile"] == 99.0


class TestProphetPredictor:
    """ProphetPredictor 测试"""

    @pytest.fixture
    def prophet_predictor(self):
        """创建 Prophet 预测器实例"""
        return ProphetPredictor(use_fallback=True)

    def test_init_default_params(self):
        """测试默认参数初始化"""
        predictor = ProphetPredictor()

        assert predictor.use_fallback == True
        assert predictor.params["daily_seasonality"] == True

    def test_fit(self, prophet_predictor, seasonal_data):
        """测试训练方法"""
        prophet_predictor.fit(seasonal_data)

        assert prophet_predictor.is_fitted == True

    def test_predict_without_fit(self, prophet_predictor):
        """测试未训练时预测"""
        with pytest.raises(ValueError, match="模型尚未训练"):
            prophet_predictor.predict(periods=10)

    def test_predict(self, prophet_predictor, seasonal_data):
        """测试预测方法"""
        prophet_predictor.fit(seasonal_data)
        result = prophet_predictor.predict(periods=60)

        assert isinstance(result, PredictionResult)
        assert len(result.yhat) == 60

    def test_fallback_mode(self, stationary_data):
        """测试降级模式"""
        # 创建会触发降级的情况
        predictor = ProphetPredictor(use_fallback=True)

        # 即使 Prophet 失败，也应该能降级到简单方法
        predictor.fit(stationary_data)
        result = predictor.predict(periods=10)

        assert isinstance(result, PredictionResult)

    def test_get_default_config_non_stationary(self):
        """测试非平稳数据的默认配置"""
        features = FeatureResult(
            has_seasonality=True,
            seasonality_strength=0.5,
            sparsity_ratio=0.1,
            is_stationary=False,  # 非平稳
            adf_pvalue=0.5,
            mean=100.0,
            std=20.0
        )

        config = ProphetPredictor.get_default_config(features)

        assert config["changepoint_prior_scale"] == 0.1
        assert config["n_changepoints"] == 35

    def test_get_default_config_strong_seasonality(self):
        """测试强季节性的默认配置"""
        features = FeatureResult(
            has_seasonality=True,
            seasonality_strength=0.8,  # 强季节性
            sparsity_ratio=0.1,
            is_stationary=True,
            adf_pvalue=0.01,
            mean=100.0,
            std=20.0
        )

        config = ProphetPredictor.get_default_config(features)

        assert config["seasonality_prior_scale"] == 15.0


class TestPredictionResult:
    """PredictionResult 测试"""

    def test_to_dataframe(self):
        """测试转换为 DataFrame"""
        dates = pd.date_range(start="2024-01-01", periods=10, freq="1min")
        result = PredictionResult(
            ds=dates,
            yhat=np.ones(10),
            yhat_upper=np.ones(10) * 2,
            yhat_lower=np.ones(10) * 0.5,
            algorithm="Test",
            confidence_level=0.95
        )

        df = result.to_dataframe()

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 10
        assert "ds" in df.columns
        assert "yhat" in df.columns

    def test_repr(self):
        """测试 __repr__ 方法"""
        dates = pd.date_range(start="2024-01-01", periods=10, freq="1min")
        result = PredictionResult(
            ds=dates,
            yhat=np.ones(10),
            yhat_upper=np.ones(10) * 2,
            yhat_lower=np.ones(10) * 0.5,
            algorithm="Welford",
            confidence_level=0.95
        )

        repr_str = repr(result)

        assert "PredictionResult" in repr_str
        assert "Welford" in repr_str
        assert "points=10" in repr_str


class TestPredictorComparison:
    """预测器对比测试"""

    def test_all_predictors_same_data(self, seasonal_data):
        """测试所有预测器处理相同数据"""
        # Prophet
        prophet = ProphetPredictor(use_fallback=True)
        prophet.fit(seasonal_data)
        prophet_result = prophet.predict(periods=10)

        # Welford
        welford = WelfordPredictor()
        welford.fit(seasonal_data)
        welford_result = welford.predict(periods=10)

        # Static
        static = StaticPredictor()
        static.fit(seasonal_data)
        static_result = static.predict(periods=10)

        # 所有预测器应该返回相同数量的预测点
        assert len(prophet_result.yhat) == 10
        assert len(welford_result.yhat) == 10
        assert len(static_result.yhat) == 10

    def test_predictor_algorithm_names(self, seasonal_data):
        """测试预测器算法名称"""
        welford = WelfordPredictor(sigma_multiplier=3.0)
        welford.fit(seasonal_data)
        result = welford.predict(periods=10)

        assert "Welford" in result.algorithm
        assert "3" in result.algorithm

    def test_predictor_confidence_levels(self, seasonal_data):
        """测试预测器置信水平"""
        welford = WelfordPredictor(sigma_multiplier=3.0)
        welford.fit(seasonal_data)
        result = welford.predict(periods=10)

        assert result.confidence_level > 0.9  # 3-sigma 约 99.7%