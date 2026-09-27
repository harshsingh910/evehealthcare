"""Unit tests for AuthService."""

import pytest
from unittest.mock import MagicMock, patch
from app.services.auth_service import AuthService
from app.utils.exceptions import ConflictError, UnauthorizedError
from app.core.security import hash_password


class TestAuthServiceSignup:
    def test_signup_success(self, db_session):
        service = AuthService(db_session)
        user = service.signup(
            name="Test User",
            email="auth_signup_test@example.com",
            password="Password@123",
        )
        assert user.name == "Test User"
        assert user.email == "auth_signup_test@example.com"
        assert user.hashed_password != "Password@123"  # Must be hashed

    def test_signup_duplicate_email(self, db_session):
        service = AuthService(db_session)
        service.signup(
            name="First",
            email="auth_dup_test@example.com",
            password="Password@123",
        )
        with pytest.raises(ConflictError):
            service.signup(
                name="Second",
                email="auth_dup_test@example.com",
                password="Password@456",
            )


class TestAuthServiceLogin:
    def test_login_success(self, db_session):
        service = AuthService(db_session)
        service.signup(
            name="Login User",
            email="auth_login_test@example.com",
            password="Password@123",
        )
        access_token, refresh_token = service.login(
            email="auth_login_test@example.com",
            password="Password@123",
        )
        assert access_token is not None
        assert len(access_token) > 0
        assert refresh_token is not None
        assert len(refresh_token) > 0

    def test_login_wrong_password(self, db_session):
        service = AuthService(db_session)
        service.signup(
            name="WP User",
            email="auth_wp_test@example.com",
            password="Password@123",
        )
        with pytest.raises(UnauthorizedError):
            service.login(
                email="auth_wp_test@example.com",
                password="WrongPassword",
            )

    def test_login_nonexistent_email(self, db_session):
        service = AuthService(db_session)
        with pytest.raises(UnauthorizedError):
            service.login(
                email="doesnt_exist@example.com",
                password="Password@123",
            )
