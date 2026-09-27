"""
Integration tests for Health and Readiness probes, and global middleware.
"""

from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


def test_health_check(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "eve-healthcare-backend"


@patch("app.main.engine")
@patch("app.main.get_redis_client")
def test_readiness_check_success(mock_redis, mock_engine, client: TestClient):
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    mock_client = MagicMock()
    mock_client.ping.return_value = True
    mock_redis.return_value = mock_client

    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["checks"]["database"] is True
    assert data["checks"]["redis"] is True


@patch("app.main.engine")
@patch("app.main.get_redis_client")
def test_readiness_check_redis_down(mock_redis, mock_engine, client: TestClient):
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_redis.return_value = None

    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    # Redis is non-critical, so status is still ready as long as DB is up
    assert data["status"] == "ready"
    assert data["checks"]["database"] is True
    assert data["checks"]["redis"] is False


@patch("app.main.engine")
@patch("app.main.get_redis_client")
def test_readiness_check_db_down(mock_redis, mock_engine, client: TestClient):
    mock_engine.connect.side_effect = Exception("DB Connection refused")
    mock_redis.return_value = None

    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["checks"]["database"] is False


def test_request_id_middleware(client: TestClient):
    # Custom request ID
    response = client.get("/health", headers={"X-Request-ID": "custom-id-999"})
    assert response.headers.get("X-Request-ID") == "custom-id-999"

    # Generated request ID
    response2 = client.get("/health")
    assert "X-Request-ID" in response2.headers
    assert len(response2.headers["X-Request-ID"]) > 0
