"""
SmartThreshold 模型展示页面

功能：
1. 展示所有预测模型及其完整参数
2. 支持动态调整参数
3. 可设置预测时长
4. 实时预览预测结果
5. 详细的参数帮助信息
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from smart_threshold.core.predictors.prophet_predictor import ProphetPredictor
from smart_threshold.core.predictors.welford_predictor import WelfordPredictor
from smart_threshold.core.predictors.static_predictor import StaticPredictor
from smart_threshold.data.generator import DataGenerator, ScenarioType
from smart_threshold.core.feature_analyzer import FeatureExtractor
from smart_threshold.core.model_router import ModelRouter


# ==================== 页面配置 ====================

st.set_page_config(
    page_title="模型展示 - SmartThreshold",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 自定义 CSS - 参考 time-art 风格
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
    .model-card {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        border-left: 4px solid #667eea;
    }
    .params-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
        gap: 1rem;
        margin-top: 1rem;
    }
    .param-group {
        background: #f8f9ff;
        border: 2px solid #e0e0e0;
        border-radius: 10px;
        padding: 0.75rem 1rem;
        transition: all 0.2s;
    }
    .param-group:hover {
        border-color: #667eea;
        background: #f0f3ff;
    }
    .param-label-wrapper {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 0.5rem;
    }
    .param-label {
        font-weight: 600;
        color: #333;
        font-size: 0.9rem;
    }
    .help-icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 18px;
        height: 18px;
        border-radius: 50%;
        background: #667eea;
        color: white;
        font-size: 12px;
        font-weight: bold;
        cursor: help;
        position: relative;
    }
    .help-tooltip {
        visibility: hidden;
        opacity: 0;
        position: absolute;
        bottom: 100%;
        left: 50%;
        transform: translateX(-50%);
        background: #333;
        color: white;
        padding: 0.5rem 0.75rem;
        border-radius: 6px;
        font-size: 0.8rem;
        white-space: nowrap;
        z-index: 1000;
        transition: all 0.2s;
        margin-bottom: 5px;
        min-width: 200px;
        line-height: 1.4;
    }
    .help-icon:hover .help-tooltip {
        visibility: visible;
        opacity: 1;
    }
    .metric-highlight {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-weight: bold;
        display: inline-block;
        margin: 0.25rem;
    }
    .range-low {
        color: #4CAF50;
        font-weight: 600;
    }
    .range-medium {
        color: #FF9800;
        font-weight: 600;
    }
    .range-high {
        color: #F44336;
        font-weight: 600;
    }
    .help-detail {
        background: #e7f3ff;
        border-left: 3px solid #2196F3;
        padding: 1rem;
        border-radius: 6px;
        margin-top: 0.5rem;
        font-size: 0.85rem;
        line-height: 1.5;
    }
    .help-detail-title {
        font-weight: 600;
        color: #0D47A1;
        margin-bottom: 0.5rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    [data-testid="stMarkdown"] p {
        margin-bottom: 0.25rem;
    }
    /* 参数表格样式 - 使用更高优先级选择器 */
    div[data-testid="stMarkdown"] table.param-table {
        width: 100% !important;
        border-collapse: separate !important;
        border-spacing: 0 !important;
        margin-top: 1rem !important;
        border: none !important;
    }
    div[data-testid="stMarkdown"] table.param-table th {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
        padding: 0.8rem 1rem !important;
        text-align: left !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        letter-spacing: 0.5px !important;
        border: none !important;
    }
    div[data-testid="stMarkdown"] table.param-table th:first-child {
        border-radius: 10px 0 0 0 !important;
    }
    div[data-testid="stMarkdown"] table.param-table th:last-child {
        border-radius: 0 10px 0 0 !important;
    }
    div[data-testid="stMarkdown"] table.param-table td {
        padding: 0.75rem 1rem !important;
        border-bottom: 1px solid #f0f0f0 !important;
        border: none !important;
    }
    div[data-testid="stMarkdown"] table.param-table tr:last-child td:first-child {
        border-radius: 0 0 0 10px !important;
    }
    div[data-testid="stMarkdown"] table.param-table tr:last-child td:last-child {
        border-radius: 0 0 10px 0 !important;
    }
    div[data-testid="stMarkdown"] table.param-table tbody tr:hover {
        background: #f8f9ff !important;
    }
    div[data-testid="stMarkdown"] table.param-table td:first-child {
        font-weight: 500 !important;
        color: #555 !important;
        font-size: 0.9rem !important;
    }
    div[data-testid="stMarkdown"] table.param-table td:last-child {
        text-align: center !important;
        background: #fafafa !important;
    }
    /* 数字方框样式 */
    span.digit-box {
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        min-width: 60px !important;
        height: 36px !important;
        padding: 0 12px !important;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
        border-radius: 8px !important;
        font-weight: 700 !important;
        font-size: 1.1rem !important;
        box-shadow: 0 3px 10px rgba(102, 126, 234, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.2) !important;
        letter-spacing: 0.5px !important;
        margin: 0 !important;
    }
    span.digit-box.secondary {
        background: linear-gradient(135deg, #28a745 0%, #20c997 100%) !important;
        box-shadow: 0 3px 10px rgba(40, 167, 69, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.2) !important;
    }
    span.digit-box.string {
        background: linear-gradient(135deg, #17a2b8 0%, #138496 100%) !important;
        box-shadow: 0 3px 10px rgba(23, 162, 184, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.2) !important;
        font-size: 0.95rem !important;
        font-weight: 600 !important;
        min-width: auto !important;
    }
    /* 勾选框样式 */
    span.check-box {
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        width: 28px !important;
        height: 28px !important;
        border-radius: 6px !important;
        font-weight: bold !important;
        font-size: 16px !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.3) !important;
        margin: 0 !important;
    }
    span.check-box.checked {
        background: linear-gradient(135deg, #28a745 0%, #20c997 100%) !important;
        color: white !important;
    }
    span.check-box.unchecked {
        background: linear-gradient(135deg, #dc3545 0%, #c82333 100%) !important;
        color: white !important;
    }
    /* 胶囊样式 */
    span.bool-pill {
        display: inline-flex !important;
        align-items: center !important;
        gap: 8px !important;
        padding: 6px 14px !important;
        border-radius: 20px !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1) !important;
        margin: 0 !important;
    }
    span.bool-pill.enabled {
        background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%) !important;
        color: #155724 !important;
        border: 1px solid #b8dabc !important;
    }
    span.bool-pill.disabled {
        background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%) !important;
        color: #721c24 !important;
        border: 1px solid #f1b2b7 !important;
    }
</style>
""", unsafe_allow_html=True)


