"""generalize_team_standings_for_n_teams

Revision ID: a1b2c3d4e5f6
Revises: f1807622ffb8
Create Date: 2026-06-29 12:00:00.000000

ArtFight has run events with more than 2 teams (e.g. 3 teams in 2026). The
old schema hard-coded exactly two teams as team1_*/team2_* columns. This
migration replaces that with a generic `team_data` JSON column keyed by the
team's config key (team1, team2, team3, ...), plus a `leader_key` column
recording which team is currently leading.

Existing rows (which only ever had two teams) are backfilled into the new
JSON format before the old columns are dropped.
"""
import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f1807622ffb8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()

    # 1. Add the new generic columns.
    op.add_column('team_standings', sa.Column('team_data', sa.Text(), nullable=True))
    op.add_column('team_standings', sa.Column('leader_key', sa.Text(), nullable=True))

    # 2. Backfill team_data/leader_key from the old team1_*/team2_* columns.
    rows = bind.execute(sa.text("""
        SELECT id, team1_percentage,
               team1_users, team1_attacks, team1_friendly_fire, team1_battle_ratio, team1_avg_points, team1_avg_attacks,
               team2_users, team2_attacks, team2_friendly_fire, team2_battle_ratio, team2_avg_points, team2_avg_attacks
        FROM team_standings
    """)).fetchall()

    for row in rows:
        (row_id, team1_percentage,
         t1_users, t1_attacks, t1_ff, t1_br, t1_avg_pts, t1_avg_atk,
         t2_users, t2_attacks, t2_ff, t2_br, t2_avg_pts, t2_avg_atk) = row

        team_data = {
            "team1": {
                "percentage": team1_percentage,
                "users": t1_users,
                "attacks": t1_attacks,
                "friendly_fire": t1_ff,
                "battle_ratio": t1_br,
                "avg_points": t1_avg_pts,
                "avg_attacks": t1_avg_atk,
            },
            "team2": {
                "percentage": (100 - team1_percentage) if team1_percentage is not None else None,
                "users": t2_users,
                "attacks": t2_attacks,
                "friendly_fire": t2_ff,
                "battle_ratio": t2_br,
                "avg_points": t2_avg_pts,
                "avg_attacks": t2_avg_atk,
            },
        }
        leader_key = "team1" if (team1_percentage or 0) > 50 else "team2"

        bind.execute(
            sa.text("UPDATE team_standings SET team_data = :data, leader_key = :leader WHERE id = :id"),
            {"data": json.dumps(team_data), "leader": leader_key, "id": row_id},
        )

    # 3. Make team_data non-nullable now that it's populated, with a sane default.
    with op.batch_alter_table('team_standings') as batch_op:
        batch_op.alter_column('team_data', existing_type=sa.Text(), nullable=False, server_default='{}')

    # 4. Drop the old fixed 2-team columns.
    with op.batch_alter_table('team_standings') as batch_op:
        batch_op.drop_column('team2_avg_attacks')
        batch_op.drop_column('team2_avg_points')
        batch_op.drop_column('team2_battle_ratio')
        batch_op.drop_column('team2_friendly_fire')
        batch_op.drop_column('team2_attacks')
        batch_op.drop_column('team2_users')

        batch_op.drop_column('team1_avg_attacks')
        batch_op.drop_column('team1_avg_points')
        batch_op.drop_column('team1_battle_ratio')
        batch_op.drop_column('team1_friendly_fire')
        batch_op.drop_column('team1_attacks')
        batch_op.drop_column('team1_users')

        batch_op.drop_column('team1_percentage')


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()

    with op.batch_alter_table('team_standings') as batch_op:
        batch_op.add_column(sa.Column('team1_percentage', sa.Float(), nullable=True))

        batch_op.add_column(sa.Column('team1_users', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('team1_attacks', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('team1_friendly_fire', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('team1_battle_ratio', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('team1_avg_points', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('team1_avg_attacks', sa.Float(), nullable=True))

        batch_op.add_column(sa.Column('team2_users', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('team2_attacks', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('team2_friendly_fire', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('team2_battle_ratio', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('team2_avg_points', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('team2_avg_attacks', sa.Float(), nullable=True))

    rows = bind.execute(sa.text("SELECT id, team_data FROM team_standings")).fetchall()
    for row_id, team_data_json in rows:
        team_data = json.loads(team_data_json or "{}")
        t1 = team_data.get("team1", {})
        t2 = team_data.get("team2", {})
        bind.execute(
            sa.text("""
                UPDATE team_standings SET
                    team1_percentage = :t1_pct,
                    team1_users = :t1_users, team1_attacks = :t1_attacks, team1_friendly_fire = :t1_ff,
                    team1_battle_ratio = :t1_br, team1_avg_points = :t1_avg_pts, team1_avg_attacks = :t1_avg_atk,
                    team2_users = :t2_users, team2_attacks = :t2_attacks, team2_friendly_fire = :t2_ff,
                    team2_battle_ratio = :t2_br, team2_avg_points = :t2_avg_pts, team2_avg_attacks = :t2_avg_atk
                WHERE id = :id
            """),
            {
                "t1_pct": t1.get("percentage"),
                "t1_users": t1.get("users"), "t1_attacks": t1.get("attacks"), "t1_ff": t1.get("friendly_fire"),
                "t1_br": t1.get("battle_ratio"), "t1_avg_pts": t1.get("avg_points"), "t1_avg_atk": t1.get("avg_attacks"),
                "t2_users": t2.get("users"), "t2_attacks": t2.get("attacks"), "t2_ff": t2.get("friendly_fire"),
                "t2_br": t2.get("battle_ratio"), "t2_avg_pts": t2.get("avg_points"), "t2_avg_atk": t2.get("avg_attacks"),
                "id": row_id,
            },
        )

    with op.batch_alter_table('team_standings') as batch_op:
        batch_op.alter_column('team1_percentage', existing_type=sa.Float(), nullable=False)
        batch_op.drop_column('leader_key')
        batch_op.drop_column('team_data')
