"""
Prediction API router.
"""

from datetime import datetime, timedelta, timezone
from typing import List

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
)
from smart_threshold.config import ModelType
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


@router.post("/analyze", response_model=FeatureAnalysisResponse)
async def analyze_features(request: FeatureAnalysisRequest):
    """分析时序数据特征"""
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
        seasonality_strength=features.seasonality_strength,
        sparsity_ratio=features.sparsity_ratio,
        is_stationary=features.is_stationary,
        adf_pvalue=features.adf_pvalue,
        mean=features.mean,
        std=features.std,
        recommended_algorithm=recommended,
    )


@router.post("/predict", response_model=PredictionResult)
async def predict(request: PredictionRequest):
    """运行预测"""
    from smart_threshold.config import get_model_config_manager

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


@router.post("/compare", response_model=ModelComparisonResponse)
async def compare_models(request: ModelComparisonRequest):
    """对比多个模型"""
    from smart_threshold.config import get_model_config_manager

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