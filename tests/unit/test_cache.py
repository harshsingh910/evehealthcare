"""
Unit tests for Redis cache layer (app/cache/centre_cache.py).

Tests cache hits, cache misses, invalidation, pattern deletion,
key generation, and graceful degradation when Redis is down.
"""

from unittest.mock import MagicMock, patch
from app.cache.centre_cache import (
    get_cached,
    set_cached,
    invalidate_cached,
    invalidate_pattern,
    centres_list_key,
    centre_detail_key,
    centre_tests_key,
    tests_list_key as cache_tests_list_key,
    test_detail_key as cache_test_detail_key,
)


def test_key_builders():
    assert centres_list_key(1, 20) == "cache:centres:list:1:20"
    assert centre_detail_key("abc-123") == "cache:centre:abc-123"
    assert centre_tests_key("abc-123") == "cache:centre:abc-123:tests"
    assert cache_tests_list_key(1, 10) == "cache:tests:list:1:10"
    assert cache_tests_list_key(1, 10, centre_id="c-456") == "cache:tests:list:1:10:c-456"
    assert cache_test_detail_key("t-789") == "cache:test:t-789"


@patch("app.cache.centre_cache.get_redis_client")
def test_get_cached_hit(mock_get_client):
    mock_client = MagicMock()
    mock_client.get.return_value = '{"data": "test"}'
    mock_get_client.return_value = mock_client

    result = get_cached("cache:test_key")
    assert result == '{"data": "test"}'
    mock_client.get.assert_called_once_with("cache:test_key")


@patch("app.cache.centre_cache.get_redis_client")
def test_get_cached_miss(mock_get_client):
    mock_client = MagicMock()
    mock_client.get.return_value = None
    mock_get_client.return_value = mock_client

    result = get_cached("cache:missing_key")
    assert result is None


@patch("app.cache.centre_cache.get_redis_client")
def test_get_cached_redis_down(mock_get_client):
    mock_get_client.return_value = None
    result = get_cached("cache:any_key")
    assert result is None


@patch("app.cache.centre_cache.get_redis_client")
def test_get_cached_redis_exception(mock_get_client):
    mock_client = MagicMock()
    mock_client.get.side_effect = Exception("Connection refused")
    mock_get_client.return_value = mock_client

    result = get_cached("cache:error_key")
    assert result is None


@patch("app.cache.centre_cache.get_redis_client")
def test_set_cached_success(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    set_cached("cache:my_key", '{"foo": "bar"}', ttl=60)
    mock_client.setex.assert_called_once_with("cache:my_key", 60, '{"foo": "bar"}')


@patch("app.cache.centre_cache.get_redis_client")
def test_set_cached_redis_down(mock_get_client):
    mock_get_client.return_value = None
    # Should not raise exception
    set_cached("cache:my_key", '{"foo": "bar"}')


@patch("app.cache.centre_cache.get_redis_client")
def test_set_cached_redis_exception(mock_get_client):
    mock_client = MagicMock()
    mock_client.setex.side_effect = Exception("Write failed")
    mock_get_client.return_value = mock_client
    # Should not raise exception
    set_cached("cache:my_key", '{"foo": "bar"}')


@patch("app.cache.centre_cache.get_redis_client")
def test_invalidate_cached(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    invalidate_cached("cache:my_key")
    mock_client.delete.assert_called_once_with("cache:my_key")


@patch("app.cache.centre_cache.get_redis_client")
def test_invalidate_cached_redis_down(mock_get_client):
    mock_get_client.return_value = None
    invalidate_cached("cache:my_key")


@patch("app.cache.centre_cache.get_redis_client")
def test_invalidate_cached_exception(mock_get_client):
    mock_client = MagicMock()
    mock_client.delete.side_effect = Exception("Delete failed")
    mock_get_client.return_value = mock_client
    invalidate_cached("cache:my_key")


@patch("app.cache.centre_cache.get_redis_client")
def test_invalidate_pattern(mock_get_client):
    mock_client = MagicMock()
    mock_client.keys.return_value = ["cache:centres:list:1:20", "cache:centres:list:2:20"]
    mock_get_client.return_value = mock_client

    invalidate_pattern("centres:*")
    mock_client.keys.assert_called_once_with("cache:centres:*")
    mock_client.delete.assert_called_once_with("cache:centres:list:1:20", "cache:centres:list:2:20")


@patch("app.cache.centre_cache.get_redis_client")
def test_invalidate_pattern_no_keys(mock_get_client):
    mock_client = MagicMock()
    mock_client.keys.return_value = []
    mock_get_client.return_value = mock_client

    invalidate_pattern("centres:*")
    mock_client.delete.assert_not_called()


@patch("app.cache.centre_cache.get_redis_client")
def test_invalidate_pattern_redis_down(mock_get_client):
    mock_get_client.return_value = None
    invalidate_pattern("centres:*")


@patch("app.cache.centre_cache.get_redis_client")
def test_invalidate_pattern_exception(mock_get_client):
    mock_client = MagicMock()
    mock_client.keys.side_effect = Exception("Redis failure")
    mock_get_client.return_value = mock_client
    invalidate_pattern("centres:*")
