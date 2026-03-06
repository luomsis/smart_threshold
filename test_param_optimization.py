"""
测试参数优化功能

验证用修改后的参数预测功能是否正常工作
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import sys

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from smart_threshold.config.model_config import (
    ModelConfigManager,
    ModelConfig,
    ModelType,
    TemplateCategory
)
from smart_threshold.core.predictors.prophet_predictor import ProphetPredictor
from smart_threshold.core.predictors.welford_predictor import WelfordPredictor
from smart_threshold.core.predictors.static_predictor import StaticPredictor


def create_test_data():
    """创建测试数据"""
    # 创建24小时的数据，每小时一个数据点
    dates = pd.date_range(
        start=datetime.now() - timedelta(days=7),
        end=datetime.now(),
        freq='h'
    )

    # 创建带有趋势和季节性的数据
    t = np.arange(len(dates))
    trend = 100 + 0.1 * t
    daily = 10 * np.sin(2 * np.pi * t / 24)
    noise = np.random.randn(len(dates)) * 5

    values = trend + daily + noise
    values = np.maximum(values, 0)  # 确保非负

    return pd.Series(values, index=dates)


def test_prophet_modified_params():
    """测试 Prophet 模型修改参数"""
    print("\n" + "="*60)
    print("测试 Prophet 模型 - 修改参数预测")
    print("="*60)

    # 获取默认配置
    manager = ModelConfigManager()
    config = manager.get_config("prophet_standard")

    print(f"\n原始配置: {config.name}")
    print(f"  - changepoint_prior_scale: {config.changepoint_prior_scale}")
    print(f"  - interval_width: {config.interval_width}")
    print(f"  - seasonality_mode: {config.seasonality_mode}")

    # 创建修改后的配置
    modified_params = {
        'changepoint_prior_scale': 0.3,  # 更敏感
        'interval_width': 0.8,  # 更窄的区间
        'seasonality_mode': 'multiplicative',
    }

    print(f"\n修改后参数:")
    for k, v in modified_params.items():
        print(f"  - {k}: {v}")

    # 创建临时配置
    temp_config = ModelConfig(
        id="temp",
        name=config.name,
        description=config.description,
        model_type=ModelType.PROPHET,
        category=TemplateCategory.CUSTOM,
        **modified_params
    )

    # 添加到 manager
    manager._configs["temp"] = temp_config

    # 创建测试数据
    data = create_test_data()

    # 分割训练集和测试集
    train_size = int(len(data) * 0.8)
    train_data = data[:train_size]
    test_data = data[train_size:]

    # 运行预测
    print(f"\n运行预测...")
    print(f"  - 训练样本数: {len(train_data)}")
    print(f"  - 预测样本数: {len(test_data)}")

    predictor = ProphetPredictor(**temp_config.get_params())
    predictor.fit(train_data)
    prediction = predictor.predict(periods=len(test_data))

    # 计算指标
    actual = test_data.values
    predicted = prediction.yhat

    mae = np.abs(actual - predicted).mean()
    mape = (np.abs(actual - predicted) / (actual + 1e-6)).mean() * 100

    print(f"\n预测结果:")
    print(f"  - MAE: {mae:.2f}")
    print(f"  - MAPE: {mape:.2f}%")
    print(f"  - 预测范围: [{prediction.yhat_lower.min():.2f}, {prediction.yhat_upper.max():.2f}]")

    # 清理
    manager._configs.pop("temp", None)

    return True


def test_welford_modified_params():
    """测试 Welford 模型修改参数"""
    print("\n" + "="*60)
    print("测试 Welford 模型 - 修改参数预测")
    print("="*60)

    # 获取默认配置
    manager = ModelConfigManager()
    config = manager.get_config("welford_standard")

    print(f"\n原始配置: {config.name}")
    print(f"  - sigma_multiplier: {config.sigma_multiplier}")
    print(f"  - use_rolling_window: {config.use_rolling_window}")

    # 创建修改后的配置
    modified_params = {
        'sigma_multiplier': 2.0,  # 更敏感的阈值
        'use_rolling_window': True,
        'window_size': 48,  # 48小时滚动窗口
    }

    print(f"\n修改后参数:")
    for k, v in modified_params.items():
        print(f"  - {k}: {v}")

    # 创建临时配置
    temp_config = ModelConfig(
        id="temp",
        name=config.name,
        description=config.description,
        model_type=ModelType.WELFORD,
        category=TemplateCategory.CUSTOM,
        **modified_params
    )

    # 添加到 manager
    manager._configs["temp"] = temp_config

    # 创建测试数据
    data = create_test_data()

    # 分割训练集和测试集
    train_size = int(len(data) * 0.8)
    train_data = data[:train_size]
    test_data = data[train_size:]

    # 运行预测
    print(f"\n运行预测...")
    print(f"  - 训练样本数: {len(train_data)}")
    print(f"  - 预测样本数: {len(test_data)}")

    predictor = WelfordPredictor(**temp_config.get_params())
    predictor.fit(train_data)
    prediction = predictor.predict(periods=len(test_data))

    # 计算指标
    actual = test_data.values
    predicted = prediction.yhat

    mae = np.abs(actual - predicted).mean()
    mape = (np.abs(actual - predicted) / (actual + 1e-6)).mean() * 100

    print(f"\n预测结果:")
    print(f"  - MAE: {mae:.2f}")
    print(f"  - MAPE: {mape:.2f}%")

    # 清理
    manager._configs.pop("temp", None)

    return True


def test_static_modified_params():
    """测试 Static 模型修改参数"""
    print("\n" + "="*60)
    print("测试 Static 模型 - 修改参数预测")
    print("="*60)

    # 获取默认配置
    manager = ModelConfigManager()
    config = manager.get_config("static_percentile")

    print(f"\n原始配置: {config.name}")
    print(f"  - upper_percentile: {config.upper_percentile}")
    print(f"  - lower_bound: {config.lower_bound}")

    # 创建修改后的配置
    modified_params = {
        'upper_percentile': 95.0,  # 更低的百分位
        'lower_bound': 10.0,  # 更高的下限
    }

    print(f"\n修改后参数:")
    for k, v in modified_params.items():
        print(f"  - {k}: {v}")

    # 创建临时配置
    temp_config = ModelConfig(
        id="temp",
        name=config.name,
        description=config.description,
        model_type=ModelType.STATIC,
        category=TemplateCategory.CUSTOM,
        **modified_params
    )

    # 添加到 manager
    manager._configs["temp"] = temp_config

    # 创建测试数据
    data = create_test_data()

    # 分割训练集和测试集
    train_size = int(len(data) * 0.8)
    train_data = data[:train_size]
    test_data = data[train_size:]

    # 运行预测
    print(f"\n运行预测...")
    print(f"  - 训练样本数: {len(train_data)}")
    print(f"  - 预测样本数: {len(test_data)}")

    predictor = StaticPredictor(**temp_config.get_params())
    predictor.fit(train_data)
    prediction = predictor.predict(periods=len(test_data))

    # 计算指标
    actual = test_data.values
    predicted = prediction.yhat

    mae = np.abs(actual - predicted).mean()
    mape = (np.abs(actual - predicted) / (actual + 1e-6)).mean() * 100

    print(f"\n预测结果:")
    print(f"  - MAE: {mae:.2f}")
    print(f"  - MAPE: {mape:.2f}%")
    print(f"  - 上限阈值: {prediction.yhat_upper[0]:.2f}")

    # 清理
    manager._configs.pop("temp", None)

    return True


if __name__ == "__main__":
    print("\n" + "="*60)
    print("参数优化功能测试")
    print("="*60)

    results = []

    try:
        results.append(("Prophet", test_prophet_modified_params()))
    except Exception as e:
        print(f"\n❌ Prophet 测试失败: {e}")
        results.append(("Prophet", False))

    try:
        results.append(("Welford", test_welford_modified_params()))
    except Exception as e:
        print(f"\n❌ Welford 测试失败: {e}")
        results.append(("Welford", False))

    try:
        results.append(("Static", test_static_modified_params()))
    except Exception as e:
        print(f"\n❌ Static 测试失败: {e}")
        results.append(("Static", False))

    # 汇总结果
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)

    for model, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{model:12s}: {status}")

    all_passed = all(r[1] for r in results)
    print("\n" + ("="*60))
    if all_passed:
        print("✅ 所有测试通过！参数优化功能正常工作")
    else:
        print("❌ 部分测试失败，请检查错误信息")
    print("="*60)
