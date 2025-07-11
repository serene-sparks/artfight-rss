"""initial_schema

Revision ID: 42670984b8b0
Revises: 
Create Date: 2025-07-09 20:40:48.689113

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '42670984b8b0'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create attacks table
    op.create_table('attacks',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('image_url', sa.Text(), nullable=True),
        sa.Column('attacker_user', sa.Text(), nullable=False),
        sa.Column('fetched_at', sa.Text(), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('first_seen', sa.Text(), nullable=False),
        sa.Column('last_updated', sa.Text(), nullable=False),
        sa.Column('defender_user', sa.Text(), nullable=True, server_default='Unknown'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create defenses table
    op.create_table('defenses',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('image_url', sa.Text(), nullable=True),
        sa.Column('defender_user', sa.Text(), nullable=False),
        sa.Column('attacker_user', sa.Text(), nullable=False),
        sa.Column('fetched_at', sa.Text(), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('first_seen', sa.Text(), nullable=False),
        sa.Column('last_updated', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create rate_limits table
    op.create_table('rate_limits',
        sa.Column('key', sa.Text(), nullable=False),
        sa.Column('last_request', sa.Text(), nullable=False),
        sa.Column('min_interval', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('key')
    )
    
    # Create team_standings table
    op.create_table('team_standings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('team1_percentage', sa.Float(), nullable=False),
        sa.Column('fetched_at', sa.Text(), nullable=False),
        sa.Column('leader_change', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('first_seen', sa.Text(), nullable=False),
        sa.Column('last_updated', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('idx_attacks_attacker_user', 'attacks', ['attacker_user'])
    op.create_index('idx_attacks_fetched_at', 'attacks', ['fetched_at'])
    op.create_index('idx_defenses_attacker_user', 'defenses', ['attacker_user'])
    op.create_index('idx_defenses_fetched_at', 'defenses', ['fetched_at'])


