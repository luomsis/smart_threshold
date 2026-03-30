"""
Task Lifecycle Manager.

Manages the complete lifecycle of background tasks:
- Concurrency control (prevent parallel execution of same pipeline)
- Task cancellation with graceful shutdown
- Heartbeat monitoring for stuck tasks
- Retry mechanism with exponential backoff
- Execution logging
"""

import json
import logging
import threading
import time
import traceback
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

import redis

logger = logging.getLogger(__name__)


class TaskLifecycleManager:
    """
    Manages task lifecycle with Redis-based coordination.

    Redis Keys:
    - task:lock:{pipeline_id} - Pipeline execution lock
    - task:heartbeat:{job_id} - Task heartbeat timestamp
    - task:cancel:{job_id} - Cancellation signal
    - task:log:{job_id} - Execution log (list)
    - task:celery_id:{job_id} - Celery task ID mapping
    """

    LOCK_TTL = 3600  # 1 hour lock timeout
    HEARTBEAT_TTL = 300  # 5 minutes heartbeat timeout
    HEARTBEAT_INTERVAL = 30  # 30 seconds between heartbeats
    LOG_MAX_ENTRIES = 1000  # Max log entries per job

    def __init__(self, redis_client: redis.Redis):
        """
        Initialize lifecycle manager.

        Args:
            redis_client: Redis client instance
        """
        self.redis = redis_client
        self._heartbeat_threads: dict[str, threading.Thread] = {}
        self._stop_events: dict[str, threading.Event] = {}

    # ==================== Lock Management ====================

    def acquire_pipeline_lock(
        self,
        pipeline_id: str,
        job_id: str,
        ttl: int = None
    ) -> tuple[bool, Optional[str]]:
        """
        Acquire execution lock for a pipeline.

        Args:
            pipeline_id: Pipeline identifier
            job_id: Current job identifier
            ttl: Lock TTL in seconds

        Returns:
            Tuple of (success, existing_job_id or error_message)
        """
        ttl = ttl or self.LOCK_TTL
        lock_key = f"task:lock:{pipeline_id}"

        # Try to acquire lock
        acquired = self.redis.set(
            lock_key,
            job_id,
            nx=True,  # Only set if not exists
            ex=ttl
        )

        if acquired:
            logger.info(f"Acquired lock for pipeline {pipeline_id}, job {job_id}")
            return True, None

        # Lock exists, get the current holder
        holder = self.redis.get(lock_key)
        if holder:
            return False, f"Pipeline is already running (job: {holder})"
        return False, "Failed to acquire lock"

    def release_pipeline_lock(self, pipeline_id: str, job_id: str) -> bool:
        """
        Release execution lock for a pipeline.

        Args:
            pipeline_id: Pipeline identifier
            job_id: Job that holds the lock

        Returns:
            True if lock was released
        """
        lock_key = f"task:lock:{pipeline_id}"

        # Only release if we hold the lock
        current_holder = self.redis.get(lock_key)
        if current_holder == job_id:
            self.redis.delete(lock_key)
            logger.info(f"Released lock for pipeline {pipeline_id}, job {job_id}")
            return True

        logger.warning(
            f"Cannot release lock: held by {current_holder}, not {job_id}"
        )
        return False

    def get_pipeline_lock_holder(self, pipeline_id: str) -> Optional[str]:
        """Get current lock holder for a pipeline."""
        lock_key = f"task:lock:{pipeline_id}"
        return self.redis.get(lock_key)

    # ==================== Heartbeat Management ====================

    def start_heartbeat(self, job_id: str) -> None:
        """
        Start heartbeat thread for a job.

        Args:
            job_id: Job identifier
        """
        if job_id in self._heartbeat_threads:
            logger.warning(f"Heartbeat already running for job {job_id}")
            return

        stop_event = threading.Event()
        self._stop_events[job_id] = stop_event

        def heartbeat_loop():
            while not stop_event.is_set():
                self.update_heartbeat(job_id)
                stop_event.wait(self.HEARTBEAT_INTERVAL)

        thread = threading.Thread(
            target=heartbeat_loop,
            name=f"heartbeat-{job_id}",
            daemon=True
        )
        thread.start()
        self._heartbeat_threads[job_id] = thread

        logger.info(f"Started heartbeat for job {job_id}")

    def stop_heartbeat(self, job_id: str) -> None:
        """Stop heartbeat thread for a job."""
        if job_id in self._stop_events:
            self._stop_events[job_id].set()
            del self._stop_events[job_id]

        if job_id in self._heartbeat_threads:
            self._heartbeat_threads[job_id].join(timeout=5)
            del self._heartbeat_threads[job_id]

        # Clear heartbeat key
        self.redis.delete(f"task:heartbeat:{job_id}")
        logger.info(f"Stopped heartbeat for job {job_id}")

    def update_heartbeat(self, job_id: str) -> bool:
        """
        Update heartbeat timestamp for a job.

        Args:
            job_id: Job identifier

        Returns:
            True if heartbeat was updated
        """
        key = f"task:heartbeat:{job_id}"
        self.redis.setex(
            key,
            self.HEARTBEAT_TTL,
            datetime.utcnow().isoformat()
        )
        return True

    def get_last_heartbeat(self, job_id: str) -> Optional[datetime]:
        """Get last heartbeat time for a job."""
        key = f"task:heartbeat:{job_id}"
        data = self.redis.get(key)
        if data:
            return datetime.fromisoformat(data)
        return None

    def is_job_alive(self, job_id: str) -> bool:
        """Check if a job is still alive (has recent heartbeat)."""
        return self.redis.exists(f"task:heartbeat:{job_id}")

    # ==================== Cancellation Management ====================

    def request_cancellation(self, job_id: str, reason: str = "user_requested") -> bool:
        """
        Request cancellation for a job.

        Args:
            job_id: Job identifier
            reason: Cancellation reason

        Returns:
            True if cancellation was requested
        """
        key = f"task:cancel:{job_id}"
        self.redis.setex(
            key,
            3600,  # 1 hour TTL
            json.dumps({
                "reason": reason,
                "requested_at": datetime.utcnow().isoformat()
            })
        )
        logger.info(f"Cancellation requested for job {job_id}: {reason}")
        return True

    def check_cancellation(self, job_id: str) -> Optional[dict]:
        """
        Check if cancellation was requested for a job.

        Args:
            job_id: Job identifier

        Returns:
            Cancellation info dict or None
        """
        key = f"task:cancel:{job_id}"
        data = self.redis.get(key)
        if data:
            return json.loads(data)
        return None

    def clear_cancellation(self, job_id: str) -> None:
        """Clear cancellation signal."""
        self.redis.delete(f"task:cancel:{job_id}")

    # ==================== Logging Management ====================

    def log(self, job_id: str, message: str, level: str = "INFO") -> None:
        """
        Add a log entry for a job.

        Args:
            job_id: Job identifier
            message: Log message
            level: Log level (DEBUG, INFO, WARNING, ERROR)
        """
        key = f"task:log:{job_id}"
        entry = json.dumps({
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message
        })

        # Add to list and trim to max entries
        pipe = self.redis.pipeline()
        pipe.rpush(key, entry)
        pipe.ltrim(key, -self.LOG_MAX_ENTRIES, -1)
        pipe.expire(key, 86400)  # 24 hour TTL
        pipe.execute()

        # Also log to Python logger
        log_func = getattr(logger, level.lower(), logger.info)
        log_func(f"[Job {job_id}] {message}")

    def get_logs(self, job_id: str, limit: int = 100) -> list[dict]:
        """
        Get log entries for a job.

        Args:
            job_id: Job identifier
            limit: Maximum number of entries to return

        Returns:
            List of log entry dicts
        """
        key = f"task:log:{job_id}"
        entries = self.redis.lrange(key, -limit, -1)
        return [json.loads(entry) for entry in entries]

    def clear_logs(self, job_id: str) -> None:
        """Clear logs for a job."""
        self.redis.delete(f"task:log:{job_id}")

    # ==================== Celery Task ID Mapping ====================

    def set_celery_task_id(self, job_id: str, celery_task_id: str) -> None:
        """Map job ID to Celery task ID."""
        key = f"task:celery_id:{job_id}"
        self.redis.setex(key, 86400, celery_task_id)

    def get_celery_task_id(self, job_id: str) -> Optional[str]:
        """Get Celery task ID for a job."""
        key = f"task:celery_id:{job_id}"
        return self.redis.get(key)

    # ==================== Cleanup ====================

    def cleanup_job(self, job_id: str, pipeline_id: str) -> None:
        """
        Cleanup all Redis keys for a completed job.

        Args:
            job_id: Job identifier
            pipeline_id: Pipeline identifier
        """
        self.stop_heartbeat(job_id)
        self.release_pipeline_lock(pipeline_id, job_id)
        self.clear_cancellation(job_id)

        # Keep logs for a while, don't delete immediately
        logger.info(f"Cleaned up job {job_id}")


# Global lifecycle manager instance
_lifecycle_manager: Optional[TaskLifecycleManager] = None


def get_lifecycle_manager() -> TaskLifecycleManager:
    """Get or create lifecycle manager instance."""
    global _lifecycle_manager

    if _lifecycle_manager is None:
        from backend.redis_client import get_redis
        redis_client = get_redis()
        _lifecycle_manager = TaskLifecycleManager(redis_client.client)

    return _lifecycle_manager