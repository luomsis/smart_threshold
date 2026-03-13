"""
Pydantic schemas for API request/response models.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from enum import Enum


# ==================== Enums ====================

class DataSourceType(str, Enum):
    """数据源类型"""
    PROMETHEUS = "prometheus"
    INFLUXDB = "influxdb"
    MOCK = "mock"
    TIMESCALEDB = "timescaledb"


class ModelType(str, Enum):
    """模型类型"""
    PROPHET = "prophet"
    WELFORD = "welford"
    STATIC = "static"


class TemplateCategory(str, Enum):
    """模板分类"""
    SYSTEM = "system"
    CUSTOM = "custom"


# ==================== Data Source Schemas ====================

class DataSourceConfigBase(BaseModel):
    """数据源配置基类"""
    name: str = Field(..., description="数据源名称")
    source_type: DataSourceType = Field(..., description="数据源类型")
    url: str = Field(..., description="数据源URL")
    enabled: bool = Field(True, description="是否启用")
    auth_token: Optional[str] = Field(None, description="认证令牌")
    headers: Dict[str, str] = Field(default_factory=dict, description="请求头")
    default_timeout: int = Field(30, description="默认超时时间")
    # TimescaleDB 特定配置
    db_host: str = Field("localhost", description="数据库主机")
    db_port: int = Field(5432, description="数据库端口")
    db_name: str = Field("postgres", description="数据库名称")
    db_user: str = Field("postgres", description="数据库用户")
    db_password: str = Field("", description="数据库密码")


class DataSourceConfigCreate(DataSourceConfigBase):
    """创建数据源配置"""
    pass


class DataSourceConfigUpdate(BaseModel):
    """更新数据源配置"""
    name: Optional[str] = None
    source_type: Optional[DataSourceType] = None
    url: Optional[str] = None
    enabled: Optional[bool] = None
    auth_token: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    default_timeout: Optional[int] = None
    db_host: Optional[str] = None
    db_port: Optional[int] = None
    db_name: Optional[str] = None
    db_user: Optional[str] = None
    db_password: Optional[str] = None


class DataSourceConfigResponse(DataSourceConfigBase):
    """数据源配置响应"""
    id: str = Field(..., description="数据源ID")

    class Config:
        from_attributes = True


class TimeRange(BaseModel):
    """时间范围"""
    start: datetime = Field(..., description="开始时间")
    end: datetime = Field(..., description="结束时间")
    step: str = Field("1m", description="查询步长")


class MetricMetadata(BaseModel):
    """指标元数据"""
    name: str = Field(..., description="指标名称")
    type: str = Field("unknown", description="指标类型")
    help: str = Field("", description="帮助信息")
    labels: List[str] = Field(default_factory=list, description="标签列表")


class LabelValues(BaseModel):
    """标签值"""
    label: str = Field(..., description="标签名称")
    values: List[str] = Field(default_factory=list, description="标签值列表")


class MetricDataPoint(BaseModel):
    """指标数据点"""
    timestamp: datetime = Field(..., description="时间戳")
    value: float = Field(..., description="值")


class MetricData(BaseModel):
    """指标数据"""
    name: str = Field(..., description="指标名称")
    query: str = Field("", description="查询语句")
    labels: Dict[str, str] = Field(default_factory=dict, description="标签")
    data: List[MetricDataPoint] = Field(default_factory=list, description="数据点列表")


class QueryResult(BaseModel):
    """查询结果"""
    success: bool = Field(..., description="是否成功")
    data: Optional[List[MetricData]] = Field(None, description="数据")
    error: Optional[str] = Field(None, description="错误信息")
    execution_time: float = Field(0.0, description="执行时间")


class QueryRequest(BaseModel):
    """查询请求"""
    query: str = Field(..., description="PromQL查询语句")
    time_range: TimeRange = Field(..., description="时间范围")
    endpoint: Optional[str] = Field(None, description="Endpoint 过滤")


# ==================== Model Config Schemas ====================

class ModelConfigBase(BaseModel):
    """模型配置基类"""
    name: str = Field(..., description="模型名称")
    description: str = Field("", description="描述")
    model_type: ModelType = Field(..., description="模型类型")

    # Prophet 参数
    daily_seasonality: bool = Field(True, description="日季节性")
    weekly_seasonality: bool = Field(False, description="周季节性")
    yearly_seasonality: bool = Field(False, description="年季节性")
    seasonality_mode: str = Field("additive", description="季节性模式")
    interval_width: float = Field(0.95, description="置信区间宽度")
    n_changepoints: int = Field(25, description="变化点数量")
    changepoint_range: float = Field(0.8, description="变化点范围")
    changepoint_prior_scale: float = Field(0.05, description="变化点先验尺度")
    seasonality_prior_scale: float = Field(10.0, description="季节性先验尺度")
    holidays_prior_scale: float = Field(10.0, description="节假日先验尺度")

    # Welford 参数
    sigma_multiplier: float = Field(3.0, description="Sigma倍数")
    use_rolling_window: bool = Field(False, description="是否使用滚动窗口")
    window_size: Optional[int] = Field(None, description="窗口大小")

    # Static 参数
    upper_percentile: float = Field(99.0, description="上限百分位")
    lower_bound: float = Field(0.0, description="下限")

    # 元数据
    tags: List[str] = Field(default_factory=list, description="标签")
    color: str = Field("#4ECDC4", description="颜色")


class ModelConfigCreate(ModelConfigBase):
    """创建模型配置"""
    pass


class ModelConfigUpdate(BaseModel):
    """更新模型配置"""
    name: Optional[str] = None
    description: Optional[str] = None

    # Prophet 参数
    daily_seasonality: Optional[bool] = None
    weekly_seasonality: Optional[bool] = None
    yearly_seasonality: Optional[bool] = None
    seasonality_mode: Optional[str] = None
    interval_width: Optional[float] = None
    n_changepoints: Optional[int] = None
    changepoint_range: Optional[float] = None
    changepoint_prior_scale: Optional[float] = None
    seasonality_prior_scale: Optional[float] = None
    holidays_prior_scale: Optional[float] = None

    # Welford 参数
    sigma_multiplier: Optional[float] = None
    use_rolling_window: Optional[bool] = None
    window_size: Optional[int] = None

    # Static 参数
    upper_percentile: Optional[float] = None
    lower_bound: Optional[float] = None

    # 元数据
    tags: Optional[List[str]] = None
    color: Optional[str] = None


class ModelConfigResponse(ModelConfigBase):
    """模型配置响应"""
    id: str = Field(..., description="模型ID")
    category: TemplateCategory = Field(..., description="分类")
    created_at: str = Field("", description="创建时间")
    updated_at: str = Field("", description="更新时间")
    author: str = Field("system", description="作者")

    class Config:
        from_attributes = True


# ==================== Prediction Schemas ====================

class FeatureAnalysisRequest(BaseModel):
    """特征分析请求"""
    data: List[float] = Field(..., description="时序数据")
    timestamps: List[datetime] = Field(..., description="时间戳列表")


class FeatureAnalysisResponse(BaseModel):
    """特征分析响应"""
    has_seasonality: bool = Field(..., description="是否有季节性")
    seasonality_strength: float = Field(..., description="季节性强度")
    sparsity_ratio: float = Field(..., description="稀疏度")
    is_stationary: bool = Field(..., description="是否平稳")
    adf_pvalue: float = Field(..., description="ADF检验p值")
    mean: float = Field(..., description="均值")
    std: float = Field(..., description="标准差")
    recommended_algorithm: str = Field(..., description="推荐算法")


class PredictionRequest(BaseModel):
    """预测请求"""
    model_id: str = Field(..., description="模型ID")
    data: List[float] = Field(..., description="训练数据")
    timestamps: List[datetime] = Field(..., description="时间戳列表")
    periods: int = Field(1440, description="预测周期数")
    freq: str = Field("1min", description="时间频率")


class PredictionResult(BaseModel):
    """预测结果"""
    timestamps: List[datetime] = Field(..., description="时间戳列表")
    yhat: List[float] = Field(..., description="预测值")
    yhat_upper: List[float] = Field(..., description="预测上限")
    yhat_lower: List[float] = Field(..., description="预测下限")
    algorithm: str = Field(..., description="算法名称")
    confidence_level: float = Field(0.95, description="置信水平")


class ModelComparisonRequest(BaseModel):
    """模型对比请求"""
    model_ids: List[str] = Field(..., description="模型ID列表")
    data: List[float] = Field(..., description="时序数据")
    timestamps: List[datetime] = Field(..., description="时间戳列表")
    train_start: datetime = Field(..., description="训练开始时间")
    train_end: datetime = Field(..., description="训练结束时间")


class ModelComparisonResult(BaseModel):
    """模型对比结果"""
    model_id: str = Field(..., description="模型ID")
    model_name: str = Field(..., description="模型名称")
    success: bool = Field(..., description="是否成功")
    mae: Optional[float] = Field(None, description="MAE")
    mape: Optional[float] = Field(None, description="MAPE")
    coverage: Optional[float] = Field(None, description="覆盖率")
    prediction: Optional[PredictionResult] = Field(None, description="预测结果")
    error: Optional[str] = Field(None, description="错误信息")


class ModelComparisonResponse(BaseModel):
    """模型对比响应"""
    results: List[ModelComparisonResult] = Field(..., description="对比结果列表")
    test_data: Optional[MetricData] = Field(None, description="测试数据")


# ==================== Common Schemas ====================

class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = Field("ok", description="状态")
    version: str = Field(..., description="版本")


class ErrorResponse(BaseModel):
    """错误响应"""
    detail: str = Field(..., description="错误详情")
    code: Optional[str] = Field(None, description="错误代码")