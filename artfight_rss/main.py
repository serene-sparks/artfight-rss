"""Main FastAPI application for the ArtFight RSS service."""

import asyncio
import signal
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.responses import PlainTextResponse

from .artfight import ArtFightClient
from .cache import RateLimiter, SQLiteCache
from .config import settings
from .database import ArtFightDatabase
from .discord_bot import discord_bot
from .event_handlers import setup_event_handlers
from .logging_config import setup_logging, get_logger
from .monitor import ArtFightMonitor
from .rss import rss_generator

# Set up logging configuration
setup_logging()
logger = get_logger(__name__)

# Global instances
cache: SQLiteCache
rate_limiter: RateLimiter
database: ArtFightDatabase
monitor: ArtFightMonitor


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    global cache, rate_limiter, database, monitor

    logger.info("Starting ArtFight RSS service...")

    # Initialize components
    cache = SQLiteCache(settings.cache_db_path)
    database = ArtFightDatabase(settings.db_path)
    rate_limiter = RateLimiter(database, settings.request_interval)
    monitor = ArtFightMonitor(cache, rate_limiter, database)

    # Start monitoring
    await monitor.start()

    # Set up event handlers
    setup_event_handlers(monitor)

    # Start Discord bot
    if settings.discord_enabled:
        logger.info("Starting Discord bot...")
        await discord_bot.start()
        logger.info("Discord bot started")

    logger.info("ArtFight RSS service started successfully")
    
    yield
    
    # Cleanup
    logger.info("Shutting down ArtFight RSS service...")
    if settings.discord_enabled:
        await discord_bot.stop()
    await monitor.stop()
    logger.info("ArtFight RSS service shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="ArtFight RSS Service",
    description="Generate RSS feeds for ArtFight profiles and team standings",
    version="0.1.0",
    lifespan=lifespan
)


def validate_users(usernames: str) -> list[str]:
    """Dependency to parse and validate a list of usernames."""
    username_list = [u.strip() for u in usernames.split('+') if u.strip()]

    if not username_list:
        raise HTTPException(
            status_code=400,
            detail="No usernames specified. Please provide at least one username."
        )

    if len(username_list) > settings.max_users_per_feed:
        raise HTTPException(
            status_code=400,
            detail=f"Too many users. Maximum allowed: {settings.max_users_per_feed}"
        )

    if settings.whitelist:
        invalid_users = [u for u in username_list if u not in settings.whitelist]
        if invalid_users:
            raise HTTPException(
                status_code=403,
                detail=f"Users not allowed: {', '.join(invalid_users)}"
            )
    
    return username_list


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "artfight-rss",
        "version": "0.1.0"
    }


@app.get("/stats")
async def get_stats():
    """Get monitoring statistics."""
    return monitor.get_stats()


@app.get("/rss/standings")
async def get_team_standings_changes_rss(limit: int = Query(None, description="Maximum number of items to return")):
    """Get RSS feed for team standing changes (daily updates and leader changes)."""
    try:
        # Get team standing changes from database with limit
        standings = database.get_team_standing_changes(days=30, limit=limit)
        feed = rss_generator.generate_team_changes_feed(standings)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return PlainTextResponse(
        feed.to_atom_xml(),
        media_type="application/atom+xml"
    )


@app.get("/rss/attacks/{usernames}")
async def get_multiuser_attacks_rss(
    username_list: list[str] = Depends(validate_users),
    limit: int = Query(None, description="Maximum number of items to return")
):
    """Get RSS feed for multiple users' attacks."""
    try:
        # Fetch fresh data and emit events
        await fetch_and_emit_events_for_users(username_list)
        
        # Get attacks for all users
        attacks = database.get_attacks_for_users(username_list, limit=limit)
        feed = rss_generator.generate_multiuser_attacks_feed(username_list, attacks)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return PlainTextResponse(
        feed.to_atom_xml(),
        media_type="application/atom+xml"
    )


@app.get("/rss/defenses/{usernames}")
async def get_multiuser_defenses_rss(
    username_list: list[str] = Depends(validate_users),
    limit: int = Query(None, description="Maximum number of items to return")
):
    """Get RSS feed for multiple users' defenses."""
    try:
        # Fetch fresh data and emit events
        await fetch_and_emit_events_for_users(username_list)
        
        # Get defenses for all users
        defenses = database.get_defenses_for_users(username_list, limit=limit)
        feed = rss_generator.generate_multiuser_defenses_feed(username_list, defenses)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return PlainTextResponse(
        feed.to_atom_xml(),
        media_type="application/atom+xml"
    )


