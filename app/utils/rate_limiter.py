"""
Redis-based fixed-window rate limiter utility.

Provides a reusable check_rate_limit() helper that can be called from any
router with custom key prefix and limits.

DESIGN:
- Key format: rate_limit:<prefix>:<identifier>
- Identifier can be client IP (unauthenticated) or user ID (authenticated)
- Uses Redis INCR + EXPIRE for atomic counter management
- Graceful degradation: if Redis is unavailable, rate limiting is bypassed
  with a WARNING log so the app never fails because of Redis being down.

CONCURRENCY:
Using pipeline (MULTI/EXEC) to atomically increment and set expiry prevents
the race window between INCR and EXPIRE that would exist if called separately.

TESTABILITY:
Module-level imports allow tests to patch get_redis_client via
unittest.mock.patch("app.utils.rate_limiter.get_redis_client").
"""

import logging
import redis as redis_module
from typing import Optional

from app.core.redis import get_redis_client
from app.utils.exceptions import TooManyRequestsError

logger = logging.getLogger(__name__)


def check_rate_limit(
    key: str,
    max_attempts: int,
    window_seconds: int,
    identifier: Optional[str] = None,
) -> None:
    """
    Enforce a Redis fixed-window rate limit.

    Args:
        key:            Full Redis key to use for tracking.
        max_attempts:   Maximum allowed calls within the window.
        window_seconds: Rolling window duration in seconds.
        identifier:     For logging — human-readable label (IP, user ID).

    Raises:
        TooManyRequestsError: When the caller has exceeded the limit.
    """
    client = get_redis_client()
    if client is None:
        logger.warning(
            "Rate limiting bypassed — Redis unavailable",
            extra={"key": key, "identifier": identifier},
        )
        return

    try:
        current = client.get(key)
        count = int(current) if current else 0

        if count >= max_attempts:
            logger.warning(
                "Rate limit exceeded",
                extra={"key": key, "identifier": identifier, "count": count},
            )
            raise TooManyRequestsError(
                detail="Too many requests. Please try again later."
            )

        # Atomically increment and (re-)set expiry
        pipe = client.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_seconds)
        pipe.execute()

    except TooManyRequestsError:
        raise
    except (redis_module.ConnectionError, redis_module.TimeoutError) as e:
        logger.warning(f"Rate limiting Redis error: {e}")
    except Exception as e:
        logger.warning(f"Rate limiting unexpected error: {e}")
