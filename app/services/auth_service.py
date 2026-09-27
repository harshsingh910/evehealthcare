"""
Auth service — business logic for authentication.

Handles signup validation, password hashing, login verification,
JWT token generation, token refresh, and logout.

LOGOUT STRATEGY:
Stateless JWTs cannot be individually invalidated without a blocklist.
We use Redis as a lightweight JTI blocklist with TTL = token remaining lifetime.
If Redis is unavailable, logout still clears the client-side token (best effort),
and access tokens expire naturally within ACCESS_TOKEN_EXPIRE_MINUTES.
"""

from datetime import datetime, timezone, timedelta

from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    get_token_jti,
    blocklist_token,
    TOKEN_TYPE_ACCESS,
)
from app.core.config import settings
from app.repositories.user_repository import UserRepository
from app.models.user import User
from app.services.audit_service import AuditService
from app.models.audit_log import AuditEventType
from app.utils.exceptions import ConflictError, UnauthorizedError
from app.core.logging import get_logger

logger = get_logger(__name__)


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = UserRepository(db)
        self.audit = AuditService(db)

    def signup(self, name: str, email: str, password: str) -> User:
        """
        Register a new user.

        Checks for duplicate email before creating.
        Password is hashed with bcrypt before storage.
        """
        existing = self.repo.get_by_email(email)
        if existing:
            raise ConflictError(detail="Email already registered")

        hashed = hash_password(password)
        user = self.repo.create(name=name, email=email, hashed_password=hashed)
        self.audit.log(
            event_type=AuditEventType.USER_SIGNUP,
            actor_user_id=user.id,
            entity_type="user",
            entity_id=str(user.id),
            metadata={"email": email},
        )
        try:
            self.db.commit()
        except Exception:
            pass
        logger.info("User registered", extra={"event": "user_signup", "user_id": str(user.id)})
        return user

    def login(self, email: str, password: str) -> tuple[str, str]:
        """
        Authenticate user and return a (access_token, refresh_token) pair.

        Returns the same error message for wrong email and wrong password
        to prevent user enumeration attacks.
        """
        user = self.repo.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            self.audit.log(
                event_type=AuditEventType.LOGIN_FAILURE,
                actor_user_id=user.id if user else None,
                entity_type="user",
                metadata={"email": email},
            )
            try:
                self.db.commit()
            except Exception:
                pass
            raise UnauthorizedError(detail="Invalid email or password")

        access_token = create_access_token(subject=str(user.id))
        refresh_token = create_refresh_token(subject=str(user.id))
        self.audit.log(
            event_type=AuditEventType.LOGIN_SUCCESS,
            actor_user_id=user.id,
            entity_type="user",
            entity_id=str(user.id),
        )
        try:
            self.db.commit()
        except Exception:
            pass
        logger.info("User logged in", extra={"event": "user_login", "user_id": str(user.id)})
        return access_token, refresh_token


    def refresh(self, refresh_token: str) -> str:
        """
        Validate a refresh token and return a new access token.

        The refresh token is validated for signature, expiry, and type claim.
        Raises 401 if invalid or expired.
        """
        result = decode_refresh_token(refresh_token)
        if result is None:
            raise UnauthorizedError(detail="Invalid or expired refresh token")

        user_id_str, jti = result

        # Verify user still exists
        import uuid
        try:
            user_id = uuid.UUID(user_id_str)
        except (ValueError, AttributeError):
            raise UnauthorizedError(detail="Invalid refresh token payload")

        user = self.repo.get_by_id(user_id)
        if user is None:
            raise UnauthorizedError(detail="User not found")

        new_access_token = create_access_token(subject=str(user.id))
        logger.info(
            "Token refreshed",
            extra={"event": "token_refresh", "user_id": str(user.id)},
        )
        return new_access_token

    def logout(self, token: str) -> bool:
        """
        Revoke the current access token by adding its JTI to the Redis blocklist.

        Returns True if blocklisted successfully, False if Redis unavailable.
        In both cases the client should discard the token.
        """
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
                options={"verify_exp": False},
            )
            jti = payload.get("jti")
            exp = payload.get("exp")
            if not jti or not exp:
                return False

            # Calculate remaining seconds for the token's TTL in Redis
            now = datetime.now(timezone.utc)
            exp_dt = datetime.fromtimestamp(exp, tz=timezone.utc)
            remaining = max(0, int((exp_dt - now).total_seconds()))
            if remaining > 0:
                return blocklist_token(jti=jti, expires_in_seconds=remaining)
            return True  # Already expired — nothing to blocklist

        except JWTError:
            return False
