"""Background monitoring service for ArtFight team standings."""

import asyncio
from datetime import datetime, UTC
from typing import Callable, Any

from .artfight import ArtFightClient
from .cache import RateLimiter, SQLiteCache
from .config import settings
from .discord_bot import discord_bot
from .logging_config import get_logger
from .models import TeamStanding, ArtFightAttack, ArtFightDefense, ArtFightNews

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

        # Battle over detection tracking
        self.consecutive_battle_over_count: int = 0
        self.battle_over_detection_enabled: bool = False

        # Background task handles
        self.team_task: asyncio.Task | None = None
        self.user_task: asyncio.Task | None = None
        self.news_task: asyncio.Task | None = None
        self.running = False

        # Event handlers
        self.event_handlers: dict[str, list[Callable]] = {
            'new_attack': [],
            'new_defense': [],
            'team_standing_update': [],
            'new_news': [],
            'post_revised': []
        }

        # Initialize battle over detection if enabled
        if settings.battle_over_detection:
            self.battle_over_detection_enabled = True
            logger.info("Battle over detection enabled - will stop team checks after 3 consecutive failures")

    def _should_stop_team_monitoring(self) -> bool:
        """Check if team monitoring should be stopped due to consecutive battle over detections."""
        if not self.battle_over_detection_enabled:
            return False
        
        if self.consecutive_battle_over_count >= 3:
            logger.warning(f"Stopping team monitoring after {self.consecutive_battle_over_count} consecutive 'battle over' detections")
            return True
        
        return False

    def _record_battle_over_detection(self) -> None:
        """Record a battle over detection and potentially stop team monitoring."""
        if not self.battle_over_detection_enabled:
            return
        
        self.consecutive_battle_over_count += 1
        logger.info(f"Battle over detection #{self.consecutive_battle_over_count}/3")
        
        if self._should_stop_team_monitoring():
            self.running = False

    def _reset_battle_over_detection(self) -> None:
        """Reset the consecutive battle over detection counter when an event is found."""
        if self.consecutive_battle_over_count > 0:
            logger.info(f"Resetting battle over detection counter (was {self.consecutive_battle_over_count})")
            self.consecutive_battle_over_count = 0

    def add_event_handler(self, event_type: str, handler: Callable) -> None:
        """Add an event handler for a specific event type."""
        if event_type in self.event_handlers:
            self.event_handlers[event_type].append(handler)
        else:
            logger.warning(f"Unknown event type: {event_type}")

    async def emit_event(self, event_type: str, data: Any) -> None:
        """Emit an event to all registered handlers."""
        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(data)
                    else:
                        handler(data)
                except Exception as e:
                    logger.error(f"Error in event handler for {event_type}: {e}")

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

        # Start background task for news monitoring if enabled
        if settings.monitor_news:
            self.news_task = asyncio.create_task(self._news_monitor_loop())
            logger.info("ArtFight news monitor started")
        else:
            logger.info("ArtFight news monitor disabled")

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

        if self.news_task:
            self.news_task.cancel()
            try:
                await asyncio.wait_for(self.news_task, timeout=5.0)
            except asyncio.CancelledError:
                pass
            except asyncio.TimeoutError:
                logger.warning("News task did not stop within timeout")

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
                # Check if team monitoring should be stopped due to no event detection
                if self._should_stop_team_monitoring():
                    logger.info("Team monitoring stopped due to no event detection")
                    break
                
                await self._fetch_team_standings()
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

    async def _fetch_team_standings(self) -> None:
        """Fetch team standings and emit events for new data."""
        standings = await self.artfight_client.get_team_standings()
        if not standings:
            # Record battle over detection if no standings found
            self._record_battle_over_detection()
            return

        # Reset battle over detection counter when standings are found
        self._reset_battle_over_detection()

        # Emit events for each standing - let handlers decide what to do
        for standing in standings:
            await self.emit_event('team_standing_update', standing)

    async def _user_monitor_loop(self) -> None:
        """Background loop for monitoring user activity."""
        while self.running:
            try:
                await self._fetch_user_activity()
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

    async def _fetch_user_activity(self) -> None:
        """Fetch user activity and emit events for new data."""
        if not settings.monitor_list:
            return

        for username in settings.monitor_list:
            logger.info(f"Fetching activity for user: {username}")

            try:
                # Fetch attacks and emit events for new ones
                await self._fetch_user_attacks(username)

                # Fetch defenses and emit events for new ones
                await self._fetch_user_defenses(username)

            except Exception as e:
                logger.error(f"Error fetching activity for {username}: {e}")

    async def _fetch_user_attacks(self, username: str) -> None:
        """Fetch attacks for a user and emit events for new ones."""
        try:
            # Get previously seen attack IDs from database BEFORE fetching new ones
            previous_attack_ids = self.database.get_existing_attack_ids(username)
            
            attacks = await self.artfight_client._fetch_user_content(username, "attacks")
            if not attacks:
                return

            # Get current attack IDs
            current_attack_ids = {attack.id for attack in attacks}

            # Find new attacks
            new_attack_ids = current_attack_ids - previous_attack_ids

            if new_attack_ids:
                logger.info(f"Found {len(new_attack_ids)} new attacks for {username}")

                # Emit events for new attacks
                for attack in attacks:
                    if attack.id in new_attack_ids:
                        await self.emit_event('new_attack', attack)

        except Exception as e:
            logger.error(f"Error fetching attacks for {username}: {e}")

    async def _fetch_user_defenses(self, username: str) -> None:
        """Fetch defenses for a user and emit events for new ones."""
        try:
            # Get previously seen defense IDs from database BEFORE fetching new ones
            previous_defense_ids = self.database.get_existing_defense_ids(username)
            
            defenses = await self.artfight_client._fetch_user_content(username, "defenses")
            if not defenses:
                return

            # Get current defense IDs
            current_defense_ids = {defense.id for defense in defenses}

            # Find new defenses
            new_defense_ids = current_defense_ids - previous_defense_ids

            if new_defense_ids:
                logger.info(f"Found {len(new_defense_ids)} new defenses for {username}")

                # Emit events for new defenses
                for defense in defenses:
                    if defense.id in new_defense_ids:
                        await self.emit_event('new_defense', defense)

        except Exception as e:
            logger.error(f"Error fetching defenses for {username}: {e}")

    async def check_teams_manual(self) -> list[TeamStanding]:
        """Manually check team standings (for API endpoints)."""
        await self._fetch_team_standings()
        return await self.artfight_client.get_team_standings()

    def get_stats(self) -> dict:
        """Get monitoring statistics."""
        return {
            "running": self.running,
            "last_team_update": self.last_team_update.isoformat() if self.last_team_update else None,
            "tracked_teams": len(self.last_team_sides),
            "cache_stats": self.cache.get_stats(),
            "no_event_detection": {
                "enabled": self.battle_over_detection_enabled,
                "consecutive_count": self.consecutive_battle_over_count,
                "stopped": self._should_stop_team_monitoring()
            }
        }

    def reset_battle_over_detection(self) -> None:
        """Manually reset the battle over detection counter and restart team monitoring."""
        if not self.battle_over_detection_enabled:
            logger.info("Battle over detection is not enabled")
            return
        
        if self.consecutive_battle_over_count > 0:
            logger.info(f"Manually resetting battle over detection counter from {self.consecutive_battle_over_count}")
            self.consecutive_battle_over_count = 0
        
        if not self.running and self._should_stop_team_monitoring():
            logger.info("Restarting team monitoring after manual reset")
            self.running = True
            if not self.team_task or self.team_task.done():
                self.team_task = asyncio.create_task(self._team_monitor_loop())

    async def _news_monitor_loop(self) -> None:
        """Background loop for monitoring news posts."""
        while self.running:
            try:
                await self._fetch_news_posts()
                # Use wait_for to make sleep cancellable
                await asyncio.wait_for(
                    asyncio.sleep(settings.news_check_interval_sec),
                    timeout=settings.news_check_interval_sec
                )
            except asyncio.CancelledError:
                logger.info("News monitor loop cancelled")
                break
            except asyncio.TimeoutError:
                # This is expected, continue the loop
                continue
            except Exception as e:
                logger.error(f"Error in news monitor loop: {e}")
                try:
                    await asyncio.wait_for(asyncio.sleep(300), timeout=300)
                except asyncio.CancelledError:
                    logger.info("News monitor loop cancelled during error recovery")
                    break
                except asyncio.TimeoutError:
                    continue

    async def _fetch_news_posts(self) -> None:
        """Fetch news posts and emit events for new ones and revisions."""
        try:
            # Get previously seen news IDs from database BEFORE fetching new ones
            previous_news_ids = self.database.get_existing_news_ids()
            
            news_posts = await self.artfight_client.get_news_posts()
            if not news_posts:
                logger.warning("No news posts found. Did the ArtFight website change?")
                return

            # Get current news IDs
            current_news_ids = {news.id for news in news_posts}

            # Find new news posts
            new_news_ids = current_news_ids - previous_news_ids

            if new_news_ids or current_news_ids:
                logger.info(f"Processing {len(new_news_ids)} new news posts and checking {len(current_news_ids)} existing posts for revisions")

                # Save news posts to database (this will detect changes and create revisions)
                # save_news now returns (current_post, old_post_if_revised) tuples
                save_results = self.database.save_news(news_posts)

                # Process results and emit appropriate events
                for current_post, old_post in save_results:
                    if old_post is not None:
                        # This post was revised - emit revision event
                        logger.info(f"News post {current_post.id} was revised, emitting post_revised event")
                        await self.emit_event('post_revised', {
                            'old_post': old_post,
                            'new_post': current_post
                        })
                    elif current_post.id in new_news_ids:
                        # This is a new post - emit new_news event
                        logger.info(f"New news post {current_post.id} found, emitting new_news event")
                        await self.emit_event('new_news', current_post)

        except Exception as e:
            logger.error(f"Error fetching news posts: {e}")
