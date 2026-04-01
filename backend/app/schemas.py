"""
Pydantic schemas for API request/response models.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from enum import Enum


# ==================== Enums ====================

class ModelType(str, Enum):
    """模型类型"""
    PROPHET = "prophet"
    WELFORD = "welford"
    STATIC = "static"


class TemplateCategory(str, Enum):
    """模板分类"""
    SYSTEM = "system"
    CUSTOM = "custom"


# ==================== Time Range Schemas ====================

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
    seasonality_periods: Dict[str, Any] = Field(default_factory=dict, description="各周期的检测结果")
    primary_period: Optional[str] = Field(None, description="主周期")
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


# ==================== Pipeline Schemas (New) ====================

class JobStatus(str, Enum):
    """Job status enum"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExcludePeriod(BaseModel):
    """Exclude period for training"""
    start: datetime = Field(..., description="Start time")
    end: datetime = Field(..., description="End time")


class OutlierDetection(BaseModel):
    """异常点检测配置"""
    method: str = Field("iqr", description="检测方法: iqr/zscore")
    action: str = Field("remove", description="处理动作: remove/interpolate")
    threshold: float = Field(3.0, description="Z-Score 阈值（仅 zscore 方法使用）")


class SmoothingConfig(BaseModel):
    """数据平滑配置"""
    method: str = Field("moving_avg", description="平滑方法: moving_avg")
    window: int = Field(5, description="窗口大小")


class PipelineCreate(BaseModel):
    """Create pipeline request"""
    name: str = Field(..., description="Pipeline name")
    description: str = Field("", description="Description")
    datasource_id: str = Field("default", description="Datasource ID")
    metric_id: str = Field(..., description="Metric identifier")
    endpoint: Optional[str] = Field(None, description="Endpoint filter")
    labels: Dict[str, str] = Field(default_factory=dict, description="Label filters")

    train_start: datetime = Field(..., description="Training start time")
    train_end: datetime = Field(..., description="Training end time")
    step: str = Field("1m", description="Query step")
    predict_periods: int = Field(1440, description="预测点数，默认 1440 (24小时)")

    # Algorithm configuration - two ways to specify:
    # Option 1 (deprecated): Direct algorithm and params
    algorithm: Optional[str] = Field(None, description="Algorithm ID (deprecated, use model_id)")
    algorithm_params: Dict[str, Any] = Field(default_factory=dict, description="Algorithm parameters (deprecated)")
    # Option 2 (preferred): Reference to Model config with optional overrides
    model_id: Optional[str] = Field(None, description="Model config ID (preferred)")
    override_params: Optional[Dict[str, Any]] = Field(None, description="Override parameters for model")

    exclude_periods: List[ExcludePeriod] = Field(default_factory=list, description="Periods to exclude")
    outlier_detection: Optional[OutlierDetection] = Field(None, description="Outlier detection config")
    smoothing: Optional[SmoothingConfig] = Field(None, description="Smoothing config")
    enabled: bool = Field(True, description="Enable pipeline")
    schedule_type: str = Field("manual", description="Schedule type: manual or scheduled")
    cron_expr: Optional[str] = Field(None, description="Cron expression for scheduled pipelines")


class PipelineUpdate(BaseModel):
    """Update pipeline request"""
    name: Optional[str] = None
    description: Optional[str] = None
    datasource_id: Optional[str] = None
    metric_id: Optional[str] = None
    endpoint: Optional[str] = None
    labels: Optional[Dict[str, str]] = None
    train_start: Optional[datetime] = None
    train_end: Optional[datetime] = None
    step: Optional[str] = None
    predict_periods: Optional[int] = None
    algorithm: Optional[str] = None
    algorithm_params: Optional[Dict[str, Any]] = None
    model_id: Optional[str] = None
    override_params: Optional[Dict[str, Any]] = None
    exclude_periods: Optional[List[ExcludePeriod]] = None
    outlier_detection: Optional[OutlierDetection] = None
    smoothing: Optional[SmoothingConfig] = None
    enabled: Optional[bool] = None
    schedule_type: Optional[str] = None
    cron_expr: Optional[str] = None


