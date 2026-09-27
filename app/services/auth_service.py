"""
Auth service — business logic for authentication.

Handles signup validation, password hashing, login verification,
and JWT token generation. Keeps route handlers thin.
"""

from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password, create_access_token
from app.repositories.user_repository import UserRepository
from app.models.user import User
from app.utils.exceptions import ConflictError, UnauthorizedError
from app.core.logging import get_logger

logger = get_logger(__name__)


class AuthService:
    def __init__(self, db: Session):
        self.repo = UserRepository(db)

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
        logger.info("User registered", extra={"event": "user_signup", "user_id": str(user.id)})
        return user

    def login(self, email: str, password: str) -> str:
        """
        Authenticate user and return a JWT access token.

        Returns the same error message for wrong email and wrong password
        to prevent user enumeration attacks.
        """
        user = self.repo.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise UnauthorizedError(detail="Invalid email or password")

        token = create_access_token(subject=str(user.id))
        logger.info("User logged in", extra={"event": "user_login", "user_id": str(user.id)})
        return token
