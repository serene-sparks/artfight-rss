"""Main FastAPI application for the ArtFight feed service."""

import asyncio
import os
import signal
import subprocess
import sys
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse

from .artfight import ArtFightClient
from .cache import RateLimiter, SQLiteCache
from .config import settings
from .database import ArtFightDatabase
from .discord_bot import discord_bot
from .event_handlers import setup_event_handlers
from .logging_config import get_logger, setup_logging
from .monitor import ArtFightMonitor
from .atom import atom_generator

# Set up logging configuration
setup_logging()
logger = get_logger(__name__)

# Global instances
cache: SQLiteCache
rate_limiter: RateLimiter
database: ArtFightDatabase
monitor: ArtFightMonitor


def run_migrations():
    """Run database migrations automatically."""
    try:
        logger.info("Running database migrations...")

        # Ensure database directory exists
        settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Database directory ensured: {settings.db_path.parent}")

        # Use the project root directory for alembic commands
        project_root = settings.db_path.parent.parent
        logger.debug(f"Using project root for migrations: {project_root}")

        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            cwd=project_root,
            env={**os.environ, "PYTHONPATH": str(project_root)}
        )

        if result.returncode == 0:
            logger.info("Database migrations completed successfully")
            if result.stdout:
                logger.debug(f"Migration output: {result.stdout}")
        else:
            logger.error(f"Migration failed with return code {result.returncode}")
            logger.error(f"Migration stdout: {result.stdout}")
            logger.error(f"Migration stderr: {result.stderr}")
            raise RuntimeError(f"Database migration failed: {result.stderr}")

    except Exception as e:
        logger.error(f"Failed to run migrations: {e}")
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    global cache, rate_limiter, database, monitor

    # Run database migrations
    run_migrations()


    logger.info("Starting ArtFight feed service...")


    # Initialize components
    database = ArtFightDatabase(settings.db_path)
    cache = SQLiteCache(database)
    rate_limiter = RateLimiter(database, settings.request_interval)
    monitor = ArtFightMonitor(cache, rate_limiter, database)

    # Start monitoring
    await monitor.start()

    # Set up event handlers
    setup_event_handlers(monitor)

    # Start Discord bot
    if settings.discord_enabled:
        logger.info("Starting Discord bot...")
        # Set the database instance on the Discord bot for rate limit access
        discord_bot.set_database(database)
        # Set the monitor instance for status reporting
        discord_bot.set_monitor(monitor)
        await discord_bot.start()
        logger.info("Discord bot started")

    logger.info("ArtFight feed service started successfully")

    yield

    # Cleanup
    logger.info("Shutting down ArtFight feed service...")
    if settings.discord_enabled:
        await discord_bot.stop()
    await monitor.stop()
    logger.info("ArtFight feed service shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="ArtFight feed Service",
    description="Generate atom feeds for ArtFight profiles and team standings",
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
        "service": "artfight-feed",
        "version": "0.1.0"
    }


@app.get("/stats")
async def get_stats():
    """Get monitoring statistics."""
    return monitor.get_stats()


@app.post("/monitor/reset-no-event-detection")
async def reset_no_event_detection():
    """Manually reset the no event detection counter and restart team monitoring."""
    try:
        monitor.reset_battle_over_detection()
        return {"message": "No event detection counter reset successfully", "status": "success"}
    except Exception as e:
        logger.error(f"Error resetting no event detection: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset no event detection: {e}")



@app.get("/atom/standings")
async def get_team_standings_changes_atom(limit: int = Query(None, description="Maximum number of items to return")):
    """Get atom feed for team standing changes (daily updates and leader changes)."""
    try:
        # Get team standing changes from database with limit
        standings = database.get_team_standing_changes(days=30, limit=limit)
        feed = atom_generator.generate_team_changes_feed(standings)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return PlainTextResponse(
        feed.to_atom_xml(),
        media_type="application/atom+xml"
    )


@app.get("/atom/news")
async def get_news_atom(limit: int = Query(None, description="Maximum number of items to return")):
    """Get atom feed for ArtFight news posts."""
    try:
        # Get news posts from database with limit
        news_posts = database.get_news(limit=limit)
        feed = atom_generator.generate_news_feed(news_posts)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return PlainTextResponse(
        feed.to_atom_xml(),
        media_type="application/atom+xml"
    )


@app.get("/atom/attacks/{usernames}")
async def get_multiuser_attacks_atom(
    username_list: list[str] = Depends(validate_users),
    limit: int = Query(None, description="Maximum number of items to return")
):
    """Get RSS feed for multiple users' attacks."""
    try:
        # Fetch fresh data and emit events
        await fetch_and_emit_events_for_users(username_list)

        # Get attacks for all users
        attacks = database.get_attacks_for_users(username_list, limit=limit)
        feed = atom_generator.generate_multiuser_attacks_feed(username_list, attacks)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return PlainTextResponse(
        feed.to_atom_xml(),
        media_type="application/atom+xml"
    )


@app.get("/atom/defenses/{usernames}")
async def get_multiuser_defenses_atom(
    username_list: list[str] = Depends(validate_users),
    limit: int = Query(None, description="Maximum number of items to return")
):
    """Get atom feed for multiple users' defenses."""
    try:
        # Fetch fresh data and emit events
        await fetch_and_emit_events_for_users(username_list)

        # Get defenses for all users
        defenses = database.get_defenses_for_users(username_list, limit=limit)
        feed = atom_generator.generate_multiuser_defenses_feed(username_list, defenses)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return PlainTextResponse(
        feed.to_atom_xml(),
        media_type="application/atom+xml"
    )


@app.get("/atom/combined/{usernames}")
async def get_multiuser_combined_atom(
    username_list: list[str] = Depends(validate_users),
    limit: int = Query(None, description="Maximum number of items to return")
):
    """Get combined atom feed for multiple users' attacks and defenses."""
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
        feed = atom_generator.generate_multiuser_combined_feed(username_list, attacks, defenses)
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
        "artfight_feed.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.live_reload,
        log_config=None,  # Use our custom logging configuration
        log_level=None,   # Let our logging config handle levels
        access_log=True,  # Enable access logging
        use_colors=True,  # Enable colored output
        loop="asyncio"    # Use asyncio event loop for better signal handling
    )
