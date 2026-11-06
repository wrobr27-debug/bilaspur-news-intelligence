"""add instagram to collection_method_enum

Revision ID: ffbbfe424321
Revises: initial_migration
Create Date: 2026-11-07 00:00:00.000000

"""
from alembic import op, context


# revision identifiers, used by Alembic.
revision = "ffbbfe424321"
down_revision = "initial_migration"
branch_labels = None
depends_on = None


def _is_postgresql():
    """Check if the target database is PostgreSQL."""
    return context.get_context().dialect.name == "postgresql"


def upgrade():
    """Add 'instagram' to the collection_method_enum (PostgreSQL only)."""
    if _is_postgresql():
        op.execute(
            "ALTER TYPE collection_method_enum ADD VALUE IF NOT EXISTS 'instagram'"
        )


def downgrade():
    """Remove 'instagram' from the collection_method_enum (PostgreSQL only)."""
    if _is_postgresql():
        # PostgreSQL does not support removing enum values directly.
        # The value remains but will no longer be used by new sources.
        pass
