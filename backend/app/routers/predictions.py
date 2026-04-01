"""
Prediction API router.
"""

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, status

from backend.app.schemas import (
    FeatureAnalysisRequest,
    FeatureAnalysisResponse,
    PredictionRequest,
    PredictionResult,
    ModelComparisonRequest,
    ModelComparisonResponse,
    ModelComparisonResult,
    MetricData,
    MetricDataPoint,
    DirectPredictRequest,
    DirectPredictResponse,
    OriginalDataPoint,
    PredictedDataPoint,
)
from smart_threshold.config import ModelType, get_model_config_manager
from smart_threshold.core.feature_analyzer import FeatureExtractor
from smart_threshold.core.predictors.prophet_predictor import ProphetPredictor
from smart_threshold.core.predictors.welford_predictor import WelfordPredictor
from smart_threshold.core.predictors.static_predictor import StaticPredictor

router = APIRouter()

# 东八区时区
TZ_SHANGHAI = timezone(timedelta(hours=8))


def normalize_timestamp(ts) -> pd.Timestamp:
    """将时间戳标准化为东八区的 tz-naive Timestamp。"""
    if isinstance(ts, pd.Timestamp):
        return ts.tz_convert(TZ_SHANGHAI).tz_localize(None) if ts.tz else ts
    if isinstance(ts, datetime):
        return pd.Timestamp(ts).tz_convert(TZ_SHANGHAI).tz_localize(None) if ts.tzinfo else pd.Timestamp(ts)
    return pd.Timestamp(ts)


def normalize_datetime_index(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """将 DatetimeIndex 标准化为东八区的 tz-naive 索引。"""
    return index.tz_convert(TZ_SHANGHAI).tz_localize(None) if index.tz else index


def create_predictor(model_type: ModelType, params: dict):
    """创建预测器实例"""
    if model_type == ModelType.PROPHET:
        return ProphetPredictor(**params)
    if model_type == ModelType.WELFORD:
        return WelfordPredictor(**params)
    if model_type == ModelType.STATIC:
        return StaticPredictor(**params)
    raise ValueError(f"Unknown model type: {model_type}")


@router.post(
    "/analyze",
    response_model=FeatureAnalysisResponse,
    summary="分析时序数据特征",
    description="分析时序数据的统计特征，包括季节性（ACF 检验）、稀疏性、平稳性（ADF 检验）。根据特征自动推荐最合适的预测算法。",
)
async def analyze_features(request: FeatureAnalysisRequest):
    if len(request.data) < 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Data length must be at least 100 points"
        )

    timestamps = normalize_datetime_index(pd.DatetimeIndex(request.timestamps))
    data = pd.Series(request.data, index=timestamps)

    features = FeatureExtractor().analyze(data)

    recommended = (
        "prophet" if features.has_seasonality
        else "static" if features.sparsity_ratio >= 0.8
        else "welford"
    )

    return FeatureAnalysisResponse(
        has_seasonality=features.has_seasonality,
        seasonality_periods={k: {"acf": v.acf, "has_seasonality": v.has_seasonality} for k, v in features.seasonality_periods.items()},
        primary_period=features.primary_period,
        sparsity_ratio=features.sparsity_ratio,
        is_stationary=features.is_stationary,
        adf_pvalue=features.adf_pvalue,
        mean=features.mean,
        std=features.std,
        recommended_algorithm=recommended,
    )


@router.post(
    "/predict",
    response_model=PredictionResult,
    summary="运行预测",
    description="使用指定模型对时序数据进行预测。返回预测值及置信区间上下限。数据长度需大于 100 点。",
)
async def predict(request: PredictionRequest):
    manager = get_model_config_manager()
    config = manager.get_config(request.model_id)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {request.model_id} not found"
        )

    timestamps = normalize_datetime_index(pd.DatetimeIndex(request.timestamps))
    data = pd.Series(request.data, index=timestamps)

    try:
        predictor = create_predictor(config.model_type, config.get_params())
        predictor.fit(data)
        result = predictor.predict(periods=request.periods, freq=request.freq)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction failed: {str(e)}"
        )

    return PredictionResult(
        timestamps=result.ds.tolist(),
        yhat=result.yhat.tolist(),
        yhat_upper=result.yhat_upper.tolist(),
        yhat_lower=result.yhat_lower.tolist(),
        algorithm=result.algorithm,
        confidence_level=result.confidence_level,
    )


