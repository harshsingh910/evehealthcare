"""
Auth router — signup, login, and current user endpoints.

Rate limiting is applied to the login endpoint to prevent brute-force attacks.
"""

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.dependencies.auth import get_current_user
from app.schemas.auth import SignupRequest, LoginRequest, TokenResponse
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService
from app.models.user import User
from app.core.redis import get_redis_client
from app.core.config import settings
from app.utils.exceptions import TooManyRequestsError
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


def _check_rate_limit(request: Request) -> None:
    """
    Redis-based rate limiting for login attempts.

    Uses a sliding window counter keyed by client IP.
    If Redis is unavailable, rate limiting is bypassed with a warning
    (defense in depth — not a single point of failure).
    """
    client = get_redis_client()
    if client is None:
        logger.warning("Rate limiting bypassed — Redis unavailable")
        return

    client_ip = request.client.host if request.client else "unknown"
    key = f"rate_limit:login:{client_ip}"

    try:
        current = client.get(key)
        if current and int(current) >= settings.RATE_LIMIT_LOGIN_ATTEMPTS:
            raise TooManyRequestsError(
                detail="Too many login attempts. Please try again later."
            )
        pipe = client.pipeline()
        pipe.incr(key)
        pipe.expire(key, settings.RATE_LIMIT_WINDOW_SECONDS)
        pipe.execute()
    except TooManyRequestsError:
        raise
    except Exception as e:
        logger.warning(f"Rate limiting error: {e}")


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
    response_model=TokenResponse,
    summary="Login and receive JWT token",
    description="Authenticate with email/password. Returns a Bearer token for protected endpoints.",
)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    _check_rate_limit(request)
    service = AuthService(db)
    token = service.login(email=body.email, password=body.password)
    return TokenResponse(access_token=token)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
    description="Returns the profile of the authenticated user.",
)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
