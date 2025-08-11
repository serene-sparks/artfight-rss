"""add_news_table

Revision ID: e1807622ffb7
Revises: 5c09c93697cf
Create Date: 2025-08-10 12:38:31.943419

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1807622ffb7'
down_revision: Union[str, Sequence[str], None] = '5c09c93697cf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create news table
    op.create_table('news',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('author', sa.Text(), nullable=True),
        sa.Column('posted_at', sa.Text(), nullable=True),
        sa.Column('edited_at', sa.Text(), nullable=True),
        sa.Column('edited_by', sa.Text(), nullable=True),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('fetched_at', sa.Text(), nullable=False),
        sa.Column('first_seen', sa.Text(), nullable=False),
        sa.Column('last_updated', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for news table
    op.create_index('idx_news_fetched_at', 'news', ['fetched_at'])
    op.create_index('idx_news_posted_at', 'news', ['posted_at'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes for news table
    op.drop_index('idx_news_posted_at', 'news')
    op.drop_index('idx_news_fetched_at', 'news')
    
    # Drop news table
    op.drop_table('news')
