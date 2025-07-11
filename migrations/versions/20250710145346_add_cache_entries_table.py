"""add_cache_entries_table

Revision ID: 5c09c93697cf
Revises: 628333ca6954
Create Date: 2025-07-10 14:53:46.942142

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5c09c93697cf'
down_revision: Union[str, Sequence[str], None] = '628333ca6954'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create cache_entries table
    op.create_table('cache_entries',
        sa.Column('key', sa.Text(), nullable=False),
        sa.Column('data', sa.Text(), nullable=False),
        sa.Column('timestamp', sa.Text(), nullable=False),
        sa.Column('ttl', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('key')
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop cache_entries table
    op.drop_table('cache_entries')
