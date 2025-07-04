"""Background monitoring service for ArtFight team standings."""

import asyncio
from datetime import datetime, timedelta

from .artfight import ArtFightClient
from .cache import RateLimiter, SQLiteCache
from .config import settings
from .models import TeamStanding


class ArtFightMonitor:
    """Monitor ArtFight team standings for changes."""

    def __init__(self, cache: SQLiteCache, rate_limiter: RateLimiter, database) -> None:
        """Initialize the monitor."""
        self.cache = cache
        self.rate_limiter = rate_limiter
        self.database = database
        self.artfight_client = ArtFightClient(rate_limiter, database)

        # Track last known team states
        self.last_team_sides: dict[str, str] = {}  # team_name -> side
        self.last_team_update: datetime | None = None

        # Background task handle
        self.team_task: asyncio.Task | None = None
        self.running = False

    async def start(self) -> None:
        """Start the monitoring service."""
        if self.running:
            return

        self.running = True

        # Start background task for team monitoring
        self.team_task = asyncio.create_task(self._team_monitor_loop())

        print("ArtFight team monitor started")

    async def stop(self) -> None:
        """Stop the monitoring service."""
        if not self.running:
            return

        self.running = False

        # Cancel background task
        if self.team_task:
            self.team_task.cancel()
            try:
                await self.team_task
            except asyncio.CancelledError:
                pass

        # Close ArtFight client
        await self.artfight_client.close()

        print("ArtFight team monitor stopped")

    async def _team_monitor_loop(self) -> None:
        """Background loop for monitoring team standings."""
        while self.running:
            try:
                await self._check_team_standings()
                await asyncio.sleep(settings.team_check_interval_sec)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in team monitor loop: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes before retrying

    async def _check_team_standings(self) -> None:
        """Check team standings for updates and side switches."""
        standings = await self.artfight_client.get_team_standings()
        if not standings:
            return

        current_time = datetime.now()
        should_update = False

        # Check for leader changes
        for standing in standings:
            if standing.leader_change:
                if settings.teams:
                    leader = (
                        settings.teams.team1.name
                        if standing.team1_percentage > 50
                        else settings.teams.team2.name
                    )
                else:
                    leader = "Team 1" if standing.team1_percentage > 50 else "Team 2"
                print(f"Leader change detected: {leader} is now leading at {standing.team1_percentage:.2f}%")


    async def check_teams_manual(self) -> list[TeamStanding]:
        """Manually check team standings (for API endpoints)."""
        await self._check_team_standings()
        return await self.artfight_client.get_team_standings()

    def get_stats(self) -> dict:
        """Get monitoring statistics."""
        return {
            "running": self.running,
            "last_team_update": self.last_team_update.isoformat() if self.last_team_update else None,
            "tracked_teams": len(self.last_team_sides),
            "cache_stats": self.cache.get_stats(),
        }