@app.get("/rss/combined/{usernames}")
async def get_multiuser_combined_rss(
    username_list: list[str] = Depends(validate_users),
    limit: int = Query(None, description="Maximum number of items to return")
):
    """Get combined RSS feed for multiple users' attacks and defenses."""
    try:
        # Fetch fresh data and emit events
        await fetch_and_emit_events_for_users(username_list)
        
        # Get both attacks and defenses for all users
        # For combined feeds, split the limit between attacks and defenses
        if limit:
            attack_limit = limit // 2
            defense_limit = limit - attack_limit  # Ensure total doesn't exceed limit
        else:
            attack_limit = None
            defense_limit = None

        attacks = database.get_attacks_for_users(username_list, limit=attack_limit)
        defenses = database.get_defenses_for_users(username_list, limit=defense_limit)
        feed = rss_generator.generate_multiuser_combined_feed(username_list, attacks, defenses)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return PlainTextResponse(
        feed.to_atom_xml(),
        media_type="application/atom+xml"
    )


# User profile webhook endpoints removed - monitor only handles team standings


@app.post("/webhook/teams")
async def trigger_team_check():
    """Manually trigger a team standings check."""
    try:
        standings = await monitor.check_teams_manual()
        return {
            "success": True,
            "teams_found": len(standings)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking teams: {e}") from e


@app.get("/cache/stats")
async def get_cache_stats():
    """Get cache statistics."""
    return cache.get_stats()


@app.post("/cache/clear")
async def clear_cache():
    """Clear all cache entries."""
    cache.clear()
    return {"success": True, "message": "Cache cleared"}


@app.post("/cache/cleanup")
async def cleanup_cache():
    """Remove expired cache entries."""
    cache.cleanup_expired()
    return {"success": True, "message": "Cache cleanup completed"}


@app.get("/auth/status")
async def get_auth_status():
    """Get authentication status and information."""
    client = ArtFightClient(rate_limiter, database)
    try:
        auth_info = client.get_authentication_info()
        is_valid = await client.validate_authentication()

        return {
            "configured": auth_info["authenticated"],
            "valid": is_valid,
            "details": auth_info,
        }
    finally:
        await client.close()


async def fetch_and_emit_events_for_user(username: str) -> None:
    """
    Fetches attacks and defenses for a user and emits events.

    Args:
        username: The ArtFight username.
    """
    logger.debug(f"Fetching data for user: {username}")
    await monitor._fetch_user_attacks(username)
    await monitor._fetch_user_defenses(username)
    logger.debug(f"Finished fetching data for user: {username}")


async def fetch_and_emit_events_for_users(usernames: list[str]) -> None:
    """
    Fetches attacks and defenses for a list of users and emits events.

    Args:
        usernames: A list of ArtFight usernames.
    """
    tasks = [fetch_and_emit_events_for_user(u) for u in usernames]
    await asyncio.gather(*tasks)


def graceful_shutdown(signal, frame):
    """Handle graceful shutdown."""
    logger.info(f"Received signal {signal}, shutting down...")
    
    # Schedule the async shutdown logic to run in the event loop
    if asyncio.get_event_loop().is_running():
        asyncio.get_event_loop().create_task(shutdown_logic())
    else:
        # If no event loop is running, we can't schedule async tasks
        logger.warning("No event loop running, cannot perform async shutdown")
        sys.exit(0)


async def shutdown_logic():
    """Contains the actual shutdown logic."""
    logger.info("Starting graceful shutdown...")
    
    # Stop monitoring and other background tasks
    if 'monitor' in globals() and monitor:
        await monitor.stop()
        
    # Stop the Discord bot
    if 'discord_bot' in globals() and discord_bot:
        await discord_bot.stop()

    logger.info("Graceful shutdown complete.")
    
    # Exit the process after cleanup
    sys.exit(0)


# Set up signal handlers for graceful shutdown
signal.signal(signal.SIGINT, graceful_shutdown)
signal.signal(signal.SIGTERM, graceful_shutdown)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "artfight_rss.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.live_reload,
        log_config=None,  # Use our custom logging configuration
        log_level=None,   # Let our logging config handle levels
        access_log=True,  # Enable access logging
        use_colors=True,  # Enable colored output
        loop="asyncio"    # Use asyncio event loop for better signal handling
    )
