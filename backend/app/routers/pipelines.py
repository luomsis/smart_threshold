"""
Pipelines API router.

Manage training pipelines and jobs with full lifecycle management.
"""

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.models.pipeline import Pipeline
from backend.models.job import Job, JobStatus
from backend.tasks.pipeline_tasks import run_pipeline_task
from backend.tasks.lifecycle import get_lifecycle_manager
from backend.app.schemas import (
    PipelineCreate,
    PipelineUpdate,
    PipelineResponse,
    PipelineRunRequest,
    PipelineRunResponse,
    JobResponse,
    ModelInfo,
)
from smart_threshold.config.model_config import get_model_config_manager
from backend.app.routers.datasources import _datasources

router = APIRouter()


def get_effective_params(pipeline: Pipeline) -> dict:
    """
    Compute effective algorithm parameters from model_id + override_params.

    Returns merged params from Model config and pipeline overrides.
    Falls back to algorithm_params if model_id is not set.
    """
    if pipeline.model_id:
        manager = get_model_config_manager()
        model_config = manager.get_config(pipeline.model_id)
        if model_config:
            # Start with model's default params
            params = model_config.get_params()
            # Apply override_params if present
            if pipeline.override_params:
                params.update(pipeline.override_params)
            return params
        # Model not found - fall back to algorithm_params
        return pipeline.algorithm_params or {}
    # No model_id - use algorithm_params directly
    return pipeline.algorithm_params or {}


def get_model_info(pipeline: Pipeline) -> Optional[ModelInfo]:
    """
    Get ModelInfo from pipeline's model_id.

    Returns None if model_id is not set or model not found.
    """
    if pipeline.model_id:
        manager = get_model_config_manager()
        model_config = manager.get_config(pipeline.model_id)
        if model_config:
            return ModelInfo(
                id=model_config.id,
                name=model_config.name,
                model_type=model_config.model_type.value,
            )
    return None


def get_algorithm_from_model(pipeline: Pipeline) -> str:
    """
    Get algorithm type from model_id or fall back to algorithm field.
    """
    if pipeline.model_id:
        manager = get_model_config_manager()
        model_config = manager.get_config(pipeline.model_id)
        if model_config:
            return model_config.model_type.value
    return pipeline.algorithm


def get_datasource_name(datasource_id: str) -> Optional[str]:
    """Get data source name by ID from in-memory storage."""
    if not datasource_id:
        return None
    ds = _datasources.get(datasource_id)
    return ds.name if ds else None


def pipeline_to_response(pipeline: Pipeline, db: Session = None) -> PipelineResponse:
    """Convert Pipeline model to response schema."""
    # Get datasource name from in-memory storage
    datasource_name = get_datasource_name(pipeline.datasource_id)

    return PipelineResponse(
        id=pipeline.id,
        name=pipeline.name,
        description=pipeline.description,
        metric_id=pipeline.metric_id,
        datasource_id=pipeline.datasource_id,
        datasource_name=datasource_name,
        endpoint=pipeline.endpoint,
        labels=pipeline.labels or {},
        train_start=pipeline.train_start,
        train_end=pipeline.train_end,
        step=pipeline.step,
        algorithm=get_algorithm_from_model(pipeline),
        algorithm_params=pipeline.algorithm_params or {},
        model_id=pipeline.model_id,
        override_params=pipeline.override_params,
        model_info=get_model_info(pipeline),
        effective_params=get_effective_params(pipeline),
        exclude_periods=pipeline.exclude_periods or [],
        outlier_detection=pipeline.outlier_detection,
        smoothing=pipeline.smoothing,
        enabled=pipeline.enabled,
        schedule_type=pipeline.schedule_type,
        cron_expr=pipeline.cron_expr,
        created_at=pipeline.created_at,
        updated_at=pipeline.updated_at,
    )


def job_to_response(job: Job) -> JobResponse:
    """Convert Job model to response schema."""
    return JobResponse(
        id=job.id,
        pipeline_id=job.pipeline_id,
        status=job.status,
        progress=job.progress,
        current_step=job.current_step,
        rmse=job.rmse,
        mae=job.mae,
        mape=job.mape,
        coverage=job.coverage,
        false_alerts=job.false_alerts,
        preview_data=job.preview_data,
        upper_bounds=job.upper_bounds,
        lower_bounds=job.lower_bounds,
        error_message=job.error_message,
        started_at=job.started_at,
        finished_at=job.finished_at,
        created_at=job.created_at,
        duration_seconds=job.duration_seconds,
    )


