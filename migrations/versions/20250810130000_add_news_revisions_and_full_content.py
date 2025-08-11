"""add_news_revisions_and_full_content

Revision ID: f1807622ffb8
Revises: e1807622ffb7
Create Date: 2025-08-10 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1807622ffb8'
down_revision: Union[str, Sequence[str], None] = 'e1807622ffb7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to support news revisions and full content storage.
    
    Changes made:
    1. Added NewsRevision model to track post revisions
    2. Updated ArtFightNews model to store full content instead of truncated
    3. Modified save_news method to detect changes and create revision records
    """
    # Create news_revisions table
    op.create_table('news_revisions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('news_id', sa.Integer(), nullable=False),
        sa.Column('revision_number', sa.Integer(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('author', sa.Text(), nullable=True),
        sa.Column('posted_at', sa.Text(), nullable=True),
        sa.Column('edited_at', sa.Text(), nullable=True),
        sa.Column('edited_by', sa.Text(), nullable=True),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('fetched_at', sa.Text(), nullable=False),
        sa.Column('created_at', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['news_id'], ['news.id'], ),
        sa.UniqueConstraint('news_id', 'revision_number', name='uq_news_revisions_news_id_revision_number')
    )
    
    # Create indexes for news_revisions table
    op.create_index('idx_news_revisions_news_id', 'news_revisions', ['news_id'])
    op.create_index('idx_news_revisions_revision_number', 'news_revisions', ['revision_number'])
    op.create_index('idx_news_revisions_created_at', 'news_revisions', ['created_at'])


def downgrade() -> None:
    """Downgrade schema by removing news revisions support."""
    # Drop indexes for news_revisions table
    op.drop_index('idx_news_revisions_created_at', 'news_revisions')
    op.drop_index('idx_news_revisions_revision_number', 'news_revisions')
    op.drop_index('idx_news_revisions_news_id', 'news_revisions')
    
    # Drop news_revisions table
    op.drop_table('news_revisions')
