# SmartThreshold Streamlit 应用

DB 监控算法自动选型系统的 Streamlit 界面。

## 应用说明

SmartThreshold Streamlit 应用是一个完整的时序数据分析和模型优化平台，提供：

- 📊 **数据源管理**: 支持 Prometheus 和 Mock 数据源
- 🔍 **指标查询**: 浏览和查询 Prometheus 指标
- 🎯 **时间段选择**: 可视化选择训练数据的时间范围
- 🤖 **多模型对比**: 支持同时对比多个预设/自定义模型
- ⚙️ **参数优化**: 修改模型参数并实时查看效果
- 💾 **保存模型**: 将优化后的参数保存为自定义模型

## 安装依赖

```bash
# 安装项目依赖（包括 Streamlit）
uv sync
```

## 启动应用

### 方式 1: 使用启动脚本（推荐）

```bash
# 给脚本添加执行权限
chmod +x run_streamlit.sh

# 运行应用
./run_streamlit.sh
```

### 方式 2: 直接运行

```bash
# 激活虚拟环境
source .venv/bin/activate

# 运行 Streamlit 应用
streamlit run streamlit_advanced.py
```

应用将在浏览器中自动打开: http://localhost:8501

## 使用流程

### 步骤 1: 数据源配置

在侧边栏选择或添加数据源：

1. **Mock 数据源**: 内置模拟数据源，用于测试
2. **Prometheus 数据源**: 连接真实的 Prometheus 服务器

添加 Prometheus 数据源：
```
名称: my-prometheus
URL: http://localhost:9090
```

点击"测试连接"验证数据源配置。

### 步骤 2: 指标查询

1. 在「指标查询」标签页，选择要查询的指标
2. 可选：使用标签筛选器过滤数据
3. 设置查询时间范围和采样间隔
4. 点击"执行查询"获取数据
5. 使用日期选择器设置训练区间

### 步骤 3: 模型对比

1. 在「模型对比」标签页，勾选要对比的模型
2. 点击"运行模型对比"
3. 查看各模型的 MAPE、MAE、覆盖率指标
4. 在交互式图表中对比预测效果

### 步骤 4: 参数优化

1. 从对比结果中选择一个模型
2. 点击"进入参数优化"
3. 调整模型参数
4. 点击"重新预测"查看效果
5. 满意后进入下一步

### 步骤 5: 保存模型

1. 在「保存模型」标签页，输入新模型的名称和描述
2. 添加标签便于分类
3. 点击"保存模型"
4. 新模型将出现在侧边栏的可用模型列表中

## 数据源支持

### Prometheus 数据源

支持的查询类型：
- **即时查询 (Instant Query)**: 查询单个时间点的值
- **范围查询 (Range Query)**: 查询一段时间内的时序数据

PromQL 示例：
```promql
# 基础指标查询
up

# 带标签筛选
up{job="prometheus"}

# 范围查询
rate(http_requests_total[5m])
```

### Mock 数据源

内置模拟数据源，生成以下类型的数据：
- `qps`: QPS 场景（带季节性和增长趋势）
- `latency_ms`: 响应时间（平稳 + 偶发尖峰）
- `error_rate`: 错误率（稀疏数据）

## 系统预设模型

应用包含以下系统预设模型：

| ID | 名称 | 类型 | 描述 |
|----|------|------|------|
| `prophet_aggressive` | Aggressive (敏感) | Prophet | 高灵敏度，检测更多异常 |
| `prophet_standard` | Standard (标准) | Prophet | 平衡配置，适合大多数场景 |
| `prophet_conservative` | Conservative (保守) | Prophet | 低灵敏度，减少误报 |
| `welford_standard` | Welford 3-Sigma | Welford | 基于统计分布的动态阈值 |
| `static_percentile` | Static Percentile | Static | 基于历史分位数的静态阈值 |

## 模型配置存储

自定义模型保存在: `config/models/model_configs.json`

配置文件格式：
```json
[
  {
    "id": "custom_my_model",
    "name": "我的优化模型",
    "description": "针对高 QPS 场景优化的配置",
    "model_type": "prophet",
    "category": "custom",
    "changepoint_prior_scale": 0.15,
    "seasonality_prior_scale": 12.0,
    "interval_width": 0.90,
    "n_changepoints": 30,
    "color": "#4ECDC4",
    "tags": ["自定义", "高QPS"],
    "created_at": "2026-03-06T10:00:00",
    "author": "user"
  }
]
```

## API 使用

应用也可作为 Python 库使用：

```python
from smart_threshold.datasource import create_datasource, DataSourceConfig, DataSourceType, TimeRange
from smart_threshold.config import get_model_config_manager, ModelType
from datetime import datetime, timedelta

# 创建数据源
config = DataSourceConfig(
    name="prometheus",
    source_type=DataSourceType.PROMETHEUS,
    url="http://localhost:9090"
)
ds = create_datasource(config)

# 查询数据
end = datetime.now()
start = end - timedelta(days=7)
time_range = TimeRange(start=start, end=end, step="1m")
result = ds.query_range("up", time_range)

# 获取模型配置
manager = get_model_config_manager()
configs = manager.get_prophet_configs()

# 创建自定义模型
from smart_threshold.config import ModelConfig, TemplateCategory
new_config = ModelConfig(
    id="my_model",
    name="我的模型",
    description="自定义配置",
    model_type=ModelType.PROPHET,
    category=TemplateCategory.CUSTOM,
    changepoint_prior_scale=0.1
)
manager.add_config(new_config)
```

## 技术栈

- **前端框架**: Streamlit
- **数据可视化**: Plotly
- **数据处理**: Pandas, NumPy
- **算法**: Prophet, Welford, Static
- **数据源**: Prometheus HTTP API

## 故障排除

### 端口被占用

如果 8501 端口被占用，可以指定其他端口:

```bash
streamlit run streamlit_advanced.py --server.port 8502
```

### Prometheus 连接失败

1. 检查 Prometheus URL 是否正确
2. 确认 Prometheus 服务正在运行
3. 检查网络连接和防火墙设置
4. 使用"测试连接"按钮验证

### 依赖问题

如果遇到依赖问题，重新安装:

```bash
uv sync --reinstall
```
