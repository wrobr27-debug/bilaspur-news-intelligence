import sys
import os

from alembic import context
from sqlalchemy import create_engine, pool

# Add the src directory to the path so we can import models
# __file__ is src/migrations/env.py, so dirname gives src/migrations
# We need src at the root, so compute repo root from config file location
sys.path.insert(0, os.path.dirname(__file__))

# Import Base and target metadata from our models
from src.database.models import Base

target_metadata = Base.metadata


def get_url():
    """Get database URL, normalizing for Psycopg 3 + Neon compatibility."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        x_args = context.get_x_argument()
        if x_args and isinstance(x_args, list):
            for arg in x_args:
                if arg.startswith("db_url="):
                    url = arg.split("=", 1)[1]
                    break
    if not url:
        # Fall back to default SQLite URL from config
        from src.config import Settings
        s = Settings()
        url = s.database_url
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
    connectable = create_engine(
        url,
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