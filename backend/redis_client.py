"""
Redis client configuration.
"""

import os
import json
from typing import Optional, Any

import redis


class RedisClient:
    """
    Redis client wrapper for caching threshold results.

    Key format:
    - Threshold upper bounds: threshold:{metric_id}:upper
    - Threshold lower bounds: threshold:{metric_id}:lower
    - Job status cache: job:{job_id}:status
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
    ):
        """
        Initialize Redis client.

        Args:
            host: Redis host
            port: Redis port
            db: Redis database number
            password: Redis password (optional)
        """
        self.client = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=True
        )

    def get_threshold(self, metric_id: str) -> Optional[dict[str, list[float]]]:
        """
        Get threshold bounds for a metric.

        Args:
            metric_id: Metric identifier

        Returns:
            Dictionary with 'upper' and 'lower' arrays, or None if not found
        """
        upper_key = f"threshold:{metric_id}:upper"
        lower_key = f"threshold:{metric_id}:lower"

        upper = self.client.get(upper_key)
        lower = self.client.get(lower_key)

        if upper is None or lower is None:
            return None

        return {
            "upper": json.loads(upper),
            "lower": json.loads(lower)
        }

    def set_threshold(
        self,
        metric_id: str,
        upper_bounds: list[float],
        lower_bounds: list[float],
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set threshold bounds for a metric.

        Args:
            metric_id: Metric identifier
            upper_bounds: Upper bound array (1440 elements)
            lower_bounds: Lower bound array (1440 elements)
            ttl: Time-to-live in seconds (optional)

        Returns:
            True if successful
        """
        upper_key = f"threshold:{metric_id}:upper"
        lower_key = f"threshold:{metric_id}:lower"

        pipe = self.client.pipeline()
        pipe.set(upper_key, json.dumps(upper_bounds))
        pipe.set(lower_key, json.dumps(lower_bounds))

        if ttl:
            pipe.expire(upper_key, ttl)
            pipe.expire(lower_key, ttl)

        pipe.execute()
        return True

    def delete_threshold(self, metric_id: str) -> bool:
        """
        Delete threshold for a metric.

        Args:
            metric_id: Metric identifier

        Returns:
            True if keys were deleted
        """
        upper_key = f"threshold:{metric_id}:upper"
        lower_key = f"threshold:{metric_id}:lower"
        return bool(self.client.delete(upper_key, lower_key))

    def set_job_status(self, job_id: str, status: dict[str, Any], ttl: int = 3600) -> bool:
        """
        Cache job status for quick access.

        Args:
            job_id: Job identifier
            status: Status dictionary
            ttl: Cache TTL in seconds (default 1 hour)

        Returns:
            True if successful
        """
        key = f"job:{job_id}:status"
        return self.client.setex(key, ttl, json.dumps(status))

    def get_job_status(self, job_id: str) -> Optional[dict[str, Any]]:
        """
        Get cached job status.

        Args:
            job_id: Job identifier

        Returns:
            Status dictionary or None
        """
        key = f"job:{job_id}:status"
        data = self.client.get(key)
        return json.loads(data) if data else None

    def ping(self) -> bool:
        """Test Redis connection."""
        try:
            return self.client.ping()
        except redis.ConnectionError:
            return False


# Global Redis client instance
_redis_client: Optional[RedisClient] = None


def get_redis() -> RedisClient:
    """
    Get Redis client instance.

    Uses environment variables for configuration:
    - REDIS_HOST: Redis host (default: 127.0.0.1)
    - REDIS_PORT: Redis port (default: 6379)
    - REDIS_DB: Redis database number (default: 0)
    - REDIS_PASSWORD: Redis password (optional)
    """
    global _redis_client

    if _redis_client is None:
        _redis_client = RedisClient(
            host=os.getenv("REDIS_HOST", "127.0.0.1"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=int(os.getenv("REDIS_DB", "0")),
            password=os.getenv("REDIS_PASSWORD")
        )

    return _redis_client