class ModelInfo(BaseModel):
    """Brief model info for Pipeline response"""
    id: str = Field(..., description="Model ID")
    name: str = Field(..., description="Model display name")
    model_type: str = Field(..., description="Model type (prophet/welford/static)")


class PipelineResponse(BaseModel):
    """Pipeline response"""
    id: str = Field(..., description="Pipeline ID")
    name: str
    description: str
    datasource_id: str = Field("default", description="Datasource ID")
    metric_id: str
    endpoint: Optional[str]
    labels: Dict[str, str]
    train_start: datetime
    train_end: datetime
    step: str
    predict_periods: int = Field(1440, description="预测点数")
    # Algorithm configuration (old fields - deprecated)
    algorithm: str
    algorithm_params: Dict[str, Any]
    # Model reference (new fields)
    model_id: Optional[str] = None
    override_params: Optional[Dict[str, Any]] = None
    # Computed fields
    model_info: Optional[ModelInfo] = Field(None, description="Model config info if model_id is set")
    effective_params: Optional[Dict[str, Any]] = Field(None, description="Merged params from model + overrides")
    exclude_periods: List[Dict[str, Any]]
    outlier_detection: Optional[Dict[str, Any]] = None
    smoothing: Optional[Dict[str, Any]] = None
    enabled: bool
    schedule_type: str
    cron_expr: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class JobResponse(BaseModel):
    """Job response"""
    id: str = Field(..., description="Job ID")
    pipeline_id: str
    status: str
    progress: int = Field(description="Progress 0-100")
    current_step: Optional[str]

    # Metrics
    rmse: Optional[float]
    mae: Optional[float]
    mape: Optional[float]
    coverage: Optional[float]
    false_alerts: Optional[int]

    # Results
    preview_data: Optional[Dict[str, Any]] = Field(
        None,
        description="预览数据，用于 ECharts 图表展示。包含: "
        "timestamps(预测时间戳列表)、predicted(预测值)、upper(上限)、lower(下限)、"
        "train_timestamps(训练数据时间戳)、train_values(训练数据值)、"
        "validation_metrics(验证指标)、train_stats(训练统计)"
    )
    upper_bounds: Optional[List[float]] = Field(None, description="阈值上限数组（完整预测周期）")
    lower_bounds: Optional[List[float]] = Field(None, description="阈值下限数组（完整预测周期）")

    # Error info
    error_message: Optional[str]

    # Timing
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    created_at: datetime
    duration_seconds: Optional[float] = None

    class Config:
        from_attributes = True


class PipelineRunRequest(BaseModel):
    """Request to run a pipeline"""
    pipeline_id: str = Field(..., description="Pipeline ID to run")
    override_params: Optional[Dict[str, Any]] = Field(None, description="Override algorithm parameters")


class PipelineRunResponse(BaseModel):
    """Response after triggering pipeline run"""
    job_id: str = Field(..., description="Created job ID")
    pipeline_id: str
    status: str
    message: str = "Pipeline started"


# ==================== Algorithm Schemas (New) ====================

class AlgorithmInfo(BaseModel):
    """Algorithm information"""
    id: str = Field(..., description="Algorithm ID")
    name: str = Field(..., description="Display name")
    description: str = Field(..., description="Algorithm description")
    param_schema: Dict[str, Any] = Field(..., description="JSON Schema for parameters")


class AlgorithmListResponse(BaseModel):
    """List of available algorithms"""
    algorithms: List[AlgorithmInfo]


# ==================== Threshold Schemas (New) ====================

class ThresholdPublishRequest(BaseModel):
    """Request to publish threshold to Redis"""
    metric_id: str = Field(..., description="Metric identifier")
    job_id: str = Field(..., description="Job ID with threshold results")
    ttl: Optional[int] = Field(None, description="Cache TTL in seconds")