# ==================== 参数帮助信息字典 ====================

PROPHET_PARAMS = {
    'growth': {
        'label': '增长类型',
        'help': '''指定时间序列的增长趋势类型<br>
<b>取值:</b><br>
• <b>linear:</b> 持续线性增长（默认）<br>
• <b>logistic:</b> 饱和生长（S型曲线）<br>
• <b>flat:</b> 平稳无趋势<br><br>
<b>场景:</b><br>
• linear - 用户增长、收入预测<br>
• logistic - 市场饱和、资源受限<br>
• flat - 温度、平稳波动数据'''
    },
    'n_changepoints': {
        'label': '变点数量',
        'help': '''趋势变化点的最大数量，控制模型对趋势变化的敏感度<br>
<b>取值范围:</b> 0~100<br>
• <span class="range-low">【低】5-10:</span> 趋势稳定，保守，变化缓慢<br>
• <span class="range-medium">【中】15-25:</span> 适中灵活性，默认推荐25<br>
• <span class="range-high">【高】30-100:</span> 高度灵活，可能过拟合'''
    },
    'changepoint_range': {
        'label': '变点范围',
        'help': '''变点可能出现在历史数据的哪个比例范围内<br>
<b>取值范围:</b> 0.5~1.0<br>
• <span class="range-low">【低】0.5-0.7:</span> 更保守，只在早期检测<br>
• <span class="range-medium">【中】0.8-0.9:</span> 默认推荐0.8<br>
• <span class="range-high">【高】0.95-1.0:</span> 更敏感，全部历史'''
    },
    'seasonality_mode': {
        'label': '季节性模式',
        'help': '''季节性效应与趋势的组合方式<br>
<b>取值:</b><br>
• <b>additive (加性):</b> 波动幅度恒定<br>
  适合: 温度、CPU使用率<br>
• <b>multiplicative (乘性):</b> 波动随趋势增长<br>
  适合: 用户访问量、收入'''
    },
    'seasonality_prior_scale': {
        'label': '季节性强度',
        'help': '''控制季节性效应的强度<br>
<b>取值范围:</b> 0~50<br>
• <span class="range-low">【低】1-5:</span> 弱季节性<br>
• <span class="range-medium">【中】10-20:</span> 适中，默认推荐10<br>
• <span class="range-high">【高】25-50:</span> 强季节性'''
    },
    'holidays_prior_scale': {
        'label': '节假日强度',
        'help': '''控制节假日效应的强度<br>
<b>取值范围:</b> 0~50<br>
• <span class="range-low">【低】1-5:</span> 节假日影响小<br>
• <span class="range-medium">【中】10-20:</span> 默认推荐10<br>
• <span class="range-high">【高】25-50:</span> 节假日影响大'''
    },
    'changepoint_prior_scale': {
        'label': '变点灵活性',
        'help': '''控制趋势变化点的灵活性<br>
<b>取值范围:</b> 0.001~0.5<br>
• <span class="range-low">【低】0.001-0.01:</span> 保守，变化缓慢<br>
• <span class="range-medium">【中】0.05-0.1:</span> 默认推荐0.05<br>
• <span class="range-high">【高】0.2-0.5:</span> 灵活，可能过拟合'''
    },
    'interval_width': {
        'label': '置信区间',
        'help': '''预测不确定性区间的宽度<br>
<b>取值范围:</b> 0.1~0.99<br>
• <span class="range-low">【低】0.68:</span> 68%置信区间，较窄<br>
• <span class="range-medium">【中】0.80:</span> 80%置信区间<br>
• <span class="range-high">【高】0.95:</span> 95%置信区间'''
    },
    'daily_seasonality': {
        'label': '日季节性',
        'help': '''是否启用24小时周期模式<br>
<b>适用:</b> 白天/夜间差异明显<br>
<b>示例:</b> 网站访问量、API调用量'''
    },
    'weekly_seasonality': {
        'label': '周季节性',
        'help': '''是否启用7天周期模式<br>
<b>适用:</b> 工作日/周末差异明显<br>
<b>示例:</b> 办公系统负载、企业应用'''
    },
    'yearly_seasonality': {
        'label': '年季节性',
        'help': '''是否启用365天周期模式<br>
<b>要求:</b> 至少1年数据<br>
<b>适用:</b> 季节性业务、年度规律'''
    },
    'add_monthly_seasonality': {
        'label': '月度季节性',
        'help': '''是否添加30.5天周期模式<br>
<b>适用:</b> 月初/月末效应、账单周期<br>
<b>注意:</b> 增加复杂度，仅在确有月度规律时使用'''
    },
    'enforce_non_negative': {
        'label': '强制非负',
        'help': '''强制预测值非负<br>
<b>适用:</b> CPU、内存、请求数、销售等不可能为负的指标<br>
<b>作用:</b> 负预测值截断为0'''
    },
}

