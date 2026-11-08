"""add category column to collected_items

Revision ID: c36c4548a5ec
Revises: ffbbfe424321
Create Date: 2026-11-08 00:00:00.000000

"""
from alembic import op, context
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c36c4548a5ec"
down_revision = "ffbbfe424321"
branch_labels = None
depends_on = None


def _is_postgresql():
    """Check if the target database is PostgreSQL."""
    return context.get_context().dialect.name == "postgresql"


def upgrade():
    """Add category column to collected_items table."""
    op.add_column(
        "collected_items",
        sa.Column("category", sa.String(100), nullable=False, server_default="uncategorized"),
    )


def downgrade():
    """Remove category column from collected_items table."""
    op.drop_column("collected_items", "category")
