"""Integration tests for CORS policy and origins."""

from fastapi.testclient import TestClient
from app.main import _get_cors_origins


def test_cors_origins_resolution_custom():
    """Verify comma-separated origins from settings are parsed correctly."""
    from unittest.mock import patch
    with patch("app.main.settings.CORS_ALLOWED_ORIGINS", "https://evehealth.com, https://app.evehealth.com"):
        origins = _get_cors_origins()
        assert origins == ["https://evehealth.com", "https://app.evehealth.com"]


def test_cors_origins_resolution_production_empty():
    """Verify production with no origins defaults to restrictive empty list."""
    from unittest.mock import patch
    with patch("app.main.settings.CORS_ALLOWED_ORIGINS", ""):
        with patch("app.main.settings.ENVIRONMENT", "production"):
            origins = _get_cors_origins()
            assert origins == []


def test_cors_preflight_request(client: TestClient):
    """Verify OPTIONS request handles preflight properly."""
    response = client.options(
        "/api/v1/centres",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    # Status code is 200 for allowed preflight in development
    assert response.status_code == 200