@router.post(
    "/compare",
    response_model=ModelComparisonResponse,
    summary="多模型对比",
    description="对比多个模型在同一数据集上的预测效果。返回每个模型的 MAE、MAPE、覆盖率等评估指标及预测结果。",
)
async def compare_models(request: ModelComparisonRequest):
    if not request.model_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one model ID is required"
        )

    manager = get_model_config_manager()
    timestamps = normalize_datetime_index(pd.DatetimeIndex(request.timestamps))
    data = pd.Series(request.data, index=timestamps)

    train_start = normalize_timestamp(request.train_start)
    train_end = normalize_timestamp(request.train_end)
    train_mask = (data.index >= train_start) & (data.index <= train_end)
    train_data = data[train_mask]

    test_start = train_end + timedelta(minutes=1)
    test_end = test_start + timedelta(hours=24)
    test_mask = (data.index >= test_start) & (data.index <= test_end)

    if test_mask.sum() == 0:
        split_idx = int(len(train_data) * 0.8)
        test_data = train_data.iloc[split_idx:]
        train_data = train_data.iloc[:split_idx]
    else:
        test_data = data[test_mask]

    results: List[ModelComparisonResult] = []

    for model_id in request.model_ids:
        config = manager.get_config(model_id)
        if not config:
            results.append(ModelComparisonResult(
                model_id=model_id,
                model_name="Unknown",
                success=False,
                error=f"Model {model_id} not found",
            ))
            continue

        try:
            predictor = create_predictor(config.model_type, config.get_params())
            predictor.fit(train_data)
            prediction = predictor.predict(periods=len(test_data))

            actual = test_data.values
            predicted = prediction.yhat

            mae = float(np.abs(actual - predicted).mean())
            mape = float((np.abs(actual - predicted) / (actual + 1e-6)).mean() * 100)
            coverage = float(((actual >= prediction.yhat_lower) & (actual <= prediction.yhat_upper)).mean())

            results.append(ModelComparisonResult(
                model_id=model_id,
                model_name=config.name,
                success=True,
                mae=mae,
                mape=mape,
                coverage=coverage,
                prediction=PredictionResult(
                    timestamps=prediction.ds.tolist(),
                    yhat=prediction.yhat.tolist(),
                    yhat_upper=prediction.yhat_upper.tolist(),
                    yhat_lower=prediction.yhat_lower.tolist(),
                    algorithm=prediction.algorithm,
                    confidence_level=prediction.confidence_level,
                ),
            ))

        except Exception as e:
            results.append(ModelComparisonResult(
                model_id=model_id,
                model_name=config.name if config else "Unknown",
                success=False,
                error=str(e),
            ))

    test_data_response = MetricData(
        name="test_data",
        query="",
        labels={},
        data=[MetricDataPoint(timestamp=ts, value=val)
              for ts, val in zip(test_data.index, test_data.values)],
    )

    return ModelComparisonResponse(
        results=results,
        test_data=test_data_response,
    )


def _get_datasource_config(ds_id: str) -> Dict[str, Any]:
    """Get datasource configuration by ID."""
    import json
    from pathlib import Path

    CONFIG_DIR = Path(__file__).parent.parent.parent.parent / "config"
    DATASOURCES_FILE = CONFIG_DIR / "datasources.json"

    if not DATASOURCES_FILE.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DataSource {ds_id} not found (no config file)"
        )

    try:
        with open(DATASOURCES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        for ds in data:
            if ds.get("id") == ds_id:
                return ds

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DataSource {ds_id} not found"
        )
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to parse datasources config"
        )


