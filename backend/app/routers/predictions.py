"""
Prediction API router.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, status

# 东八区时区
TZ_SHANGHAI = timezone(timedelta(hours=8))


def normalize_timestamp(ts) -> pd.Timestamp:
    """将时间戳标准化为东八区的 tz-naive Timestamp。"""
    if isinstance(ts, pd.Timestamp):
        if ts.tz is not None:
            # 带时区：转换为东八区后移除时区信息
            return ts.tz_convert(TZ_SHANGHAI).tz_localize(None)
        return ts
    elif isinstance(ts, datetime):
        if ts.tzinfo is not None:
            # 带时区：转换为东八区后移除时区信息
            return pd.Timestamp(ts).tz_convert(TZ_SHANGHAI).tz_localize(None)
        return pd.Timestamp(ts)
    else:
        return pd.Timestamp(ts)


def normalize_datetime_index(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """将 DatetimeIndex 标准化为东八区的 tz-naive 索引。"""
    if index.tz is not None:
        return index.tz_convert(TZ_SHANGHAI).tz_localize(None)
    return index

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

router = APIRouter()


@router.post("/analyze", response_model=FeatureAnalysisResponse)
async def analyze_features(request: FeatureAnalysisRequest):
    """Analyze time series features."""
    from smart_threshold.core.feature_analyzer import FeatureExtractor
    from smart_threshold.core.model_router import ModelRouter, AlgorithmType

    if len(request.data) < 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Data length must be at least 100 points"
        )

    # Create pandas Series with normalized timezone
    timestamps = pd.DatetimeIndex(request.timestamps)
    timestamps = normalize_datetime_index(timestamps)
    data = pd.Series(request.data, index=timestamps)

    # Analyze features
    extractor = FeatureExtractor()
    features = extractor.analyze(data)

    # Determine recommended algorithm
    if features.has_seasonality:
        recommended = "prophet"
    elif features.sparsity_ratio >= 0.8:
        recommended = "static"
    else:
        recommended = "welford"

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
    """Run prediction with specified model."""
    from smart_threshold.config import get_model_config_manager, ModelType
    from smart_threshold.core.predictors.prophet_predictor import ProphetPredictor
    from smart_threshold.core.predictors.welford_predictor import WelfordPredictor
    from smart_threshold.core.predictors.static_predictor import StaticPredictor

    manager = get_model_config_manager()
    config = manager.get_config(request.model_id)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {request.model_id} not found"
        )

    # Create pandas Series with normalized timezone
    timestamps = pd.DatetimeIndex(request.timestamps)
    timestamps = normalize_datetime_index(timestamps)
    data = pd.Series(request.data, index=timestamps)

    # Create predictor
    params = config.get_params()
    if config.model_type == ModelType.PROPHET:
        predictor = ProphetPredictor(**params)
    elif config.model_type == ModelType.WELFORD:
        predictor = WelfordPredictor(**params)
    elif config.model_type == ModelType.STATIC:
        predictor = StaticPredictor(**params)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown model type: {config.model_type}"
        )

    # Fit and predict
    try:
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
    """Compare multiple models."""
    from smart_threshold.config import get_model_config_manager, ModelType
    from smart_threshold.core.predictors.prophet_predictor import ProphetPredictor
    from smart_threshold.core.predictors.welford_predictor import WelfordPredictor
    from smart_threshold.core.predictors.static_predictor import StaticPredictor

    if not request.model_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one model ID is required"
        )

    manager = get_model_config_manager()

    # Create pandas Series with normalized timezone
    timestamps = pd.DatetimeIndex(request.timestamps)
    timestamps = normalize_datetime_index(timestamps)
    data = pd.Series(request.data, index=timestamps)

    # Split train/test - normalize timestamps for comparison
    train_start = normalize_timestamp(request.train_start)
    train_end = normalize_timestamp(request.train_end)
    train_mask = (data.index >= train_start) & (data.index <= train_end)
    train_data = data[train_mask]

    # Test data: 24 hours after training or last 20% if not enough
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
            # Create predictor
            params = config.get_params()
            if config.model_type == ModelType.PROPHET:
                predictor = ProphetPredictor(**params)
            elif config.model_type == ModelType.WELFORD:
                predictor = WelfordPredictor(**params)
            elif config.model_type == ModelType.STATIC:
                predictor = StaticPredictor(**params)
            else:
                raise ValueError(f"Unknown model type: {config.model_type}")

            # Fit and predict
            predictor.fit(train_data)
            prediction = predictor.predict(periods=len(test_data))

            # Calculate metrics
            actual = test_data.values
            predicted = prediction.yhat

            mae = float(np.abs(actual - predicted).mean())
            mape = float((np.abs(actual - predicted) / (actual + 1e-6)).mean() * 100)

            # Coverage
            in_range = (actual >= prediction.yhat_lower) & (actual <= prediction.yhat_upper)
            coverage = float(in_range.mean())

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

    # Prepare test data for response
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