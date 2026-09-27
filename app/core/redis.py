"""
Redis client configuration.

Redis serves two purposes:
1. Cache-aside layer for read-heavy endpoints (centres, tests)
2. Rate limiting for login attempts

CRITICAL: Redis is NOT the source of truth. If Redis is unavailable,
the application degrades gracefully — queries go directly to PostgreSQL,
and rate limiting is bypassed with a warning log.
"""

import redis
from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> Optional[redis.Redis]:
    """
    Get or create a Redis client singleton.

    Returns None if Redis is unavailable, allowing graceful degradation.
    """
    global _redis_client

    if _redis_client is not None:
        try:
            _redis_client.ping()
            return _redis_client
        except (redis.ConnectionError, redis.TimeoutError):
            logger.warning("Redis connection lost, attempting reconnect")
            _redis_client = None

    try:
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
            retry_on_timeout=True,
        )
        _redis_client.ping()
        logger.info("Redis connection established")
        return _redis_client
    except (redis.ConnectionError, redis.TimeoutError, Exception) as e:
        logger.warning(f"Redis unavailable: {e}. Operating without cache/rate-limiting.")
        _redis_client = None
        return None


def close_redis() -> None:
    """Close Redis connection on shutdown."""
    global _redis_client
    if _redis_client:
        try:
            _redis_client.close()
        except Exception:
            pass
        _redis_client = None
