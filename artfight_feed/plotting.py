"""Plotting utilities for ArtFight team standings.

Generalized to support any number of teams (ArtFight has run events with 2
teams in past years and 3 teams in 2026). Each team is plotted using its
configured color and name; the team-balance subplot shows each team's user
count over time instead of a single pairwise difference (which only made
sense when there were exactly 2 teams).
"""

import io
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

import discord

from .config import settings
from .logging_config import get_logger

logger = get_logger(__name__)

# Fallback colors used when a team has no configured color (or no config at all)
_DEFAULT_COLORS = ["#ff6b6b", "#4ecdc4", "#ffd93d", "#6c5ce7", "#1abc9c", "#e17055"]


def _team_display(team_key: str, index: int) -> tuple[str, str]:
    """Return (name, color) for a team key, falling back to sane defaults."""
    if settings.teams is not None:
        try:
            team = settings.teams[team_key]
            return team.name, team.color
        except (KeyError, AttributeError):
            pass
    return team_key, _DEFAULT_COLORS[index % len(_DEFAULT_COLORS)]


def _load_standings_series(db_path: Path) -> Optional[dict]:
    """Load and reshape team_standings rows into per-team time series.

    Returns a dict with: fetched_times, leader_keys, team_keys (in stable
    order), and per-team lists: percentages, users, scores. Returns None if
    there's no data or the DB is missing.
    """
    if not db_path.exists():
        logger.warning("Database file not found for plotting")
        return None

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT team_data, leader_key, fetched_at, leader_change
        FROM team_standings
        ORDER BY fetched_at ASC
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        logger.warning("No team standings data found for plotting")
        return None

    # Determine a stable, ordered list of team keys: prefer config order,
    # then fall back to whatever keys show up in the data.
    if settings.teams is not None:
        team_keys = list(settings.teams.keys())
    else:
        team_keys = []
    for team_data_json, *_ in rows:
        for key in json.loads(team_data_json or "{}").keys():
            if key not in team_keys:
                team_keys.append(key)

    fetched_times: list[datetime] = []
    leader_keys: list[str | None] = []
    percentages: dict[str, list[float]] = {key: [] for key in team_keys}
    users: dict[str, list[int]] = {key: [] for key in team_keys}
    scores: dict[str, list[float]] = {key: [] for key in team_keys}

    for team_data_json, leader_key, fetched_at_str, _leader_change in rows:
        try:
            fetched_at = datetime.fromisoformat(fetched_at_str)
        except ValueError:
            fetched_at = datetime.strptime(fetched_at_str, "%Y-%m-%d %H:%M:%S")

        fetched_times.append(fetched_at)
        leader_keys.append(leader_key)

        team_data = json.loads(team_data_json or "{}")
        for key in team_keys:
            team = team_data.get(key, {})
            pct = team.get("percentage")
            percentages[key].append(pct if pct is not None else float("nan"))

            team_users = team.get("users") or 0
            users[key].append(team_users)

            avg_points = team.get("avg_points")
            score = (team_users * avg_points / 1_000_000) if (team_users and avg_points) else 0
            scores[key].append(score)

    return {
        "fetched_times": fetched_times,
        "leader_keys": leader_keys,
        "team_keys": team_keys,
        "percentages": percentages,
        "users": users,
        "scores": scores,
    }


