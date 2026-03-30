"""
Celery application configuration.
"""

import os

from celery import Celery

# Redis URL from environment
REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_DB = os.getenv("REDIS_DB", "0")

# Celery broker and backend
BROKER_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
RESULT_BACKEND = f"redis://{REDIS_HOST}:{REDIS_PORT}/1"  # Use different DB for results

# Create Celery app
celery_app = Celery(
    "smart_threshold",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
)

# Configuration
celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="Asia/Shanghai",
    enable_utc=True,

    # Task settings
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes max
    task_soft_time_limit=25 * 60,  # Soft limit at 25 minutes

    # Result settings
    result_expires=3600,  # Results expire after 1 hour

    # Worker settings
    worker_prefetch_multiplier=1,
    worker_concurrency=4,

    # Task routing - all tasks to default queue for simplicity
    # task_routes={
    #     "backend.tasks.pipeline_tasks.*": {"queue": "pipeline"},
    # },

    # Default queue
    task_default_queue="default",
)

# Auto-discover tasks - must import tasks module for registration
celery_app.autodiscover_tasks(["backend.tasks"])

# Explicitly import tasks to ensure registration
from backend.tasks import pipeline_tasks  # noqa: F401