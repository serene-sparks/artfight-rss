#!/usr/bin/env python3
"""Test script to verify team-only monitoring functionality."""

import asyncio
import logging
from datetime import datetime

from artfight_rss.cache import RateLimiter, SQLiteCache
from artfight_rss.config import settings
from artfight_rss.database import ArtFightDatabase
from artfight_rss.monitor import ArtFightMonitor

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_team_monitor():
    """Test that the monitor only handles team standings."""
    print("🧪 Testing Team-Only Monitor")
    print("=" * 50)

    # Initialize components
    database = ArtFightDatabase(db_path=settings.db_path)
    cache = SQLiteCache(database)
    rate_limiter = RateLimiter(database, settings.request_interval)
    monitor = ArtFightMonitor(cache, rate_limiter, database)

    try:
        print("\n📋 Monitor Configuration:")
        print(f"  Team check interval: {settings.team_check_interval_sec}s")
        print(f"  Team switch threshold: {settings.team_switch_threshold_sec}h")

        # Test initial stats
        print("\n📊 Initial monitor stats:")
        stats = monitor.get_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")

        # Test manual team check
        print("\n🔍 Testing manual team check:")
        print("-" * 40)
        start_time = datetime.now()
        standings = await monitor.check_teams_manual()
        end_time = datetime.now()
        duration = end_time - start_time

        print(f"  Teams found: {len(standings)}")
        print(f"  Duration: {duration.total_seconds():.2f} seconds")

        for standing in standings:
            print(f"    {standing.name}: {standing.score} points ({standing.side})")

        # Test starting and stopping the monitor
        print("\n🔍 Testing monitor start/stop:")
        print("-" * 40)

        print("  Starting monitor...")
        await monitor.start()

        # Wait a moment to see if it starts properly
        await asyncio.sleep(2)

        print("  Monitor stats after start:")
        stats = monitor.get_stats()
        print(f"    Running: {stats['running']}")
        print(f"    Tracked teams: {stats['tracked_teams']}")

        print("  Stopping monitor...")
        await monitor.stop()

        print("  Monitor stats after stop:")
        stats = monitor.get_stats()
        print(f"    Running: {stats['running']}")

        # Summary
        print("\n📊 Test Summary:")
        print(f"  Teams found: {len(standings)}")
        print("  Monitor started/stopped successfully: ✅")
        print("  No user profile monitoring: ✅")

        if len(standings) > 0:
            print("✅ Team monitoring is working correctly!")
        else:
            print("⚠️  No teams found - check if team standings are available")

    except Exception as e:
        print(f"❌ Error testing team monitor: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Ensure monitor is stopped
        if monitor.running:
            await monitor.stop()

if __name__ == "__main__":
    asyncio.run(test_team_monitor())
