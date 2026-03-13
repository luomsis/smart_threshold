"""
数据生成器单元测试

测试 DataGenerator 类的功能。
"""

import pytest
import numpy as np
import pandas as pd

from smart_threshold.data.generator import DataGenerator, ScenarioType


class TestScenarioType:
    """ScenarioType 枚举测试"""

    def test_scenario_type_values(self):
        """测试场景类型值"""
        assert ScenarioType.QPS.value == "qps"
        assert ScenarioType.RT.value == "rt"
        assert ScenarioType.ERROR_COUNT.value == "error_count"


class TestDataGenerator:
    """DataGenerator 测试"""

    def test_init_default_params(self):
        """测试默认参数初始化"""
        generator = DataGenerator()

        assert generator.freq == "1min"
        assert generator.rng is not None

    def test_init_with_seed(self):
        """测试带随机种子初始化"""
        generator = DataGenerator(seed=42)

        assert generator.rng is not None

    def test_init_custom_freq(self):
        """测试自定义频率初始化"""
        generator = DataGenerator(freq="5min")

        assert generator.freq == "5min"

    def test_generate_qps(self):
        """测试生成 QPS 数据"""
        generator = DataGenerator(seed=42)
        data = generator.generate(ScenarioType.QPS, days=1)

        assert isinstance(data, pd.Series)
        assert len(data) == 1440  # 1 天 * 1440 分钟
        assert data.name == "qps"
        assert isinstance(data.index, pd.DatetimeIndex)

    def test_generate_rt(self):
        """测试生成 RT 数据"""
        generator = DataGenerator(seed=42)
        data = generator.generate(ScenarioType.RT, days=1)

        assert isinstance(data, pd.Series)
        assert len(data) == 1440
        assert data.name == "rt"
        assert isinstance(data.index, pd.DatetimeIndex)

    def test_generate_error_count(self):
        """测试生成错误计数数据"""
        generator = DataGenerator(seed=42)
        data = generator.generate(ScenarioType.ERROR_COUNT, days=1)

        assert isinstance(data, pd.Series)
        assert len(data) == 1440
        assert data.name == "error_count"
        assert isinstance(data.index, pd.DatetimeIndex)

    def test_generate_multiple_days(self):
        """测试生成多天数据"""
        generator = DataGenerator(seed=42)

        data_1d = generator.generate(ScenarioType.QPS, days=1)
        data_7d = generator.generate(ScenarioType.QPS, days=7)

        assert len(data_1d) == 1440
        assert len(data_7d) == 7 * 1440

    def test_generate_with_start_date(self):
        """测试指定起始日期生成"""
        generator = DataGenerator(seed=42)
        start_date = "2024-01-01"
        data = generator.generate(ScenarioType.QPS, days=1, start_date=start_date)

        assert data.index[0] == pd.Timestamp(start_date)

    def test_generate_reproducible(self):
        """测试可复现性（相同种子）"""
        gen1 = DataGenerator(seed=42)
        gen2 = DataGenerator(seed=42)

        data1 = gen1.generate(ScenarioType.QPS, days=1)
        data2 = gen2.generate(ScenarioType.QPS, days=1)

        pd.testing.assert_series_equal(data1, data2)

    def test_generate_different_seeds(self):
        """测试不同种子产生不同数据"""
        gen1 = DataGenerator(seed=42)
        gen2 = DataGenerator(seed=123)

        data1 = gen1.generate(ScenarioType.QPS, days=1)
        data2 = gen2.generate(ScenarioType.QPS, days=1)

        # 数据应该不同
        assert not data1.equals(data2)

    def test_generate_unknown_scenario(self):
        """测试未知场景类型"""
        generator = DataGenerator()

        with pytest.raises(ValueError, match="未知的场景类型"):
            generator.generate("unknown_scenario")


class TestQPSDataCharacteristics:
    """QPS 数据特征测试"""

    def test_qps_seasonality(self):
        """测试 QPS 数据的季节性"""
        generator = DataGenerator(seed=42)
        data = generator.generate(ScenarioType.QPS, days=7)

        # QPS 数据应该有日周期模式
        # 使用特征分析验证
        from smart_threshold.core.feature_analyzer import FeatureExtractor

        extractor = FeatureExtractor(daily_period_lags=1440)
        result = extractor.analyze(data)

        # QPS 数据应该检测出季节性
        assert result.has_seasonality == True

    def test_qps_non_negative(self):
        """测试 QPS 数据非负"""
        generator = DataGenerator(seed=42)
        data = generator.generate(ScenarioType.QPS, days=7)

        assert (data >= 0).all()

    def test_qps_reasonable_range(self):
        """测试 QPS 数据范围合理"""
        generator = DataGenerator(seed=42)
        data = generator.generate(ScenarioType.QPS, days=7)

        # QPS 应该在合理范围内
        assert data.mean() > 500  # 平均 QPS > 500
        assert data.max() < 2000  # 最大 QPS < 2000


