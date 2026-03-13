"""
特征分析模块单元测试

测试 FeatureExtractor 类的各项功能。
"""

import pytest
import numpy as np
import pandas as pd
from smart_threshold.core.feature_analyzer import FeatureExtractor, FeatureResult


class TestFeatureExtractor:
    """FeatureExtractor 类测试"""

    def test_analyze_seasonal_data(self, seasonal_data):
        """测试季节性数据检测"""
        extractor = FeatureExtractor(daily_period_lags=1440)
        result = extractor.analyze(seasonal_data)

        assert isinstance(result, FeatureResult)
        assert result.has_seasonality == True
        assert result.seasonality_strength > 0.3
        assert result.sparsity_ratio < 0.1  # 季节性数据不稀疏

    def test_analyze_sparse_data(self, sparse_data):
        """测试稀疏数据检测"""
        extractor = FeatureExtractor(daily_period_lags=1440)
        result = extractor.analyze(sparse_data)

        assert isinstance(result, FeatureResult)
        assert result.sparsity_ratio > 0.8  # 95% 的数据为 0
        assert result.has_seasonality == False

    def test_analyze_stationary_data(self, stationary_data):
        """测试平稳数据检测"""
        extractor = FeatureExtractor(daily_period_lags=1440)
        result = extractor.analyze(stationary_data)

        assert isinstance(result, FeatureResult)
        # 平稳数据通常 ADF p-value < 0.05
        assert result.is_stationary == True
        assert result.adf_pvalue < 0.05

    def test_analyze_non_stationary_data(self, non_stationary_data):
        """测试非平稳数据检测"""
        extractor = FeatureExtractor(daily_period_lags=1440)
        result = extractor.analyze(non_stationary_data)

        assert isinstance(result, FeatureResult)
        # 有趋势的数据通常不平稳
        assert result.is_stationary == False

    def test_insufficient_data(self, small_data):
        """测试数据量不足时的错误处理"""
        extractor = FeatureExtractor()

        with pytest.raises(ValueError, match="数据量不足"):
            extractor.analyze(small_data)

    def test_minimal_data(self, minimal_data):
        """测试最小数据量（刚好 100 点）"""
        extractor = FeatureExtractor(daily_period_lags=50)  # 缩小周期以适应小数据
        result = extractor.analyze(minimal_data)

        assert isinstance(result, FeatureResult)

    def test_empty_data(self, empty_data):
        """测试空数据处理"""
        extractor = FeatureExtractor()

        with pytest.raises(ValueError):
            extractor.analyze(empty_data)

    def test_numpy_array_input(self, seasonal_data):
        """测试 numpy array 输入"""
        extractor = FeatureExtractor(daily_period_lags=1440)
        values = seasonal_data.values

        result = extractor.analyze(values)

        assert isinstance(result, FeatureResult)

    def test_with_nan_values(self, seasonal_data):
        """测试包含 NaN 值的数据"""
        data_with_nan = seasonal_data.copy()
        data_with_nan.iloc[100:110] = np.nan

        extractor = FeatureExtractor(daily_period_lags=1440)
        result = extractor.analyze(data_with_nan)

        # 应该能够处理 NaN 并返回有效结果
        assert isinstance(result, FeatureResult)

    def test_custom_thresholds(self, seasonal_data):
        """测试自定义阈值"""
        extractor = FeatureExtractor(
            daily_period_lags=1440,
            min_value_threshold=1.0,  # 自定义最小值阈值
            acf_nlags=1000
        )
        result = extractor.analyze(seasonal_data)

        assert isinstance(result, FeatureResult)

    def test_feature_result_repr(self, seasonal_data):
        """测试 FeatureResult 的 __repr__ 方法"""
        extractor = FeatureExtractor(daily_period_lags=1440)
        result = extractor.analyze(seasonal_data)

        repr_str = repr(result)
        assert "FeatureResult" in repr_str
        assert "seasonality" in repr_str
        assert "sparsity" in repr_str

    def test_mean_and_std(self, stationary_data):
        """测试均值和标准差计算"""
        extractor = FeatureExtractor(daily_period_lags=1440)
        result = extractor.analyze(stationary_data)

        # 均值应该接近 50
        assert 40 < result.mean < 60
        # 标准差应该接近 10
        assert 5 < result.std < 15

    def test_calculate_sparsity_with_threshold(self):
        """测试稀疏度计算的自定义阈值"""
        # 创建数据：90% 为 0，10% 为非零
        data = pd.Series([0] * 90 + [10] * 10)
        data.index = pd.date_range(start="2024-01-01", periods=100, freq="1min")

        extractor = FeatureExtractor(min_value_threshold=0.1)
        result = extractor.analyze(data)

        assert result.sparsity_ratio > 0.8

    def test_simple_seasonality_check(self):
        """测试简单季节性检测（备用方法）"""
        # 创建明显的周期数据
        n = 3000
        period = 1440
        t = np.arange(n)
        values = 100 + 50 * np.sin(2 * np.pi * t / period)

        dates = pd.date_range(start="2024-01-01", periods=n, freq="1min")
        data = pd.Series(values, index=dates)

        extractor = FeatureExtractor(daily_period_lags=period)
        result = extractor.analyze(data)

        assert result.has_seasonality == True


class TestFeatureResult:
    """FeatureResult 类测试"""

    def test_feature_result_attributes(self):
        """测试 FeatureResult 属性"""
        result = FeatureResult(
            has_seasonality=True,
            seasonality_strength=0.5,
            sparsity_ratio=0.1,
            is_stationary=True,
            adf_pvalue=0.01,
            mean=100.0,
            std=10.0
        )

        assert result.has_seasonality == True
        assert result.seasonality_strength == 0.5
        assert result.sparsity_ratio == 0.1
        assert result.is_stationary == True
        assert result.adf_pvalue == 0.01
        assert result.mean == 100.0
        assert result.std == 10.0


class TestFeatureExtractorEdgeCases:
    """边界情况测试"""

    def test_constant_data(self):
        """测试常量数据"""
        dates = pd.date_range(start="2024-01-01", periods=1000, freq="1min")
        values = np.full(1000, 100.0)  # 全部相同的值
        data = pd.Series(values, index=dates)

        extractor = FeatureExtractor(daily_period_lags=1440)
        result = extractor.analyze(data)

        # 常量数据的稀疏度可能较高（取决于阈值）
        assert result.std == 0.0

    def test_all_zeros(self):
        """测试全零数据"""
        dates = pd.date_range(start="2024-01-01", periods=1000, freq="1min")
        values = np.zeros(1000)
        data = pd.Series(values, index=dates)

        extractor = FeatureExtractor(daily_period_lags=1440)
        result = extractor.analyze(data)

        assert result.sparsity_ratio == 1.0
        assert result.mean == 0.0

    def test_large_data(self):
        """测试大数据量"""
        n = 100000
        dates = pd.date_range(start="2024-01-01", periods=n, freq="1min")
        values = np.random.randn(n)
        data = pd.Series(values, index=dates)

        extractor = FeatureExtractor(daily_period_lags=1440)
        result = extractor.analyze(data)

        assert isinstance(result, FeatureResult)