class ThresholdPublishResponse(BaseModel):
    """Response after publishing threshold"""
    success: bool
    metric_id: str
    message: str = "Threshold published"


class ThresholdGetResponse(BaseModel):
    """Response for getting threshold"""
    metric_id: str
    upper: List[float]
    lower: List[float]
    cached_at: Optional[str] = None


# ==================== Job Log Schema ====================

class JobLogEntry(BaseModel):
    """Single log entry for a job"""
    timestamp: str
    level: str
    message: str


class JobLogsResponse(BaseModel):
    """Response for job logs"""
    job_id: str
    logs: List[JobLogEntry]


# ==================== Check Schemas (New) ====================

class CheckRequest(BaseModel):
    """实时异常判断请求"""
    metric_id: str = Field(..., description="指标标识符")
    current_value: float = Field(..., description="当前值")
    timestamp: Optional[datetime] = Field(None, description="时间戳，用于选择对应时间点的阈值")


class CheckResponse(BaseModel):
    """异常判断响应"""
    metric_id: str = Field(..., description="指标标识符")
    is_anomaly: bool = Field(..., description="是否异常")
    severity: str = Field(..., description="异常严重程度: normal/warning/critical")
    threshold_used: Dict[str, float] = Field(..., description="使用的阈值: {upper, lower}")
    deviation_percent: Optional[float] = Field(None, description="偏离百分比")


# ==================== Direct Predict Schemas ====================

class OriginalDataPoint(BaseModel):
    """原始数据点"""
    timestamp: datetime = Field(..., description="时间戳")
    value: float = Field(..., description="值")


class PredictedDataPoint(BaseModel):
    """预测数据点"""
    timestamp: datetime = Field(..., description="时间戳")
    yhat: float = Field(..., description="预测值")
    yhat_upper: float = Field(..., description="预测上限")
    yhat_lower: float = Field(..., description="预测下限")


class DirectPredictRequest(BaseModel):
    """直接预测请求"""
    metric_id: str = Field(..., description="指标名/查询语句")
    endpoint: Optional[str] = Field(None, description="Endpoint 过滤")
    labels: Dict[str, str] = Field(default_factory=dict, description="标签过滤")
    train_start: datetime = Field(..., description="训练开始时间")
    train_end: datetime = Field(..., description="训练结束时间")
    step: str = Field("1m", description="采样间隔")
    model_id: str = Field(..., description="模型配置 ID")
    override_params: Optional[Dict[str, Any]] = Field(None, description="覆盖参数")
    predict_periods: Optional[int] = Field(None, description="预测点数，默认根据 step 计算 24 小时")
    predict_end: Optional[datetime] = Field(None, description="预测结束时间，优先于 predict_periods")
    exclude_periods: List[ExcludePeriod] = Field(default_factory=list, description="排除时间段")
    outlier_detection: Optional[OutlierDetection] = Field(None, description="异常点检测配置")
    smoothing: Optional[SmoothingConfig] = Field(None, description="数据平滑配置")


class DirectPredictResponse(BaseModel):
    """直接预测响应"""
    metric_id: str = Field(..., description="指标名")
    model_id: str = Field(..., description="模型配置 ID")
    algorithm: str = Field(..., description="使用的算法")
    train_start: datetime = Field(..., description="训练开始时间")
    train_end: datetime = Field(..., description="训练结束时间")
    train_points: int = Field(..., description="训练数据点数")
    predict_points: int = Field(..., description="预测数据点数")
    original_data: List[OriginalDataPoint] = Field(..., description="原始数据")
    predicted_data: List[PredictedDataPoint] = Field(..., description="预测数据")
    train_stats: Dict[str, Any] = Field(default_factory=dict, description="训练统计")
    validation_metrics: Dict[str, Any] = Field(default_factory=dict, description="验证指标")
    execution_time: float = Field(..., description="执行时间(秒)")