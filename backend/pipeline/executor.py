"""
Pipeline Executor.

Orchestrates the 5-step training pipeline with full lifecycle management:
1. Data Fetching
2. Data Cleaning
3. Model Training
4. Validation
5. Output Generation
"""

import json
import traceback
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from backend.models.pipeline import Pipeline
from backend.models.job import Job, JobStatus
from backend.redis_client import RedisClient, get_redis
from backend.tasks.lifecycle import TaskLifecycleManager, get_lifecycle_manager
from backend.pipeline.steps import (
    fetch_data,
    clean_data,
    train_model,
    validate_model,
    generate_output,
)


class PipelineCancellationError(Exception):
    """Raised when a job is cancelled."""
    pass


class PipelineExecutor:
    """
    5-Step Training Pipeline Executor with Lifecycle Management.

    Executes the training pipeline asynchronously and updates job status.
    Supports cancellation, heartbeat, and logging.
    """

    def __init__(
        self,
        pipeline: Pipeline,
        db: Session,
        redis: Optional[RedisClient] = None,
        lifecycle: Optional[TaskLifecycleManager] = None,
        datasource_configs: Optional[dict[str, dict]] = None,
    ):
        """
        Initialize executor.

        Args:
            pipeline: Pipeline configuration
            db: Database session
            redis: Redis client (optional, will create if not provided)
            lifecycle: Lifecycle manager (optional, will create if not provided)
            datasource_configs: Map of datasource_id -> config
        """
        self.pipeline = pipeline
        self.db = db
        self.redis = redis or get_redis()
        self.lifecycle = lifecycle or get_lifecycle_manager()
        self.datasource_configs = datasource_configs or {}

        # Internal state
        self._raw_data = None
        self._cleaned_data = None
        self._model = None
        self._prediction = None
        self._validation_metrics = None
        self._output = None
        self._train_stats = None

    def _log(self, message: str, level: str = "INFO") -> None:
        """Log a message for the current job."""
        if hasattr(self, '_current_job_id'):
            self.lifecycle.log(self._current_job_id, message, level)

    def _check_cancellation(self, job: Job) -> None:
        """Check if job was cancelled and raise if so."""
        cancel_info = self.lifecycle.check_cancellation(job.id)
        if cancel_info:
            self._log(f"Job cancelled: {cancel_info['reason']}", "WARNING")
            raise PipelineCancellationError(cancel_info['reason'])

    def execute(self, job: Job) -> Job:
        """
        Execute the complete pipeline with lifecycle management.

        Args:
            job: Job record to update

        Returns:
            Updated job record
        """
        self._current_job_id = job.id

        try:
            # Acquire pipeline lock
            acquired, reason = self.lifecycle.acquire_pipeline_lock(
                self.pipeline.id, job.id
            )
            if not acquired:
                job.status = JobStatus.FAILED.value
                job.error_message = reason
                job.finished_at = datetime.utcnow()
                self._update_job(job)
                return job

            # Start heartbeat
            self.lifecycle.start_heartbeat(job.id)

            # Update job status
            job.status = JobStatus.RUNNING.value
            job.started_at = datetime.utcnow()
            self._update_job(job)
            self._log("Pipeline execution started")

            # Step 1: Fetch Data
            self._check_cancellation(job)
            job = self._step_fetch(job)
            self._update_job(job)

            # Step 2: Clean Data
            self._check_cancellation(job)
            job = self._step_clean(job)
            self._update_job(job)

            # Step 3: Train Model
            self._check_cancellation(job)
            job = self._step_train(job)
            self._update_job(job)

            # Step 4: Validate
            self._check_cancellation(job)
            job = self._step_validate(job)
            self._update_job(job)

            # Step 5: Generate Output
            self._check_cancellation(job)
            job = self._step_output(job)
            self._update_job(job)

            # Success
            job.status = JobStatus.SUCCESS.value
            job.progress = 100
            job.finished_at = datetime.utcnow()
            self._update_job(job)
            self._log("Pipeline completed successfully", "INFO")

        except PipelineCancellationError as e:
            job.status = JobStatus.CANCELLED.value
            job.error_message = str(e)
            job.finished_at = datetime.utcnow()
            self._update_job(job)
            self._log(f"Pipeline cancelled: {e}", "WARNING")

        except Exception as e:
            job.status = JobStatus.FAILED.value
            job.error_message = str(e)
            job.error_traceback = traceback.format_exc()
            job.finished_at = datetime.utcnow()
            self._update_job(job)
            self._log(f"Pipeline failed: {e}", "ERROR")

        finally:
            # Stop heartbeat and release lock
            self.lifecycle.stop_heartbeat(job.id)
            self.lifecycle.release_pipeline_lock(self.pipeline.id, job.id)

        return job

    def _update_job(self, job: Job) -> None:
        """Update job in database and cache status in Redis."""
        self.db.commit()

        # Cache status in Redis for quick access
        self.redis.set_job_status(job.id, {
            "status": job.status,
            "progress": job.progress,
            "current_step": job.current_step,
        })

    def _step_fetch(self, job: Job) -> Job:
        """Step 1: Fetch data from TSDB."""
        job.current_step = "fetching_data"
        job.progress = 10
        self._log("Fetching data from datasource")

        # Get datasource config
        datasource_config = self.datasource_configs.get(self.pipeline.datasource_id, {})

        # Fetch data
        self._raw_data, error = fetch_data(
            datasource_config=datasource_config,
            metric_id=self.pipeline.metric_id,
            train_start=self.pipeline.train_start,
            train_end=self.pipeline.train_end,
            step=self.pipeline.step,
            endpoint=self.pipeline.endpoint,
            labels=self.pipeline.labels,
        )

        if error:
            raise RuntimeError(f"Data fetch failed: {error}")

        self._log(f"Fetched {len(self._raw_data) if self._raw_data is not None else 0} data points")
        job.progress = 20
        return job

    def _step_clean(self, job: Job) -> Job:
        """Step 2: Clean data."""
        job.current_step = "cleaning_data"
        job.progress = 30
        self._log("Cleaning data")

        self._cleaned_data, cleaning_stats = clean_data(
            data=self._raw_data,
            exclude_periods=self.pipeline.exclude_periods,
            outlier_detection=self.pipeline.outlier_detection,
            smoothing=self.pipeline.smoothing,
        )

        # Store cleaning stats in job preview
        if job.preview_data is None:
            job.preview_data = {}
        job.preview_data["cleaning_stats"] = cleaning_stats

        self._log(f"Cleaning complete: {cleaning_stats}")
        job.progress = 40
        return job

    def _step_train(self, job: Job) -> Job:
        """Step 3: Train model."""
        job.current_step = "training"
        job.progress = 50

        # Determine algorithm and params from model_id or direct fields
        algorithm = self.pipeline.algorithm
        algorithm_params = self.pipeline.algorithm_params or {}

        if self.pipeline.model_id:
            self._log(f"Using model config: {self.pipeline.model_id}")
            # Import locally to avoid circular import
            from smart_threshold.config.model_config import get_model_config_manager
            manager = get_model_config_manager()
            model_config = manager.get_config(self.pipeline.model_id)
            if model_config:
                algorithm = model_config.model_type.value
                # Start with model's default params
                algorithm_params = model_config.get_params()
                # Apply override_params if present
                if self.pipeline.override_params:
                    algorithm_params.update(self.pipeline.override_params)
                    self._log(f"Applied override params: {self.pipeline.override_params}")
            else:
                self._log(f"WARNING: Model config not found: {self.pipeline.model_id}, falling back to algorithm field")

        self._log(f"Training model with algorithm: {algorithm}")

        self._model, self._prediction, error = train_model(
            data=self._cleaned_data,
            algorithm=algorithm,
            algorithm_params=algorithm_params,
        )

        if error:
            raise RuntimeError(f"Training failed: {error}")

        self._log("Model training completed")
        job.progress = 60
        return job

    def _step_validate(self, job: Job) -> Job:
        """Step 4: Validate model."""
        job.current_step = "validating"
        job.progress = 70
        self._log("Validating model")

        # Calculate train data stats
        train_stats = {
            "mean": float(self._cleaned_data.mean()),
            "std": float(self._cleaned_data.std()),
            "min": float(self._cleaned_data.min()),
            "max": float(self._cleaned_data.max()),
            "count": len(self._cleaned_data),
        }

        self._validation_metrics = validate_model(
            train_data=self._cleaned_data,
            prediction=self._prediction,
        )

        # Update job with metrics
        job.rmse = self._validation_metrics.get("rmse")
        job.mae = self._validation_metrics.get("mae")
        job.mape = self._validation_metrics.get("mape")
        job.coverage = self._validation_metrics.get("coverage")
        job.false_alerts = self._validation_metrics.get("false_alerts")

        self._train_stats = train_stats
        self._log(f"Validation metrics: MAPE={job.mape:.2f}%, Coverage={job.coverage:.1%}")
        job.progress = 80
        return job

    def _step_output(self, job: Job) -> Job:
        """Step 5: Generate output."""
        job.current_step = "generating_output"
        job.progress = 90
        self._log("Generating output")

        self._output = generate_output(
            prediction=self._prediction,
            train_data_stats=self._train_stats,
            validation_metrics=self._validation_metrics,
        )

        # Store results in job
        job.upper_bounds = self._output["upper_bounds"]
        job.lower_bounds = self._output["lower_bounds"]
        job.preview_data = self._output["preview_data"]
        job.preview_data["validation_metrics"] = self._validation_metrics
        job.preview_data["train_stats"] = self._train_stats

        job.progress = 95
        return job


def run_pipeline(
    pipeline_id: str,
    job_id: str,
    db_url: Optional[str] = None,
    redis_url: Optional[str] = None,
) -> dict[str, Any]:
    """
    Run a pipeline synchronously (for Celery task).

    Args:
        pipeline_id: Pipeline ID
        job_id: Job ID
        db_url: Database URL (optional)
        redis_url: Redis URL (optional)

    Returns:
        Job result dict
    """
    from backend.db import SessionLocal

    db = SessionLocal()
    lifecycle = get_lifecycle_manager()

    try:
        # Load pipeline and job
        pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
        if not pipeline:
            raise ValueError(f"Pipeline not found: {pipeline_id}")

        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        # Load datasource configs from datasources router
        from backend.app.routers.datasources import _load_datasources
        datasource_configs_raw = _load_datasources()

        # Convert DataSourceConfigResponse to dict format
        datasource_configs = {}
        for ds_id, ds_config in datasource_configs_raw.items():
            datasource_configs[ds_id] = ds_config.model_dump()

        # Execute
        executor = PipelineExecutor(
            pipeline=pipeline,
            db=db,
            datasource_configs=datasource_configs,
        )
        job = executor.execute(job)

        return job.to_dict()

    finally:
        db.close()