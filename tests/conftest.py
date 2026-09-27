"""
Test configuration and fixtures.

Uses SQLite for tests — no external PostgreSQL/Redis dependency required.
Each test function gets a fresh database session. Tables are created once
per session and dropped after all tests complete.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session

# Set test environment BEFORE importing app modules
os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"

from app.core.database import Base
from app.core.security import hash_password, create_access_token
from app.dependencies.database import get_db
from app.main import app

# Import all models to register them with Base.metadata
from app.models.user import User
from app.models.diagnostic_centre import DiagnosticCentre
from app.models.diagnostic_test import DiagnosticTest
from app.models.centre_test import CentreTest
from app.models.booking import Booking, BookingStatus
from app.models.payment import Payment, PaymentStatus

# SQLite for tests — no external DB dependency
TEST_DATABASE_URL = "sqlite:///./test.db"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create all tables once per test session."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)
    if os.path.exists("./test.db"):
        os.remove("./test.db")


@pytest.fixture()
def db_session():
    """
    Provide a database session per test.

    Uses a nested transaction (SAVEPOINT) so that service-layer commits
    don't actually persist — the outer transaction is rolled back after
    each test, ensuring clean state.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestSessionLocal(bind=connection)

    # Intercept session.commit() calls from service layer —
    # redirect them to a nested savepoint so data stays in the
    # outer transaction that we roll back after the test.
    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(session, transaction):
        nonlocal nested
        if transaction.nested and not transaction._parent.nested:
            nested = connection.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session) -> TestClient:
    """FastAPI test client with overridden DB dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


# ---------- Helper Fixtures ----------

@pytest.fixture()
def sample_user(db_session) -> User:
    """Create a test user."""
    user = User(
        name="Test User",
        email=f"test_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("Password@123"),
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture()
def auth_headers(sample_user) -> dict:
    """Generate auth headers for the sample user."""
    token = create_access_token(subject=str(sample_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def second_user(db_session) -> User:
    """Create a second test user for authorization tests."""
    user = User(
        name="Second User",
        email=f"second_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("Password@456"),
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture()
def second_auth_headers(second_user) -> dict:
    """Auth headers for the second user."""
    token = create_access_token(subject=str(second_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def sample_centre(db_session) -> DiagnosticCentre:
    """Create a test diagnostic centre."""
    centre = DiagnosticCentre(name="Test Apollo Diagnostics", location="Test Delhi")
    db_session.add(centre)
    db_session.flush()
    return centre


@pytest.fixture()
def sample_test(db_session) -> DiagnosticTest:
    """Create a test diagnostic test."""
    test = DiagnosticTest(name="Test CBC", description="Complete Blood Count test")
    db_session.add(test)
    db_session.flush()
    return test


@pytest.fixture()
def sample_centre_test(db_session, sample_centre, sample_test) -> CentreTest:
    """Create a centre-test association with pricing."""
    ct = CentreTest(
        centre_id=sample_centre.id,
        test_id=sample_test.id,
        price=Decimal("500.00"),
    )
    db_session.add(ct)
    db_session.flush()
    return ct


@pytest.fixture()
def sample_booking(db_session, sample_user, sample_centre, sample_test, sample_centre_test) -> Booking:
    """Create a test booking."""
    booking = Booking(
        user_id=sample_user.id,
        centre_id=sample_centre.id,
        test_id=sample_test.id,
        appointment_datetime=datetime.now(timezone.utc) + timedelta(days=7),
        amount=sample_centre_test.price,
        status=BookingStatus.PENDING,
    )
    db_session.add(booking)
    db_session.flush()
    return booking


@pytest.fixture()
def future_datetime() -> str:
    """Return a future datetime string for booking tests."""
    return (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()


@pytest.fixture()
def past_datetime() -> str:
    """Return a past datetime string for validation tests."""
    return (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
