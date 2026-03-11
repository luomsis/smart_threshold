"""
Model management API router.
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, status

from backend.app.schemas import (
    ModelConfigCreate,
    ModelConfigUpdate,
    ModelConfigResponse,
    ModelType,
    TemplateCategory,
)

router = APIRouter()


def _get_manager():
    """Get model config manager."""
    from smart_threshold.config import get_model_config_manager
    return get_model_config_manager()


def _config_to_response(config) -> ModelConfigResponse:
    """Convert ModelConfig to response schema."""
    return ModelConfigResponse(
        id=config.id,
        name=config.name,
        description=config.description,
        model_type=ModelType(config.model_type.value),
        category=TemplateCategory(config.category.value),
        daily_seasonality=config.daily_seasonality,
        weekly_seasonality=config.weekly_seasonality,
        yearly_seasonality=config.yearly_seasonality,
        seasonality_mode=config.seasonality_mode,
        interval_width=config.interval_width,
        n_changepoints=config.n_changepoints,
        changepoint_range=config.changepoint_range,
        changepoint_prior_scale=config.changepoint_prior_scale,
        seasonality_prior_scale=config.seasonality_prior_scale,
        holidays_prior_scale=config.holidays_prior_scale,
        sigma_multiplier=config.sigma_multiplier,
        use_rolling_window=config.use_rolling_window,
        window_size=config.window_size,
        upper_percentile=config.upper_percentile,
        lower_bound=config.lower_bound,
        created_at=config.created_at,
        updated_at=config.updated_at,
        author=config.author,
        tags=config.tags,
        color=config.color,
    )


@router.get("", response_model=List[ModelConfigResponse])
async def list_models(
    model_type: Optional[ModelType] = None,
    category: Optional[TemplateCategory] = None,
):
    """List all model configurations."""
    manager = _get_manager()
    configs = manager.list_configs(
        model_type=model_type and model_type.value,
        category=category and category.value,
    )
    return [_config_to_response(c) for c in configs]


@router.get("/{model_id}", response_model=ModelConfigResponse)
async def get_model(model_id: str):
    """Get model configuration by ID."""
    manager = _get_manager()
    config = manager.get_config(model_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {model_id} not found"
        )
    return _config_to_response(config)


@router.post("", response_model=ModelConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_model(config: ModelConfigCreate):
    """Create a new model configuration."""
    from smart_threshold.config import ModelConfig as CoreModelConfig

    manager = _get_manager()

    # Generate unique ID
    import uuid
    model_id = f"custom_{uuid.uuid4().hex[:8]}"

    core_config = CoreModelConfig(
        id=model_id,
        name=config.name,
        description=config.description,
        model_type=config.model_type.value,
        category=TemplateCategory.CUSTOM.value,
        daily_seasonality=config.daily_seasonality,
        weekly_seasonality=config.weekly_seasonality,
        yearly_seasonality=config.yearly_seasonality,
        seasonality_mode=config.seasonality_mode,
        interval_width=config.interval_width,
        n_changepoints=config.n_changepoints,
        changepoint_range=config.changepoint_range,
        changepoint_prior_scale=config.changepoint_prior_scale,
        seasonality_prior_scale=config.seasonality_prior_scale,
        holidays_prior_scale=config.holidays_prior_scale,
        sigma_multiplier=config.sigma_multiplier,
        use_rolling_window=config.use_rolling_window,
        window_size=config.window_size,
        upper_percentile=config.upper_percentile,
        lower_bound=config.lower_bound,
        tags=config.tags,
        color=config.color,
        author="user",
    )

    if not manager.add_config(core_config):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create model"
        )

    return _config_to_response(core_config)


@router.put("/{model_id}", response_model=ModelConfigResponse)
async def update_model(model_id: str, updates: ModelConfigUpdate):
    """Update model configuration."""
    manager = _get_manager()
    config = manager.get_config(model_id)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {model_id} not found"
        )

    if config.category == TemplateCategory.SYSTEM.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify system models"
        )

    # Filter out None values
    update_dict = {k: v for k, v in updates.model_dump().items() if v is not None}

    if not manager.update_config(model_id, update_dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update model"
        )

    updated_config = manager.get_config(model_id)
    return _config_to_response(updated_config)


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(model_id: str):
    """Delete model configuration."""
    manager = _get_manager()

    if not manager.delete_config(model_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {model_id} not found or cannot be deleted"
        )