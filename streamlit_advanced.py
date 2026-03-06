"""
SmartThreshold 高级应用

功能：
1. 仪表盘 - 指标查询、可视化、模型对比、参数优化
2. 模型管理 - 查看列表、参数详情、编辑、删除
3. 数据源管理 - 选择默认、添加、删除
"""

import json
import sys
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from smart_threshold.datasource import (
    create_datasource,
    DataSourceConfig,
    DataSourceType,
    TimeRange,
)
from smart_threshold.config import (
    ModelConfig,
    get_model_config_manager,
    ModelType,
    TemplateCategory,
)
from smart_threshold.core.predictors.prophet_predictor import ProphetPredictor
from smart_threshold.core.predictors.welford_predictor import WelfordPredictor
from smart_threshold.core.predictors.static_predictor import StaticPredictor


# ==================== 页面配置 ====================

st.set_page_config(
    page_title="SmartThreshold",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 自定义 CSS
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        margin-bottom: 1.5rem;
        text-align: center;
        color: white;
    }
    .main-header h1 {
        margin: 0;
        font-size: 2rem;
    }
    .metric-card {
        background: white;
        border-radius: 8px;
        padding: 1rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        text-align: center;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: bold;
        color: #667eea;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #666;
    }
    .model-card {
        background: white;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 1rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid #667eea;
    }
    .winner-badge {
        background: linear-gradient(135deg, #FFD700 0%, #FFA500 100%);
        color: white;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-weight: bold;
        display: inline-block;
        font-size: 0.9rem;
    }

    /* Tooltip 样式 */
    .tooltip-container {
        position: relative;
        display: inline-flex;
        align-items: center;
        gap: 6px;
        position: relative;
    }
    .tooltip-icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 16px;
        height: 16px;
        border-radius: 50%;
        background: #667eea;
        color: white;
        font-size: 11px;
        font-weight: bold;
        cursor: help;
        position: relative;
        flex-shrink: 0;
    }
    .tooltip-icon:hover {
        background: #764ba2;
    }
    .tooltip-text {
        position: absolute;
        left: calc(100% + 8px);
        top: 50%;
        transform: translateY(-50%);
        background: #333;
        color: #fff;
        padding: 10px 14px;
        border-radius: 6px;
        font-size: 12px;
        line-height: 1.5;
        white-space: normal;
        min-width: 150px;
        max-width: 300px;
        width: max-content;
        opacity: 0;
        visibility: hidden;
        transition: opacity 0.2s, visibility 0.2s;
        z-index: 1000;
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    .tooltip-container:hover .tooltip-text {
        opacity: 1;
        visibility: visible;
    }
    .tooltip-text::after {
        content: '';
        position: absolute;
        top: 50%;
        right: 100%;
        transform: translateY(-50%);
        border: 5px solid transparent;
        border-right-color: #333;
    }
    .param-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.3rem 0;
        gap: 1rem;
    }
    .param-label {
        flex: 1;
        font-weight: 500;
    }
    .param-value {
        flex: 0 0 auto;
        text-align: right;
        font-weight: 600;
        color: #667eea;
    }
    .param-label .tooltip-container {
        display: inline-flex;
        align-items: center;
        gap: 6px;
    }
