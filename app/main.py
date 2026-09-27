"""
EVE Healthcare — Diagnostic Test Booking & Payment Backend

Main FastAPI application entry point.

Architecture: Modular monolith with clean separation of concerns:
  Routers → Services → Repositories → Database

Key design decisions documented throughout the codebase:
  - Server-side price derivation (never trust client amounts)
  - Webhook idempotency via UNIQUE database constraints
  - State machine for booking status transitions
  - Redis cache-aside with graceful degradation
  - Structured JSON logging for observability
"""

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import setup_logging, get_logger, generate_request_id, request_id_ctx
from app.core.redis import get_redis_client, close_redis
from app.core.database import engine

from app.routers import auth, centres, tests, bookings, payments

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    setup_logging()
    logger.info("EVE Healthcare backend starting", extra={"event": "app_startup"})

    # Warm up Redis connection (non-blocking — app works without Redis)
    get_redis_client()

    yield

    # Cleanup
    close_redis()
    engine.dispose()
    logger.info("EVE Healthcare backend stopped", extra={"event": "app_shutdown"})


app = FastAPI(
    title="EVE Healthcare — Diagnostic Booking API",
    description=(
        "Backend API for diagnostic test booking and simulated payment processing. "
        "Features JWT authentication, server-side pricing, idempotent webhooks, "
        "Redis caching, and Celery background tasks."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

def _get_cors_origins() -> list[str]:
    """Parse CORS origins from environment, with development/test fallback."""
    if settings.CORS_ALLOWED_ORIGINS:
        return [o.strip() for o in settings.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]
    if settings.ENVIRONMENT in ("development", "test"):
        return ["*"]
    return []



# CORS — restrictive in production, configurable via CORS_ALLOWED_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# ---------- Middleware ----------

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Attach a unique request ID to every request for log correlation."""
    req_id = request.headers.get("X-Request-ID", generate_request_id())
    request_id_ctx.set(req_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = req_id
    return response


# ---------- Exception Handlers ----------

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catch-all handler — prevents stack traces from leaking to clients.
    Logs the full error server-side for debugging.
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


# ---------- Health/Readiness ----------

@app.get("/health", tags=["Health"], summary="Health check")
def health_check():
    """Basic liveness probe — confirms the application process is running."""
    return {"status": "healthy", "service": "eve-healthcare-backend"}


@app.get("/ready", tags=["Health"], summary="Readiness check")
def readiness_check():
    """
    Readiness probe — checks that dependencies are reachable.
    Distinguishes between app-running and dependencies-available.
    """
    checks = {"database": False, "redis": False}

    # Check PostgreSQL
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception as e:
        logger.warning(f"Database readiness check failed: {e}")

    # Check Redis (non-critical)
    try:
        client = get_redis_client()
        if client and client.ping():
            checks["redis"] = True
    except Exception as e:
        logger.warning(f"Redis readiness check failed: {e}")

    all_critical_ready = checks["database"]
    return {
        "status": "ready" if all_critical_ready else "degraded",
        "checks": checks,
    }


# ---------- Register Routers ----------

app.include_router(auth.router)
app.include_router(centres.router)
app.include_router(tests.router)
app.include_router(bookings.router)
app.include_router(payments.router)
