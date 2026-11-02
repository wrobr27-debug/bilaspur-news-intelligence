import sys
import os

from alembic import context
from sqlalchemy import engine_from_config, pool

# Add the src directory to the path so we can import models
# __file__ is src/migrations/env.py, so dirname gives src/migrations
# We need src at the root, so compute repo root from config file location
sys.path.insert(0, os.path.dirname(__file__))

# Import Base and target metadata from our models
from src.database.models import Base

target_metadata = Base.metadata


def get_url():
    """Get database URL, normalizing for Psycopg 3 + Neon compatibility."""
    url = os.environ.get("DATABASE_URL") or context.get_x_argument().get("db_url")
    if not url:
        raise Exception("No database URL found for migrations")
    # Normalize postgresql:// to postgresql+psycopg:// for SQLAlchemy 2.0 + Psycopg 3
    if url.startswith("postgresql://") and "+psycopg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def run_migrations_offline():
    """Run migrations in 'offline mode'."""
    url = get_url()
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online mode'."""
    url = get_url()
    connectable = engine_from_config(
        context.get_configuration().get_section(config_ini_section="alembic"),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()