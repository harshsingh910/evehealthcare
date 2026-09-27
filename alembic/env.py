"""
Alembic environment configuration.

Reads DATABASE_URL from the application config (pydantic-settings)
so the migration tool and the app always use the same connection string.
"""

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Import all models so Alembic can detect them for autogenerate
from app.core.database import Base
from app.core.config import settings

# These imports register the models with Base.metadata
from app.models.user import User  # noqa: F401
from app.models.diagnostic_centre import DiagnosticCentre  # noqa: F401
from app.models.diagnostic_test import DiagnosticTest  # noqa: F401
from app.models.centre_test import CentreTest  # noqa: F401
from app.models.booking import Booking  # noqa: F401
from app.models.payment import Payment  # noqa: F401

config = context.config

# Override sqlalchemy.url with the app's DATABASE_URL
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — generates SQL without connecting."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode — connects to the database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
