"""
Auth router — signup, login, refresh, logout, and current user endpoints.

Rate limiting is applied to the login endpoint to prevent brute-force attacks.

TOKEN LIFECYCLE:
1. POST /signup → register
2. POST /login  → returns access_token + refresh_token
3. GET  /me     → authenticated endpoint (Bearer access_token)
4. POST /refresh → exchange refresh_token for new access_token
5. POST /logout → revoke access_token (adds JTI to Redis blocklist)
"""

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.dependencies.auth import get_current_user
from app.schemas.auth import (
    SignupRequest,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    TokenPairResponse,
)
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService
from app.models.user import User
from app.core.config import settings
from app.utils.rate_limiter import check_rate_limit
from app.core.logging import get_logger
from app.utils.exceptions import UnauthorizedError

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


def _check_rate_limit(request: Request) -> None:
    """
    Redis-based rate limiting for login attempts.

    Uses a fixed-window counter keyed by client IP.
    If Redis is unavailable, rate limiting is bypassed with a warning
    (defense in depth — not a single point of failure).
    """
    client_ip = request.client.host if request.client else "unknown"
    key = f"rate_limit:login:{client_ip}"
    check_rate_limit(
        key=key,
        max_attempts=settings.RATE_LIMIT_LOGIN_ATTEMPTS,
        window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
        identifier=client_ip,
    )


@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Creates a new user account. Email must be unique. Password is hashed with bcrypt.",
)
def signup(body: SignupRequest, db: Session = Depends(get_db)):
    service = AuthService(db)
    user = service.signup(name=body.name, email=body.email, password=body.password)
    return user


@router.post(
    "/login",
    response_model=TokenPairResponse,
    summary="Login and receive JWT token pair",
    description=(
        "Authenticate with email/password. Returns an access token (short-lived, 30 min) "
        "and a refresh token (long-lived, 7 days). Use the access token in "
        "Authorization: Bearer headers. Use the refresh token to get a new access token "
        "without re-entering credentials."
    ),
)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    _check_rate_limit(request)
    service = AuthService(db)
    access_token, refresh_token = service.login(email=body.email, password=body.password)
    return TokenPairResponse(access_token=access_token, refresh_token=refresh_token)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description=(
        "Exchange a valid refresh token for a new access token. "
        "The refresh token must be valid and not expired (7-day lifetime). "
        "The original refresh token remains valid until it expires."
    ),
)
def refresh_token(body: RefreshRequest, db: Session = Depends(get_db)):
    service = AuthService(db)
    new_access_token = service.refresh(refresh_token=body.refresh_token)
    return TokenResponse(access_token=new_access_token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout (revoke access token)",
    description=(
        "Revoke the current access token by adding its JTI to the Redis blocklist. "
        "The token remains in the blocklist until its natural expiry. "
        "If Redis is unavailable, the logout is best-effort — the client should "
        "still discard the token locally."
    ),
)
def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from fastapi.security import HTTPBearer
    from fastapi import HTTPException

    # Extract the raw token from the Authorization header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise UnauthorizedError(detail="Not authenticated")

    token = auth_header.removeprefix("Bearer ").strip()
    service = AuthService(db)
    blocklisted = service.logout(token=token)
    if not blocklisted:
        logger.warning(
            "Logout best-effort — token not blocklisted (Redis may be unavailable)",
            extra={"event": "logout_degraded", "user_id": str(current_user.id)},
        )
    else:
        logger.info(
            "User logged out",
            extra={"event": "user_logout", "user_id": str(current_user.id)},
        )
    # 204 No Content — no body


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
    description="Returns the profile of the authenticated user.",
)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
