"""
Security utilities for password hashing and JWT token management.

Uses passlib with bcrypt for password hashing (industry standard).
Uses python-jose for JWT token creation and verification.

TOKEN TYPES:
- Access token (short-lived, 30 min): used in Authorization: Bearer header
- Refresh token (long-lived, 7 days): used to obtain new access tokens

LOGOUT / TOKEN BLOCKLIST:
Logout stores the JTI (JWT ID) in Redis with a TTL matching the token's
remaining lifetime. The auth dependency checks the blocklist on every request.
If Redis is unavailable, logout falls back gracefully (logs warning).
"""

import uuid as uuid_module
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.core.config import settings

# bcrypt is the industry standard for password hashing.
# It incorporates a salt and is computationally expensive, resisting brute force.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Token type claim values
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.

    The 'sub' claim contains the user ID — a stable identifier
    that doesn't change if the user updates their email.
    Includes a 'jti' (JWT ID) for blocklist-based logout support.
    """
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))

    payload = {
        "sub": subject,
        "type": TOKEN_TYPE_ACCESS,
        "jti": str(uuid_module.uuid4()),
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str) -> str:
    """
    Create a long-lived JWT refresh token.

    Refresh tokens have a 7-day lifetime and carry a 'type: refresh' claim
    so they cannot be used as access tokens (and vice versa).
    Includes 'jti' for logout/revocation support.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    payload = {
        "sub": subject,
        "type": TOKEN_TYPE_REFRESH,
        "jti": str(uuid_module.uuid4()),
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[str]:
    """
    Decode and validate a JWT access token. Returns the subject (user ID) or None.

    Returns None rather than raising to keep the auth dependency clean.
    Only accepts tokens with type='access' to prevent refresh tokens being
    used as access tokens.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        # Enforce token type — refresh tokens must not be used as access tokens
        if payload.get("type") != TOKEN_TYPE_ACCESS:
            return None
        return payload.get("sub")
    except JWTError:
        return None


def decode_refresh_token(token: str) -> Optional[tuple[str, str]]:
    """
    Decode and validate a refresh token.

    Returns (subject, jti) tuple on success, or None on failure.
    Only accepts tokens with type='refresh'.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != TOKEN_TYPE_REFRESH:
            return None
        sub = payload.get("sub")
        jti = payload.get("jti")
        if not sub or not jti:
            return None
        return (sub, jti)
    except JWTError:
        return None


def get_token_jti(token: str) -> Optional[str]:
    """
    Extract the JTI from a JWT without validating expiry.

    Used during logout to blocklist an already-valid token.
    Returns None if the token is malformed.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_exp": False},  # allow extracting JTI from expired tokens
        )
        return payload.get("jti")
    except JWTError:
        return None


# ---------- Token Blocklist (Redis-backed) ----------

_BLOCKLIST_PREFIX = "token:blocklist:"


def blocklist_token(jti: str, expires_in_seconds: int) -> bool:
    """
    Add a token JTI to the Redis blocklist.

    Returns True if successfully blocklisted, False if Redis is unavailable
    (graceful degradation — logout still clears client-side token).
    """
    from app.core.redis import get_redis_client

    client = get_redis_client()
    if client is None:
        return False
    try:
        key = f"{_BLOCKLIST_PREFIX}{jti}"
        client.setex(key, expires_in_seconds, "1")
        return True
    except Exception:
        return False


def is_token_blocklisted(token: str) -> bool:
    """
    Check if a token's JTI is in the blocklist.

    Returns False (not blocklisted) if Redis is unavailable — this means
    logout may not immediately revoke tokens when Redis is down, but the
    app continues to function.
    """
    from app.core.redis import get_redis_client

    jti = get_token_jti(token)
    if not jti:
        return False

    client = get_redis_client()
    if client is None:
        return False
    try:
        key = f"{_BLOCKLIST_PREFIX}{jti}"
        return client.exists(key) == 1
    except Exception:
        return False