@router.post(
    "/direct",
    response_model=DirectPredictResponse,
    summary="直接预测接口",
    description="不通过 Pipeline 直接提供预测功能。从数据源查询数据，清洗后使用指定模型进行训练和预测。",
)
async def direct_predict(request: DirectPredictRequest):
    from backend.pipeline.steps.fetch import fetch_data
    from backend.pipeline.steps.clean import clean_data
    from backend.pipeline.steps.train import train_model, parse_step_to_freq

    start_time = time.time()

    # Model type to algorithm ID mapping
    # model_config.model_type values: prophet, welford, static
    # AlgorithmRegistry IDs: prophet, three_sigma, moving_average
    MODEL_TYPE_TO_ALGORITHM = {
        "prophet": "prophet",
        "welford": "three_sigma",
        "static": "moving_average",
    }

    # Step 1: Get datasource config
    ds_config = _get_datasource_config(request.datasource_id)

    # Step 2: Get model config
    manager = get_model_config_manager()
    model_config = manager.get_config(request.model_id)

    if not model_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {request.model_id} not found"
        )

    # Step 3: Fetch data
    data, fetch_error = fetch_data(
        datasource_config=ds_config,
        metric_id=request.metric_id,
        train_start=request.train_start,
        train_end=request.train_end,
        step=request.step,
        endpoint=request.endpoint,
        labels=request.labels,
    )

    if fetch_error or data is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=fetch_error or "Failed to fetch data"
        )

    # Step 4: Clean data
    exclude_periods = [p.model_dump() for p in request.exclude_periods] if request.exclude_periods else None
    outlier_detection = request.outlier_detection.model_dump() if request.outlier_detection else None
    smoothing = request.smoothing.model_dump() if request.smoothing else None

    cleaned_data, cleaning_stats = clean_data(
        data=data,
        exclude_periods=exclude_periods,
        outlier_detection=outlier_detection,
        smoothing=smoothing,
    )

    # Step 5: Calculate predict periods
    if request.predict_end:
        # Calculate periods from predict_end
        freq = parse_step_to_freq(request.step)
        # Calculate time delta in appropriate units
        time_delta = request.predict_end - request.train_end
        if freq.endswith("min"):
            periods = int(time_delta.total_seconds() / 60)
        elif freq == "H":
            periods = int(time_delta.total_seconds() / 3600)
        elif freq == "D":
            periods = int(time_delta.days)
        else:
            # Default: assume minutes
            periods = int(time_delta.total_seconds() / 60)
    elif request.predict_periods:
        periods = request.predict_periods
    else:
        # Default: 24 hours based on step
        step_minutes = _parse_step_to_minutes(request.step)
        periods = int(24 * 60 / step_minutes)  # 24 hours worth of points

    # Step 6: Get effective algorithm params
    base_params = model_config.get_params()
    if request.override_params:
        effective_params = {**base_params, **request.override_params}
    else:
        effective_params = base_params

    # Map model_type to algorithm ID
    model_type_value = model_config.model_type.value
    algorithm = MODEL_TYPE_TO_ALGORITHM.get(model_type_value, model_type_value)

    # Step 7: Train model and predict
    model, result, train_error = train_model(
        data=cleaned_data,
        algorithm=algorithm,
        algorithm_params=effective_params,
        periods=periods,
        step=request.step,
    )

    if train_error or result is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=train_error or "Training failed"
        )

    # Step 8: Build response
    execution_time = time.time() - start_time

    # Convert original data to response format
    original_data_points = [
        OriginalDataPoint(timestamp=ts, value=val)
        for ts, val in zip(cleaned_data.index, cleaned_data.values)
    ]

    # Convert predicted data to response format
    # AlgorithmResult uses 'timestamps' attribute (not 'ds')
    yhat_list = result.yhat.tolist() if hasattr(result.yhat, 'tolist') else list(result.yhat)
    yhat_upper_list = result.yhat_upper.tolist() if hasattr(result.yhat_upper, 'tolist') else list(result.yhat_upper)
    yhat_lower_list = result.yhat_lower.tolist() if hasattr(result.yhat_lower, 'tolist') else list(result.yhat_lower)

    predicted_data_points = [
        PredictedDataPoint(
            timestamp=ts,
            yhat=yhat,
            yhat_upper=yhat_upper,
            yhat_lower=yhat_lower,
        )
        for ts, yhat, yhat_upper, yhat_lower in zip(
            result.timestamps, yhat_list, yhat_upper_list, yhat_lower_list
        )
    ]

    # Get algorithm name from metadata
    result_algorithm = result.metadata.get("algorithm", algorithm)

    # Calculate validation metrics on training data
    validation_metrics = _calculate_validation_metrics(cleaned_data, result)

    return DirectPredictResponse(
        metric_id=request.metric_id,
        model_id=request.model_id,
        algorithm=result_algorithm,
        train_start=request.train_start,
        train_end=request.train_end,
        train_points=len(cleaned_data),
        predict_points=len(predicted_data_points),
        original_data=original_data_points,
        predicted_data=predicted_data_points,
        train_stats=cleaning_stats,
        validation_metrics=validation_metrics,
        execution_time=execution_time,
    )


def _parse_step_to_minutes(step: str) -> int:
    """Parse step string to minutes."""
    step_map = {
        "1m": 1,
        "5m": 5,
        "15m": 15,
        "30m": 30,
        "1h": 60,
        "1d": 1440,
    }
    return step_map.get(step, 1)


def _calculate_validation_metrics(data: pd.Series, result) -> Dict[str, Any]:
    """Calculate validation metrics comparing actual vs predicted on training period."""
    # For training data, we compare the fitted values
    # Prophet provides yhat for historical data, other algorithms may not

    metrics = {
        "mean": float(data.mean()),
        "std": float(data.std()),
        "min": float(data.min()),
        "max": float(data.max()),
    }

    # Calculate coverage metrics for the prediction
    if hasattr(result, 'yhat_upper') and hasattr(result, 'yhat_lower'):
        # For prediction interval coverage analysis
        avg_interval_width = np.mean(result.yhat_upper - result.yhat_lower)
        metrics["avg_interval_width"] = float(avg_interval_width)
        metrics["interval_width_ratio"] = float(avg_interval_width / (metrics["std"] + 1e-10))

    return metrics