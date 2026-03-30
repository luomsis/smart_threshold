"""
Pipeline-related Celery tasks with lifecycle management.
"""

import logging
from datetime import datetime
from typing import Any, Optional

from celery import current_app
from celery.exceptions import TaskRevokedError

from backend.tasks.celery_app import celery_app
from backend.tasks.lifecycle import get_lifecycle_manager
from backend.pipeline.executor import run_pipeline, PipelineCancellationError

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="run_pipeline_task",
    max_retries=3,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def run_pipeline_task(self, pipeline_id: str, job_id: str) -> dict[str, Any]:
    """
    Execute a training pipeline asynchronously with retry support.

    Args:
        self: Celery task instance
        pipeline_id: Pipeline ID
        job_id: Job ID

    Returns:
        Job result dictionary
    """
    lifecycle = get_lifecycle_manager()
    lifecycle.log(job_id, f"Task started (attempt {self.request.retries + 1})")

    # Store Celery task ID for cancellation support
    lifecycle.set_celery_task_id(job_id, self.request.id)

    try:
        result = run_pipeline(pipeline_id=pipeline_id, job_id=job_id)

        # Check if task was cancelled during execution
        if result.get("status") == "cancelled":
            raise TaskRevokedError("Task was cancelled")

        lifecycle.log(job_id, f"Pipeline completed: {result.get('status')}")
        return result

    except PipelineCancellationError as e:
        # Don't retry cancelled tasks
        lifecycle.log(job_id, f"Task cancelled: {e}", "WARNING")
        raise

    except TaskRevokedError:
        # Task was revoked via Celery
        lifecycle.log(job_id, "Task revoked by Celery", "WARNING")
        raise

    except Exception as e:
        lifecycle.log(job_id, f"Task failed: {e}", "ERROR")

        # Check if we should retry
        if self.request.retries < self.max_retries:
            lifecycle.log(
                job_id,
                f"Retrying in {self.default_retry_delay}s (attempt {self.request.retries + 2})",
                "WARNING"
            )
            raise self.retry(exc=e)

        # Max retries exceeded
        lifecycle.log(job_id, "Max retries exceeded", "ERROR")
        raise


@celery_app.task(name="cleanup_old_jobs")
def cleanup_old_jobs(days: int = 7) -> int:
    """
    Clean up old job records.

    Args:
        days: Delete jobs older than this many days

    Returns:
        Number of deleted jobs
    """
    from datetime import timedelta
    from backend.db import SessionLocal
    from backend.models.job import Job

    db = SessionLocal()
    lifecycle = get_lifecycle_manager()

    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        deleted = db.query(Job).filter(
            Job.created_at < cutoff,
            Job.status.in_(["success", "failed", "cancelled"])
        ).delete()
        db.commit()
        logger.info(f"Cleaned up {deleted} old jobs")
        return deleted

    finally:
        db.close()


@celery_app.task(name="expire_threshold_cache")
def expire_threshold_cache(metric_id: str) -> bool:
    """
    Expire threshold cache for a metric.

    Args:
        metric_id: Metric identifier

    Returns:
        True if successful
    """
    from backend.redis_client import get_redis

    redis = get_redis()
    return redis.delete_threshold(metric_id)


@celery_app.task(name="health_check")
def health_check() -> dict[str, str]:
    """
    Health check task for monitoring.

    Returns:
        Health status dict
    """
    from backend.redis_client import get_redis
    from backend.db import SessionLocal

    status = {
        "celery": "ok",
        "redis": "unknown",
        "database": "unknown",
    }

    # Check Redis
    try:
        redis = get_redis()
        if redis.ping():
            status["redis"] = "ok"
        else:
            status["redis"] = "error"
    except Exception as e:
        status["redis"] = f"error: {str(e)}"

    # Check Database
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        status["database"] = "ok"
    except Exception as e:
        status["database"] = f"error: {str(e)}"

    return status


@celery_app.task(name="check_stale_jobs")
def check_stale_jobs(timeout_minutes: int = 10) -> list[str]:
    """
    Check for stale jobs (running but no heartbeat).

    Args:
        timeout_minutes: Consider stale if no heartbeat for this many minutes

    Returns:
        List of stale job IDs
    """
    from backend.db import SessionLocal
    from backend.models.job import Job
    from backend.tasks.lifecycle import get_lifecycle_manager

    db = SessionLocal()
    lifecycle = get_lifecycle_manager()

    try:
        # Find running jobs
        running_jobs = db.query(Job).filter(
            Job.status == "running"
        ).all()

        stale_jobs = []
        for job in running_jobs:
            # Check heartbeat
            last_heartbeat = lifecycle.get_last_heartbeat(job.id)

            if last_heartbeat is None:
                # No heartbeat at all - might be from old system
                # Check if job started more than timeout ago
                if job.started_at:
                    elapsed = datetime.utcnow() - job.started_at
                    if elapsed.total_seconds() > timeout_minutes * 60:
                        stale_jobs.append(job.id)
                        logger.warning(
                            f"Job {job.id} has no heartbeat and started {elapsed} ago"
                        )
            else:
                elapsed = datetime.utcnow() - last_heartbeat
                if elapsed.total_seconds() > timeout_minutes * 60:
                    stale_jobs.append(job.id)
                    logger.warning(
                        f"Job {job.id} last heartbeat was {elapsed} ago"
                    )

        return stale_jobs

    finally:
        db.close()


@celery_app.task(name="mark_stale_jobs_failed")
def mark_stale_jobs_failed(timeout_minutes: int = 10) -> int:
    """
    Mark stale jobs as failed.

    Args:
        timeout_minutes: Consider stale if no heartbeat for this many minutes

    Returns:
        Number of jobs marked as failed
    """
    from backend.db import SessionLocal
    from backend.models.job import Job
    from backend.tasks.lifecycle import get_lifecycle_manager

    db = SessionLocal()
    lifecycle = get_lifecycle_manager()

    try:
        stale_ids = check_stale_jobs(timeout_minutes)

        for job_id in stale_ids:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = "Job stalled (no heartbeat)"
                job.finished_at = datetime.utcnow()
                lifecycle.log(job_id, "Job marked as failed due to stall", "ERROR")

        db.commit()
        return len(stale_ids)

    finally:
        db.close()