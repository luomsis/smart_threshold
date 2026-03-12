# SmartThreshold - DB 监控算法自动选型系统

智能阈值系统，能够根据时序数据的特征自动选择最合适的动态阈值算法。

## 背景

传统 DB 监控使用固定阈值进行告警，存在以下问题：

- **QPS（查询量）**：有明显的日/周周期，固定阈值会产生大量误报
- **RT（响应时间）**：高波动且偶发尖峰，固定阈值难以捕捉
- **错误数**：大部分为 0，传统预测算法效果不佳

SmartThreshold 通过**特征分析**自动选择最合适的算法，实现精准的动态阈值告警。

## 系统架构

SmartThreshold 采用前后端分离架构：

### 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                         前端 (Frontend)                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │   仪表盘     │  │  模型管理    │  │      数据源管理          │ │
│  │  (Chart.js) │  │  (ECharts)  │  │   (Prometheus/Mock)     │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │ HTTP REST API
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      后端 API (FastAPI)                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │  数据源接口  │  │  模型接口    │  │      预测接口            │ │
│  │  /datasources│  │  /models    │  │   /predictions          │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    核心算法库 (Python)                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │  特征分析层  │  │  算法路由层  │  │       预测器层           │ │
│  │FeatureAnalyzer│  │ModelRouter  │  │  Prophet/Welford/Static │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 三层核心架构

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

### 方式一：前后端分离模式（推荐）

启动后端 API 服务：

```bash
# 开发模式（带热重载）
./run_backend.sh dev

# 或后台运行
./run_backend.sh start
```

启动前端（使用 Python HTTP 服务器）：

```bash
cd frontend
python3 -m http.server 3000
```

访问应用：
- 前端界面：http://localhost:3000
- 后端 API：http://localhost:8000
- API 文档：http://localhost:8000/api/docs

### 方式二：命令行演示

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
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── main.py            # FastAPI 主应用
│   │   └── routers/           # API 路由
│   │       ├── datasources.py # 数据源管理
│   │       ├── models.py      # 模型管理
│   │       └── predictions.py # 预测与对比
│   └── run_backend.sh         # 后端启动脚本
├── frontend/                   # 纯前端应用
│   ├── index.html             # 主页面
│   ├── css/                   # 样式文件
│   │   ├── main.css
│   │   ├── grafana-theme.css
│   │   └── components.css
│   ├── js/                    # JavaScript 模块
│   │   ├── api.js             # API 客户端
│   │   ├── app.js             # 应用入口
│   │   └── components/        # 组件
│   │       ├── dashboard.js   # 仪表盘（模型对比）
│   │       ├── charts.js      # 图表组件
│   │       ├── models.js      # 模型管理
│   │       └── datasources.js # 数据源管理
│   └── static/                # 静态资源
│       └── echarts.min.js     # ECharts 图表库
├── smart_threshold/           # 核心算法库
│   ├── core/
│   │   ├── feature_analyzer.py    # 特征提取
│   │   ├── model_router.py        # 算法路由
│   │   └── predictors/            # 预测器实现
│   │       ├── prophet_predictor.py
│   │       ├── welford_predictor.py
│   │       └── static_predictor.py
│   ├── datasource/            # 数据源客户端
│   │   ├── prometheus_client.py
│   │   └── timescaledb_client.py
│   └── data/
│       └── generator.py       # Mock 数据生成
└── examples/
    └── demo.py                # 命令行演示
```

## Web 界面功能

SmartThreshold 提供了一个功能完整的 Web 应用，采用 Grafana 风格的深色主题：

### 仪表盘

- 📊 **数据查询**：支持 Prometheus 和 Mock 数据源
- 🎯 **训练区间设置**：可视化选择训练数据时间范围
- 🤖 **模型对比**：同时对比多个模型，自动选择最佳模型
- 📈 **结果可视化**：使用 ECharts 展示预测结果和置信区间

### 模型对比功能

模型对比时会自动：
1. 按 MAPE 排序所有模型结果
2. 高亮显示最佳模型
3. **默认只选中最佳模型**，其他模型保留选项但取消选中
4. 在图表中显示最佳模型的置信区间

### 模型管理

- 查看所有预设模型和自定义模型
- 添加自定义模型（基于现有算法修改参数）
- 编辑模型参数（独立页面，支持 help 悬浮提示）
- 删除自定义模型

### 数据源管理

- 支持 Prometheus 数据源
- 支持 TimescaleDB 数据源
- 支持 Mock 数据源（用于演示）
- 添加、编辑、删除数据源配置

### 启动 Web 应用

```bash
# 1. 启动后端
./run_backend.sh dev

# 2. 启动前端（新终端）
cd frontend
python3 -m http.server 3000

# 3. 访问 http://localhost:3000
```

## API 接口

后端提供 RESTful API，启动后访问 http://localhost:8000/api/docs 查看完整文档。

### 主要接口

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/datasources` | GET/POST | 数据源列表/创建 |
| `/api/v1/datasources/{id}` | GET/DELETE | 获取/删除数据源 |
| `/api/v1/datasources/{id}/metrics` | GET | 获取指标列表 |
| `/api/v1/datasources/{id}/query` | POST | 查询时序数据 |
| `/api/v1/models` | GET/POST | 模型列表/创建 |
| `/api/v1/models/{id}` | GET/PUT/DELETE | 获取/更新/删除模型 |
| `/api/v1/predictions/compare` | POST | 多模型对比 |
| `/api/v1/predictions/predict` | POST | 单模型预测 |
| `/api/health` | GET | 健康检查 |

### 模型对比示例

```bash
curl -X POST http://localhost:8000/api/v1/predictions/compare \
  -H "Content-Type: application/json" \
  -d '{
    "model_ids": ["prophet_default", "welford_default"],
    "data": [100, 102, 98, ...],
    "timestamps": ["2024-01-01T00:00:00", ...],
    "train_start": "2024-01-01T00:00:00",
    "train_end": "2024-01-06T23:59:59"
  }'
```

返回结果包含各模型的 MAPE、MAE、覆盖率等指标，以及预测数据。

## 依赖

- Python >= 3.10
- pandas, numpy, statsmodels
- prophet, matplotlib, scipy
- fastapi, uvicorn
- requests, pyyaml

## License

MIT
