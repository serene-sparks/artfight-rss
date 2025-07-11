"""add_team_metrics_and_update_types

Revision ID: 628333ca6954
Revises: 42670984b8b0
Create Date: 2025-07-09 20:41:36.156603

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '628333ca6954'
down_revision: Union[str, Sequence[str], None] = '42670984b8b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add team metrics fields to team_standings table
    op.add_column('team_standings', sa.Column('team1_users', sa.Integer(), nullable=True))
    op.add_column('team_standings', sa.Column('team1_attacks', sa.Integer(), nullable=True))
    op.add_column('team_standings', sa.Column('team1_friendly_fire', sa.Integer(), nullable=True))
    op.add_column('team_standings', sa.Column('team1_battle_ratio', sa.Float(), nullable=True))
    op.add_column('team_standings', sa.Column('team1_avg_points', sa.Float(), nullable=True))
    op.add_column('team_standings', sa.Column('team1_avg_attacks', sa.Float(), nullable=True))
    
    op.add_column('team_standings', sa.Column('team2_users', sa.Integer(), nullable=True))
    op.add_column('team_standings', sa.Column('team2_attacks', sa.Integer(), nullable=True))
    op.add_column('team_standings', sa.Column('team2_friendly_fire', sa.Integer(), nullable=True))
    op.add_column('team_standings', sa.Column('team2_battle_ratio', sa.Float(), nullable=True))
    op.add_column('team_standings', sa.Column('team2_avg_points', sa.Float(), nullable=True))
    op.add_column('team_standings', sa.Column('team2_avg_attacks', sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove team metrics fields from team_standings table
    op.drop_column('team_standings', 'team2_avg_attacks')
    op.drop_column('team_standings', 'team2_avg_points')
    op.drop_column('team_standings', 'team2_battle_ratio')
    op.drop_column('team_standings', 'team2_friendly_fire')
    op.drop_column('team_standings', 'team2_attacks')
    op.drop_column('team_standings', 'team2_users')
    
    op.drop_column('team_standings', 'team1_avg_attacks')
    op.drop_column('team_standings', 'team1_avg_points')
    op.drop_column('team_standings', 'team1_battle_ratio')
    op.drop_column('team_standings', 'team1_friendly_fire')
    op.drop_column('team_standings', 'team1_attacks')
    op.drop_column('team_standings', 'team1_users')
