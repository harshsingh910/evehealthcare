"""Integration tests for Auth endpoints."""

import pytest


class TestSignup:
    def test_signup_success(self, client):
        response = client.post("/api/v1/auth/signup", json={
            "name": "Harsh Singh",
            "email": "integ_signup@example.com",
            "password": "Password@123",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Harsh Singh"
        assert data["email"] == "integ_signup@example.com"
        assert "hashed_password" not in data
        assert "password" not in data

    def test_signup_duplicate_email(self, client):
        client.post("/api/v1/auth/signup", json={
            "name": "First",
            "email": "integ_dup@example.com",
            "password": "Password@123",
        })
        response = client.post("/api/v1/auth/signup", json={
            "name": "Second",
            "email": "integ_dup@example.com",
            "password": "Password@456",
        })
        assert response.status_code == 409

    def test_signup_invalid_email(self, client):
        response = client.post("/api/v1/auth/signup", json={
            "name": "Bad Email",
            "email": "not-an-email",
            "password": "Password@123",
        })
        assert response.status_code == 422

    def test_signup_weak_password(self, client):
        response = client.post("/api/v1/auth/signup", json={
            "name": "Short Password",
            "email": "integ_short@example.com",
            "password": "123",
        })
        assert response.status_code == 422

    def test_signup_missing_name(self, client):
        response = client.post("/api/v1/auth/signup", json={
            "email": "integ_noname@example.com",
            "password": "Password@123",
        })
        assert response.status_code == 422


class TestLogin:
    def test_login_success(self, client):
        client.post("/api/v1/auth/signup", json={
            "name": "Login Test",
            "email": "integ_login@example.com",
            "password": "Password@123",
        })
        response = client.post("/api/v1/auth/login", json={
            "email": "integ_login@example.com",
            "password": "Password@123",
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client):
        client.post("/api/v1/auth/signup", json={
            "name": "WP Test",
            "email": "integ_wp@example.com",
            "password": "Password@123",
        })
        response = client.post("/api/v1/auth/login", json={
            "email": "integ_wp@example.com",
            "password": "WrongPassword",
        })
        assert response.status_code == 401

    def test_login_nonexistent_email(self, client):
        response = client.post("/api/v1/auth/login", json={
            "email": "nobody@example.com",
            "password": "Password@123",
        })
        assert response.status_code == 401

    def test_login_rate_limited(self, client):
        from unittest.mock import patch, MagicMock
        with patch("app.routers.auth.get_redis_client") as mock_redis:
            mock_client = MagicMock()
            mock_client.get.return_value = "5"
            mock_redis.return_value = mock_client

            response = client.post("/api/v1/auth/login", json={
                "email": "rate_limit@example.com",
                "password": "Password@123",
            })
            assert response.status_code == 429
            assert "Too many login attempts" in response.json()["detail"]

    def test_login_rate_limiting_pipeline_and_graceful_degradation(self, client):
        from unittest.mock import patch, MagicMock
        with patch("app.routers.auth.get_redis_client") as mock_redis:
            mock_client = MagicMock()
            mock_client.get.return_value = "0"
            mock_pipe = MagicMock()
            mock_client.pipeline.return_value = mock_pipe
            mock_redis.return_value = mock_client

            response = client.post("/api/v1/auth/login", json={
                "email": "nobody@example.com",
                "password": "Password@123",
            })
            # Pipeline incremented counter
            mock_pipe.incr.assert_called_once()
            mock_pipe.expire.assert_called_once()
            mock_pipe.execute.assert_called_once()
            assert response.status_code == 401



class TestMe:
    def test_me_authenticated(self, client, auth_headers):
        response = client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "name" in data
        assert "email" in data
        assert "hashed_password" not in data

    def test_me_no_token(self, client):
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401

    def test_me_invalid_token(self, client):
        response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid"})
        assert response.status_code == 401

    def test_me_invalid_uuid_payload(self, client):
        from app.core.security import create_access_token
        token = create_access_token(subject="not-a-valid-uuid")
        response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
        assert "Invalid token payload" in response.json()["detail"]

    def test_me_user_not_found(self, client):
        import uuid
        from app.core.security import create_access_token
        token = create_access_token(subject=str(uuid.uuid4()))
        response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
        assert "User not found" in response.json()["detail"]

