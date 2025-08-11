"""Event handlers for the ArtFight monitor."""

from datetime import datetime, UTC

from .config import settings
from .discord_bot import discord_bot
from .logging_config import get_logger
from .models import TeamStanding, ArtFightAttack, ArtFightDefense, ArtFightNews

from redlines import Redlines
import html2text

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

    async def handle_new_news(self, news: ArtFightNews) -> None:
        """Handle new news event by sending Discord notification."""
        if settings.discord_notify_news:
            await discord_bot.send_news_notification(news)

    async def handle_post_revised(self, revision_data: dict) -> None:
        """Handle post revised event by sending Discord notification."""
        if settings.discord_notify_news:
            old_post = revision_data['old_post']
            new_post = revision_data['new_post']
            await discord_bot.send_news_revision_notification(old_post, new_post)


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

    async def handle_new_news(self, news: ArtFightNews) -> None:
        """Log new news event."""
        logger.info(f"New news post detected: {news.title} (ID: {news.id})")

    async def handle_post_revised(self, revision_data: dict) -> None:
        """Log post revised event with visual differences."""
        old_post = revision_data['old_post']
        new_post = revision_data['new_post']
        
        # Convert HTML to markdown for content comparison (same logic as database and Discord bot)
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = False
        h.body_width = 0
        
        old_markdown = h.handle(old_post.content).strip() if old_post.content else ""
        new_markdown = h.handle(new_post.content).strip() if new_post.content else ""
        
        # Log basic revision info
        logger.info(f"News post revised: {new_post.title} (ID: {new_post.id})")
        
        # Log content changes with visual diff if available
        if old_markdown != new_markdown and old_post.content and new_post.content:
            try:
                # Convert HTML to markdown for cleaner comparison
                h = html2text.HTML2Text()
                h.ignore_links = False
                h.ignore_images = False
                h.body_width = 0  # Don't wrap text
                
                old_markdown = h.handle(old_post.content).strip()
                new_markdown = h.handle(new_post.content).strip()
                
                # Generate diff for markdown content changes
                diff = Redlines(old_markdown, new_markdown)
                diff_markdown = diff.output_markdown
                
                # Truncate for logging if too long
                if len(diff_markdown) > 500:
                    diff_markdown = diff_markdown[:497] + "..."
                
                logger.info(f"  Content changed - Visual diff:\n{diff_markdown}")
                    
            except Exception as e:
                logger.warning(f"  Content changed but failed to generate visual diff: {e}")
                logger.info(f"  Content length: {len(old_post.content)} -> {len(new_post.content)} chars")
        # Log title changes
        if old_post.title != new_post.title:
            logger.info(f"  Title changed: '{old_post.title}' -> '{new_post.title}'")
        
        # Note: We only log revisions for title/content changes, not time/editor changes
        logger.info(f"  Revision detected for news post {new_post.id} - Title or content changed")


def setup_event_handlers(monitor) -> None:
    """Set up event handlers for the monitor."""
    # Create event handler instances
    discord_handler = DiscordEventHandler()
    logging_handler = LoggingEventHandler()

    # Register Discord event handlers
    monitor.add_event_handler('new_attack', discord_handler.handle_new_attack)
    monitor.add_event_handler('new_defense', discord_handler.handle_new_defense)
    monitor.add_event_handler('team_standing_update', discord_handler.handle_team_standing_update)
    monitor.add_event_handler('new_news', discord_handler.handle_new_news)
    monitor.add_event_handler('post_revised', discord_handler.handle_post_revised)

    # Register logging event handlers
    monitor.add_event_handler('new_attack', logging_handler.handle_new_attack)
    monitor.add_event_handler('new_defense', logging_handler.handle_new_defense)
    monitor.add_event_handler('team_standing_update', logging_handler.handle_team_standing_update)
    monitor.add_event_handler('new_news', logging_handler.handle_new_news)
    monitor.add_event_handler('post_revised', logging_handler.handle_post_revised)

    logger.info("Event handlers registered for monitor") 