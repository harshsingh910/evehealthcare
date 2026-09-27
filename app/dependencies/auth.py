"""
Authentication dependency for FastAPI.

Extracts and validates the JWT Bearer token from the Authorization header,
then resolves it to a User object. Used as a dependency in protected endpoints.

TOKEN BLOCKLIST:
If a user has logged out, their token's JTI is stored in Redis with a TTL
matching the token's remaining lifetime. The blocklist check is performed
on every authenticated request. If Redis is unavailable, the blocklist is
skipped (graceful degradation — logged at WARNING level).
"""

import uuid as uuid_mod

from typing import Optional
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.security import decode_access_token, is_token_blocklisted
from app.dependencies.database import get_db
from app.models.user import User
from app.utils.exceptions import UnauthorizedError

# HTTP Bearer security scheme for Swagger/OpenAPI documentation
bearer_scheme = HTTPBearer(
    auto_error=False,
    bearerFormat="JWT",
    scheme_name="BearerAuth",
    description="Enter your JWT Bearer token (without 'Bearer ' prefix)",
)


def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency that extracts and validates the current user from JWT.

    Returns the User ORM object for downstream use.
    Raises 401 if the token is missing, invalid, expired, revoked, or the user no longer exists.
    """
    if auth is None or not auth.credentials:
        raise UnauthorizedError(detail="Not authenticated")

    token = auth.credentials

    # Check token blocklist (logout support) — Redis gracefully degrades if down
    if is_token_blocklisted(token):
        raise UnauthorizedError(detail="Token has been revoked")

    user_id_str = decode_access_token(token)
    if user_id_str is None:
        raise UnauthorizedError(detail="Invalid or expired token")

    # Convert string back to UUID for proper SQLAlchemy comparison
    try:
        user_id = uuid_mod.UUID(user_id_str)
    except (ValueError, AttributeError):
        raise UnauthorizedError(detail="Invalid token payload")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise UnauthorizedError(detail="User not found")

    return user
