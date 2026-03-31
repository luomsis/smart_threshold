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
from backend.app.routers.algorithms import router as algorithms_router
from backend.app.routers.pipelines import router as pipelines_router
from backend.app.routers.thresholds import router as thresholds_router
from backend.app.routers.check import router as check_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    print("Starting SmartThreshold API server...")

    # Initialize database tables
    from backend.db import init_db
    try:
        init_db()
        print("Database tables initialized.")
    except Exception as e:
        print(f"Warning: Could not initialize database: {e}")

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

# New routers for pipeline system
app.include_router(algorithms_router, prefix="/api/v1/algorithms", tags=["algorithms"])
app.include_router(pipelines_router, prefix="/api/v1/pipelines", tags=["pipelines"])
app.include_router(thresholds_router, prefix="/api/v1/thresholds", tags=["thresholds"])
app.include_router(check_router, prefix="/api/v1", tags=["check"])


@app.get(
    "/api/health",
    tags=["health"],
    summary="健康检查",
    description="检查 API 服务是否正常运行。返回服务状态和版本号。",
)
async def health_check():
    return {"status": "ok", "version": "0.1.0"}


@app.get(
    "/",
    tags=["root"],
    summary="API 根路径",
    description="返回 API 基本信息，包括名称、版本和文档路径。",
)
async def root():
    return {
        "name": "SmartThreshold API",
        "version": "0.1.0",
        "docs": "/api/docs",
    }