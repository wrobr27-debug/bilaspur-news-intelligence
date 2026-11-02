import sys
import os

from alembic import context
from sqlalchemy import engine_from_config, pool

# Add the src directory to the path so we can import models
sys.path.insert(0, os.path.dirname(__file__))

# Import Base and target metadata from our models
from src.database.models import Base

target_metadata = Base.metadata


def run_migrations_offline():
    """Run migrations in 'offline mode'."""
    url = context.get_x_argument().get("db_url") or os.environ.get(
        "DATABASE_URL"
    )
    if not url:
        raise Exception("No database URL found for offline migrations")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online mode'."""
    connectable = engine_from_config(
        context.get_configuration().get_section(config_ini_section="alembic"),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()