WELFORD_PARAMS = {
    'confidence_level': {
        'label': '置信水平',
        'help': '''置信水平对应不同的 Sigma 倍数<br>
<b>映射关系:</b><br>
• 68% → 1-Sigma（稳定系统）<br>
• 90% → 1.645-Sigma<br>
• 95% → 1.96-Sigma<br>
• 99% → 2.576-Sigma<br>
• <b>99.7% → 3-Sigma（默认推荐）</b>'''
    },
    'use_rolling_window': {
        'label': '滚动窗口',
        'help': '''是否使用滚动窗口计算统计量<br>
<b>启用:</b> 适合有趋势的数据，能适应变化<br>
<b>禁用:</b> 适合平稳数据，更稳定'''
    },
    'window_size': {
        'label': '窗口大小',
        'help': '''滚动窗口的大小（分钟）<br>
<b>取值范围:</b> 60~10080<br>
• <span class="range-low">【低】60-360:</span> 1-6小时，短期变化<br>
• <span class="range-medium">【中】720-1440:</span> 12-24小时，默认1440<br>
• <span class="range-high">【高】2880-10080:</span> 2-7天，长期趋势'''
    },
}

STATIC_PARAMS = {
    'upper_percentile': {
        'label': '上限百分位',
        'help': '''使用历史数据的哪个百分位数作为上限阈值<br>
<b>取值范围:</b> 90~100<br>
• <span class="range-low">【低】90-95:</span> 更敏感，更多告警<br>
• <span class="range-medium">【中】97-99:</span> 适中，默认推荐99<br>
• <span class="range-high">【高】99.5-100:</span> 只检测极值'''
    },
    'lower_bound': {
        'label': '下限值',
        'help': '''下限阈值（计数类指标不能为负）<br>
<b>通常设置:</b> 0<br>
<b>说明:</b> 错误计数、告警数等不可能为负'''
    },
    'confidence_level': {
        'label': '置信水平',
        'help': '''置信水平，用于报告显示<br>
<b>说明:</b> 实际阈值由 upper_percentile 决定<br>
<b>取值范围:</b> 0.90~0.999'''
    },
}


# ==================== Session State 初始化 ====================

def init_session_state():
    """初始化 session state"""
    if 'generated_data' not in st.session_state:
        st.session_state.generated_data = None
    if 'selected_scenario' not in st.session_state:
        st.session_state.selected_scenario = ScenarioType.QPS
    if 'selected_model' not in st.session_state:
        st.session_state.selected_model = 'prophet'
    if 'prediction_days' not in st.session_state:
        st.session_state.prediction_days = 1
    if 'prediction_hours' not in st.session_state:
        st.session_state.prediction_hours = 0
    if 'prophet_params' not in st.session_state:
        st.session_state.prophet_params = {
            'growth': 'linear',
            'n_changepoints': 25,
            'changepoint_range': 0.8,
            'seasonality_mode': 'additive',
            'seasonality_prior_scale': 10.0,
            'holidays_prior_scale': 10.0,
            'changepoint_prior_scale': 0.05,
            'interval_width': 0.95,
            'daily_seasonality': True,
            'weekly_seasonality': False,
            'yearly_seasonality': False,
            'add_monthly_seasonality': False,
            'enforce_non_negative': True,
        }
    if 'welford_params' not in st.session_state:
        st.session_state.welford_params = {
            'confidence_level': 0.997,
            'use_rolling_window': False,
            'window_size': 1440,
        }
    if 'static_params' not in st.session_state:
        st.session_state.static_params = {
            'upper_percentile': 99.0,
            'confidence_level': 0.99,
            'lower_bound': 0.0,
        }
    if 'prediction_result' not in st.session_state:
        st.session_state.prediction_result = None
    if 'feature_result' not in st.session_state:
        st.session_state.feature_result = None


init_session_state()


# ==================== 辅助函数 ====================

def generate_data(scenario: ScenarioType, days: int = 7) -> pd.Series:
    """生成模拟数据"""
    generator = DataGenerator(freq="1min", seed=42)
    return generator.generate(scenario, days=days)


def analyze_features(data: pd.Series) -> Dict:
    """分析数据特征"""
    extractor = FeatureExtractor()
    features = extractor.analyze(data)
    return features


