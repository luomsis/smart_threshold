# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

SmartThreshold 是一个 DB 监控动态阈值系统，根据时序数据特征自动选择最合适的预测算法。

**核心功能**：
- 特征分析：季节性 (ACF)、稀疏性、平稳性 (ADF 检验)
- 算法路由：有季节性→Prophet，高稀疏→Static，其余→Welford 3-Sigma
- Web 界面：Pipeline 管理、模型管理、数据源管理（支持 Prometheus/TimescaleDB）

## 开发命令

```bash
# 安装依赖
uv sync

# 启动后端 API（开发模式，带热重载）
./run_backend.sh dev

# 启动后端 API（后台运行）
./run_backend.sh start
./run_backend.sh stop
./run_backend.sh status
./run_backend.sh logs

# 启动前端（另开终端）
cd frontend && python3 -m http.server 3000

# 或使用前端启动脚本
./run_frontend.sh dev          # 开发模式（前台运行，端口 8011）
./run_frontend.sh start        # 后台运行
./run_frontend.sh stop         # 停止服务

# 运行命令行演示
python examples/demo.py
```

**访问地址**：
- 前端界面：http://localhost:3000
- 后端 API：http://localhost:8010
- API 文档：http://localhost:8010/api/docs

## 项目结构

```
smart_threshold/
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── main.py            # FastAPI 主应用
│   │   └── routers/           # API 路由（datasources, models, predictions）
│   └── run_backend.sh         # 后端启动脚本
├── frontend/                   # 纯前端（Vanilla JS + ECharts）
│   ├── index.html
│   ├── css/                   # main.css, grafana-theme.css, components.css
│   └── js/
│       ├── app.js             # 应用入口
│       ├── api.js             # API 客户端
│       └── components/        # predict.js, charts.js, models.js, datasources.js, pipelines.js, jobs.js
└── smart_threshold/           # 核心算法库
    ├── core/
    │   ├── feature_analyzer.py    # 特征提取（ACF, ADF, 稀疏度）
    │   ├── model_router.py        # 算法路由逻辑
    │   └── predictors/            # Prophet, Welford, Static
    └── datasource/            # Prometheus, TimescaleDB 客户端
```

## 核心架构

### 算法路由规则（model_router.py）
1. **有季节性** (ACF > 0.3) → Prophet（适合 QPS 等周期数据）
2. **高稀疏性** (零值占比 > 80%) → Static 百分位数（适合错误数等稀疏数据）
3. **默认情况** → Welford 3-Sigma（适合 RT 等高波动数据）

### 特征分析（feature_analyzer.py）
- `FeatureExtractor.analyze(data)` → `FeatureResult`
- 关键特征：`has_seasonality`, `sparsity_ratio`, `is_stationary`

### 预测器工厂（predictors/）
- `ProphetPredictor`: 季节性数据，支持置信区间
- `WelfordPredictor`: 流式计算，阈值 = 均值 ± 3σ
- `StaticPredictor`: 百分位数阈值

## API 接口

主要端点（完整文档见 `/api/docs`）：
- `GET/POST /api/v1/datasources` - 数据源管理
- `GET/POST /api/v1/models` - 模型管理
- `POST /api/v1/predictions/compare` - 多模型对比
- `GET /api/health` - 健康检查

## 前端架构

- **无框架依赖**：纯 Vanilla JavaScript 模块化开发
- **ECharts**: 图表可视化（`frontend/static/echarts.min.js`）
- **Grafana 风格主题**: 深色 UI 设计

**组件职责**：
- `predict.js`: 快速预测功能（无需 Pipeline）
- `charts.js`: ECharts 封装，统一时间格式 `YYYY-MM-DD HH:mm:ss`
- `models.js`: 模型列表、编辑（带 help 悬浮提示）
- `datasources.js`: 数据源配置管理
- `pipelines.js`: Pipeline 管理和任务配置
- `jobs.js`: 任务状态监控
- `helpers.js`: 工具函数（`formatChartDate`, `formatNumber` 等）

## 配置管理

- **数据源配置**: `config/datasources.json`
- **模型默认参数**: `smart_threshold/config/model_config.py`
- **后端端口**: 8010（在 `run_backend.sh` 中配置）

## 测试与调试

```bash
# 运行单元测试（每次修改代码后必须运行）
uv run pytest tests/ -v

# 查看后端日志
./run_backend.sh logs

# 查看进程状态
./run_backend.sh status

# 测试 API
curl http://localhost:8010/api/health
```

**测试文件**：
- `tests/test_feature_analyzer.py` - 特征分析测试
- `tests/test_model_router.py` - 模型路由测试
- `tests/test_predictors.py` - 预测器测试
- `tests/test_factory.py` - 预测器工厂测试
- `tests/test_generator.py` - 数据生成器测试

## 注意事项

- 后端使用 uvicorn 热重载，修改代码后自动生效
- 前端无构建步骤，直接修改 JS/CSS 文件，刷新浏览器即可
- 确保 `.venv` 存在，`run_backend.sh` 会自动创建并安装依赖
- 模型对比功能默认只选中最佳模型（MAPE 最小）
- **Git Push 使用代理**：`export http_proxy=http://127.0.0.1:1087; export https_proxy=http://127.0.0.1:1087; git push`
