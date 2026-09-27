"""
Redis cache-aside layer for read-heavy endpoints.

CACHE-ASIDE PATTERN:
1. Check Redis for cached data
2. If hit → return cached (fast path)
3. If miss → query PostgreSQL, store in Redis with TTL, return

GRACEFUL DEGRADATION:
If Redis is unavailable, all methods return None (cache miss),
and the caller falls through to PostgreSQL. The API never breaks
because Redis is down.

TTL: Configurable via CACHE_TTL_SECONDS (default 300s).
"""

import json
from typing import Optional

from app.core.redis import get_redis_client
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

CACHE_PREFIX = "cache"


def _build_key(*parts: str) -> str:
    return f"{CACHE_PREFIX}:{':'.join(parts)}"


def get_cached(key: str) -> Optional[str]:
    """Get a value from Redis cache. Returns None on miss or Redis failure."""
    try:
        client = get_redis_client()
        if client is None:
            return None
        value = client.get(key)
        if value:
            logger.debug(f"Cache HIT: {key}")
        return value
    except Exception as e:
        logger.warning(f"Redis GET failed for {key}: {e}")
        return None


def set_cached(key: str, value: str, ttl: Optional[int] = None) -> None:
    """Set a value in Redis cache with TTL. Silently fails if Redis is down."""
    try:
        client = get_redis_client()
        if client is None:
            return
        client.setex(key, ttl or settings.CACHE_TTL_SECONDS, value)
        logger.debug(f"Cache SET: {key} (TTL={ttl or settings.CACHE_TTL_SECONDS}s)")
    except Exception as e:
        logger.warning(f"Redis SET failed for {key}: {e}")


def invalidate_cached(key: str) -> None:
    """Delete a key from cache. Used when data changes."""
    try:
        client = get_redis_client()
        if client is None:
            return
        client.delete(key)
        logger.debug(f"Cache INVALIDATED: {key}")
    except Exception as e:
        logger.warning(f"Redis DEL failed for {key}: {e}")


def invalidate_pattern(pattern: str) -> None:
    """Delete all keys matching a pattern. Used for bulk invalidation."""
    try:
        client = get_redis_client()
        if client is None:
            return
        keys = client.keys(f"{CACHE_PREFIX}:{pattern}")
        if keys:
            client.delete(*keys)
            logger.debug(f"Cache INVALIDATED pattern: {pattern} ({len(keys)} keys)")
    except Exception as e:
        logger.warning(f"Redis pattern DEL failed for {pattern}: {e}")


# Convenience key builders
def centres_list_key(page: int, page_size: int) -> str:
    return _build_key("centres", "list", str(page), str(page_size))


def centre_detail_key(centre_id: str) -> str:
    return _build_key("centre", centre_id)


def centre_tests_key(centre_id: str) -> str:
    return _build_key("centre", centre_id, "tests")


def tests_list_key(page: int, page_size: int, centre_id: Optional[str] = None) -> str:
    parts = ["tests", "list", str(page), str(page_size)]
    if centre_id:
        parts.append(centre_id)
    return _build_key(*parts)


def test_detail_key(test_id: str) -> str:
    return _build_key("test", test_id)