def render_param_help(param_key: str, params_dict: dict):
    """渲染参数帮助信息"""
    if param_key not in params_dict:
        return

    param_info = params_dict[param_key]
    st.markdown(f"""
    <div class="help-detail">
        <div class="help-detail-title">💡 {param_info['label']}</div>
        {param_info['help']}
    </div>
    """, unsafe_allow_html=True)


def create_prediction_chart(
    train_data: pd.Series,
    prediction: 'PredictionResult',
    title: str = "预测结果"
) -> go.Figure:
    """创建预测图表"""
    fig = go.Figure()

    # 训练数据
    fig.add_trace(go.Scatter(
        x=train_data.index,
        y=train_data.values,
        mode='lines',
        name='训练数据',
        line=dict(color='#2C3E50', width=1.5),
        hovertemplate='%{x}<br>值: %{y:.2f}<extra></extra>'
    ))

    # 预测值
    fig.add_trace(go.Scatter(
        x=prediction.ds,
        y=prediction.yhat,
        mode='lines',
        name='预测值',
        line=dict(color='#667eea', width=2, dash='solid'),
        hovertemplate='%{x}<br>预测: %{y:.2f}<extra></extra>'
    ))

    # 置信区间
    fig.add_trace(go.Scatter(
        x=prediction.ds.tolist() + prediction.ds[::-1].tolist(),
        y=prediction.yhat_upper.tolist() + prediction.yhat_lower[::-1].tolist(),
        fill='toself',
        fillcolor='rgba(102, 126, 234, 0.2)',
        line=dict(color='rgba(0,0,0,0)'),
        name=f'{int(prediction.confidence_level*100)}% 置信区间',
        hoverinfo='skip'
    ))

    # 预测上限
    fig.add_trace(go.Scatter(
        x=prediction.ds,
        y=prediction.yhat_upper,
        mode='lines',
        name='上限',
        line=dict(color='#e74c3c', width=1, dash='dash'),
        hovertemplate='%{x}<br>上限: %{y:.2f}<extra></extra>'
    ))

    # 预测下限
    fig.add_trace(go.Scatter(
        x=prediction.ds,
        y=prediction.yhat_lower,
        mode='lines',
        name='下限',
        line=dict(color='#27ae60', width=1, dash='dash'),
        hovertemplate='%{x}<br>下限: %{y:.2f}<extra></extra>'
    ))

    fig.update_layout(
        title=title,
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


def create_feature_badge(label: str, value: str, color: str = "#667eea") -> str:
    """创建特征徽章"""
    return f'<span class="metric-highlight" style="background: {color}">{label}: {value}</span>'


# ==================== 侧边栏 ====================

def render_sidebar():
    """渲染侧边栏"""
    with st.sidebar:
        st.markdown("# 🤖 模型展示")
        st.divider()

        # 数据生成
        st.markdown("## 📊 数据生成")
        scenario_options = {
            ScenarioType.QPS: "QPS (有季节性)",
            ScenarioType.RT: "RT (高波动)",
            ScenarioType.ERROR_COUNT: "错误计数 (稀疏)",
        }
        selected_scenario = st.selectbox(
            "选择场景",
            options=list(scenario_options.keys()),
            format_func=lambda x: scenario_options[x],
            index=list(scenario_options.keys()).index(st.session_state.selected_scenario)
        )
        st.session_state.selected_scenario = selected_scenario

        train_days = st.slider("训练天数", 3, 14, 7)

        if st.button("🔄 生成数据", type="primary", use_container_width=True):
            with st.spinner("正在生成数据..."):
                data = generate_data(selected_scenario, days=train_days)
                st.session_state.generated_data = data
                features = analyze_features(data)
                st.session_state.feature_result = features
                st.session_state.prediction_result = None
            st.success(f"✅ 生成了 {len(data)} 个数据点")
            st.rerun()

        st.divider()

        # 预测时长设置
        st.markdown("## ⏱️ 预测时长")
        col1, col2 = st.columns(2)
        with col1:
            days = st.number_input("天数", min_value=0, max_value=7, value=st.session_state.prediction_days)
            st.session_state.prediction_days = days
        with col2:
            hours = st.number_input("小时", min_value=0, max_value=23, value=st.session_state.prediction_hours)
            st.session_state.prediction_hours = hours

        total_minutes = days * 1440 + hours * 60
        st.info(f"📅 总计: {total_minutes:,} 分钟 ({days}天 {hours}小时)")

        st.divider()

        # 模型选择
        st.markdown("## 🎯 模型选择")
        model_options = {
            'prophet': 'Prophet 预测器',
            'welford': 'Welford 预测器',
            'static': 'Static 预测器',
        }
        selected_model = st.radio(
            "选择模型",
            options=list(model_options.keys()),
            format_func=lambda x: model_options[x],
            index=list(model_options.keys()).index(st.session_state.selected_model)
        )
        st.session_state.selected_model = selected_model

        # 快捷预设
        st.markdown("### ⚡ 快捷预设")
        if st.button("恢复默认参数", use_container_width=True):
            if selected_model == 'prophet':
                st.session_state.prophet_params = {
                    'growth': 'linear',
                    'n_changepoints': 25,
                    'changepoint_range': 0.8,
                    'seasonality_mode': 'additive',
                    'seasonality_prior_scale': 10.0,
                    'holidays_prior_scale': 10.0,
                    'changepoint_prior_scale': 0.05,
                    'interval_width': 0.95,
                    'daily_seasonality': True,
                    'weekly_seasonality': False,
                    'yearly_seasonality': False,
                    'add_monthly_seasonality': False,
                    'enforce_non_negative': True,
                }
            elif selected_model == 'welford':
                st.session_state.welford_params = {
                    'confidence_level': 0.997,
                    'use_rolling_window': False,
                    'window_size': 1440,
                }
            elif selected_model == 'static':
                st.session_state.static_params = {
                    'upper_percentile': 99.0,
                    'confidence_level': 0.99,
                    'lower_bound': 0.0,
                }
            st.success("✅ 已恢复默认参数")
            st.rerun()

        st.divider()

        # 根据数据特征推荐
        if st.session_state.generated_data is not None:
            st.markdown("## 💡 智能推荐")
            features = st.session_state.feature_result

            if features:
                if features.has_seasonality:
                    st.success("🎯 检测到季节性，推荐使用 **Prophet**")
                elif features.sparsity_ratio > 0.9:
                    st.success("🎯 检测到稀疏数据，推荐使用 **Static**")
                else:
                    st.success("🎯 检测到高波动数据，推荐使用 **Welford**")


# ==================== 参数面板 ====================

def render_prophet_params():
    """渲染 Prophet 参数面板"""
    st.markdown('<div class="model-card">', unsafe_allow_html=True)
    st.markdown("### 📈 Prophet 预测器")
    st.markdown("*基于 Facebook Prophet 的时间序列预测，适合具有明显季节性的数据*")

    params = st.session_state.prophet_params

    st.markdown('<div class="params-grid">', unsafe_allow_html=True)

    # 增长类型
    st.markdown('<div class="param-group">', unsafe_allow_html=True)
    growth = st.selectbox(
        PROPHET_PARAMS['growth']['label'],
        ['linear', 'logistic', 'flat'],
        index=['linear', 'logistic', 'flat'].index(params.get('growth', 'linear')),
        label_visibility="collapsed"
    )
    st.session_state.prophet_params['growth'] = growth
    st.markdown('</div>', unsafe_allow_html=True)

    # 预测周期数（在侧边栏设置，这里显示帮助）
    render_param_help('growth', PROPHET_PARAMS)

    # 变点数量
    st.markdown('<div class="param-group">', unsafe_allow_html=True)
    n_cp = st.slider(
        PROPHET_PARAMS['n_changepoints']['label'],
        0, 100, params.get('n_changepoints', 25),
        label_visibility="collapsed"
    )
    st.session_state.prophet_params['n_changepoints'] = n_cp
    st.markdown('</div>', unsafe_allow_html=True)
    render_param_help('n_changepoints', PROPHET_PARAMS)

    # 变点范围
    st.markdown('<div class="param-group">', unsafe_allow_html=True)
    cp_range = st.slider(
        PROPHET_PARAMS['changepoint_range']['label'],
        0.5, 1.0, params.get('changepoint_range', 0.8), 0.05,
        label_visibility="collapsed"
    )
    st.session_state.prophet_params['changepoint_range'] = cp_range
    st.markdown('</div>', unsafe_allow_html=True)
    render_param_help('changepoint_range', PROPHET_PARAMS)

    # 季节性模式
    st.markdown('<div class="param-group">', unsafe_allow_html=True)
    season_mode = st.selectbox(
        PROPHET_PARAMS['seasonality_mode']['label'],
        ['additive', 'multiplicative'],
        index=['additive', 'multiplicative'].index(params.get('seasonality_mode', 'additive')),
        label_visibility="collapsed"
    )
    st.session_state.prophet_params['seasonality_mode'] = season_mode
    st.markdown('</div>', unsafe_allow_html=True)
    render_param_help('seasonality_mode', PROPHET_PARAMS)

    # 季节性强度
    st.markdown('<div class="param-group">', unsafe_allow_html=True)
    season_prior = st.slider(
        PROPHET_PARAMS['seasonality_prior_scale']['label'],
        0.0, 50.0, params.get('seasonality_prior_scale', 10.0), 0.5,
        label_visibility="collapsed"
    )
    st.session_state.prophet_params['seasonality_prior_scale'] = season_prior
    st.markdown('</div>', unsafe_allow_html=True)
    render_param_help('seasonality_prior_scale', PROPHET_PARAMS)

    # 变点灵活性
    st.markdown('<div class="param-group">', unsafe_allow_html=True)
    cp_prior = st.slider(
        PROPHET_PARAMS['changepoint_prior_scale']['label'],
        0.001, 0.5, params.get('changepoint_prior_scale', 0.05), 0.001,
        label_visibility="collapsed"
    )
    st.session_state.prophet_params['changepoint_prior_scale'] = cp_prior
    st.markdown('</div>', unsafe_allow_html=True)
    render_param_help('changepoint_prior_scale', PROPHET_PARAMS)

    # 置信区间
    st.markdown('<div class="param-group">', unsafe_allow_html=True)
    interval = st.slider(
        PROPHET_PARAMS['interval_width']['label'],
        0.1, 0.99, params.get('interval_width', 0.95), 0.01,
        label_visibility="collapsed"
    )
    st.session_state.prophet_params['interval_width'] = interval
    st.markdown('</div>', unsafe_allow_html=True)
    render_param_help('interval_width', PROPHET_PARAMS)

    st.markdown('</div>', unsafe_allow_html=True)  # end params-grid

    st.markdown('---')
    st.markdown('#### 📅 季节性设置')

    col1, col2, col3 = st.columns(3)
    with col1:
        daily = st.checkbox("日季节性", value=params.get('daily_seasonality', True))
        st.session_state.prophet_params['daily_seasonality'] = daily
        render_param_help('daily_seasonality', PROPHET_PARAMS)
    with col2:
        weekly = st.checkbox("周季节性", value=params.get('weekly_seasonality', False))
        st.session_state.prophet_params['weekly_seasonality'] = weekly
        render_param_help('weekly_seasonality', PROPHET_PARAMS)
    with col3:
        yearly = st.checkbox("年季节性", value=params.get('yearly_seasonality', False))
        st.session_state.prophet_params['yearly_seasonality'] = yearly
        render_param_help('yearly_seasonality', PROPHET_PARAMS)

    st.markdown('---')
    col1, col2 = st.columns(2)
    with col1:
        monthly = st.checkbox("添加月度季节性", value=params.get('add_monthly_seasonality', False))
        st.session_state.prophet_params['add_monthly_seasonality'] = monthly
        render_param_help('add_monthly_seasonality', PROPHET_PARAMS)
    with col2:
        non_negative = st.checkbox("强制非负值", value=params.get('enforce_non_negative', True))
        st.session_state.prophet_params['enforce_non_negative'] = non_negative
        render_param_help('enforce_non_negative', PROPHET_PARAMS)

    # 参数摘要
    st.markdown('---')
    st.markdown('##### 📋 当前参数值')

    def bool_html(value: bool) -> str:
        check = '<span class="check-box checked">✓</span>' if value else '<span class="check-box unchecked">✗</span>'
        label = '启用' if value else '禁用'
        cls = 'enabled' if value else 'disabled'
        return f'<span class="bool-pill {cls}">{check} {label}</span>'

    # 从 session_state 获取最新参数值
    current_params = st.session_state.prophet_params

    param_summary = f"""
    <table class="param-table">
        <thead>
            <tr><th>参数</th><th>值</th></tr>
        </thead>
        <tbody>
            <tr><td>增长类型</td><td><span class="digit-box string">{current_params.get('growth', growth)}</span></td></tr>
            <tr><td>变点数量</td><td><span class="digit-box">{current_params.get('n_changepoints', n_cp)}</span></td></tr>
            <tr><td>变点范围</td><td><span class="digit-box">{current_params.get('changepoint_range', cp_range)}</span></td></tr>
            <tr><td>季节性模式</td><td><span class="digit-box string">{current_params.get('seasonality_mode', season_mode)}</span></td></tr>
            <tr><td>季节性强度</td><td><span class="digit-box">{current_params.get('seasonality_prior_scale', season_prior)}</span></td></tr>
            <tr><td>变点灵活性</td><td><span class="digit-box">{current_params.get('changepoint_prior_scale', cp_prior)}</span></td></tr>
            <tr><td>置信区间</td><td><span class="digit-box">{current_params.get('interval_width', interval):.0%}</span></td></tr>
            <tr><td>日季节性</td><td>{bool_html(current_params.get('daily_seasonality', daily))}</td></tr>
            <tr><td>周季节性</td><td>{bool_html(current_params.get('weekly_seasonality', weekly))}</td></tr>
            <tr><td>年季节性</td><td>{bool_html(current_params.get('yearly_seasonality', yearly))}</td></tr>
            <tr><td>月度季节性</td><td>{bool_html(current_params.get('add_monthly_seasonality', monthly))}</td></tr>
            <tr><td>强制非负</td><td>{bool_html(current_params.get('enforce_non_negative', non_negative))}</td></tr>
        </tbody>
    </table>
    """
    st.markdown(param_summary, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


def render_welford_params():
    """渲染 Welford 参数面板"""
    st.markdown('<div class="model-card">', unsafe_allow_html=True)
    st.markdown("### 📊 Welford 预测器")
    st.markdown("*基于 Welford 在线算法的 3-Sigma 动态阈值，适合高波动、无周期的数据*")

    params = st.session_state.welford_params

    st.markdown('<div class="params-grid">', unsafe_allow_html=True)

    # 置信水平
    st.markdown('<div class="param-group">', unsafe_allow_html=True)
    confidence_options = {
        0.68: "68% (1-Sigma)",
        0.90: "90% (1.645-Sigma)",
        0.95: "95% (1.96-Sigma)",
        0.99: "99% (2.576-Sigma)",
        0.997: "99.7% (3-Sigma)",
    }
    conf_label = st.selectbox(
        WELFORD_PARAMS['confidence_level']['label'],
        options=list(confidence_options.keys()),
        format_func=lambda x: confidence_options[x],
        index=list(confidence_options.keys()).index(params.get('confidence_level', 0.997)),
        label_visibility="collapsed"
    )
    st.session_state.welford_params['confidence_level'] = conf_label
    st.markdown('</div>', unsafe_allow_html=True)
    render_param_help('confidence_level', WELFORD_PARAMS)

    # 滚动窗口
    st.markdown('<div class="param-group">', unsafe_allow_html=True)
    use_rolling = st.checkbox(
        WELFORD_PARAMS['use_rolling_window']['label'],
        value=params.get('use_rolling_window', False),
        label_visibility="collapsed"
    )
    st.session_state.welford_params['use_rolling_window'] = use_rolling
    st.markdown('</div>', unsafe_allow_html=True)
    render_param_help('use_rolling_window', WELFORD_PARAMS)

    # 窗口大小
    if use_rolling:
        st.markdown('<div class="param-group">', unsafe_allow_html=True)
        window_size = st.slider(
            WELFORD_PARAMS['window_size']['label'],
            60, 10080, params.get('window_size', 1440), 60,
            label_visibility="collapsed"
        )
        st.session_state.welford_params['window_size'] = window_size
        st.markdown('</div>', unsafe_allow_html=True)
        render_param_help('window_size', WELFORD_PARAMS)

    st.markdown('</div>', unsafe_allow_html=True)

    # 参数摘要
    st.markdown('---')
    sigma_map = {0.68: 1.0, 0.90: 1.645, 0.95: 1.96, 0.99: 2.576, 0.997: 3.0}
    sigma_val = sigma_map.get(conf_label, 3.0)

    def bool_html(value: bool) -> str:
        check = '<span class="check-box checked">✓</span>' if value else '<span class="check-box unchecked">✗</span>'
        label = '启用' if value else '禁用'
        cls = 'enabled' if value else 'disabled'
        return f'<span class="bool-pill {cls}">{check} {label}</span>'

    # 从 session_state 获取最新参数值
    current_params = st.session_state.welford_params

    param_summary = f"""
    <table class="param-table">
        <thead>
            <tr><th>参数</th><th>值</th></tr>
        </thead>
        <tbody>
            <tr><td>置信水平</td><td><span class="digit-box">{current_params.get('confidence_level', conf_label):.1%}</span></td></tr>
            <tr><td>Sigma 倍数</td><td><span class="digit-box secondary">{sigma_val}</span></td></tr>
            <tr><td>滚动窗口</td><td>{bool_html(current_params.get('use_rolling_window', use_rolling))}</td></tr>
            <tr><td>窗口大小</td><td><span class="digit-box">{current_params.get('window_size', params.get('window_size', 1440)) if current_params.get('use_rolling_window', use_rolling) else '-'} min</span></td></tr>
        </tbody>
    </table>
    """
    st.markdown(param_summary, unsafe_allow_html=True)

    # 阈值公式
    st.markdown('##### 📐 阈值公式')
    st.markdown(f"""
    **上限:** mean + {sigma_val} × std

    **下限:** max(0, mean - {sigma_val} × std)
    """)

    st.markdown('</div>', unsafe_allow_html=True)


def render_static_params():
    """渲染 Static 参数面板"""
    st.markdown('<div class="model-card">', unsafe_allow_html=True)
    st.markdown("### 📊 Static 预测器")
    st.markdown("*基于百分位数的静态阈值，适合稀疏数据或低频指标*")

    params = st.session_state.static_params

    st.markdown('<div class="params-grid">', unsafe_allow_html=True)

    # 上限百分位
    st.markdown('<div class="param-group">', unsafe_allow_html=True)
    percentile = st.slider(
        STATIC_PARAMS['upper_percentile']['label'],
        90.0, 100.0, params.get('upper_percentile', 99.0), 0.5,
        label_visibility="collapsed"
    )
    st.session_state.static_params['upper_percentile'] = percentile
    st.markdown('</div>', unsafe_allow_html=True)
    render_param_help('upper_percentile', STATIC_PARAMS)

    # 下限值
    st.markdown('<div class="param-group">', unsafe_allow_html=True)
    lower_bound = st.slider(
        STATIC_PARAMS['lower_bound']['label'],
        0.0, 100.0, params.get('lower_bound', 0.0), 1.0,
        label_visibility="collapsed"
    )
    st.session_state.static_params['lower_bound'] = lower_bound
    st.markdown('</div>', unsafe_allow_html=True)
    render_param_help('lower_bound', STATIC_PARAMS)

    # 置信水平
    st.markdown('<div class="param-group">', unsafe_allow_html=True)
    conf = st.slider(
        STATIC_PARAMS['confidence_level']['label'],
        0.90, 0.999, params.get('confidence_level', 0.99), 0.001,
        label_visibility="collapsed"
    )
    st.session_state.static_params['confidence_level'] = conf
    st.markdown('</div>', unsafe_allow_html=True)
    render_param_help('confidence_level', STATIC_PARAMS)

    st.markdown('</div>', unsafe_allow_html=True)

    # 参数摘要
    st.markdown('---')

    # 从 session_state 获取最新参数值
    current_params = st.session_state.static_params

    param_summary = f"""
    <table class="param-table">
        <thead>
            <tr><th>参数</th><th>值</th></tr>
        </thead>
        <tbody>
            <tr><td>上限百分位</td><td><span class="digit-box">P{current_params.get('upper_percentile', percentile):.1f}</span></td></tr>
            <tr><td>下限值</td><td><span class="digit-box secondary">{current_params.get('lower_bound', lower_bound)}</span></td></tr>
            <tr><td>置信水平</td><td><span class="digit-box">{current_params.get('confidence_level', conf):.1%}</span></td></tr>
        </tbody>
    </table>
    """
    st.markdown(param_summary, unsafe_allow_html=True)

    # 阈值公式
    st.markdown('##### 📐 阈值公式')
    st.markdown(f"""
    **基准值:** median

    **上限:** P{percentile:.1f}

    **下限:** {lower_bound}
    """)

    st.markdown('</div>', unsafe_allow_html=True)


# ==================== 主页面 ====================

def render_main():
    """渲染主页面"""
    st.markdown('<div class="main-header"><h1>🤖 模型参数展示</h1></div>', unsafe_allow_html=True)

    # 数据预览
    if st.session_state.generated_data is not None:
        data = st.session_state.generated_data

        # 数据统计
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("数据点数", f"{len(data):,}")
        with col2:
            st.metric("最小值", f"{data.min():.2f}")
        with col3:
            st.metric("最大值", f"{data.max():.2f}")
        with col4:
            st.metric("平均值", f"{data.mean():.2f}")
        with col5:
            st.metric("标准差", f"{data.std():.2f}")

        # 特征分析
        if st.session_state.feature_result:
            features = st.session_state.feature_result
            st.markdown("### 🔍 数据特征分析")

            feature_html = ""
            if features.has_seasonality:
                feature_html += create_feature_badge("季节性", "是", "#28a745") + " "
            else:
                feature_html += create_feature_badge("季节性", "否", "#6c757d") + " "

            if features.is_stationary:
                feature_html += create_feature_badge("平稳性", "是", "#28a745") + " "
            else:
                feature_html += create_feature_badge("平稳性", "否", "#dc3545") + " "

            feature_html += create_feature_badge("稀疏度", f"{features.sparsity_ratio:.1%}", "#667eea") + " "

            # 获取主周期的 ACF 值作为季节性强度
            seasonality_strength = 0.0
            if features.primary_period and features.primary_period in features.seasonality_periods:
                seasonality_strength = features.seasonality_periods[features.primary_period].acf
            elif features.seasonality_periods:
                seasonality_strength = max(v.acf for v in features.seasonality_periods.values())

            feature_html += create_feature_badge("季节强度", f"{seasonality_strength:.2f}", "#17a2b8")

            st.markdown(feature_html, unsafe_allow_html=True)

        st.divider()

        # 模型参数面板
        selected_model = st.session_state.selected_model

        if selected_model == 'prophet':
            render_prophet_params()
        elif selected_model == 'welford':
            render_welford_params()
        elif selected_model == 'static':
            render_static_params()

        st.divider()

        # 预测按钮
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🚀 运行预测", type="primary", use_container_width=True):
                total_minutes = st.session_state.prediction_days * 1440 + st.session_state.prediction_hours * 60

                with st.spinner("正在训练模型并预测..."):
                    # 分割训练集
                    train_size = int(len(data) * 0.8)
                    train_data = data[:train_size]

                    # 创建预测器
                    if selected_model == 'prophet':
                        params = st.session_state.prophet_params.copy()
                        # 移除不支持传递给 Prophet 的参数
                        for key in ['add_monthly_seasonality', 'enforce_non_negative']:
                            params.pop(key, None)
                        predictor = ProphetPredictor(**params)
                    elif selected_model == 'welford':
                        params = st.session_state.welford_params.copy()
                        predictor = WelfordPredictor(**params)
                    elif selected_model == 'static':
                        params = st.session_state.static_params.copy()
                        predictor = StaticPredictor(**params)

                    # 训练
                    predictor.fit(train_data)

                    # 预测
                    prediction = predictor.predict(periods=total_minutes, freq="1min")

                    st.session_state.prediction_result = {
                        'predictor': predictor,
                        'prediction': prediction,
                        'train_data': train_data,
                    }

                st.success(f"✅ 预测完成！预测了 {total_minutes:,} 个时间点")
                st.rerun()

        # 显示预测结果
        if st.session_state.prediction_result:
            result = st.session_state.prediction_result
            prediction = result['prediction']
            train_data = result['train_data']

            st.markdown("### 📈 预测结果")

            # 图表
            fig = create_prediction_chart(train_data, prediction, f"{selected_model.upper()} 预测结果")
            st.plotly_chart(fig, use_container_width=True)

            # 统计信息
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("预测点数", f"{len(prediction.ds):,}")
            with col2:
                st.metric("预测均值", f"{prediction.yhat.mean():.2f}")
            with col3:
                st.metric("上限均值", f"{prediction.yhat_upper.mean():.2f}")
            with col4:
                st.metric("下限均值", f"{prediction.yhat_lower.mean():.2f}")

            # 模型信息
            st.markdown("### 📋 模型信息")
            st.json({
                'algorithm': prediction.algorithm,
                'confidence_level': prediction.confidence_level,
                'prediction_range': f"{prediction.ds[0]} ~ {prediction.ds[-1]}",
            })

    else:
        # 未生成数据时的提示
        st.info("👈 请在侧边栏选择场景并生成数据")


# ==================== 主函数 ====================

def main():
    # 渲染侧边栏
    render_sidebar()

    # 渲染主页面
    render_main()


if __name__ == "__main__":
    main()
