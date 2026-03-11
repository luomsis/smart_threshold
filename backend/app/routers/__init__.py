"""API routers package."""

from .datasources import router as datasources_router
from .models import router as models_router
from .predictions import router as predictions_router

__all__ = ["datasources_router", "models_router", "predictions_router"]