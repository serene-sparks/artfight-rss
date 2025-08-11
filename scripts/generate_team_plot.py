#!/usr/bin/env python3
"""Standalone script to generate ArtFight team standings plots."""

import argparse
import sys
from pathlib import Path

# Add the parent directory to the path so we can import artfight_feed
sys.path.insert(0, str(Path(__file__).parent.parent))

from artfight_feed.plotting import save_team_standings_plot
from artfight_feed.config import settings
from artfight_feed.logging_config import get_logger

logger = get_logger(__name__)


def main():
    """Main entry point for the team plot generator."""
    parser = argparse.ArgumentParser(
        description="Generate ArtFight team standings plots",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate plot with default settings
  python scripts/generate_team_plot.py

  # Generate plot with custom team names
  python scripts/generate_team_plot.py --team1 "Red Team" --team2 "Blue Team"

  # Generate plot with custom database and output paths
  python scripts/generate_team_plot.py --db-path data/custom.db --output plots/standings.png

  # Generate plot with custom team names from config
  python scripts/generate_team_plot.py --use-config-teams
        """
    )

    parser.add_argument(
        "--team1", "-t1",
        default="Team 1",
        help="Name of the first team (default: 'Team 1')"
    )

    parser.add_argument(
        "--team2", "-t2", 
        default="Team 2",
        help="Name of the second team (default: 'Team 2')"
    )

    parser.add_argument(
        "--use-config-teams",
        action="store_true",
        help="Use team names from configuration file instead of command line arguments"
    )

    parser.add_argument(
        "--db-path", "-d",
        type=Path,
        help="Path to the SQLite database (default: from config)"
    )

    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("team_standings_plot.png"),
        help="Output path for the plot (default: team_standings_plot.png)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Set up logging
    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)

    # Determine team names
    team1_name = args.team1
    team2_name = args.team2

    if args.use_config_teams:
        if settings.teams:
            team1_name = settings.teams.team1.name
            team2_name = settings.teams.team2.name
            logger.info(f"Using team names from config: {team1_name} vs {team2_name}")
        else:
            logger.warning("No team configuration found, using default team names")
            logger.info(f"Using default team names: {team1_name} vs {team2_name}")
    else:
        logger.info(f"Using provided team names: {team1_name} vs {team2_name}")

    # Check if database exists
    db_path = args.db_path or settings.db_path
    if not db_path.exists():
        logger.error(f"Database file not found: {db_path}")
        logger.error("Make sure the database exists and the path is correct.")
        sys.exit(1)

    logger.info(f"Using database: {db_path}")
    logger.info(f"Output will be saved to: {args.output}")

    # Generate the plot
    try:
        success = save_team_standings_plot(
            output_path=args.output,
            team1_name=team1_name,
            team2_name=team2_name,
            db_path=db_path
        )

        if success:
            logger.info(f"✅ Team standings plot generated successfully!")
            logger.info(f"📁 Plot saved to: {args.output.absolute()}")
            sys.exit(0)
        else:
            logger.error("❌ Failed to generate team standings plot")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 