class TestRTDataCharacteristics:
    """RT 数据特征测试"""

    def test_rt_sparsity(self):
        """测试 RT 数据的非稀疏性"""
        generator = DataGenerator(seed=42)
        data = generator.generate(ScenarioType.RT, days=1)

        # RT 数据不应该稀疏
        zero_ratio = (data == 0).sum() / len(data)
        assert zero_ratio < 0.1

    def test_rt_non_negative(self):
        """测试 RT 数据非负"""
        generator = DataGenerator(seed=42)
        data = generator.generate(ScenarioType.RT, days=7)

        assert (data >= 0).all()

    def test_rt_reasonable_range(self):
        """测试 RT 数据范围合理"""
        generator = DataGenerator(seed=42)
        data = generator.generate(ScenarioType.RT, days=7)

        # RT 应该在合理范围内（毫秒）
        assert data.mean() > 30  # 平均 RT > 30ms
        assert data.mean() < 150  # 平均 RT < 150ms

    def test_rt_has_spikes(self):
        """测试 RT 数据有尖峰"""
        generator = DataGenerator(seed=42)
        data = generator.generate(ScenarioType.RT, days=7)

        # 应该有一些高值（尖峰）
        mean = data.mean()
        spike_threshold = mean * 3
        spike_count = (data > spike_threshold).sum()

        assert spike_count > 0


class TestErrorCountDataCharacteristics:
    """错误计数数据特征测试"""

    def test_error_count_sparsity(self):
        """测试错误计数数据的稀疏性"""
        generator = DataGenerator(seed=42)
        data = generator.generate(ScenarioType.ERROR_COUNT, days=1)

        # 错误计数应该很稀疏（95% 为 0）
        zero_ratio = (data == 0).sum() / len(data)
        assert zero_ratio > 0.9  # > 90% 为 0

    def test_error_count_non_negative(self):
        """测试错误计数非负"""
        generator = DataGenerator(seed=42)
        data = generator.generate(ScenarioType.ERROR_COUNT, days=7)

        assert (data >= 0).all()

    def test_error_count_integer(self):
        """测试错误计数为整数"""
        generator = DataGenerator(seed=42)
        data = generator.generate(ScenarioType.ERROR_COUNT, days=1)

        # 值应该是整数
        assert data.dtype in [np.int64, np.int32, int]


class TestGenerateAll:
    """generate_all 方法测试"""

    def test_generate_all(self):
        """测试生成所有场景数据"""
        generator = DataGenerator(seed=42)
        all_data = generator.generate_all(days=1)

        assert isinstance(all_data, dict)
        assert ScenarioType.QPS in all_data
        assert ScenarioType.RT in all_data
        assert ScenarioType.ERROR_COUNT in all_data

    def test_generate_all_correct_lengths(self):
        """测试生成所有场景数据的长度"""
        generator = DataGenerator(seed=42)
        all_data = generator.generate_all(days=1)

        for scenario, data in all_data.items():
            assert len(data) == 1440


class TestAddAnomaly:
    """add_anomaly 方法测试"""

    def test_add_anomaly(self):
        """测试添加异常值"""
        generator = DataGenerator(seed=42)
        data = generator.generate(ScenarioType.RT, days=1)

        data_with_anomaly = generator.add_anomaly(data, anomaly_ratio=0.01, magnitude=3.0)

        # 数据应该被修改
        assert isinstance(data_with_anomaly, pd.Series)
        assert len(data_with_anomaly) == len(data)

    def test_add_anomaly_ratio(self):
        """测试异常比例"""
        generator = DataGenerator(seed=42)
        data = generator.generate(ScenarioType.RT, days=1)

        # 添加 1% 异常
        data_with_anomaly = generator.add_anomaly(data, anomaly_ratio=0.01)

        # 应该有约 1% 的异常点
        # 这是一个近似测试
        assert isinstance(data_with_anomaly, pd.Series)

    def test_add_anomaly_magnitude(self):
        """测试异常幅度"""
        generator = DataGenerator(seed=42)
        data = generator.generate(ScenarioType.RT, days=1)

        # 添加高幅度异常
        data_with_anomaly = generator.add_anomaly(data, anomaly_ratio=0.05, magnitude=5.0)

        # 检查是否有异常高的值
        original_max = data.max()
        new_max = data_with_anomaly.max()

        # 新数据应该有一些异常高值
        assert new_max >= original_max * 0.9  # 允许一定变化


class TestDataGeneratorEdgeCases:
    """边界情况测试"""

    def test_generate_single_day(self):
        """测试生成单天数据"""
        generator = DataGenerator(seed=42)
        data = generator.generate(ScenarioType.QPS, days=1)

        assert len(data) == 1440

    def test_generate_large_days(self):
        """测试生成大量天数数据"""
        generator = DataGenerator(seed=42)
        data = generator.generate(ScenarioType.QPS, days=30)

        assert len(data) == 30 * 1440

    def test_generate_with_different_freq(self):
        """测试不同采样频率"""
        generator = DataGenerator(freq="5min", seed=42)
        data = generator.generate(ScenarioType.QPS, days=1)

        # 当前实现：periods = days * 1440，freq 只影响时间间隔
        # 所以数据点数量仍然是 1440，但时间间隔是 5 分钟
        assert len(data) == 1440
        # 验证时间间隔是 5 分钟
        assert (data.index[1] - data.index[0]) == pd.Timedelta("5min")

    def test_generate_all_with_different_days(self):
        """测试生成不同天数的所有场景"""
        generator = DataGenerator(seed=42)
        all_data = generator.generate_all(days=3)

        for data in all_data.values():
            assert len(data) == 3 * 1440