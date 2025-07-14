"""Plotting utilities for ArtFight team standings."""

import io
from datetime import datetime
from pathlib import Path
from typing import Optional

import discord

from .config import settings
from .logging_config import get_logger

logger = get_logger(__name__)


def generate_team_standings_plot(team1_name: str, team2_name: str, db_path: Optional[Path] = None) -> Optional[discord.File]:
    """Generate a team standings plot and return it as a Discord file."""
    try:
        # Import matplotlib here to avoid adding it as a main dependency
        import sqlite3

        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt

        # Use provided db_path or default from settings
        if db_path is None:
            db_path = settings.db_path
            
        if not db_path.exists():
            logger.warning("Database file not found for plotting")
            return None

        # Fetch standings data
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT team1_percentage, fetched_at, leader_change,
                   team1_users, team1_attacks, team1_friendly_fire, team1_battle_ratio, team1_avg_points, team1_avg_attacks,
                   team2_users, team2_attacks, team2_friendly_fire, team2_battle_ratio, team2_avg_points, team2_avg_attacks
            FROM team_standings
            ORDER BY fetched_at ASC
        """)

        data = cursor.fetchall()
        conn.close()

        if not data:
            logger.warning("No team standings data found for plotting")
            return None

        # Parse the data
        team1_percentages = []
        team1_scores = []
        team2_scores = []
        fetched_times = []
        leader_changes = []

        for row in data:
            (team1_percentage, fetched_at_str, leader_change,
             team1_users, team1_attacks, team1_friendly_fire, team1_battle_ratio, team1_avg_points, team1_avg_attacks,
             team2_users, team2_attacks, team2_friendly_fire, team2_battle_ratio, team2_avg_points, team2_avg_attacks) = row

            # Parse the datetime string
            try:
                fetched_at = datetime.fromisoformat(fetched_at_str)
            except ValueError:
                # Try alternative format if needed
                fetched_at = datetime.strptime(fetched_at_str, "%Y-%m-%d %H:%M:%S")

            team1_percentages.append(team1_percentage)
            fetched_times.append(fetched_at)
            leader_changes.append(bool(leader_change))

            # Calculate team scores (total points = users * avg_points)
            team1_score = team1_users * team1_avg_points if team1_users and team1_avg_points else 0
            team2_score = team2_users * team2_avg_points if team2_users and team2_avg_points else 0
            
            # Convert to millions for better display
            team1_scores.append(team1_score / 1_000_000)
            team2_scores.append(team2_score / 1_000_000)

        # Create the plot with dual y-axes
        fig, ax1 = plt.subplots(1, 1, figsize=(12, 8))
        ax2 = ax1.twinx()  # Create second y-axis

        # Get team colors from config
        team1_color = "#ff6b6b"  # Default red
        team2_color = "#4ecdc4"  # Default teal
        
        if settings.teams:
            team1_color = settings.teams.team1.color
            team2_color = settings.teams.team2.color

        # Plot team scores on the secondary y-axis (behind the percentage line)
        if any(score > 0 for score in team1_scores + team2_scores):
            ax2.plot(fetched_times, team1_scores, color=team1_color, linewidth=1.5, alpha=0.7, 
                    label=f'{team1_name} Score', zorder=1)
            ax2.plot(fetched_times, team2_scores, color=team2_color, linewidth=1.5, alpha=0.7, 
                    label=f'{team2_name} Score', zorder=1)

            # Set y-axis limits for scores (0 to 10% more than max score)
            max_score = max(max(team1_scores), max(team2_scores))
            if max_score > 0:
                ax2.set_ylim(0, max_score * 1.1)
                ax2.set_ylabel('Team Scores (Millions)', fontsize=10, color='gray')
                ax2.tick_params(axis='y', labelcolor='gray')

        # Plot team percentages over time on primary y-axis
        ax1.plot(fetched_times, team1_percentages, 'b-', linewidth=2, label=f'{team1_name} %', zorder=3)

        # Add a horizontal line at 50% to show the center
        ax1.axhline(y=50, color='gray', linestyle='--', alpha=0.7, label='Center (50%)', zorder=2)

        # Highlight leader changes
        leader_change_times = [fetched_times[i] for i in range(len(leader_changes)) if leader_changes[i]]
        leader_change_percentages = [team1_percentages[i] for i in range(len(leader_changes)) if leader_changes[i]]

        if leader_change_times:
            ax1.scatter(leader_change_times, leader_change_percentages,
                       color='orange', s=100, zorder=5, label='Leader Change', marker='*')

        # Format the primary y-axis (percentages)
        ax1.set_ylabel('Percentage (%)', fontsize=12)
        ax1.set_xlabel('Time', fontsize=12)
        ax1.set_title(f'ArtFight Team Standings Over Time\n{team1_name} vs {team2_name}',
                      fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3, zorder=0)

        # Calculate y-axis limits based on largest distance from 50%
        differences = [abs(p - 50) for p in team1_percentages]
        max_distance = max(differences)

        # Set min and max at 15% more than the largest distance from 50%
        padding = max_distance * 0.15
        y_min = max(0, 50 - max_distance - padding)
        y_max = min(100, 50 + max_distance + padding)

        ax1.set_ylim(y_min, y_max)

        # Format x-axis dates
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
        ax1.xaxis.set_major_locator(mdates.AutoDateLocator())
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)

        # Combine legends from both axes
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

        # Adjust layout
        plt.tight_layout()

        # Save plot to bytes buffer
        buffer = io.BytesIO()
        fig.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)

        # Close the figure to free memory
        plt.close(fig)

        # Create Discord file
        file = discord.File(buffer, filename="team_standings.png")

        logger.info("Team standings plot generated successfully")
        return file

    except ImportError:
        logger.warning("matplotlib not available for plotting")
        return None
    except Exception as e:
        logger.error(f"Failed to generate team standings plot: {e}")
        return None


def save_team_standings_plot(output_path: Path, team1_name: str = "Team 1", team2_name: str = "Team 2", 
                           db_path: Optional[Path] = None) -> bool:
    """Generate and save a team standings plot to a file."""
    try:
        # Import matplotlib here to avoid adding it as a main dependency
        import sqlite3

        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt

        # Use provided db_path or default from settings
        if db_path is None:
            db_path = settings.db_path
            
        if not db_path.exists():
            logger.warning("Database file not found for plotting")
            return False

        # Fetch standings data
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT team1_percentage, fetched_at, leader_change,
                   team1_users, team1_attacks, team1_friendly_fire, team1_battle_ratio, team1_avg_points, team1_avg_attacks,
                   team2_users, team2_attacks, team2_friendly_fire, team2_battle_ratio, team2_avg_points, team2_avg_attacks
            FROM team_standings
            ORDER BY fetched_at ASC
        """)

        data = cursor.fetchall()
        conn.close()

        if not data:
            logger.warning("No team standings data found for plotting")
            return False

        # Parse the data
        team1_percentages = []
        team1_scores = []
        team2_scores = []
        fetched_times = []
        leader_changes = []

        for row in data:
            (team1_percentage, fetched_at_str, leader_change,
             team1_users, team1_attacks, team1_friendly_fire, team1_battle_ratio, team1_avg_points, team1_avg_attacks,
             team2_users, team2_attacks, team2_friendly_fire, team2_battle_ratio, team2_avg_points, team2_avg_attacks) = row

            # Parse the datetime string
            try:
                fetched_at = datetime.fromisoformat(fetched_at_str)
            except ValueError:
                # Try alternative format if needed
                fetched_at = datetime.strptime(fetched_at_str, "%Y-%m-%d %H:%M:%S")

            team1_percentages.append(team1_percentage)
            fetched_times.append(fetched_at)
            leader_changes.append(bool(leader_change))

            # Calculate team scores (total points = users * avg_points)
            team1_score = team1_users * team1_avg_points if team1_users and team1_avg_points else 0
            team2_score = team2_users * team2_avg_points if team2_users and team2_avg_points else 0
            
            # Convert to millions for better display
            team1_scores.append(team1_score / 1_000_000)
            team2_scores.append(team2_score / 1_000_000)

        # Create the plot with dual y-axes
        fig, ax1 = plt.subplots(1, 1, figsize=(12, 8))
        ax2 = ax1.twinx()  # Create second y-axis

        # Get team colors from config
        team1_color = "#ff6b6b"  # Default red
        team2_color = "#4ecdc4"  # Default teal
        
        if settings.teams:
            team1_color = settings.teams.team1.color
            team2_color = settings.teams.team2.color

        # Plot team scores on the secondary y-axis (behind the percentage line)
        if any(score > 0 for score in team1_scores + team2_scores):
            ax2.plot(fetched_times, team1_scores, color=team1_color, linewidth=1.5, alpha=0.7, 
                    label=f'{team1_name} Score', zorder=1)
            ax2.plot(fetched_times, team2_scores, color=team2_color, linewidth=1.5, alpha=0.7, 
                    label=f'{team2_name} Score', zorder=1)

            # Set y-axis limits for scores (0 to 10% more than max score)
            max_score = max(max(team1_scores), max(team2_scores))
            if max_score > 0:
                ax2.set_ylim(0, max_score * 1.1)
                ax2.set_ylabel('Team Scores (Millions)', fontsize=10, color='gray')
                ax2.tick_params(axis='y', labelcolor='gray')

        # Plot team percentages over time on primary y-axis
        ax1.plot(fetched_times, team1_percentages, 'b-', linewidth=2, label=f'{team1_name} %', zorder=3)

        # Add a horizontal line at 50% to show the center
        ax1.axhline(y=50, color='gray', linestyle='--', alpha=0.7, label='Center (50%)', zorder=2)

        # Highlight leader changes
        leader_change_times = [fetched_times[i] for i in range(len(leader_changes)) if leader_changes[i]]
        leader_change_percentages = [team1_percentages[i] for i in range(len(leader_changes)) if leader_changes[i]]

        if leader_change_times:
            ax1.scatter(leader_change_times, leader_change_percentages,
                       color='orange', s=100, zorder=5, label='Leader Change', marker='*')

        # Format the primary y-axis (percentages)
        ax1.set_ylabel('Percentage (%)', fontsize=12)
        ax1.set_xlabel('Time', fontsize=12)
        ax1.set_title(f'ArtFight Team Standings Over Time\n{team1_name} vs {team2_name}',
                      fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3, zorder=0)

        # Calculate y-axis limits based on largest distance from 50%
        differences = [abs(p - 50) for p in team1_percentages]
        max_distance = max(differences)

        # Set min and max at 15% more than the largest distance from 50%
        padding = max_distance * 0.15
        y_min = max(0, 50 - max_distance - padding)
        y_max = min(100, 50 + max_distance + padding)

        ax1.set_ylim(y_min, y_max)

        # Format x-axis dates
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
        ax1.xaxis.set_major_locator(mdates.AutoDateLocator())
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)

        # Combine legends from both axes
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

        # Adjust layout
        plt.tight_layout()

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save plot to file
        fig.savefig(output_path, format='png', dpi=150, bbox_inches='tight')

        # Close the figure to free memory
        plt.close(fig)

        logger.info(f"Team standings plot saved to {output_path}")
        return True

    except ImportError:
        logger.warning("matplotlib not available for plotting")
        return False
    except Exception as e:
        logger.error(f"Failed to generate team standings plot: {e}")
        return False 