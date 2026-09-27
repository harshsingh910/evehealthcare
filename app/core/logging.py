"""
Structured JSON logging configuration.

Provides consistent log format across the application with contextual fields
like request_id, user_id, booking_id for observability and debugging.

IMPORTANT: Never log passwords, JWT tokens, or database credentials.
"""

import logging
import json
import sys
import uuid
from contextvars import ContextVar
from typing import Optional

from app.core.config import settings

# Context variables for request-scoped logging
request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
user_id_ctx: ContextVar[Optional[str]] = ContextVar("user_id", default=None)


class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter for production observability."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add request context if available
        req_id = request_id_ctx.get()
        if req_id:
            log_data["request_id"] = req_id

        usr_id = user_id_ctx.get()
        if usr_id:
            log_data["user_id"] = str(usr_id)

        # Add extra fields from record
        for key in ("booking_id", "payment_id", "event_id", "event"):
            value = getattr(record, key, None)
            if value is not None:
                log_data[key] = str(value)

        # Add exception info
        if record.exc_info and record.exc_info[2]:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def setup_logging() -> None:
    """Configure application-wide structured logging."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    # Remove existing handlers
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root_logger.addHandler(handler)

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger instance."""
    return logging.getLogger(name)


def generate_request_id() -> str:
    """Generate a unique request ID for tracing."""
    return str(uuid.uuid4())