# ==================== Pipeline CRUD ====================

@router.post(
    "",
    response_model=PipelineResponse,
    status_code=201,
    summary="创建训练管道",
    description="创建新的阈值训练管道。配置包括数据源、指标、训练时间范围、算法及参数等。",
)
async def create_pipeline(request: PipelineCreate, db: Session = Depends(get_db)):
    # Determine algorithm from model_id or direct algorithm field
    algorithm = request.algorithm
    algorithm_params = request.algorithm_params

    if request.model_id:
        # Validate model exists
        manager = get_model_config_manager()
        model_config = manager.get_config(request.model_id)
        if not model_config:
            raise HTTPException(
                status_code=400,
                detail=f"Model config not found: {request.model_id}"
            )
        # Use model's algorithm type
        algorithm = model_config.model_type.value
        # Get params from model, will be overridden later if override_params provided
        algorithm_params = model_config.get_params()
    elif not algorithm:
        # Neither model_id nor algorithm provided
        raise HTTPException(
            status_code=400,
            detail="Either model_id or algorithm must be provided"
        )

    pipeline = Pipeline(
        id=str(uuid.uuid4()),
        name=request.name,
        description=request.description,
        metric_id=request.metric_id,
        datasource_id=request.datasource_id,
        endpoint=request.endpoint,
        labels=request.labels,
        train_start=request.train_start,
        train_end=request.train_end,
        step=request.step,
        algorithm=algorithm,
        algorithm_params=algorithm_params,
        model_id=request.model_id,
        override_params=request.override_params,
        exclude_periods=[p.model_dump() for p in request.exclude_periods],
        outlier_detection=request.outlier_detection.model_dump() if request.outlier_detection else None,
        smoothing=request.smoothing.model_dump() if request.smoothing else None,
        enabled=request.enabled,
        schedule_type=request.schedule_type,
        cron_expr=request.cron_expr,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    db.add(pipeline)
    db.commit()
    db.refresh(pipeline)

    return pipeline_to_response(pipeline, db)


@router.get(
    "",
    response_model=List[PipelineResponse],
    summary="获取管道列表",
    description="获取所有训练管道列表。可按启用状态和算法类型筛选。",
)
async def list_pipelines(
    enabled: Optional[bool] = None,
    algorithm: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Pipeline)

    if enabled is not None:
        query = query.filter(Pipeline.enabled == enabled)
    if algorithm:
        query = query.filter(Pipeline.algorithm == algorithm)

    pipelines = query.order_by(Pipeline.created_at.desc()).all()
    return [pipeline_to_response(p, db) for p in pipelines]


@router.get(
    "/{pipeline_id}",
    response_model=PipelineResponse,
    summary="获取管道详情",
    description="根据 ID 获取指定训练管道的完整配置信息。",
)
async def get_pipeline(pipeline_id: str, db: Session = Depends(get_db)):
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail=f"Pipeline not found: {pipeline_id}")
    return pipeline_to_response(pipeline, db)


@router.put(
    "/{pipeline_id}",
    response_model=PipelineResponse,
    summary="更新管道配置",
    description="更新指定训练管道的配置。只需提供要更新的字段。",
)
async def update_pipeline(
    pipeline_id: str,
    request: PipelineUpdate,
    db: Session = Depends(get_db),
):
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail=f"Pipeline not found: {pipeline_id}")

    update_data = request.model_dump(exclude_unset=True)

    # Handle model_id update - update algorithm accordingly
    if "model_id" in update_data and update_data["model_id"]:
        manager = get_model_config_manager()
        model_config = manager.get_config(update_data["model_id"])
        if not model_config:
            raise HTTPException(
                status_code=400,
                detail=f"Model config not found: {update_data['model_id']}"
            )
        # Update algorithm to match model type
        update_data["algorithm"] = model_config.model_type.value
        # Update algorithm_params to model defaults if not explicitly provided
        if "algorithm_params" not in update_data and "override_params" not in update_data:
            update_data["algorithm_params"] = model_config.get_params()

    # Handle exclude_periods specially
    if "exclude_periods" in update_data and request.exclude_periods:
        update_data["exclude_periods"] = [p.model_dump() for p in request.exclude_periods]

    # Handle outlier_detection specially
    if "outlier_detection" in update_data and request.outlier_detection:
        update_data["outlier_detection"] = request.outlier_detection.model_dump()

    # Handle smoothing specially
    if "smoothing" in update_data and request.smoothing:
        update_data["smoothing"] = request.smoothing.model_dump()

    for key, value in update_data.items():
        setattr(pipeline, key, value)

    pipeline.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(pipeline)

    return pipeline_to_response(pipeline, db)


