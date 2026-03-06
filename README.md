# SmartThreshold - DB 监控算法自动选型系统

智能阈值系统，能够根据时序数据的特征自动选择最合适的动态阈值算法。

## 背景

传统 DB 监控使用固定阈值进行告警，存在以下问题：

- **QPS（查询量）**：有明显的日/周周期，固定阈值会产生大量误报
- **RT（响应时间）**：高波动且偶发尖峰，固定阈值难以捕捉
- **错误数**：大部分为 0，传统预测算法效果不佳

SmartThreshold 通过**特征分析**自动选择最合适的算法，实现精准的动态阈值告警。

## 系统架构

```
输入时序数据 → 特征分析 → 算法路由 → 预测/阈值 → 可视化输出
```

### 三层架构

```
┌─────────────────────────────────────────────────────────────┐
│                      特征分析层                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  季节性检测  │  │  稀疏性检测  │  │    平稳性检测       │ │
│  │   (ACF)     │  │ (零值占比)  │  │    (ADF 检验)       │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                      算法路由层                              │
│                                                             │
│   有季节性 → Prophet                                        │
│   无季节性 + 低稀疏 → Welford 3-Sigma                       │
│   高稀疏 → Static 百分位数                                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                      预测器层                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   Prophet   │  │   Welford   │  │       Static        │ │
│  │  (周期数据)  │  │  (高波动)   │  │     (稀疏数据)       │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 安装

```bash
# 使用 uv (推荐)
uv sync

# 或使用 pip
pip install -e .
```

## 快速开始

```bash
# 运行完整演示
python examples/demo.py
```

演示脚本会生成三种 DB 场景的数据并自动选择算法：

| 场景 | 特征 | 自动选择算法 |
|------|------|-------------|
| QPS | 强季节性 + 线性增长 | Prophet |
| RT | 高波动 + 偶发尖峰 | Welford 3-Sigma |
| 错误数 | 高稀疏性 (95% 为 0) | Static 百分位数 |

## 代码示例

```python
from smart_threshold import ModelRouter, DataGenerator, ScenarioType
import pandas as pd

# 1. 生成 Mock 数据
generator = DataGenerator()
data = generator.generate(ScenarioType.QPS, days=7)

# 2. 自动选择算法并训练
router = ModelRouter()
predictor = router.select_predictor(data)

# 3. 分割训练集和测试集
train_data = data[:6*1440]  # 前 6 天
test_data = data[6*1440:]   # 第 7 天

# 4. 训练与预测
predictor.fit(train_data)
prediction = predictor.predict(periods=1440)

# 5. 获取动态阈值
print(f"预测上限: {prediction.yhat_upper}")
print(f"预测下限: {prediction.yhat_lower}")
```

## 算法说明

### Prophet (Facebook)
- **适用**: 强季节性数据（QPS、连接数、流量）
- **特点**: 自动检测周期、对异常值鲁棒
- **容错**: 失败时降级为滑动平均

### Welford 3-Sigma
- **适用**: 高波动、无周期数据（RT、延迟）
- **特点**: 数值稳定、适合流式计算
- **阈值**: mean ± 3σ (99.7% 置信区间)

### Static 百分位数
- **适用**: 稀疏/低频数据（错误计数、报警数）
- **特点**: 稳健、简单高效
- **阈值**: 99th 百分位数

## 项目结构

```
smart_threshold/
├── core/
│   ├── feature_analyzer.py    # 特征提取
│   ├── model_router.py        # 算法路由
│   └── predictors/
│       ├── prophet_predictor.py
│       ├── welford_predictor.py
│       └── static_predictor.py
├── data/
│   └── generator.py           # Mock 数据生成
├── utils/
│   └── visualization.py       # 可视化工具
└── examples/
    └── demo.py                # 完整演示
```

## 输出示例

运行 `python examples/demo.py` 后，会在 `outputs/` 目录生成可视化图表：

![QPS 预测示例](outputs/qps_prediction.png)

图表包含：
- 蓝色实线：真实值
- 橙色虚线：预测值
- 橙色阴影：95% 置信区间（动态阈值）
- 红色叉点：检测到的异常值

## 依赖

- Python >= 3.10
- pandas, numpy, statsmodels
- prophet, matplotlib, scipy
- streamlit, plotly, requests
- pyyaml

## Streamlit 应用

SmartThreshold 提供了一个功能完整的 Streamlit Web 应用：

### 功能特点

- 📊 **数据源管理**: 支持 Prometheus 和 Mock 数据源
- 🔍 **指标查询**: 浏览和查询 Prometheus 指标
- 🎯 **时间段选择**: 可视化选择训练数据的时间范围
- 🤖 **多模型对比**: 支持同时对比多个预设/自定义模型
- ⚙️ **参数优化**: 修改模型参数并实时查看效果
- 💾 **保存模型**: 将优化后的参数保存为自定义模型

### 启动应用

```bash
# 使用启动脚本（推荐）
./run_streamlit.sh

# 或直接运行
source .venv/bin/activate
streamlit run streamlit_advanced.py
```

应用将在浏览器中打开: http://localhost:8501

详细使用说明请参考 [STREAMLIT_README.md](STREAMLIT_README.md)

## License

MIT
