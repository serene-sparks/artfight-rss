#!/usr/bin/env python3
"""Test script to verify pagination functionality for attacks and defenses."""

import asyncio
import logging
from datetime import datetime

from artfight_rss.artfight import ArtFightClient
from artfight_rss.cache import RateLimiter
from artfight_rss.config import settings
from artfight_rss.database import ArtFightDatabase

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_pagination():
    """Test pagination for attacks and defenses."""
    print("🧪 Testing Pagination Functionality")
    print("=" * 50)

    # Initialize components
    rate_limiter = RateLimiter(database=settings.cache_db_path, min_interval=settings.request_interval)
    database = ArtFightDatabase(db_path=settings.db_path)
    client = ArtFightClient(rate_limiter, database)

    try:
        # Test with a known username
        username = "fourleafisland"

        print(f"\n📋 Testing pagination for user: {username}")
        print(f"  Page delay: {settings.page_request_delay_sec}s")
        print(f"  Page wobble: {settings.page_request_wobble} (±{settings.page_request_wobble*100:.0f}%)")

        # Test attacks pagination
        print("\n🔍 Testing attacks pagination:")
        print("-" * 40)
        start_time = datetime.now()
        attacks = await client.get_user_attacks(username)
        end_time = datetime.now()
        duration = end_time - start_time

        print(f"  Total attacks found: {len(attacks)}")
        print(f"  Duration: {duration.total_seconds():.2f} seconds")

        if attacks:
            print(f"  First attack: {attacks[0].title}")
            print(f"  Last attack: {attacks[-1].title}")

        # Test defenses pagination
        print("\n🔍 Testing defenses pagination:")
        print("-" * 40)
        start_time = datetime.now()
        defenses = await client.get_user_defenses(username)
        end_time = datetime.now()
        duration = end_time - start_time

        print(f"  Total defenses found: {len(defenses)}")
        print(f"  Duration: {duration.total_seconds():.2f} seconds")

        if defenses:
            print(f"  First defense: {defenses[0].title}")
            print(f"  Last defense: {defenses[-1].title}")

        # Test with a user that might have fewer items
        print("\n🔍 Testing with user that might have fewer items:")
        print("-" * 40)
        test_username = "example_user"  # This might not exist or have few items

        start_time = datetime.now()
        test_attacks = await client.get_user_attacks(test_username)
        end_time = datetime.now()
        duration = end_time - start_time

        print(f"  {test_username} attacks: {len(test_attacks)}")
        print(f"  Duration: {duration.total_seconds():.2f} seconds")

        start_time = datetime.now()
        test_defenses = await client.get_user_defenses(test_username)
        end_time = datetime.now()
        duration = end_time - start_time

        print(f"  {test_username} defenses: {len(test_defenses)}")
        print(f"  Duration: {duration.total_seconds():.2f} seconds")

        # Summary
        print("\n📊 Pagination Test Summary:")
        print(f"  {username} attacks: {len(attacks)} items")
        print(f"  {username} defenses: {len(defenses)} items")
        print(f"  {test_username} attacks: {len(test_attacks)} items")
        print(f"  {test_username} defenses: {len(test_defenses)} items")

        if len(attacks) > 0 or len(defenses) > 0:
            print("✅ Pagination appears to be working!")
        else:
            print("⚠️  No items found - check if user exists or has content")

    except Exception as e:
        print(f"❌ Error testing pagination: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(test_pagination())
