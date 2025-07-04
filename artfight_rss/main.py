"""Main FastAPI application for the ArtFight RSS service."""

import logging
from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse

from .artfight import ArtFightClient
from .cache import RateLimiter, SQLiteCache
from .config import settings
from .database import ArtFightDatabase
from .monitor import ArtFightMonitor
from .rss import rss_generator

# Configure logging based on debug setting
if settings.debug:
    # Configure logging for debug mode
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[logging.StreamHandler()]
    )
    
    # Set specific loggers to DEBUG level
    logging.getLogger("artfight_rss").setLevel(logging.DEBUG)
    logging.getLogger("artfight_rss.artfight").setLevel(logging.DEBUG)
    logging.getLogger("artfight_rss.database").setLevel(logging.DEBUG)
    logging.getLogger("artfight_rss.cache").setLevel(logging.DEBUG)
    logging.getLogger("artfight_rss.monitor").setLevel(logging.DEBUG)
    logging.getLogger("artfight_rss.rss").setLevel(logging.DEBUG)
    logging.getLogger("artfight_rss.config").setLevel(logging.DEBUG)
    
    print("Debug logging enabled for artfight_rss package")

    logging.getLogger("httpcore").setLevel(logging.INFO)
else:
    # Basic INFO level logging for production
    logging.basicConfig(level=logging.INFO)

# Global instances
cache: SQLiteCache
rate_limiter: RateLimiter
database: ArtFightDatabase
monitor: ArtFightMonitor


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    global cache, rate_limiter, database, monitor

    # Initialize components
    cache = SQLiteCache(settings.cache_db_path)
    database = ArtFightDatabase(settings.db_path)
    rate_limiter = RateLimiter(database, settings.request_interval)
    monitor = ArtFightMonitor(cache, rate_limiter, database)

    # Start monitoring
    await monitor.start()

    yield

    # Cleanup
    await monitor.stop()


# Create FastAPI app
app = FastAPI(
    title="ArtFight RSS Service",
    description="Generate RSS feeds for ArtFight profiles and team standings",
    version="0.1.0",
    lifespan=lifespan
)


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


@app.get("/rss/user/{username}/attacks")
async def get_user_rss(username: str):
    """Get RSS feed for a user's attacks."""
    # Check if user is in whitelist
    if settings.whitelist and username not in settings.whitelist:
        raise HTTPException(status_code=404, detail="User not found")

    # Get attacks for user
    artfight_client = ArtFightClient(rate_limiter, database)
    try:
        attacks = await artfight_client.get_user_attacks(username)
        feed = rss_generator.generate_user_feed(username, attacks)
    finally:
        await artfight_client.close()

    return PlainTextResponse(
        feed.to_rss_xml(),
        media_type="application/rss+xml"
    )


@app.get("/rss/user/{username}/defenses")
async def get_user_defense_rss(username: str):
    """Get RSS feed for a user's defenses."""
    # Check if user is in whitelist
    if settings.whitelist and username not in settings.whitelist:
        raise HTTPException(status_code=404, detail="User not found")

    # Get defenses for user
    artfight_client = ArtFightClient(rate_limiter, database)
    try:
        defenses = await artfight_client.get_user_defenses(username)
        feed = rss_generator.generate_user_defense_feed(username, defenses)
    finally:
        await artfight_client.close()

    return PlainTextResponse(
        feed.to_rss_xml(),
        media_type="application/rss+xml"
    )


@app.get("/rss/standings")
async def get_team_standings_changes_rss():
    """Get RSS feed for team standing changes (daily updates and leader changes)."""
    # Get team standing changes from database
    standings = database.get_team_standing_changes(days=30)
    feed = rss_generator.generate_team_changes_feed(standings)

    return PlainTextResponse(
        feed.to_rss_xml(),
        media_type="application/rss+xml"
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
    artfight_client = ArtFightClient(rate_limiter, database)
    try:
        auth_info = artfight_client.get_authentication_info()
        is_valid = await artfight_client.validate_authentication() if auth_info["authenticated"] else False
        
        return {
            "configured": auth_info["authenticated"],
            "valid": is_valid,
            "details": auth_info
        }
    finally:
        await artfight_client.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "artfight_rss.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_config=None,  # Prevent uvicorn from overriding our logging config
        log_level=None    # Prevent uvicorn from resetting log level
    )