def _render_team_standings_figure(data: dict, include_team_balance: bool):
    """Build the matplotlib Figure for team standings. Caller closes it."""
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    team_keys = data["team_keys"]
    fetched_times = data["fetched_times"]
    percentages = data["percentages"]
    scores = data["scores"]
    users = data["users"]
    leader_keys = data["leader_keys"]

    names_colors = {key: _team_display(key, i) for i, key in enumerate(team_keys)}

    if include_team_balance:
        fig, (ax1, ax3) = plt.subplots(2, 1, figsize=(12, 12), height_ratios=[1, 1])
        ax2 = ax1.twinx()
        ax4 = ax3.twinx()
    else:
        fig, ax1 = plt.subplots(1, 1, figsize=(12, 8))
        ax2 = ax1.twinx()

    # Team scores on the secondary y-axis (behind the percentage lines)
    any_scores = any(score > 0 for team_scores in scores.values() for score in team_scores)
    if any_scores:
        for key in team_keys:
            name, color = names_colors[key]
            ax2.plot(fetched_times, scores[key], color=color, linewidth=1.5, alpha=0.7,
                      label=f'{name} Score', zorder=1)

        max_score = max((max(team_scores) for team_scores in scores.values() if team_scores), default=0)
        if max_score > 0:
            ax2.set_ylim(0, max_score * 1.1)
            ax2.set_ylabel('Team Scores (Millions)', fontsize=10, color='gray')
            ax2.tick_params(axis='y', labelcolor='gray')

    # Team percentages over time on the primary y-axis
    all_percentages: list[float] = []
    for key in team_keys:
        name, color = names_colors[key]
        ax1.plot(fetched_times, percentages[key], color=color, linewidth=2, label=f'{name} %', zorder=3)
        all_percentages.extend(p for p in percentages[key] if p == p)  # filter NaN

    # Only the classic 2-team case has a meaningful "center" line
    if len(team_keys) == 2:
        ax1.axhline(y=50, color='gray', linestyle='--', alpha=0.7, label='Center (50%)', zorder=2)

    # Highlight leader changes: mark the leading team's percentage at the
    # moment the lead changed.
    leader_change_times = []
    leader_change_values = []
    previous_leader = None
    for i, leader_key in enumerate(leader_keys):
        if leader_key is not None and previous_leader is not None and leader_key != previous_leader:
            value = percentages.get(leader_key, [None] * len(fetched_times))[i]
            if value == value:  # not NaN
                leader_change_times.append(fetched_times[i])
                leader_change_values.append(value)
        previous_leader = leader_key

    if leader_change_times:
        ax1.scatter(leader_change_times, leader_change_values,
                    color='orange', s=100, zorder=5, label='Leader Change', marker='*')

    ax1.set_ylabel('Percentage (%)', fontsize=12)
    team_names = " vs ".join(names_colors[key][0] for key in team_keys)
    ax1.set_title(f'ArtFight Team Standings Over Time\n{team_names}', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3, zorder=0)

    if all_percentages:
        y_min = max(0, min(all_percentages) - 5)
        y_max = min(100, max(all_percentages) + 5)
        if y_min < y_max:
            ax1.set_ylim(y_min, y_max)

    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
    ax1.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

    if not include_team_balance:
        ax1.set_xlabel('Time', fontsize=12)

    if include_team_balance:
        for key in team_keys:
            name, color = names_colors[key]
            ax3.plot(fetched_times, users[key], color=color, linewidth=2, label=f'{name} Users', zorder=3)

        all_users = [u for team_users in users.values() for u in team_users]
        if all_users:
            max_users = max(all_users)
            min_users = min(all_users)
            padding = max((max_users - min_users) * 0.15, 1)
            ax3.set_ylim(max(0, min_users - padding), max_users + padding)

        ax3.set_ylabel('User Count', fontsize=12)
        ax3.set_xlabel('Time', fontsize=12)
        ax3.set_title('Team User Counts', fontsize=12, fontweight='bold')
        ax3.grid(True, alpha=0.3, zorder=0)
        ax4.set_visible(False)

        ax3.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
        ax3.xaxis.set_major_locator(mdates.AutoDateLocator())
        plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45)

        lines3, labels3 = ax3.get_legend_handles_labels()
        ax3.legend(lines3, labels3, loc='upper left')

    plt.tight_layout()
    return fig


def generate_team_standings_plot(db_path: Optional[Path] = None, include_team_balance: Optional[bool] = None) -> Optional[discord.File]:
    """Generate a team standings plot and return it as a Discord file."""
    try:
        if include_team_balance is None:
            include_team_balance = settings.discord_include_team_balance_plot
        if db_path is None:
            db_path = settings.db_path

        data = _load_standings_series(db_path)
        if data is None:
            return None

        import matplotlib.pyplot as plt
        fig = _render_team_standings_figure(data, include_team_balance)

        buffer = io.BytesIO()
        fig.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        plt.close(fig)

        logger.info("Team standings plot generated successfully")
        return discord.File(buffer, filename="team_standings.png")

    except ImportError:
        logger.warning("matplotlib not available for plotting")
        return None
    except Exception as e:
        logger.error(f"Failed to generate team standings plot: {e}")
        return None


def save_team_standings_plot(output_path: Path, db_path: Optional[Path] = None, include_team_balance: Optional[bool] = None) -> bool:
    """Generate and save a team standings plot to a file."""
    try:
        if include_team_balance is None:
            include_team_balance = settings.discord_include_team_balance_plot
        if db_path is None:
            db_path = settings.db_path

        data = _load_standings_series(db_path)
        if data is None:
            return False

        import matplotlib.pyplot as plt
        fig = _render_team_standings_figure(data, include_team_balance)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, format='png', dpi=150, bbox_inches='tight')
        plt.close(fig)

        logger.info(f"Team standings plot saved to {output_path}")
        return True

    except ImportError:
        logger.warning("matplotlib not available for plotting")
        return False
    except Exception as e:
        logger.error(f"Failed to generate team standings plot: {e}")
        return False
