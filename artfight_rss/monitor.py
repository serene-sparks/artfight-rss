"""Background monitoring service for ArtFight team standings."""

import asyncio
from datetime import datetime, UTC

from .artfight import ArtFightClient
from .cache import RateLimiter, SQLiteCache
from .config import settings
from .discord_bot import discord_bot
from .logging_config import get_logger
from .models import TeamStanding

logger = get_logger(__name__)


class ArtFightMonitor:
    """Monitor ArtFight team standings and user activity for changes."""

    def __init__(self, cache: SQLiteCache, rate_limiter: RateLimiter, database) -> None:
        """Initialize the monitor."""
        self.cache = cache
        self.rate_limiter = rate_limiter
        self.database = database
        self.artfight_client = ArtFightClient(rate_limiter, database)

        # Track last known team states
        self.last_team_sides: dict[str, str] = {}  # team_name -> side
        self.last_team_update: datetime | None = None

        # Track last known user activity
        self.last_user_attacks: dict[str, set[str]] = {}  # username -> set of attack IDs
        self.last_user_defenses: dict[str, set[str]] = {}  # username -> set of defense IDs
        self.last_user_update: datetime | None = None

        # Background task handles
        self.team_task: asyncio.Task | None = None
        self.user_task: asyncio.Task | None = None
        self.running = False

    async def start(self) -> None:
        """Start the monitoring service."""
        if self.running:
            return

        self.running = True

        # Start background task for team monitoring
        self.team_task = asyncio.create_task(self._team_monitor_loop())

        # Start background task for user monitoring if users are configured
        if settings.monitor_list:
            self.user_task = asyncio.create_task(self._user_monitor_loop())
            logger.info("ArtFight team and user monitor started")
        else:
            logger.info("ArtFight team monitor started (no users configured)")

    async def stop(self) -> None:
        """Stop the monitoring service."""
        if not self.running:
            return

        logger.info("Stopping ArtFight monitor...")
        self.running = False

        # Cancel background tasks with timeout
        if self.team_task:
            self.team_task.cancel()
            try:
                await asyncio.wait_for(self.team_task, timeout=5.0)
            except asyncio.CancelledError:
                pass
            except asyncio.TimeoutError:
                logger.warning("Team task did not stop within timeout")

        if self.user_task:
            self.user_task.cancel()
            try:
                await asyncio.wait_for(self.user_task, timeout=5.0)
            except asyncio.CancelledError:
                pass
            except asyncio.TimeoutError:
                logger.warning("User task did not stop within timeout")

        # Close ArtFight client
        try:
            await asyncio.wait_for(self.artfight_client.close(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("ArtFight client did not close within timeout")

        logger.info("ArtFight monitor stopped")

    async def _team_monitor_loop(self) -> None:
        """Background loop for monitoring team standings."""
        while self.running:
            try:
                await self._check_team_standings()
                # Use wait_for to make sleep cancellable
                await asyncio.wait_for(
                    asyncio.sleep(settings.team_check_interval_sec),
                    timeout=settings.team_check_interval_sec
                )
            except asyncio.CancelledError:
                logger.info("Team monitor loop cancelled")
                break
            except asyncio.TimeoutError:
                # This is expected, continue the loop
                continue
            except Exception as e:
                logger.error(f"Error in team monitor loop: {e}")
                try:
                    await asyncio.wait_for(asyncio.sleep(300), timeout=300)
                except asyncio.CancelledError:
                    logger.info("Team monitor loop cancelled during error recovery")
                    break
                except asyncio.TimeoutError:
                    continue

    async def _check_team_standings(self) -> None:
        """Check team standings for updates and side switches."""
        standings = await self.artfight_client.get_team_standings()
        if not standings:
            return

        # Only send Discord notifications for standings that would be included in the RSS feed
        # This means: first standing of each day OR leader changes
        for standing in standings:
            should_notify = False
            notification_reason = ""

            # Check if this is a leader change (always notify)
            if standing.leader_change:
                should_notify = True
                notification_reason = "leader change"
                
                if settings.teams:
                    leader = (
                        settings.teams.team1.name
                        if standing.team1_percentage > 50
                        else settings.teams.team2.name
                    )
                else:
                    leader = "Team 1" if standing.team1_percentage > 50 else "Team 2"
                logger.info(f"Leader change detected: {leader} is now leading at {standing.team1_percentage:.2f}%")

            # Check if this is the first standing of the day (daily update)
            else:
                # Get the first standing of today to see if this is it
                today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
                today_standings = self.database.get_team_standings_history()
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
                
                # For leader changes, only send the leader change notification
                if standing.leader_change:
                    await discord_bot.send_leader_change_notification(standing)
                else:
                    # For daily updates, send the regular team standing notification
                    await discord_bot.send_team_standing_notification(standing)
            else:
                logger.debug(f"Skipping Discord notification for team standings (not included in RSS feed)")

    async def _user_monitor_loop(self) -> None:
        """Background loop for monitoring user activity."""
        while self.running:
            try:
                await self._check_user_activity()
                # Use wait_for to make sleep cancellable
                await asyncio.wait_for(
                    asyncio.sleep(settings.request_interval),
                    timeout=settings.request_interval
                )
            except asyncio.CancelledError:
                logger.info("User monitor loop cancelled")
                break
            except asyncio.TimeoutError:
                # This is expected, continue the loop
                continue
            except Exception as e:
                logger.error(f"Error in user monitor loop: {e}")
                try:
                    await asyncio.wait_for(asyncio.sleep(300), timeout=300)
                except asyncio.CancelledError:
                    logger.info("User monitor loop cancelled during error recovery")
                    break
                except asyncio.TimeoutError:
                    continue

    async def _check_user_activity(self) -> None:
        """Check user activity for new attacks and defenses."""
        if not settings.monitor_list:
            return

        for username in settings.monitor_list:
            logger.info(f"Checking activity for user: {username}")

            try:
                # Check for new attacks
                await self._check_user_attacks(username)

                # Check for new defenses
                await self._check_user_defenses(username)

            except Exception as e:
                logger.error(f"Error checking activity for {username}: {e}")

    async def _check_user_attacks(self, username: str) -> None:
        """Check for new attacks by a user."""
        try:
            attacks = await self.artfight_client.get_user_attacks(username)
            if not attacks:
                return

            # Get current attack IDs
            current_attack_ids = {attack.id for attack in attacks}

            # Get previous attack IDs
            previous_attack_ids = self.last_user_attacks.get(username, set())

            # Find new attacks
            new_attack_ids = current_attack_ids - previous_attack_ids

            if new_attack_ids:
                logger.info(f"Found {len(new_attack_ids)} new attacks for {username}")

                # Send Discord notifications for new attacks
                for attack in attacks:
                    if attack.id in new_attack_ids:
                        await discord_bot.send_attack_notification(attack)

                # Update tracked attacks
                self.last_user_attacks[username] = current_attack_ids

        except Exception as e:
            logger.error(f"Error checking attacks for {username}: {e}")

    async def _check_user_defenses(self, username: str) -> None:
        """Check for new defenses by a user."""
        try:
            defenses = await self.artfight_client.get_user_defenses(username)
            if not defenses:
                return

            # Get current defense IDs
            current_defense_ids = {defense.id for defense in defenses}

            # Get previous defense IDs
            previous_defense_ids = self.last_user_defenses.get(username, set())

            # Find new defenses
            new_defense_ids = current_defense_ids - previous_defense_ids

            if new_defense_ids:
                logger.info(f"Found {len(new_defense_ids)} new defenses for {username}")

                # Send Discord notifications for new defenses
                for defense in defenses:
                    if defense.id in new_defense_ids:
                        await discord_bot.send_defense_notification(defense)

                # Update tracked defenses
                self.last_user_defenses[username] = current_defense_ids

        except Exception as e:
            logger.error(f"Error checking defenses for {username}: {e}")


    async def check_teams_manual(self) -> list[TeamStanding]:
        """Manually check team standings (for API endpoints)."""
        await self._check_team_standings()
        return await self.artfight_client.get_team_standings()

    def get_stats(self) -> dict:
        """Get monitoring statistics."""
        return {
            "running": self.running,
            "last_team_update": self.last_team_update.isoformat() if self.last_team_update else None,
            "last_user_update": self.last_user_update.isoformat() if self.last_user_update else None,
            "tracked_teams": len(self.last_team_sides),
            "tracked_users": len(self.last_user_attacks),
            "cache_stats": self.cache.get_stats(),
        }