</style>
""", unsafe_allow_html=True)


# ==================== 工具函数 ====================

def tooltip(label: str, help_text: str) -> None:
    """
    显示带悬停提示的标签

    Args:
        label: 标签文本
        help_text: 悬停显示的帮助文本
    """
    tooltip_html = f"""
    <div style="display: inline-flex; align-items: center; gap: 6px;">
        {label}
        <div class="tooltip-container">
            <span class="tooltip-icon">?</span>
            <span class="tooltip-text">{help_text}</span>
        </div>
    </div>
    """
    st.markdown(tooltip_html, unsafe_allow_html=True)


# ==================== Session State 初始化 ====================

def init_session_state():
    """初始化 session state"""
    # 页面导航
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'dashboard'

    # 数据源相关
    if 'datasources' not in st.session_state:
        st.session_state.datasources = {
            'mock': DataSourceConfig(
                name="Mock 数据源",
                source_type=DataSourceType.MOCK,
                url="mock://localhost"
            )
        }
    if 'current_datasource' not in st.session_state:
        st.session_state.current_datasource = 'mock'

    # 查询相关
    if 'query_data' not in st.session_state:
        st.session_state.query_data = None
    if 'selected_metric' not in st.session_state:
        st.session_state.selected_metric = None

    # 时间范围
    if 'time_range_days' not in st.session_state:
        st.session_state.time_range_days = 7
    if 'step' not in st.session_state:
        st.session_state.step = '1m'

    # 训练区间
    if 'train_start_date' not in st.session_state:
        st.session_state.train_start_date = None
    if 'train_end_date' not in st.session_state:
        st.session_state.train_end_date = None

    # 模型对比相关
    if 'selected_model_ids' not in st.session_state:
        st.session_state.selected_model_ids = []
    if 'comparison_results' not in st.session_state:
        st.session_state.comparison_results = None

    # 参数编辑相关
    if 'editing_model_id' not in st.session_state:
        st.session_state.editing_model_id = None
    if 'modified_params' not in st.session_state:
        st.session_state.modified_params = {}


init_session_state()


# ==================== 辅助函数 ====================

def hex_to_rgba(hex_color: str, alpha: float = 0.2) -> str:
    """将 hex 颜色转换为 rgba 格式"""
    hex_color = hex_color.lstrip('#')
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f'rgba({r}, {g}, {b}, {alpha})'


def create_time_series_chart(
    data: pd.Series,
    title: str = "时序数据",
    highlight_range: Optional[Tuple[datetime, datetime]] = None
) -> go.Figure:
    """创建时序数据图表"""
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=data.index,
        y=data.values,
        mode='lines',
        name='指标值',
        line=dict(color='#667eea', width=2),
        hovertemplate='%{x}<br>值: %{y:.2f}<extra></extra>'
    ))

    # 添加训练区间高亮
    if highlight_range:
        fig.add_vrect(
            x0=highlight_range[0],
            x1=highlight_range[1],
            fillcolor="rgba(255, 235, 59, 0.3)",
            layer="below",
            line_width=0,
            annotation_text="训练区间",
            annotation_position="top left"
        )

    fig.update_layout(
        title=title,
        xaxis_title='时间',
        yaxis_title='值',
        hovermode='x unified',
        template='plotly_white',
        height=400,
        dragmode='select'
    )

    return fig


def create_comparison_chart(
    test_data: pd.Series,
    results: Dict,
    visible_model_ids: List[str]
) -> go.Figure:
    """创建模型对比图表"""
    fig = go.Figure()

    # 实际值
    fig.add_trace(go.Scatter(
        x=test_data.index,
        y=test_data.values,
        mode='lines',
        name='实际值',
        line=dict(color='#2C3E50', width=2),
    ))

    # 添加每个模型的预测
    manager = get_model_config_manager()
    for model_id in visible_model_ids:
        result = results.get(model_id)
        if result and result.get('success') and result.get('prediction') is not None:
            pred = result['prediction']
            config = manager.get_config(model_id)

            # 预测值
            fig.add_trace(go.Scatter(
                x=pred.index,
                y=pred['yhat'],
                mode='lines',
                name=f'{config.name} - 预测',
                line=dict(color=config.color, width=2, dash='dash'),
            ))

            # 置信区间
            fig.add_trace(go.Scatter(
                x=pred.index.tolist() + pred.index[::-1].tolist(),
                y=pred['yhat_upper'].tolist() + pred['yhat_lower'][::-1].tolist(),
                fill='toself',
                fillcolor=hex_to_rgba(config.color, 0.2),
                line=dict(color='rgba(0,0,0,0)'),
                name=f'{config.name} - 区间',
                hoverinfo='skip'
            ))

    fig.update_layout(
        title="模型预测对比",
        xaxis_title='时间',
        yaxis_title='值',
        hovermode='x unified',
        template='plotly_white',
        height=500,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    return fig


def run_model_comparison(
    data: pd.Series,
    train_start: datetime,
    train_end: datetime,
    model_ids: List[str]
) -> Dict:
    """运行模型对比"""
    manager = get_model_config_manager()
    results = {}

    # 分割训练集和测试集
    train_mask = (data.index >= train_start) & (data.index <= train_end)
    train_data = data[train_mask]

    # 测试集使用训练集之后的数据（未来24小时）
    test_start = train_end + timedelta(minutes=1)
    test_end = test_start + timedelta(hours=24)
    test_mask = (data.index >= test_start) & (data.index <= test_end)

    if test_mask.sum() == 0:
        # 如果没有测试数据，使用训练集最后 20%
        split_idx = int(len(train_data) * 0.8)
        test_data = train_data.iloc[split_idx:]
        train_data = train_data.iloc[:split_idx]
    else:
        test_data = data[test_mask]

    for model_id in model_ids:
        config = manager.get_config(model_id)
        if not config:
            continue

        try:
            # 创建预测器
            if config.model_type == ModelType.PROPHET:
                predictor = ProphetPredictor(**config.get_params())
            elif config.model_type == ModelType.WELFORD:
                predictor = WelfordPredictor(**config.get_params())
            elif config.model_type == ModelType.STATIC:
                predictor = StaticPredictor(**config.get_params())
            else:
                continue

            # 训练
            predictor.fit(train_data)

            # 预测
            prediction = predictor.predict(periods=len(test_data))

            # 计算指标
            actual = test_data.values
            predicted = prediction.yhat

            mae = np.abs(actual - predicted).mean()
            mape = (np.abs(actual - predicted) / (actual + 1e-6)).mean() * 100

            # 覆盖率
            in_range = (actual >= prediction.yhat_lower) & (actual <= prediction.yhat_upper)
            coverage = in_range.mean()

            # 构建预测 DataFrame
            pred_df = pd.DataFrame({
                'yhat': prediction.yhat,
                'yhat_upper': prediction.yhat_upper,
                'yhat_lower': prediction.yhat_lower,
            }, index=test_data.index)

            results[model_id] = {
                'config': config,
                'mae': mae,
                'mape': mape,
                'coverage': coverage,
                'prediction': pred_df,
                'success': True,
                'error': None
            }

        except Exception as e:
            results[model_id] = {
                'config': config,
                'mae': float('inf'),
                'mape': float('inf'),
                'coverage': 0,
                'prediction': None,
                'success': False,
                'error': str(e)
            }

    return results


# ==================== 页面函数 ====================

def render_sidebar():
    """渲染侧边栏"""
    with st.sidebar:
        st.markdown("# 📊 SmartThreshold")

        st.divider()

        # 页面导航
        pages = [
            ("📊 仪表盘", "dashboard"),
            ("🤖 模型管理", "models"),
            ("🔌 数据源", "datasources"),
        ]

        for label, page_id in pages:
            if st.session_state.current_page == page_id:
                st.button(label, use_container_width=True, type="primary")
            else:
                if st.button(label, use_container_width=True):
                    st.session_state.current_page = page_id
                    st.rerun()

        st.divider()

        # 当前数据源信息
        st.markdown("### 当前数据源")
        current_ds = st.session_state.datasources.get(st.session_state.current_datasource)
        if current_ds:
            st.info(f"**{current_ds.name}**\n{current_ds.source_type.value}")

        st.divider()

        # 重置按钮
        if st.button("🔄 重置应用", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            init_session_state()
            st.rerun()


def render_dashboard():
    """渲染仪表盘页面"""
    st.markdown('<div class="main-header"><h1>📊 仪表盘</h1></div>', unsafe_allow_html=True)

    # 获取当前数据源
    ds_name = st.session_state.current_datasource
    ds_config = st.session_state.datasources[ds_name]
    ds = create_datasource(ds_config)

    # 列1: 查询控制
    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("### 📋 数据查询")

        # 获取可用指标
        metrics = ds.list_metrics()
        metric_names = [m.name for m in metrics]

        if metric_names:
            selected_metric = st.selectbox("选择指标", metric_names)

            # 标签筛选
            labels = ds.list_label_names()
            if labels:
                selected_label = st.selectbox("筛选标签", labels)
                if selected_label:
                    label_values = ds.get_label_values(selected_label)
                    if label_values.values:
                        selected_value = st.selectbox("标签值", label_values.values)
        else:
            st.warning("无可用指标")
            return

    with col2:
        st.markdown("### ⏱️ 时间范围")

        col_a, col_b = st.columns(2)
        with col_a:
            days = st.slider("查询天数", 1, 30, st.session_state.time_range_days)
            st.session_state.time_range_days = days
        with col_b:
            step = st.selectbox("采样间隔", ["1m", "5m", "15m", "1h"],
                              index=["1m", "5m", "15m", "1h"].index(st.session_state.step))
            st.session_state.step = step

    st.divider()

    # 执行查询按钮
    if st.button("🔍 执行查询", type="primary", use_container_width=True):
        end = datetime.now()
        start = end - timedelta(days=days)
        time_range = TimeRange(start=start, end=end, step=step)

        with st.spinner(f"正在查询 {selected_metric}..."):
            result = ds.query_range(selected_metric, time_range)

            if result.success and result.data:
                metric_data = result.data[0]
                data_series = pd.Series(
                    metric_data.values,
                    index=pd.DatetimeIndex(metric_data.timestamps),
                    name=selected_metric
                )

                st.session_state.query_data = data_series
                st.session_state.selected_metric = selected_metric

                # 默认训练区间：前 80%
                split_idx = int(len(data_series) * 0.8)
                st.session_state.train_start_date = data_series.index[0].date()
                st.session_state.train_end_date = data_series.index[split_idx].date()

                st.success(f"✅ 查询成功！获取到 {len(data_series)} 个数据点")
                st.rerun()
            else:
                st.error(f"❌ 查询失败: {result.error}")

    # 显示数据
    if st.session_state.query_data is not None:
        data = st.session_state.query_data

        # 数据概览
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("数据点数", len(data))
        with col2:
            st.metric("最小值", f"{data.min():.2f}")
        with col3:
            st.metric("最大值", f"{data.max():.2f}")
        with col4:
            st.metric("平均值", f"{data.mean():.2f}")

        st.divider()

        # 数据图表
        col1, col2 = st.columns([2, 1])

        with col1:
            # 设置训练区间
            st.markdown("### 🎯 设置训练区间")

            col_a, col_b = st.columns(2)
            with col_a:
                start_date = st.date_input("开始日期", value=st.session_state.train_start_date or data.index[0].date())
            with col_b:
                end_date = st.date_input("结束日期", value=st.session_state.train_end_date or data.index[int(len(data)*0.8)].date())

            if st.button("设置训练区间", use_container_width=True):
                st.session_state.train_start_date = start_date
                st.session_state.train_end_date = end_date
                st.rerun()

        with col2:
            # 快捷操作
            st.markdown("### ⚡ 快捷操作")
            if st.button("使用前 80% 作为训练集", use_container_width=True):
                split_idx = int(len(data) * 0.8)
                st.session_state.train_start_date = data.index[0].date()
                st.session_state.train_end_date = data.index[split_idx].date()
                st.rerun()

        # 显示图表
        if st.session_state.train_start_date and st.session_state.train_end_date:
            train_start = datetime.combine(st.session_state.train_start_date, datetime.min.time())
            train_end = datetime.combine(st.session_state.train_end_date, datetime.max.time())

            fig = create_time_series_chart(
                data,
                title=f"指标: {st.session_state.selected_metric}",
                highlight_range=(train_start, train_end)
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            fig = create_time_series_chart(data, title=f"指标: {st.session_state.selected_metric}")
            st.plotly_chart(fig, use_container_width=True)

        st.divider()

        # 模型对比
        st.markdown("### 🤖 模型对比")

        manager = get_model_config_manager()
        all_models = manager.list_configs()

        # 选择模型
        col1, col2 = st.columns([1, 1])

        with col1:
            st.markdown("**选择模型进行对比**")
            for model in all_models:
                checked = st.checkbox(
                    f"**{model.name}**" + (f" 🏆" if model.id in st.session_state.selected_model_ids and st.session_state.comparison_results and
                     st.session_state.comparison_results.get(model.id, {}).get('success') and
                     min((r.get('mape', float('inf')) for r in st.session_state.comparison_results.values()), default=float('inf')) == st.session_state.comparison_results[model.id]['mape'] else ""),
                    value=model.id in st.session_state.selected_model_ids,
                    key=f"select_{model.id}"
                )
                if checked and model.id not in st.session_state.selected_model_ids:
                    st.session_state.selected_model_ids.append(model.id)
                elif not checked and model.id in st.session_state.selected_model_ids:
                    st.session_state.selected_model_ids.remove(model.id)

        with col2:
            if st.session_state.train_start_date and st.session_state.train_end_date:
                if st.button("🚀 运行对比", type="primary", use_container_width=True):
                    train_start = datetime.combine(st.session_state.train_start_date, datetime.min.time())
                    train_end = datetime.combine(st.session_state.train_end_date, datetime.max.time())

                    with st.spinner("正在运行模型对比..."):
                        results = run_model_comparison(
                            data,
                            train_start,
                            train_end,
                            st.session_state.selected_model_ids
                        )
                        st.session_state.comparison_results = results
                    st.rerun()

        # 显示对比结果
        if st.session_state.comparison_results:
            results = st.session_state.comparison_results

            # 指标表格
            st.markdown("**对比结果**")

            summary_data = []
            for model_id in st.session_state.selected_model_ids:
                result = results.get(model_id, {})
                config = manager.get_config(model_id)

                if result.get('success'):
                    summary_data.append({
                        '模型': config.name,
                        'MAPE (%)': f"{result['mape']:.2f}",
                        'MAE': f"{result['mae']:.2f}",
                        '覆盖率 (%)': f"{result['coverage']*100:.1f}",
                    })
                else:
                    summary_data.append({
                        '模型': config.name,
                        'MAPE (%)': '-',
                        'MAE': '-',
                        '覆盖率 (%)': '-',
                    })

            st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)

            # 对比图表
            st.markdown("**预测对比**")

            visible_models = [
                mid for mid in st.session_state.selected_model_ids
                if results.get(mid, {}).get('success')
            ]

            if visible_models:
                # 选择显示的模型
                display_options = {
                    mid: manager.get_config(mid).name
                    for mid in visible_models
                }

                selected_display = st.multiselect(
                    "选择显示的模型",
                    options=list(display_options.keys()),
                    format_func=lambda x: display_options[x],
                    default=visible_models
                )

                if selected_display:
                    # 准备测试数据
                    train_end = datetime.combine(st.session_state.train_end_date, datetime.max.time())
                    test_start = train_end + timedelta(minutes=1)
                    test_end = test_start + timedelta(hours=24)

                    test_mask = (data.index >= test_start) & (data.index <= test_end)
                    if test_mask.sum() == 0:
                        split_idx = int(len(data[data.index <= train_end]) * 0.8)
                        test_data = data[data.index <= train_end].iloc[split_idx:]
                    else:
                        test_data = data[test_mask]

                    fig = create_comparison_chart(test_data, results, selected_display)
                    st.plotly_chart(fig, use_container_width=True)

            st.divider()

            # 参数优化
            st.markdown("### ⚙️ 参数优化")

            # 选择要优化的模型
            successful_models = [
                (mid, manager.get_config(mid).name)
                for mid in st.session_state.selected_model_ids
                if results.get(mid, {}).get('success')
            ]

            if successful_models:
                selected_opt = st.selectbox(
                    "选择要优化的模型",
                    options=range(len(successful_models)),
                    format_func=lambda i: successful_models[i][1]
                )

                if st.button("⚙️ 进入参数优化", use_container_width=True):
                    opt_id = successful_models[selected_opt][0]
                    st.session_state.editing_model_id = opt_id
                    st.rerun()

            # 显示当前编辑的模型参数
            if st.session_state.editing_model_id:
                st.markdown("---")
                st.markdown("### 🛠️ 编辑模型参数")

                config = manager.get_config(st.session_state.editing_model_id)

                st.markdown(f"**{config.name}** - {config.description}")

                if config.category == TemplateCategory.SYSTEM:
                    st.info("📌 系统预设模型，修改后需另存为新模型")

                st.markdown("---")

                # 参数编辑区域
                modified_params = {}

                if config.model_type == ModelType.PROPHET:
                    # Prophet 参数帮助信息
                    prophet_help = {
                        'daily_seasonality': '是否启用24小时周期模式。适合白天/夜间差异明显的数据（如网站访问量）',
                        'weekly_seasonality': '是否启用7天周期模式。适合工作日/周末差异明显的数据（如办公系统负载）',
                        'changepoint_prior_scale': '控制趋势变化点的灵活性。0.001-0.01保守，0.05-0.1推荐，0.2-0.5灵活',
                        'seasonality_prior_scale': '控制季节性效应的强度。1-5弱，10-20适中（推荐10），25-50强',
                        'interval_width': '预测不确定性区间宽度。0.68窄，0.80平衡，0.95宽',
                        'n_changepoints': '趋势变化点数量。5-10保守，15-25适中（推荐25），30-100灵活',
                        'seasonality_mode': '季节性模式。additive=加性(恒定振幅)，multiplicative=乘性(相对振幅)',
                        'holidays_prior_scale': '节假日效应强度。1-5小，10-20推荐，25-50大',
                        'changepoint_range': '变点可能出现的比例范围。0.5-0.7保守，0.8-0.9推荐，0.95-1.0敏感',
                    }

                    # 季节性模式
                    tooltip("季节性模式", prophet_help['seasonality_mode'])
                    season_mode = st.selectbox("", ["additive", "multiplicative"],
                        index=["additive", "multiplicative"].index(config.seasonality_mode), label_visibility="collapsed")
                    modified_params['seasonality_mode'] = season_mode

                    # 变化点参数
                    tooltip("变化点数量", prophet_help['n_changepoints'])
                    n_cp = st.slider("", 5, 50, config.n_changepoints, 1, label_visibility="collapsed")
                    modified_params['n_changepoints'] = n_cp

                    tooltip("变化点灵活性", prophet_help['changepoint_prior_scale'])
                    cp_prior = st.slider("", 0.001, 0.5, config.changepoint_prior_scale, 0.001, label_visibility="collapsed", format="%.3f")
                    modified_params['changepoint_prior_scale'] = cp_prior

                    # 季节性参数
                    tooltip("日季节性", prophet_help['daily_seasonality'])
                    daily = st.checkbox("", config.daily_seasonality, label_visibility="collapsed")
                    modified_params['daily_seasonality'] = daily

                    tooltip("周季节性", prophet_help['weekly_seasonality'])
                    weekly = st.checkbox("", config.weekly_seasonality, label_visibility="collapsed")
                    modified_params['weekly_seasonality'] = weekly

                    tooltip("季节性强度", prophet_help['seasonality_prior_scale'])
                    season_prior = st.slider("", 1.0, 50.0, config.seasonality_prior_scale, 0.5, label_visibility="collapsed")
                    modified_params['seasonality_prior_scale'] = season_prior

                    tooltip("置信区间", prophet_help['interval_width'])
                    interval = st.slider("", 0.1, 0.99, config.interval_width, 0.01, label_visibility="collapsed", format="%.2f")
                    modified_params['interval_width'] = interval

                elif config.model_type == ModelType.WELFORD:
                    # Welford 参数帮助信息
                    welford_help = {
                        'sigma_multiplier': 'Sigma倍数控制阈值宽度。1.5-2.5敏感，3推荐，3.5-4宽松',
                        'use_rolling_window': '是否使用滚动窗口。适合有趋势的数据，能适应变化',
                        'window_size': '滚动窗口大小（分钟）。60-360短期，720-1440中期，2880+长期',
                    }

                    # Sigma 倍数
                    tooltip("Sigma 倍数", welford_help['sigma_multiplier'])
                    sigma = st.slider("", 1.0, 5.0, config.sigma_multiplier, 0.1, label_visibility="collapsed")
                    modified_params['sigma_multiplier'] = sigma

                    # 滚动窗口
                    tooltip("启用滚动窗口", welford_help['use_rolling_window'])
                    use_rolling = st.checkbox("", config.use_rolling_window, label_visibility="collapsed")
                    modified_params['use_rolling_window'] = use_rolling

                    if use_rolling:
                        tooltip("窗口大小(分钟)", welford_help['window_size'])
                        window = st.slider("", 60, 10080, config.window_size or 1440, 60, label_visibility="collapsed")
                        modified_params['window_size'] = window

                elif config.model_type == ModelType.STATIC:
                    # Static 参数帮助信息
                    static_help = {
                        'upper_percentile': '上限百分位数。90-95敏感，97-99适中（推荐99），99.5-100只检测极值',
                        'lower_bound': '下限值。通常为0（计数类指标不能为负）',
                    }

                    tooltip("上限百分位", static_help['upper_percentile'])
                    percentile = st.slider("", 90.0, 100.0, config.upper_percentile, 0.5, label_visibility="collapsed")
                    modified_params['upper_percentile'] = percentile

                    tooltip("下限值", static_help['lower_bound'])
                    lower = st.slider("", 0.0, 100.0, config.lower_bound, 1.0, label_visibility="collapsed")
                    modified_params['lower_bound'] = lower

                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("🔙 取消", use_container_width=True):
                        st.session_state.editing_model_id = None
                        st.rerun()
                with col_b:
                    if st.button("🚀 用修改后的参数预测", use_container_width=True):
                        train_start = datetime.combine(st.session_state.train_start_date, datetime.min.time())
                        train_end = datetime.combine(st.session_state.train_end_date, datetime.max.time())

                        # 创建临时配置
                        temp_config = ModelConfig(
                            id="temp",
                            name=config.name,
                            description=config.description,
                            model_type=config.model_type,
                            category=TemplateCategory.CUSTOM,
                            **modified_params
                        )

                        # 临时添加到 manager
                        manager = get_model_config_manager()
                        manager._configs["temp"] = temp_config

                        with st.spinner("正在预测..."):
                            try:
                                results = run_model_comparison(
                                    data,
                                    train_start,
                                    train_end,
                                    ["temp"]
                                )

                                if "temp" in results and results['temp']['success']:
                                    st.success(f"✅ MAPE: {results['temp']['mape']:.2f}%")
                                    # 显示预测结果
                                    prediction = results['temp']['prediction']
                                    fig = go.Figure()
                                    fig.add_trace(go.Scatter(
                                        x=prediction.index,
                                        y=prediction['yhat'],
                                        mode='lines',
                                        name='预测值',
                                        line=dict(color='#4ECDC4')
                                    ))
                                    fig.add_trace(go.Scatter(
                                        x=prediction.index,
                                        y=prediction['yhat_upper'],
                                        mode='lines',
                                        name='上限',
                                        line=dict(color='#FF6B6B', dash='dash'),
                                        fill=None
                                    ))
                                    fig.add_trace(go.Scatter(
                                        x=prediction.index,
                                        y=prediction['yhat_lower'],
                                        mode='lines',
                                        name='下限',
                                        line=dict(color='#FF6B6B', dash='dash'),
                                        fill='tonexty',
                                        fillcolor='rgba(255, 107, 107, 0.1)'
                                    ))
                                    fig.update_layout(
                                        title="预测结果",
                                        xaxis_title="时间",
                                        yaxis_title="值",
                                        height=300,
                                        hovermode='x unified'
                                    )
                                    st.plotly_chart(fig, use_container_width=True)
                                else:
                                    error_msg = results.get('temp', {}).get('error', '未知错误')
                                    st.error(f"❌ 预测失败: {error_msg}")
                            finally:
                                # 清理临时配置
                                manager._configs.pop("temp", None)

                # 保存为新模型
                if config.category == TemplateCategory.SYSTEM or st.session_state.editing_model_id != config.id:
                    st.markdown("---")
                    st.markdown("#### 💾 保存为新模型")

                    new_name = st.text_input("模型名称", value=f"{config.name} (修改)")
                    new_desc = st.text_area("描述", value=f"基于 {config.name} 修改")

                    if st.button("保存模型", use_container_width=True):
                        new_id = f"custom_{datetime.now().strftime('%Y%m%d%H%M%S')}"

                        new_config = ModelConfig(
                            id=new_id,
                            name=new_name,
                            description=new_desc,
                            model_type=config.model_type,
                            category=TemplateCategory.CUSTOM,
                            author="user",
                            color=config.color,
                            tags=["自定义"],
                            **modified_params
                        )

                        manager = get_model_config_manager()
                        if manager.add_config(new_config):
                            st.success(f"✅ 模型保存成功！ID: {new_id}")
                        else:
                            st.error(f"❌ 保存失败")


def _display_model_params(model: ModelConfig) -> None:
    """显示模型参数配置（只读，带悬停提示）"""
    params = model.get_params()

    # 参数帮助信息（与参数优化页面保持一致）
    prophet_help = {
        'daily_seasonality': '是否启用24小时周期模式。适合白天/夜间差异明显的数据（如网站访问量）',
        'weekly_seasonality': '是否启用7天周期模式。适合工作日/周末差异明显的数据（如办公系统负载）',
        'changepoint_prior_scale': '控制趋势变化点的灵活性。0.001-0.01保守，0.05-0.1推荐，0.2-0.5灵活',
        'seasonality_prior_scale': '控制季节性效应的强度。1-5弱，10-20适中（推荐10），25-50强',
        'interval_width': '预测不确定性区间宽度。0.68窄，0.80平衡，0.95宽',
        'n_changepoints': '趋势变化点数量。5-10保守，15-25适中（推荐25），30-100灵活',
        'seasonality_mode': '季节性模式。additive=加性(恒定振幅)，multiplicative=乘性(相对振幅)',
        'holidays_prior_scale': '节假日效应强度。1-5小，10-20推荐，25-50大',
        'changepoint_range': '变点可能出现的比例范围。0.5-0.7保守，0.8-0.9推荐，0.95-1.0敏感',
    }

    welford_help = {
        'sigma_multiplier': 'Sigma倍数控制阈值宽度。1.5-2.5敏感，3推荐，3.5-4宽松',
        'use_rolling_window': '是否使用滚动窗口。适合有趋势的数据，能适应变化',
        'window_size': '滚动窗口大小（分钟）。60-360短期，720-1440中期，2880+长期',
    }

    static_help = {
        'upper_percentile': '上限百分位数。90-95敏感，97-99适中（推荐99），100=最大值',
        'lower_bound': '下限值。计数类指标通常为0，其他根据业务需求设定',
    }

    def param_with_tooltip(label: str, value: str, help_text: str):
        """显示带悬停提示的参数行"""
        html = f"""
        <div class="param-row">
            <div class="param-label">
                <div style="display: inline-flex; align-items: center; gap: 6px;">
                    {label}
                    <div class="tooltip-container">
                        <span class="tooltip-icon">?</span>
                        <span class="tooltip-text">{help_text}</span>
                    </div>
                </div>
            </div>
            <div class="param-value">{value}</div>
        </div>
        """
        st.markdown(html, unsafe_allow_html=True)

    if model.model_type == ModelType.PROPHET:
        # 显示 Prophet 参数
        param_with_tooltip("季节性模式", params.get('seasonality_mode', 'additive'), prophet_help['seasonality_mode'])
        param_with_tooltip("变化点数量", str(params.get('n_changepoints', 25)), prophet_help['n_changepoints'])
        param_with_tooltip("变化点灵活性", f"{params.get('changepoint_prior_scale', 0.05):.3f}", prophet_help['changepoint_prior_scale'])
        param_with_tooltip("季节性强度", f"{params.get('seasonality_prior_scale', 10.0):.1f}", prophet_help['seasonality_prior_scale'])
        param_with_tooltip("置信区间", f"{params.get('interval_width', 0.95):.2f}", prophet_help['interval_width'])
        param_with_tooltip("日季节性", "✅" if params.get('daily_seasonality') else "❌", prophet_help['daily_seasonality'])
        param_with_tooltip("周季节性", "✅" if params.get('weekly_seasonality') else "❌", prophet_help['weekly_seasonality'])

    elif model.model_type == ModelType.WELFORD:
        # 显示 Welford 参数
        param_with_tooltip("Sigma 倍数", f"{params.get('sigma_multiplier', 3.0):.1f}", welford_help['sigma_multiplier'])
        rolling = params.get('use_rolling_window', False)
        param_with_tooltip("滚动窗口", "✅ 启用" if rolling else "❌ 禁用", welford_help['use_rolling_window'])
        if rolling and params.get('window_size'):
            param_with_tooltip("窗口大小", f"{params['window_size']} 分钟", welford_help['window_size'])

    elif model.model_type == ModelType.STATIC:
        # 显示 Static 参数
        param_with_tooltip("上限百分位", f"{params.get('upper_percentile', 99.0):.1f}%", static_help['upper_percentile'])
        param_with_tooltip("下限值", f"{params.get('lower_bound', 0.0):.1f}", static_help['lower_bound'])


def render_models():
    """渲染模型管理页面"""
    st.markdown('<div class="main-header"><h1>🤖 模型管理</h1></div>', unsafe_allow_html=True)

    manager = get_model_config_manager()
    all_models = manager.list_configs()

    # 按分类分组
    system_models = [m for m in all_models if m.category == TemplateCategory.SYSTEM]
    custom_models = [m for m in all_models if m.category == TemplateCategory.CUSTOM]

    # 统计信息
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("总模型数", len(all_models))
    with col2:
        st.metric("系统预设", len(system_models))
    with col3:
        st.metric("自定义模型", len(custom_models))

    st.divider()

    # 系统预设模型
    st.markdown("## 📌 系统预设模型")

    for model in system_models:
        with st.expander(f"### {model.name}"):
            col1, col2 = st.columns([3, 1])

            with col1:
                st.markdown(f"**描述**: {model.description}")
                st.markdown(f"**类型**: {model.model_type.value}")
                st.markdown(f"**标签**: {', '.join(model.tags)}")

            with col2:
                st.markdown(f"**颜色**: {model.color}")

            st.markdown("**参数配置**:")
            _display_model_params(model)

    # 自定义模型
    st.markdown("## 🎨 自定义模型")

    if custom_models:
        for model in custom_models:
            with st.expander(f"### {model.name}", expanded=False):
                col1, col2, col3 = st.columns([3, 1, 1])

                with col1:
                    st.markdown(f"**描述**: {model.description}")
                    st.markdown(f"**类型**: {model.model_type.value}")
                    st.markdown(f"**创建时间**: {model.created_at}")
                    st.markdown(f"**标签**: {', '.join(model.tags)}")

                with col2:
                    if st.button("✏️ 编辑", key=f"edit_{model.id}", use_container_width=True):
                        st.session_state.editing_model_id = model.id
                        st.rerun()

                with col3:
                    if st.button("🗑️ 删除", key=f"delete_{model.id}", use_container_width=True):
                        if manager.delete_config(model.id):
                            st.success(f"已删除 {model.name}")
                            st.rerun()

                st.markdown("**参数配置**:")
                _display_model_params(model)
    else:
        st.info("还没有自定义模型，请到仪表盘页面创建")

    # 编辑模型
    if st.session_state.editing_model_id:
        st.divider()
        st.markdown("## ✏️ 编辑模型")

        model = manager.get_config(st.session_state.editing_model_id)

        if model and model.category == TemplateCategory.CUSTOM:
            col1, col2 = st.columns([1, 1])

            with col1:
                new_name = st.text_input("模型名称", value=model.name)
                new_desc = st.text_area("描述", value=model.description)

                # 参数编辑
                st.markdown("**修改参数**")

                updated_params = {}

                if model.model_type == ModelType.PROPHET:
                    updated_params['daily_seasonality'] = st.checkbox("日季节性", model.daily_seasonality)
                    updated_params['changepoint_prior_scale'] = st.slider("变化点先验", 0.001, 0.5, model.changepoint_prior_scale, 0.001)
                    updated_params['seasonality_prior_scale'] = st.slider("季节性先验", 1.0, 50.0, model.seasonality_prior_scale, 0.5)
                    updated_params['interval_width'] = st.slider("置信区间", 0.1, 0.99, model.interval_width, 0.01)

                elif model.model_type == ModelType.WELFORD:
                    updated_params['sigma_multiplier'] = st.slider("Sigma 倍数", 1.0, 5.0, model.sigma_multiplier, 0.1)
                    updated_params['use_rolling_window'] = st.checkbox("滚动窗口", model.use_rolling_window)
                    if updated_params['use_rolling_window']:
                        updated_params['window_size'] = st.slider("窗口大小", 60, 10080, model.window_size or 1440, 60)

                elif model.model_type == ModelType.STATIC:
                    updated_params['upper_percentile'] = st.slider("上限百分位", 90.0, 100.0, model.upper_percentile, 0.5)
                    updated_params['lower_bound'] = st.slider("下限值", 0.0, 100.0, model.lower_bound, 1.0)

            with col2:
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("❌ 取消", use_container_width=True):
                        st.session_state.editing_model_id = None
                        st.rerun()
                with col_b:
                    if st.button("💾 保存修改", type="primary", use_container_width=True):
                        # 更新配置
                        manager.update_config(model.id, {
                            **updated_params,
                            'name': new_name,
                            'description': new_desc,
                        })
                        st.success("✅ 模型已更新")
                        st.session_state.editing_model_id = None
                        st.rerun()


def render_datasources():
    """渲染数据源管理页面"""
    st.markdown('<div class="main-header"><h1>🔌 数据源管理</h1></div>', unsafe_allow_html=True)

    st.markdown("### 当前数据源")

    # 数据源列表
    for ds_id, ds_config in st.session_state.datasources.items():
        with st.expander(f"### {ds_config.name} {'✅ (当前)' if ds_id == st.session_state.current_datasource else ''}", expanded=ds_id == st.session_state.current_datasource):
            col1, col2, col3 = st.columns([3, 1, 1])

            with col1:
                st.markdown(f"**类型**: {ds_config.source_type.value}")
                st.markdown(f"**URL**: `{ds_config.url}`")

            with col2:
                if ds_id != st.session_state.current_datasource:
                    if st.button("设为默认", key=f"set_{ds_id}"):
                        st.session_state.current_datasource = ds_id
                        st.rerun()

            with col3:
                if ds_id != 'mock':  # 不允许删除 mock 数据源
                    if st.button("删除", key=f"delete_ds_{ds_id}"):
                        del st.session_state.datasources[ds_id]
                        if st.session_state.current_datasource == ds_id:
                            st.session_state.current_datasource = 'mock'
                        st.rerun()

    st.divider()

    # 添加新数据源
    st.markdown("### ➕ 添加数据源")

    with st.form("add_datasource"):
        new_name = st.text_input("名称", placeholder="my-prometheus")
        new_url = st.text_input("URL", placeholder="http://localhost:9090")

        submitted = st.form_submit_button("添加", use_container_width=True)

        if submitted and new_name and new_url:
            # 检查 ID 是否已存在
            ds_id = new_name.lower().replace(' ', '_')
            if ds_id in st.session_state.datasources:
                st.error(f"数据源 '{new_name}' 已存在")
            else:
                st.session_state.datasources[ds_id] = DataSourceConfig(
                    name=new_name,
                    source_type=DataSourceType.PROMETHEUS,
                    url=new_url
                )
                st.success(f"✅ 数据源 '{new_name}' 添加成功")
                st.rerun()


# ==================== 主函数 ====================

def main():
    # 渲染侧边栏
    render_sidebar()

    # 根据当前页面渲染内容
    if st.session_state.current_page == 'dashboard':
        render_dashboard()
    elif st.session_state.current_page == 'models':
        render_models()
    elif st.session_state.current_page == 'datasources':
        render_datasources()


if __name__ == "__main__":
    main()