@router.delete(
    "/{pipeline_id}",
    summary="删除管道",
    description="删除指定训练管道及其所有关联的 Job 记录。",
)
async def delete_pipeline(pipeline_id: str, db: Session = Depends(get_db)):
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail=f"Pipeline not found: {pipeline_id}")

    db.delete(pipeline)
    db.commit()

    return {"success": True, "message": f"Pipeline {pipeline_id} deleted"}


# ==================== Pipeline Execution ====================

@router.post(
    "/run",
    response_model=PipelineRunResponse,
    summary="启动管道训练",
    description="触发指定管道的训练任务。创建新的 Job 并分发到 Celery 异步执行。如果管道已有正在运行的 Job，将返回 409 冲突错误。",
)
async def run_pipeline(request: PipelineRunRequest, db: Session = Depends(get_db)):
    from backend.redis_client import get_redis

    # Get pipeline
    pipeline = db.query(Pipeline).filter(Pipeline.id == request.pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail=f"Pipeline not found: {request.pipeline_id}")

    # Check for existing running job
    lifecycle = get_lifecycle_manager()
    existing_holder = lifecycle.get_pipeline_lock_holder(pipeline.id)
    if existing_holder:
        raise HTTPException(
            status_code=409,
            detail=f"Pipeline is already running (job: {existing_holder})"
        )

    # Override params if provided
    if request.override_params:
        pipeline.algorithm_params = {**pipeline.algorithm_params, **request.override_params}

    # Create job
    job = Job(
        id=str(uuid.uuid4()),
        pipeline_id=pipeline.id,
        status=JobStatus.PENDING.value,
        progress=0,
        created_at=datetime.utcnow(),
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    # Dispatch to Celery
    task = run_pipeline_task.delay(pipeline.id, job.id)

    # Store Celery task ID
    lifecycle.set_celery_task_id(job.id, task.id)
    lifecycle.log(job.id, f"Task dispatched to Celery (task_id: {task.id})")

    return PipelineRunResponse(
        job_id=job.id,
        pipeline_id=pipeline.id,
        status=job.status,
        message="Pipeline training started",
    )


# ==================== Job Management ====================

@router.get(
    "/jobs/running",
    response_model=List[JobResponse],
    summary="获取所有运行中的任务",
    description="获取所有处于 pending 或 running 状态的任务列表，用于前端实时显示。",
)
async def list_running_jobs(db: Session = Depends(get_db)):
    """Get all jobs that are currently pending or running."""
    jobs = db.query(Job).filter(
        Job.status.in_([JobStatus.PENDING.value, JobStatus.RUNNING.value])
    ).order_by(Job.created_at.desc()).all()
    return [job_to_response(j) for j in jobs]


@router.get(
    "/jobs/all",
    response_model=List[JobResponse],
    summary="获取所有任务列表",
    description="获取所有 Job 记录。可按状态和 Pipeline ID 筛选，支持分页。",
)
async def list_all_jobs(
    status: Optional[str] = None,
    pipeline_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """Get all jobs with optional filters."""
    query = db.query(Job)

    if status:
        query = query.filter(Job.status == status)
    if pipeline_id:
        query = query.filter(Job.pipeline_id == pipeline_id)

    jobs = query.order_by(Job.created_at.desc()).offset(offset).limit(limit).all()
    return [job_to_response(j) for j in jobs]


@router.get(
    "/jobs/{job_id}",
    response_model=JobResponse,
    summary="获取 Job 详情",
    description="获取指定 Job 的状态、进度、评估指标和阈值结果。preview_data 字段包含 ECharts 兼容的可视化数据。",
)
async def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    return job_to_response(job)


@router.get(
    "/{pipeline_id}/jobs",
    response_model=List[JobResponse],
    summary="获取管道的 Job 列表",
    description="获取指定管道的所有 Job 记录。可按状态筛选，支持分页。",
)
async def list_pipeline_jobs(
    pipeline_id: str,
    status: Optional[str] = None,
    limit: int = 10,
    db: Session = Depends(get_db),
):
    query = db.query(Job).filter(Job.pipeline_id == pipeline_id)

    if status:
        query = query.filter(Job.status == status)

    jobs = query.order_by(Job.created_at.desc()).limit(limit).all()
    return [job_to_response(j) for j in jobs]


@router.post(
    "/jobs/{job_id}/cancel",
    summary="取消 Job",
    description="取消正在运行的 Job。发送取消信号到 Worker 并撤销 Celery 任务。",
)
async def cancel_job(job_id: str, db: Session = Depends(get_db)):
    from celery import current_app

    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    if job.status not in [JobStatus.PENDING.value, JobStatus.RUNNING.value]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel job with status: {job.status}"
        )

    # Get lifecycle manager
    lifecycle = get_lifecycle_manager()

    # Request cancellation via Redis signal
    lifecycle.request_cancellation(job_id, "user_requested")

    # Also revoke Celery task
    celery_task_id = lifecycle.get_celery_task_id(job_id)
    if celery_task_id:
        current_app.control.revoke(
            celery_task_id,
            terminate=True,
            signal='SIGTERM'
        )
        lifecycle.log(job_id, f"Celery task {celery_task_id} revoked")

    # Update job status
    job.status = JobStatus.CANCELLED.value
    job.finished_at = datetime.utcnow()
    db.commit()

    lifecycle.log(job_id, "Job cancelled by user")

    return {"success": True, "status": job.status}


@router.post(
    "/jobs/{job_id}/retry",
    response_model=PipelineRunResponse,
    summary="重试失败的 Job",
    description="重试失败的或已取消的 Job。创建新的 Job 并分发执行。有最大重试次数限制。",
)
async def retry_job(job_id: str, db: Session = Depends(get_db)):
    # Get original job
    original_job = db.query(Job).filter(Job.id == job_id).first()
    if not original_job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    if original_job.status not in [JobStatus.FAILED.value, JobStatus.CANCELLED.value]:
        raise HTTPException(
            status_code=400,
            detail=f"Can only retry failed or cancelled jobs, current status: {original_job.status}"
        )

    # Check retry limit
    if original_job.retry_count >= original_job.max_retries:
        raise HTTPException(
            status_code=400,
            detail=f"Max retries ({original_job.max_retries}) exceeded"
        )

    # Get pipeline
    pipeline = db.query(Pipeline).filter(Pipeline.id == original_job.pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    # Check for existing running job
    lifecycle = get_lifecycle_manager()
    existing_holder = lifecycle.get_pipeline_lock_holder(pipeline.id)
    if existing_holder:
        raise HTTPException(
            status_code=409,
            detail=f"Pipeline is already running (job: {existing_holder})"
        )

    # Create new job
    new_job = Job(
        id=str(uuid.uuid4()),
        pipeline_id=pipeline.id,
        status=JobStatus.PENDING.value,
        progress=0,
        retry_count=original_job.retry_count + 1,
        max_retries=original_job.max_retries,
        parent_job_id=original_job.id,
        created_at=datetime.utcnow(),
    )

    db.add(new_job)
    db.commit()
    db.refresh(new_job)

    # Dispatch to Celery
    task = run_pipeline_task.delay(pipeline.id, new_job.id)

    # Store Celery task ID
    lifecycle.set_celery_task_id(new_job.id, task.id)
    lifecycle.log(new_job.id, f"Retry #{new_job.retry_count} started (parent: {original_job.id})")

    return PipelineRunResponse(
        job_id=new_job.id,
        pipeline_id=pipeline.id,
        status=new_job.status,
        message=f"Job retry #{new_job.retry_count} started",
    )


@router.get(
    "/jobs/{job_id}/logs",
    summary="获取 Job 执行日志",
    description="获取指定 Job 的执行日志记录。日志存储在 Redis 中。",
)
async def get_job_logs(job_id: str, limit: int = 100, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    lifecycle = get_lifecycle_manager()
    logs = lifecycle.get_logs(job_id, limit)

    return {"job_id": job_id, "logs": logs}