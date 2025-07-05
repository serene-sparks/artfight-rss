#!/usr/bin/env python3
"""Test script to verify authentication validation caching."""

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

async def test_auth_cache():
    """Test the authentication validation cache."""
    print("🧪 Testing Authentication Validation Cache")
    print("=" * 50)

    # Initialize components
    rate_limiter = RateLimiter(database=settings.cache_db_path, min_interval=settings.request_interval)
    database = ArtFightDatabase(db_path=settings.db_path)
    client = ArtFightClient(rate_limiter, database)

    try:
        # Show initial authentication info
        print("\n📋 Initial authentication info:")
        auth_info = client.get_authentication_info()
        print(f"  Laravel session configured: {auth_info['laravel_session_configured']}")
        print(f"  CF clearance configured: {auth_info['cf_clearance_configured']}")
        print(f"  Auth cache: {auth_info['auth_cache']}")

        if not auth_info['laravel_session_configured']:
            print("❌ No Laravel session configured, skipping test")
            return

        # Test 1: First validation (should perform actual check)
        print("\n🔍 Test 1: First validation (should perform actual check)")
        print("-" * 40)
        start_time = datetime.now()
        is_valid = await client.validate_authentication()
        end_time = datetime.now()
        duration = end_time - start_time

        print(f"  Result: {is_valid}")
        print(f"  Duration: {duration.total_seconds():.2f} seconds")

        # Show updated auth info
        auth_info = client.get_authentication_info()
        print(f"  Auth cache after first check: {auth_info['auth_cache']}")

        # Test 2: Second validation (should use cache)
        print("\n🔍 Test 2: Second validation (should use cache)")
        print("-" * 40)
        start_time = datetime.now()
        is_valid_cached = await client.validate_authentication()
        end_time = datetime.now()
        duration_cached = end_time - start_time

        print(f"  Result: {is_valid_cached}")
        print(f"  Duration: {duration_cached.total_seconds():.2f} seconds")
        print(f"  Cache hit: {duration_cached < duration}")

        # Test 3: Clear cache and validate again
        print("\n🔍 Test 3: Clear cache and validate again")
        print("-" * 40)
        client.clear_auth_cache()
        print("  Cache cleared")

        start_time = datetime.now()
        is_valid_after_clear = await client.validate_authentication()
        end_time = datetime.now()
        duration_after_clear = end_time - start_time

        print(f"  Result: {is_valid_after_clear}")
        print(f"  Duration: {duration_after_clear.total_seconds():.2f} seconds")

        # Test 4: Multiple rapid validations (should all use cache)
        print("\n🔍 Test 4: Multiple rapid validations (should all use cache)")
        print("-" * 40)
        durations = []
        for i in range(3):
            start_time = datetime.now()
            await client.validate_authentication()
            end_time = datetime.now()
            durations.append(end_time - start_time)
            print(f"  Validation {i+1}: {durations[-1].total_seconds():.3f} seconds")

        avg_duration = sum(d.total_seconds() for d in durations) / len(durations)
        print(f"  Average duration: {avg_duration:.3f} seconds")
        print(f"  All cached: {all(d.total_seconds() < 0.1 for d in durations)}")

        # Summary
        print("\n📊 Summary:")
        print(f"  First validation: {duration.total_seconds():.2f}s (actual check)")
        print(f"  Cached validation: {duration_cached.total_seconds():.2f}s (cache hit)")
        print(f"  After cache clear: {duration_after_clear.total_seconds():.2f}s (actual check)")
        print(f"  Average cached: {avg_duration:.3f}s")

        if duration_cached < duration * 0.1:  # Cache should be at least 10x faster
            print("✅ Cache is working correctly!")
        else:
            print("⚠️  Cache might not be working as expected")

    except Exception as e:
        print(f"❌ Error testing auth cache: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(test_auth_cache())
