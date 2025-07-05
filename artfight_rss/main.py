"""Main FastAPI application for the ArtFight RSS service."""

import logging
from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, HTTPException, Query
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
 




@app.get("/rss/standings")
async def get_team_standings_changes_rss(limit: int = Query(None, description="Maximum number of items to return")):
    """Get RSS feed for team standing changes (daily updates and leader changes)."""
    try:
        # Get team standing changes from database with limit
        standings = database.get_team_standing_changes(days=30, limit=limit)
        feed = rss_generator.generate_team_changes_feed(standings)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return PlainTextResponse(
        feed.to_atom_xml(),
        media_type="application/atom+xml"
    )


@app.get("/rss/attacks/{usernames}")
async def get_multiuser_attacks_rss(usernames: str, limit: int = Query(None, description="Maximum number of items to return")):
    """Get RSS feed for multiple users' attacks."""
    # Parse usernames from URL (format: user1+user2+user3)
    username_list = usernames.split('+')
    
    # Check if any users are provided
    if not username_list or not any(username_list):
        raise HTTPException(
            status_code=400, 
            detail="No users specified. Please provide at least one username."
        )
    
    # Check user limit
    if len(username_list) > settings.max_users_per_feed:
        raise HTTPException(
            status_code=400, 
            detail=f"Too many users. Maximum allowed: {settings.max_users_per_feed}"
        )
    
    # Check if all users are in whitelist
    if settings.whitelist:
        invalid_users = [u for u in username_list if u not in settings.whitelist]
        if invalid_users:
            raise HTTPException(
                status_code=404, 
                detail=f"Users not found: {', '.join(invalid_users)}"
            )

    try:
        # Get attacks for all users
        attacks = database.get_attacks_for_users(username_list, limit=limit)
        feed = rss_generator.generate_multiuser_attacks_feed(username_list, attacks)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return PlainTextResponse(
        feed.to_atom_xml(),
        media_type="application/atom+xml"
    )


@app.get("/rss/defenses/{usernames}")
async def get_multiuser_defenses_rss(usernames: str, limit: int = Query(None, description="Maximum number of items to return")):
    """Get RSS feed for multiple users' defenses."""
    # Parse usernames from URL (format: user1+user2+user3)
    username_list = usernames.split('+')
    
    # Check if any users are provided
    if not username_list or not any(username_list):
        raise HTTPException(
            status_code=400, 
            detail="No users specified. Please provide at least one username."
        )
    
    # Check user limit
    if len(username_list) > settings.max_users_per_feed:
        raise HTTPException(
            status_code=400, 
            detail=f"Too many users. Maximum allowed: {settings.max_users_per_feed}"
        )
    
    # Check if all users are in whitelist
    if settings.whitelist:
        invalid_users = [u for u in username_list if u not in settings.whitelist]
        if invalid_users:
            raise HTTPException(
                status_code=404, 
                detail=f"Users not found: {', '.join(invalid_users)}"
            )

    try:
        # Get defenses for all users
        defenses = database.get_defenses_for_users(username_list, limit=limit)
        feed = rss_generator.generate_multiuser_defenses_feed(username_list, defenses)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return PlainTextResponse(
        feed.to_atom_xml(),
        media_type="application/atom+xml"
    )


@app.get("/rss/combined/{usernames}")
async def get_multiuser_combined_rss(usernames: str, limit: int = Query(None, description="Maximum number of items to return")):
    """Get combined RSS feed for multiple users' attacks and defenses."""
    # Parse usernames from URL (format: user1+user2+user3)
    username_list = usernames.split('+')
    
    # Check if any users are provided
    if not username_list or not any(username_list):
        raise HTTPException(
            status_code=400, 
            detail="No users specified. Please provide at least one username."
        )
    
    # Check user limit
    if len(username_list) > settings.max_users_per_feed:
        raise HTTPException(
            status_code=400, 
            detail=f"Too many users. Maximum allowed: {settings.max_users_per_feed}"
        )
    
    # Check if all users are in whitelist
    if settings.whitelist:
        invalid_users = [u for u in username_list if u not in settings.whitelist]
        if invalid_users:
            raise HTTPException(
                status_code=404, 
                detail=f"Users not found: {', '.join(invalid_users)}"
            )

    try:
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
        raise HTTPException(status_code=400, detail=str(e))

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
        reload=settings.live_reload,
        log_config=None,  # Prevent uvicorn from overriding our logging config
        log_level=None    # Prevent uvicorn from resetting log level
    )
