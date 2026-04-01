"""API routers package."""

from .models import router as models_router
from .predictions import router as predictions_router

__all__ = ["models_router", "predictions_router"]