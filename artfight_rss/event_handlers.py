"""Event handlers for the ArtFight monitor."""

from datetime import datetime, UTC

from .config import settings
from .discord_bot import discord_bot
from .logging_config import get_logger
from .models import TeamStanding, ArtFightAttack, ArtFightDefense

logger = get_logger(__name__)


class DiscordEventHandler:
    """Handles Discord notifications for monitor events."""

    async def handle_new_attack(self, attack: ArtFightAttack) -> None:
        """Handle new attack event by sending Discord notification."""
        if settings.discord_notify_attacks:
            await discord_bot.send_attack_notification(attack)

    async def handle_new_defense(self, defense: ArtFightDefense) -> None:
        """Handle new defense event by sending Discord notification."""
        if settings.discord_notify_defenses:
            await discord_bot.send_defense_notification(defense)

    async def handle_team_standing_update(self, standing: TeamStanding) -> None:
        """Handle team standing update event by sending Discord notification if appropriate."""
        # Handle leader change notifications
        if standing.leader_change and settings.discord_notify_leader_changes:
            await discord_bot.send_leader_change_notification(standing)
            return

        # Handle regular team standing notifications
        if not settings.discord_notify_team_changes:
            return

        # Only send notifications for standings that would be included in the RSS feed
        # This means: first standing of each day OR leader changes
        should_notify = False
        notification_reason = ""

        # Check if this is the first standing of the day (daily update)
        # Get the first standing of today to see if this is it
        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        from .database import ArtFightDatabase
        database = ArtFightDatabase(settings.db_path)
        today_standings = database.get_team_standings_history()
        today_standings = [s for s in today_standings if s.fetched_at >= today_start]
        
        if today_standings:
            # Sort by time and check if this is the earliest standing of today
            today_standings.sort(key=lambda s: s.fetched_at)
            earliest_today = today_standings[0]
            
            # If this standing is the earliest of today (within 1 second tolerance)
            if abs((standing.fetched_at - earliest_today.fetched_at).total_seconds()) < 1:
                should_notify = True
                notification_reason = "daily update"

        # Send Discord notification if this standing should be included in RSS feed
        if should_notify:
            logger.info(f"Sending Discord notification for team standings ({notification_reason})")
            await discord_bot.send_team_standing_notification(standing)
        else:
            logger.debug(f"Skipping Discord notification for team standings (not included in RSS feed)")


class LoggingEventHandler:
    """Handles logging for monitor events."""

    async def handle_new_attack(self, attack: ArtFightAttack) -> None:
        """Log new attack event."""
        logger.info(f"New attack detected: {attack.title} by {attack.attacker_user}")

    async def handle_new_defense(self, defense: ArtFightDefense) -> None:
        """Log new defense event."""
        logger.info(f"New defense detected: {defense.title} by {defense.defender_user}")

    async def handle_team_standing_update(self, standing: TeamStanding) -> None:
        """Log team standing update event."""
        if standing.leader_change:
            if settings.teams:
                leader = (
                    settings.teams.team1.name
                    if standing.team1_percentage > 50
                    else settings.teams.team2.name
                )
            else:
                leader = "Team 1" if standing.team1_percentage > 50 else "Team 2"
            logger.info(f"Leader change detected: {leader} is now leading at {standing.team1_percentage:.2f}%")
        else:
            logger.debug(f"Team standing update: {standing.team1_percentage:.2f}% vs {100-standing.team1_percentage:.2f}%")


def setup_event_handlers(monitor) -> None:
    """Set up event handlers for the monitor."""
    # Create event handler instances
    discord_handler = DiscordEventHandler()
    logging_handler = LoggingEventHandler()

    # Register Discord event handlers
    monitor.add_event_handler('new_attack', discord_handler.handle_new_attack)
    monitor.add_event_handler('new_defense', discord_handler.handle_new_defense)
    monitor.add_event_handler('team_standing_update', discord_handler.handle_team_standing_update)

    # Register logging event handlers
    monitor.add_event_handler('new_attack', logging_handler.handle_new_attack)
    monitor.add_event_handler('new_defense', logging_handler.handle_new_defense)
    monitor.add_event_handler('team_standing_update', logging_handler.handle_team_standing_update)

    logger.info("Event handlers registered for monitor") 