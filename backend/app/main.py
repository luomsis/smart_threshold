"""
FastAPI main application entry point.
"""

import sys
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import Request
from fastapi.responses import JSONResponse

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.routers import datasources_router, models_router, predictions_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    print("Starting SmartThreshold API server...")
    yield
    # Shutdown
    print("Shutting down SmartThreshold API server...")


app = FastAPI(
    title="SmartThreshold API",
    description="DB 监控算法自动选型系统 API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS middleware - must be added before routers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler to ensure CORS headers on errors."""
    import traceback
    traceback.print_exc()  # Log the full traceback
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )

# Include routers
app.include_router(datasources_router, prefix="/api/v1/datasources", tags=["datasources"])
app.include_router(models_router, prefix="/api/v1/models", tags=["models"])
app.include_router(predictions_router, prefix="/api/v1/predictions", tags=["predictions"])


@app.get("/api/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}


@app.get("/", tags=["root"])
async def root():
    """Root endpoint."""
    return {
        "name": "SmartThreshold API",
        "version": "0.1.0",
        "docs": "/api/docs",
    }