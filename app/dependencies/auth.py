"""
Authentication dependency for FastAPI.

Extracts and validates the JWT Bearer token from the Authorization header,
then resolves it to a User object. Used as a dependency in protected endpoints.
"""

import uuid as uuid_mod

from typing import Optional
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
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
    Raises 401 if the token is missing, invalid, expired, or the user no longer exists.
    """
    if auth is None or not auth.credentials:
        raise UnauthorizedError(detail="Not authenticated")

    token = auth.credentials
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
